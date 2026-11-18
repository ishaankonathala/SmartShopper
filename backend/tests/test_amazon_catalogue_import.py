"""Tests for selecting and importing the isolated Amazon catalogue."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.catalogue import DEMO_PRODUCTS
from app.models.amazon_catalogue_product import AmazonCatalogueProduct
from app.models.product import Product
from app.services.amazon_catalogue_import import (
    convert_usd_to_inr,
    import_selected_records,
    map_category,
    parse_usd_price,
    select_import_records,
    _valid_large_image,
)
from app.services.seed import seed_products


def _row(
    *,
    asin: str = "B000000001",
    title: str = "Reliable computer accessory",
    category: str = "Computers & Accessories",
    price: str = "19.99",
    rating: float = 4.5,
    rating_count: int = 100,
    image: str = "https://m.media-amazon.com/images/I/41image.jpg",
) -> dict[str, object]:
    return {
        "main_category": "Computers",
        "title": title,
        "average_rating": rating,
        "rating_number": rating_count,
        "features": ["A listed feature"],
        "description": ["A listed description."],
        "price": price,
        "images": repr({"large": [image]}),
        "categories": repr(["Electronics", category]),
        "store": "Example Store",
        "parent_asin": asin,
    }


def test_usd_price_conversion_rounds_to_nearest_rupee() -> None:
    price = parse_usd_price("$19.99")

    assert price == Decimal("19.99")
    assert convert_usd_to_inr(price) == 1699


def test_invalid_or_missing_usd_prices_are_rejected() -> None:
    for value in (None, "", "None", "0", "-1.00", "NaN", "1,23.00", "$unknown"):
        assert parse_usd_price(value) is None


def test_category_mapping_rejects_misleading_headphone_accessories() -> None:
    assert (
        map_category(
            repr(["Electronics", "Computers & Accessories", "Laptop Accessories"]),
            "Laptop skin for a computer",
        )
        == "Computers & Accessories"
    )
    assert (
        map_category(
            repr(["Electronics", "Headphones", "Accessories"]),
            "Replacement ear hooks for wireless earbuds",
        )
        is None
    )
    assert map_category(repr(["Home & Kitchen"]), "Headphones") is None


def test_only_secure_amazon_large_image_urls_are_accepted() -> None:
    assert (
        _valid_large_image(
            repr(
                {
                    "large": [
                        None,
                        "https://m.media-amazon.com/images/I/41image.jpg",
                    ]
                }
            )
        )
        == "https://m.media-amazon.com/images/I/41image.jpg"
    )
    assert _valid_large_image(repr({"large": ["http://m.media-amazon.com/a.jpg"]})) is None
    assert _valid_large_image(repr({"large": ["https://example.com/a.jpg"]})) is None
    assert _valid_large_image(repr({"thumb": ["https://m.media-amazon.com/a.jpg"]})) is None


def test_duplicate_asins_are_selected_once() -> None:
    selection = select_import_records(
        [_row(), _row(title="A duplicate computer product")],
        limit=2,
    )

    assert selection.source_count == 2
    assert selection.candidate_count == 1
    assert len(selection.selected) == 1
    assert selection.rejected_by_reason["duplicate_parent_asin"] == 1


def test_import_is_idempotent_and_preserves_curated_products(
    db_session: Session,
) -> None:
    seed_products(db_session)
    curated = db_session.scalar(
        select(Product).where(Product.product_id == "SS-HP-002")
    )
    assert curated is not None
    curated_snapshot = (curated.name, curated.price, dict(curated.attributes))

    record = select_import_records([_row()], limit=1).selected
    first = import_selected_records(db_session, record)
    second = import_selected_records(db_session, record)

    assert first.inserted_count == 1
    assert second.inserted_count == 0
    assert second.already_present_count == 1
    assert db_session.query(AmazonCatalogueProduct).count() == 1
    assert db_session.query(Product).count() == len(DEMO_PRODUCTS)
    db_session.refresh(curated)
    assert (curated.name, curated.price, dict(curated.attributes)) == curated_snapshot


def test_invalid_rating_and_image_are_rejected_with_reasons() -> None:
    selection = select_import_records(
        [
            _row(asin="B000000002", rating=2.5),
            _row(asin="B000000003", image="https://example.com/image.jpg"),
        ],
        limit=2,
    )

    assert selection.selected == []
    assert selection.rejected_by_reason["insufficient_rating_or_review_count"] == 1
    assert selection.rejected_by_reason["missing_or_invalid_large_image"] == 1
