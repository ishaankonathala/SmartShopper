"""Grounded comparison tool for actual catalogue products."""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.amazon_catalogue_product import AmazonCatalogueProduct
from app.models.product import Product
from app.agent.schemas import (
    ComparedProduct,
    ProductComparisonArguments,
    ProductComparisonResult,
)
from app.agent.state import AgentState
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendation import (
    AMAZON_PRODUCT_ID_PREFIX,
    RecommendationCandidate,
    load_recommendation_products,
)

_COMPARISON_FIELDS = (
    "price",
    "rating",
    "rating_count",
    "category",
    "brand",
    "availability_status",
    "price_is_historical",
)


def _available_product_ids(state: AgentState) -> set[str]:
    available = set(state.previously_shown_product_ids)
    for record in state.tool_results:
        if isinstance(record.result, RecommendationResponse):
            available.update(product.product_id for product in record.result.products)
    return available


def _product_fields(product: RecommendationCandidate) -> dict[str, object | None]:
    fields: dict[str, object | None] = {
        "price": product.price,
        "rating": product.rating,
        "rating_count": product.rating_count,
        "category": product.category,
        "brand": product.brand,
        "availability_status": product.availability_status,
        "price_is_historical": product.price_is_historical,
    }
    fields.update(
        {
            key: value
            for key, value in (product.attributes or {}).items()
            if isinstance(key, str)
        }
    )
    return fields


def _catalogue_features_and_description(
    db: Session,
    product_ids: list[str],
) -> dict[str, tuple[list[str] | None, str | None]]:
    curated_ids = [
        product_id
        for product_id in product_ids
        if not product_id.startswith(AMAZON_PRODUCT_ID_PREFIX)
    ]
    amazon_asins = [
        product_id.removeprefix(AMAZON_PRODUCT_ID_PREFIX)
        for product_id in product_ids
        if product_id.startswith(AMAZON_PRODUCT_ID_PREFIX)
    ]
    details: dict[str, tuple[list[str] | None, str | None]] = {}
    if curated_ids:
        for product in db.scalars(
            select(Product).where(Product.product_id.in_(curated_ids))
        ).all():
            attributes = product.attributes if isinstance(product.attributes, dict) else {}
            raw_features = attributes.get("features")
            features = (
                [item for item in raw_features if isinstance(item, str)]
                if isinstance(raw_features, list)
                else None
            )
            description = product.description.strip() or None
            details[product.product_id] = (features, description)
    if amazon_asins:
        for product in db.scalars(
            select(AmazonCatalogueProduct).where(
                AmazonCatalogueProduct.asin.in_(amazon_asins)
            )
        ).all():
            features = [
                item for item in (product.features or []) if isinstance(item, str)
            ] or None
            description = "\n".join(
                item for item in (product.description or []) if isinstance(item, str)
            ).strip() or None
            details[f"{AMAZON_PRODUCT_ID_PREFIX}{product.asin}"] = (
                features,
                description,
            )
    return details


def compare_products(
    raw_arguments: BaseModel,
    state: AgentState,
    db: Session,
) -> ProductComparisonResult:
    arguments = ProductComparisonArguments.model_validate(raw_arguments)
    if len(set(arguments.product_ids)) != len(arguments.product_ids):
        raise ValueError("Comparison product IDs must be unique.")
    allowed_ids = _available_product_ids(state)
    if any(product_id not in allowed_ids for product_id in arguments.product_ids):
        raise ValueError("Comparison may only use previously shown or searched products.")

    products = load_recommendation_products(db, arguments.product_ids)
    products_by_id = {product.product_id: product for product in products}
    if set(products_by_id) != set(arguments.product_ids):
        raise ValueError("One or more comparison products are unavailable.")

    ordered = [products_by_id[product_id] for product_id in arguments.product_ids]
    feature_details = _catalogue_features_and_description(db, arguments.product_ids)
    product_fields = {
        product.product_id: {
            **_product_fields(product),
            "features": feature_details.get(product.product_id, (None, None))[0],
            "description": feature_details.get(product.product_id, (None, None))[1],
        }
        for product in ordered
    }
    compared_fields = list(_COMPARISON_FIELDS)
    compared_fields.extend(
        sorted(
            {
                field
                for fields in product_fields.values()
                for field in fields
                if field not in _COMPARISON_FIELDS
            }
        )
    )

    compared: list[ComparedProduct] = []
    missing_fields: dict[str, list[str]] = {}
    for product in ordered:
        fields = product_fields[product.product_id]
        row = {field: fields.get(field) for field in compared_fields}
        missing_fields[product.product_id] = [
            field
            for field, value in row.items()
            if value is None or value == []
        ]
        features, description = feature_details.get(product.product_id, (None, None))
        compared.append(
            ComparedProduct(
                product_id=product.product_id,
                catalogue_source=product.catalogue_source,
                name=product.name,
                brand=product.brand,
                category=product.category,
                price=product.price,
                rating=product.rating,
                rating_count=product.rating_count,
                availability_status=product.availability_status,
                price_is_historical=product.price_is_historical,
                features=features,
                description=description,
                fields=row,
            )
        )

    return ProductComparisonResult(
        products=compared,
        compared_fields=compared_fields,
        missing_fields=missing_fields,
    )
