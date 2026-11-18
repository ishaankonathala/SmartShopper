"""Validated inputs and outputs for registered agent tools."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.assistant import AssistantIntent
from app.schemas.recommendation import RecommendationResponse

AgentToolName = Literal[
    "product_search",
    "product_comparison",
    "get_shopper_profile",
    "simulate_preferences",
    "evaluate_results",
]


class ToolSelection(BaseModel):
    """One model-selected action from the registered tool allowlist."""

    model_config = ConfigDict(extra="forbid")

    tool_name: AgentToolName
    arguments: dict[str, object] = Field(default_factory=dict)


class ProductSearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=10, ge=1, le=25)


class ProductComparisonArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_ids: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(
        min_length=2,
        max_length=3,
    )

    @field_validator("product_ids")
    @classmethod
    def validate_unique_ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Comparison product IDs must be unique.")
        return value


class EmptyToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreferenceSimulationArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_budget_override: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    min_budget_override: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    comfort_priority: int | None = Field(default=None, ge=0, le=100)
    brand_loyalty: int | None = Field(default=None, ge=0, le=100)
    battery_life_priority: int | None = Field(default=None, ge=0, le=100)
    portability_priority: int | None = Field(default=None, ge=0, le=100)


class EvaluationArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_index: int = Field(ge=0)


class ComparedProduct(BaseModel):
    product_id: str
    catalogue_source: Literal["curated", "amazon"]
    name: str
    brand: str | None
    category: str
    price: float | None
    rating: float | None
    rating_count: int | None
    availability_status: str
    price_is_historical: bool
    features: list[str] | None = None
    description: str | None = None
    fields: dict[str, object | None]


class ProductComparisonResult(BaseModel):
    products: list[ComparedProduct]
    compared_fields: list[str]
    missing_fields: dict[str, list[str]]


class ShopperProfileResult(BaseModel):
    user_id: int
    max_budget: float
    min_budget: float | None
    preferred_categories: list[str]
    preferred_brands: list[str]
    disliked_attributes: list[str]
    inferred_preferences: dict[str, int]
    confidence_scores: dict[str, int]
    preference_sources: dict[str, str]


class PreferenceSimulationResult(BaseModel):
    recommendations: RecommendationResponse
    simulated_constraints: AssistantIntent


class EvaluationResult(BaseModel):
    satisfied: bool
    outcome: Literal[
        "eligible_results",
        "comparison_complete",
        "profile_retrieved",
        "simulated_results",
        "no_matches",
        "needs_comparison",
        "constraint_violation",
        "missing_result",
        "tool_failed",
    ]
    eligible_product_count: int = Field(default=0, ge=0)
    missing_specifications: list[str] = Field(default_factory=list)
    duplicate_product_ids: list[str] = Field(default_factory=list)
    catalogue_sources: list[str] = Field(default_factory=list)
    availability_statuses: list[str] = Field(default_factory=list)
    price_provenance: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
