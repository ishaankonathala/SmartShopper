"""Schema models for explainable product recommendations."""

from __future__ import annotations

from datetime import datetime

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CatalogueSource = Literal["curated", "amazon"]
AvailabilityStatus = Literal["available", "unavailable", "unverified"]


class RecommendationRequest(BaseModel):
    """Recommendation query for a shopper profile."""

    user_id: int = Field(gt=0)
    category: str | None = None
    limit: int = Field(default=10, ge=1, le=25)
    include_explanations: bool = True
    require_available: bool = True
    max_budget_override: float | None = Field(default=None, ge=0)
    min_budget_override: float | None = Field(default=None, ge=0)
    brand: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    ] | None = None
    min_rating: float | None = Field(default=None, ge=1, le=5, allow_inf_nan=False)
    include_unverified_availability: bool = False

    @model_validator(mode="after")
    def validate_budget_range(self) -> RecommendationRequest:
        if (
            self.min_budget_override is not None
            and self.max_budget_override is not None
            and self.min_budget_override > self.max_budget_override
        ):
            raise ValueError("min_budget_override cannot exceed max_budget_override")
        return self

    @property
    def effective_category(self) -> str | None:
        if self.category is None:
            return None
        cleaned = self.category.strip()
        return cleaned or None


class ExcludedProduct(BaseModel):
    """A product excluded before ranking."""

    product_id: str
    name: str
    reason_code: str
    message: str
    catalogue_source: CatalogueSource = "curated"


class RecommendedProduct(BaseModel):
    """A ranked product recommendation with transparent scoring."""

    model_config = ConfigDict(from_attributes=True)

    product_id: str
    name: str
    brand: str
    category: str
    price: float
    rating: float
    image_url: str | None
    score: float = Field(
        ge=0,
        le=100,
        description="Normalized recommendation ranking score.",
    )
    confidence: float = Field(
        ge=0,
        le=100,
        description="Weighted confidence in the user-preference signals used for ranking.",
    )
    reasons: list[str]
    attribute_breakdown: dict[str, float]
    score_breakdown: dict[str, float]
    catalogue_source: CatalogueSource = "curated"
    availability_status: AvailabilityStatus = "available"
    price_is_historical: bool = False
    rating_count: int | None = Field(default=None, ge=0)


class RecommendationResponse(BaseModel):
    """Recommendation response with ranked products and exclusions."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    generated_at: datetime
    requested_limit: int
    products: list[RecommendedProduct]
    excluded_products: list[ExcludedProduct]
    explanation_summary: str
    has_more: bool = False
