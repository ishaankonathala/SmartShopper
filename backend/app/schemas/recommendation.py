"""Schema models for explainable product recommendations."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    """Recommendation query for a shopper profile."""

    user_id: int = Field(gt=0)
    category: str | None = None
    limit: int = Field(default=10, ge=1, le=25)
    include_explanations: bool = True
    require_available: bool = True
    max_budget_override: float | None = Field(default=None, ge=0)

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
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    reasons: list[str]
    attribute_breakdown: dict[str, float]
    score_breakdown: dict[str, float]


class RecommendationResponse(BaseModel):
    """Recommendation response with ranked products and exclusions."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    generated_at: datetime
    requested_limit: int
    products: list[RecommendedProduct]
    excluded_products: list[ExcludedProduct]
    explanation_summary: str
