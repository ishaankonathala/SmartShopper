"""Selection and additive import for the Amazon Reviews 2023 metadata file."""

from __future__ import annotations

import ast
import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Iterable

import pyarrow.parquet as parquet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.amazon_catalogue_product import AmazonCatalogueProduct

DEFAULT_USD_TO_INR_RATE = Decimal("85")
DEFAULT_IMPORT_LIMIT = 500
CATEGORY_TARGETS: dict[str, int] = {
    "Computers & Accessories": 150,
    "Camera & Photo": 75,
    "Headphones & Earbuds": 100,
    "Television & Video": 60,
    "Home Audio": 50,
    "Car Electronics": 20,
    "Portable Audio & Video": 20,
    "Wearable Technology": 15,
    "Other Electronics": 10,
}
PARQUET_COLUMNS = [
    "main_category",
    "title",
    "average_rating",
    "rating_number",
    "features",
    "description",
    "price",
    "images",
    "categories",
    "store",
    "parent_asin",
]
_ASIN_PATTERN = re.compile(r"[A-Z0-9]{10}\Z")
_USD_PRICE_PATTERN = re.compile(
    r"\$?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\s*\Z"
)
_HEADPHONE_TITLE_PATTERN = re.compile(
    r"\b(?:headphones?|headsets?|ear[ -]?buds?|earphones?)\b",
    re.IGNORECASE,
)
_HEADPHONE_ACCESSORY_PATTERN = re.compile(
    r"\b(?:replacement|ear ?loops?|ear ?hooks?|ear ?tips?|ear ?pads?|earpads|"
    r"headband|headphone stand|charging case|carrying case|protective case|"
    r"cables?|adapters?|covers?|silicone tips?)\b",
    re.IGNORECASE,
)
_CATEGORY_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Computers & Accessories", ("computers & accessories",)),
    ("Camera & Photo", ("camera & photo",)),
    ("Headphones & Earbuds", ("headphones", "earbuds", "earphones")),
    ("Television & Video", ("television & video",)),
    ("Home Audio", ("home audio",)),
    ("Car Electronics", ("car electronics",)),
    ("Portable Audio & Video", ("portable audio & video",)),
    ("Wearable Technology", ("wearable technology",)),
)


@dataclass(frozen=True)
class AmazonImportRecord:
    asin: str
    title: str
    store: str | None
    category: str
    price_inr: int
    rating: float
    rating_count: int
    image_url: str
    description: list[str]
    features: list[str]
    source_metadata: dict[str, Any]

    def as_model(self) -> AmazonCatalogueProduct:
        return AmazonCatalogueProduct(**self.__dict__)


@dataclass(frozen=True)
class ImportSelection:
    source_count: int
    candidate_count: int
    selected: list[AmazonImportRecord]
    rejected_by_reason: dict[str, int]
    selected_by_category: dict[str, int]


@dataclass(frozen=True)
class ImportResult:
    selected_count: int
    inserted_count: int
    already_present_count: int
    inserted_by_category: dict[str, int]


def _literal(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None


def parse_usd_price(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    if not text or not _USD_PRICE_PATTERN.fullmatch(text):
        return None
    try:
        amount = Decimal(text.replace("$", "").replace(",", "").strip())
    except InvalidOperation:
        return None
    return amount if amount.is_finite() and amount > 0 else None


def convert_usd_to_inr(price: Decimal, rate: Decimal = DEFAULT_USD_TO_INR_RATE) -> int:
    if not price.is_finite() or price <= 0:
        raise ValueError("USD price must be finite and positive.")
    if not rate.is_finite() or rate <= 0:
        raise ValueError("USD-to-INR conversion rate must be finite and positive.")
    return int((price * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def map_category(categories_value: object, title: str) -> str | None:
    raw_categories = _literal(categories_value)
    if not isinstance(raw_categories, (list, tuple)):
        return None
    categories = [str(category).strip().casefold() for category in raw_categories]

    for label, markers in _CATEGORY_MARKERS:
        if not any(
            marker in category
            for category in categories
            for marker in markers
        ):
            continue
        if label == "Headphones & Earbuds" and (
            not _HEADPHONE_TITLE_PATTERN.search(title)
            or _HEADPHONE_ACCESSORY_PATTERN.search(title)
        ):
            return None
        return label

    if any(category in {"electronics", "all electronics"} for category in categories):
        return "Other Electronics"
    return None


def _valid_large_image(images_value: object) -> str | None:
    images = _literal(images_value)
    if not isinstance(images, dict):
        return None
    large_images = images.get("large")
    if not isinstance(large_images, (list, tuple)):
        return None
    for image in large_images:
        if not isinstance(image, str):
            continue
        parsed = urlparse(image.strip())
        host = (parsed.hostname or "").casefold()
        is_amazon_host = (
            host == "m.media-amazon.com"
            or host.endswith(".media-amazon.com")
            or host == "images-na.ssl-images-amazon.com"
            or host.endswith(".amazon.com")
        )
        if parsed.scheme == "https" and is_amazon_host and parsed.path:
            return image.strip()
    return None


def _text_list(value: object) -> list[str]:
    parsed = _literal(value)
    if isinstance(parsed, str):
        candidates: Iterable[object] = [parsed]
    elif isinstance(parsed, (list, tuple)):
        candidates = parsed
    else:
        return []
    return [
        item.strip()
        for item in candidates
        if isinstance(item, str) and item.strip()
    ]


def _normalize_record(
    row: dict[str, Any],
    *,
    usd_to_inr_rate: Decimal,
) -> tuple[AmazonImportRecord | None, str | None]:
    title_value = row.get("title")
    title = title_value.strip() if isinstance(title_value, str) else ""
    if len(title) < 4:
        return None, "invalid_title"

    asin_value = row.get("parent_asin")
    asin = asin_value.strip().upper() if isinstance(asin_value, str) else ""
    if not _ASIN_PATTERN.fullmatch(asin):
        return None, "invalid_parent_asin"

    original_price = parse_usd_price(row.get("price"))
    if original_price is None:
        return None, "missing_or_invalid_usd_price"

    image_url = _valid_large_image(row.get("images"))
    if image_url is None:
        return None, "missing_or_invalid_large_image"

    category = map_category(row.get("categories"), title)
    if category is None:
        return None, "irrelevant_or_unreliable_category"

    try:
        rating = float(row.get("average_rating"))
        rating_count = int(row.get("rating_number"))
    except (TypeError, ValueError, OverflowError):
        return None, "missing_or_invalid_rating"
    if not math.isfinite(rating) or not 3.5 <= rating <= 5 or rating_count < 5:
        return None, "insufficient_rating_or_review_count"

    store_value = row.get("store")
    store = store_value.strip() if isinstance(store_value, str) and store_value.strip() else None
    source_categories = _literal(row.get("categories"))
    metadata = {
        "source": "Amazon Reviews 2023 Electronics metadata",
        "parent_asin": asin,
        "original_price_usd": str(original_price),
        "usd_to_inr_rate": str(usd_to_inr_rate),
        "source_main_category": row.get("main_category"),
        "source_categories": (
            list(source_categories)
            if isinstance(source_categories, (list, tuple))
            else []
        ),
    }
    return (
        AmazonImportRecord(
            asin=asin,
            title=title,
            store=store,
            category=category,
            price_inr=convert_usd_to_inr(original_price, usd_to_inr_rate),
            rating=rating,
            rating_count=rating_count,
            image_url=image_url,
            description=_text_list(row.get("description")),
            features=_text_list(row.get("features")),
            source_metadata=metadata,
        ),
        None,
    )


def select_import_records(
    rows: Iterable[dict[str, Any]],
    *,
    limit: int = DEFAULT_IMPORT_LIMIT,
    usd_to_inr_rate: Decimal = DEFAULT_USD_TO_INR_RATE,
) -> ImportSelection:
    if limit < 1:
        raise ValueError("Import limit must be positive.")
    if not usd_to_inr_rate.is_finite() or usd_to_inr_rate <= 0:
        raise ValueError("USD-to-INR conversion rate must be finite and positive.")

    source_count = 0
    rejected = Counter()
    seen_asins: set[str] = set()
    candidate_heaps: dict[
        str,
        list[tuple[int, float, tuple[int, ...], AmazonImportRecord]],
    ] = {
        category: [] for category in CATEGORY_TARGETS
    }
    candidate_count = 0
    for row in rows:
        source_count += 1
        record, reason = _normalize_record(row, usd_to_inr_rate=usd_to_inr_rate)
        if reason is not None:
            rejected[reason] += 1
            continue
        if record is None:
            raise RuntimeError("Record normalization returned no product or rejection reason.")
        if record.asin in seen_asins:
            rejected["duplicate_parent_asin"] += 1
            continue
        seen_asins.add(record.asin)
        candidate_count += 1
        asin_tiebreaker = tuple(-ord(character) for character in record.asin)
        ranked_record = (
            record.rating_count,
            record.rating,
            asin_tiebreaker,
            record,
        )
        category_heap = candidate_heaps[record.category]
        if len(category_heap) < limit:
            heapq.heappush(category_heap, ranked_record)
        elif ranked_record[:3] > category_heap[0][:3]:
            heapq.heapreplace(category_heap, ranked_record)

    candidates_by_category = {
        category: [entry[3] for entry in heap]
        for category, heap in candidate_heaps.items()
    }
    for candidates in candidates_by_category.values():
        candidates.sort(key=lambda product: (-product.rating_count, -product.rating, product.asin))

    selected: list[AmazonImportRecord] = []
    selected_asins: set[str] = set()
    for category, target in CATEGORY_TARGETS.items():
        for record in candidates_by_category[category][:target]:
            if len(selected) == limit:
                break
            selected.append(record)
            selected_asins.add(record.asin)
        if len(selected) == limit:
            break

    if len(selected) < limit:
        remainder = [
            record
            for records in candidates_by_category.values()
            for record in records
            if record.asin not in selected_asins
        ]
        remainder.sort(
            key=lambda product: (-product.rating_count, -product.rating, product.asin)
        )
        for record in remainder[: limit - len(selected)]:
            selected.append(record)
            selected_asins.add(record.asin)

    rejected["category_targets_or_import_limit"] += (
        candidate_count - len(selected)
    )
    selected_by_category = dict(Counter(record.category for record in selected))
    for category in CATEGORY_TARGETS:
        selected_by_category.setdefault(category, 0)

    return ImportSelection(
        source_count=source_count,
        candidate_count=candidate_count,
        selected=selected,
        rejected_by_reason=dict(rejected),
        selected_by_category=selected_by_category,
    )


def read_parquet_records(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Amazon catalogue dataset not found: {path}")
    parquet_file = parquet.ParquetFile(path)
    available_columns = set(parquet_file.schema_arrow.names)
    missing_columns = set(PARQUET_COLUMNS) - available_columns
    if missing_columns:
        raise ValueError(
            "Amazon catalogue dataset is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )
    for batch in parquet_file.iter_batches(
        batch_size=2048,
        columns=PARQUET_COLUMNS,
    ):
        yield from batch.to_pylist()


def import_selected_records(
    db: Session,
    records: list[AmazonImportRecord],
) -> ImportResult:
    asins = list(dict.fromkeys(record.asin for record in records))
    existing_asins = (
        set(
            db.scalars(
                select(AmazonCatalogueProduct.asin).where(
                    AmazonCatalogueProduct.asin.in_(asins)
                )
            ).all()
        )
        if asins
        else set()
    )
    new_records = [record for record in records if record.asin not in existing_asins]
    db.add_all([record.as_model() for record in new_records])
    if new_records:
        db.commit()

    inserted_by_category = dict(Counter(record.category for record in new_records))
    for category in CATEGORY_TARGETS:
        inserted_by_category.setdefault(category, 0)
    return ImportResult(
        selected_count=len(records),
        inserted_count=len(new_records),
        already_present_count=len(records) - len(new_records),
        inserted_by_category=inserted_by_category,
    )
