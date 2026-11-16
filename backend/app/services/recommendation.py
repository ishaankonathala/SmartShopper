"""Deterministic, explainable recommendation engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dna_defaults import PREFERENCE_DIMENSIONS
from app.models.product import Product
from app.models.shopper_dna import ShopperDNA
from app.models.user_profile import UserProfile
from app.schemas.recommendation import (
    ExcludedProduct,
    RecommendationRequest,
    RecommendationResponse,
    RecommendedProduct,
)

DIMENSION_WEIGHTS: dict[str, float] = {
    "comfort_priority": 0.25,
    "brand_loyalty": 0.20,
    "price_sensitivity": 0.20,
    "quality_preference": 0.20,
    "portability_preference": 0.10,
    "battery_life_priority": 0.05,
}

DIMENSION_ORDER: tuple[str, ...] = tuple(PREFERENCE_DIMENSIONS)
PreferenceOverrideDimension = Literal[
    "comfort_priority",
    "brand_loyalty",
    "battery_life_priority",
]


def _clamp(value: float, *, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _effective_dna_value(
    dna: ShopperDNA | None,
    dimension: str,
    preference_overrides: Mapping[PreferenceOverrideDimension, int],
) -> float:
    if dimension in preference_overrides:
        return _clamp(float(preference_overrides[dimension]))

    if dna is None:
        return 50.0

    inferred = dna.inferred_preferences.get(dimension, 50)
    confidence = dna.confidence_scores.get(dimension, 0)
    source = dna.preference_sources.get(dimension, "default")
    if source == "default":
        confidence = 0
    return _clamp(50 + (inferred - 50) * (confidence / 100.0))


def _matches_disliked_attributes(product: Product, disliked: list[str]) -> bool:
    if not disliked:
        return False

    attributes = product.attributes if isinstance(product.attributes, dict) else {}
    normalized_dislikes = {item.strip().lower() for item in disliked if str(item).strip()}
    if not normalized_dislikes:
        return False

    for key, value in attributes.items():
        key_text = str(key).lower()
        if key_text in normalized_dislikes:
            return True
        if isinstance(value, str):
            value_text = value.lower()
            if value_text in normalized_dislikes or any(
                dislike in value_text for dislike in normalized_dislikes
            ):
                return True
        else:
            value_text = str(value).lower()
            if value_text in normalized_dislikes or any(
                dislike in value_text for dislike in normalized_dislikes
            ):
                return True
    return False


def _product_brand_match(product: Product, preferred_brands: list[str]) -> bool:
    if not preferred_brands:
        return False
    preferred = {brand.strip().lower() for brand in preferred_brands if str(brand).strip()}
    return product.brand.lower() in preferred


def _feature_value_for_dimension(
    product: Product,
    dimension: str,
    *,
    preferred_brands: list[str] | None = None,
    max_budget: float | None = None,
    battery_max_hours: float | None = None,
) -> float | None:
    attributes = product.attributes if isinstance(product.attributes, dict) else {}

    if dimension == "comfort_priority":
        value = attributes.get("comfort_score")
        if value is None:
            return None
        try:
            return _clamp(float(value))
        except (TypeError, ValueError):
            return None

    if dimension == "brand_loyalty":
        if not preferred_brands:
            return None
        return 100.0 if _product_brand_match(product, preferred_brands) else 0.0

    if dimension == "price_sensitivity":
        if max_budget is None or max_budget <= 0:
            return None
        if product.price <= 0:
            return 100.0
        ratio = product.price / max_budget
        return _clamp(100.0 - (ratio * 100.0))

    if dimension == "quality_preference":
        build_quality = attributes.get("build_quality")
        if build_quality is not None:
            try:
                return _clamp(float(build_quality))
            except (TypeError, ValueError):
                pass
        rating = product.rating
        if rating is None:
            return None
        try:
            return _clamp((float(rating) / 5.0) * 100.0)
        except (TypeError, ValueError):
            return None

    if dimension == "portability_preference":
        value = attributes.get("portability")
        if value is None:
            return None
        try:
            return _clamp(float(value))
        except (TypeError, ValueError):
            return None

    if dimension == "battery_life_priority":
        value = attributes.get("battery_life_hours")
        if value is None or battery_max_hours is None or battery_max_hours <= 0:
            return None
        try:
            hours = float(value)
            return _clamp((hours / battery_max_hours) * 100.0)
        except (TypeError, ValueError):
            return None

    return None


def _compute_exclusion_reason(
    product: Product,
    *,
    request: RecommendationRequest,
    profile: UserProfile,
    require_available: bool,
) -> ExcludedProduct | None:
    if not product.is_active:
        return ExcludedProduct(
            product_id=product.product_id,
            name=product.name,
            reason_code="inactive_product",
            message="Product is inactive and excluded from recommendations.",
        )

    if require_available and product.stock_quantity <= 0:
        return ExcludedProduct(
            product_id=product.product_id,
            name=product.name,
            reason_code="out_of_stock",
            message="Product is out of stock and excluded from recommendations.",
        )

    effective_budget = (
        request.max_budget_override if request.max_budget_override is not None else profile.max_budget
    )
    if product.price > effective_budget:
        return ExcludedProduct(
            product_id=product.product_id,
            name=product.name,
            reason_code="budget_exceeded",
            message=(
                f"Product price {product.price} exceeds the effective budget of {effective_budget}."
            ),
        )

    if profile.min_budget is not None and product.price < profile.min_budget:
        return ExcludedProduct(
            product_id=product.product_id,
            name=product.name,
            reason_code="below_min_budget",
            message=(
                f"Product price {product.price} is below the minimum budget of {profile.min_budget}."
            ),
        )

    requested_category = request.effective_category
    if requested_category and product.category.strip().lower() != requested_category.strip().lower():
        return ExcludedProduct(
            product_id=product.product_id,
            name=product.name,
            reason_code="category_mismatch",
            message=(
                f"Product category '{product.category}' does not match the requested category "
                f"'{requested_category}'."
            ),
        )

    if _matches_disliked_attributes(product, profile.disliked_attributes):
        return ExcludedProduct(
            product_id=product.product_id,
            name=product.name,
            reason_code="disliked_attribute",
            message="Product attributes match a disliked attribute or value in the profile.",
        )

    return None


def _score_product(
    product: Product,
    *,
    profile: UserProfile,
    dna: ShopperDNA | None,
    max_budget: float,
    requested_category: str | None,
    battery_max_hours: float | None,
    include_explanations: bool,
    preference_overrides: Mapping[PreferenceOverrideDimension, int],
) -> RecommendedProduct:
    reasons: list[str] = []
    attribute_breakdown: dict[str, float] = {}
    score_breakdown: dict[str, float] = {}
    active_weights: dict[str, float] = {}
    active_confidences: dict[str, float] = {}
    preferred_brands = list(profile.preferred_brands or [])
    brand_match = _product_brand_match(product, preferred_brands)

    if brand_match:
        reasons.append(f"Matches your preferred brand {product.brand}.")
    if product.price <= max_budget:
        reasons.append("Fits within your budget.")

    for dimension in DIMENSION_ORDER:
        feature_value = _feature_value_for_dimension(
            product,
            dimension,
            preferred_brands=preferred_brands,
            max_budget=max_budget,
            battery_max_hours=battery_max_hours,
        )
        if feature_value is None:
            continue

        weight = DIMENSION_WEIGHTS[dimension]
        active_weights[dimension] = weight
        attribute_breakdown[dimension] = round(_clamp(feature_value), 2)

        effective_value = _effective_dna_value(dna, dimension, preference_overrides)
        contribution = (feature_value / 100.0) * (effective_value / 100.0) * 100.0
        score_breakdown[dimension] = round(contribution * weight, 2)

        if dimension in preference_overrides:
            confidence_value = 100.0
        else:
            source = (dna.preference_sources.get(dimension, "default") if dna else "default")
            if source == "default":
                confidence_value = 0.0
            else:
                confidence_value = float(dna.confidence_scores.get(dimension, 0)) if dna else 0.0
        active_confidences[dimension] = confidence_value

        if dimension == "comfort_priority" and feature_value >= 75:
            reasons.append("Strong comfort score matches your comfort preference.")
        if dimension == "quality_preference" and feature_value >= 75:
            reasons.append("Good build quality matches your quality preference.")
        if dimension == "portability_preference" and feature_value >= 75:
            reasons.append("High portability aligns with your portability preference.")
        if dimension == "battery_life_priority" and feature_value >= 75:
            reasons.append("Strong battery life aligns with your battery preference.")

    if requested_category and product.category.strip().lower() == requested_category.strip().lower():
        reasons.append(f"Matches your requested category '{requested_category}'.")

    if not active_weights:
        final_score = 0.0
        final_confidence = 0.0
    else:
        total_weight = sum(active_weights.values())
        final_score = round(sum(score_breakdown.values()) / total_weight, 2)
        final_confidence = round(
            sum(active_confidences.get(dim, 0.0) * weight for dim, weight in active_weights.items())
            / total_weight,
            2,
        )

    if not include_explanations:
        reasons = []
    elif not reasons:
        reasons.append("Recommended based on current catalogue fit and profile signals.")

    return RecommendedProduct(
        product_id=product.product_id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        price=product.price,
        rating=product.rating,
        image_url=product.image_url,
        score=_clamp(final_score),
        confidence=_clamp(final_confidence),
        reasons=list(dict.fromkeys(reasons)),
        attribute_breakdown={key: round(_clamp(value), 2) for key, value in attribute_breakdown.items()},
        score_breakdown={key: round(value, 2) for key, value in score_breakdown.items()},
    )


def generate_recommendations(
    db: Session,
    request: RecommendationRequest,
    *,
    preference_overrides: Mapping[PreferenceOverrideDimension, int] | None = None,
    product_snapshot: Sequence[Product] | None = None,
) -> RecommendationResponse:
    """Generate deterministic, explainable product recommendations for a user."""
    overrides = dict(preference_overrides or {})
    unsupported_dimensions = set(overrides) - {
        "comfort_priority",
        "brand_loyalty",
        "battery_life_priority",
    }
    if unsupported_dimensions:
        raise ValueError(f"Unsupported recommendation preference overrides: {sorted(unsupported_dimensions)}")

    profile = db.get(UserProfile, request.user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User profile {request.user_id} not found",
        )

    dna_query = select(ShopperDNA).where(ShopperDNA.user_id == profile.id)
    dna = db.scalar(dna_query)
    if dna is None:
        dna = ShopperDNA(
            user_id=profile.id,
            inferred_preferences={dimension: 50 for dimension in DIMENSION_ORDER},
            confidence_scores={dimension: 0 for dimension in DIMENSION_ORDER},
            preference_sources={dimension: "default" for dimension in DIMENSION_ORDER},
        )

    effective_max_budget = (
        request.max_budget_override if request.max_budget_override is not None else profile.max_budget
    )
    requested_category = request.effective_category

    if product_snapshot is None:
        stmt = select(Product)
        all_products = list(db.scalars(stmt).all())
    else:
        all_products = product_snapshot
    candidate_count = len(all_products)

    battery_max_hours = 0.0
    for product in all_products:
        attributes = product.attributes
        battery_value = (
            attributes.get("battery_life_hours")
            if isinstance(attributes, dict)
            else None
        )
        if battery_value is None:
            continue
        try:
            battery_max_hours = max(battery_max_hours, float(battery_value))
        except (TypeError, ValueError):
            continue

    ranked_products: list[RecommendedProduct] = []
    excluded: list[ExcludedProduct] = []

    for product in all_products:
        exclusion = _compute_exclusion_reason(
            product,
            request=request,
            profile=profile,
            require_available=request.require_available,
        )
        if exclusion is not None:
            excluded.append(exclusion)
            continue

        ranked_products.append(
            _score_product(
                product,
                profile=profile,
                dna=dna,
                max_budget=effective_max_budget,
                requested_category=requested_category,
                battery_max_hours=battery_max_hours,
                include_explanations=request.include_explanations,
                preference_overrides=overrides,
            )
        )

    ranked_products.sort(key=lambda item: (-item.score, item.product_id))
    selected = ranked_products[: request.limit]

    explanation_summary = (
        f"Returned {len(selected)} recommendation(s) for user {request.user_id} "
        f"after evaluating {candidate_count} candidate product(s)."
    )

    return RecommendationResponse(
        user_id=request.user_id,
        generated_at=datetime.now(timezone.utc),
        requested_limit=request.limit,
        products=selected,
        excluded_products=excluded,
        explanation_summary=explanation_summary,
    )
