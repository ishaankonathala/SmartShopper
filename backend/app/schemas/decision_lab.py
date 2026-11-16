"""Pydantic schemas for Decision Lab simulations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DecisionLabRequest(BaseModel):
    """Temporary recommendation overrides for a Decision Lab comparison."""

    user_id: int = Field(gt=0)
    max_budget_override: float | None = Field(default=None, ge=0)
    comfort_priority: int | None = Field(default=None, ge=0, le=100)
    brand_loyalty: int | None = Field(default=None, ge=0, le=100)


class DecisionLabProductState(BaseModel):
    """Product status in one recommendation run."""

    status: Literal["recommended", "excluded", "outside_limit"]
    rank: int | None = Field(default=None, ge=1)
    score: float | None = Field(default=None, ge=0, le=100)
    exclusion_reason_code: str | None = None
    exclusion_reason: str | None = None


class DecisionLabProductComparison(BaseModel):
    """Baseline-versus-simulation comparison for one product."""

    product_id: str
    name: str
    baseline: DecisionLabProductState
    simulated: DecisionLabProductState
    rank_movement: int | None
    score_difference: float | None
    explanation: str


class DecisionLabResponse(BaseModel):
    """Decision Lab response with per-product changes and context."""

    user_id: int
    baseline_budget: float
    simulated_budget: float
    comparisons: list[DecisionLabProductComparison]
    notes: list[str] = Field(default_factory=list)
