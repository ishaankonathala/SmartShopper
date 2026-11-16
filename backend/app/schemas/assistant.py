"""Pydantic schemas for the AI shopping assistant intent and API contract."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.recommendation import RecommendedProduct

AssistantCategory = Literal["Headphones", "Laptops", "Smartwatches", "Home Appliances"]
PreferencePriority = Annotated[int, Field(ge=0, le=100)]
UnsupportedRequirement = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]

CATEGORY_ALIASES: dict[str, AssistantCategory] = {
    "headphone": "Headphones",
    "headphones": "Headphones",
    "earbud": "Headphones",
    "earbuds": "Headphones",
    "laptop": "Laptops",
    "laptops": "Laptops",
    "ultrabook": "Laptops",
    "smartwatch": "Smartwatches",
    "smartwatches": "Smartwatches",
    "smart band": "Smartwatches",
    "smart bands": "Smartwatches",
    "home appliance": "Home Appliances",
    "home appliances": "Home Appliances",
}


class AssistantIntent(BaseModel):
    """Validated, catalogue-aware interpretation of a shopper request."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category: AssistantCategory | None = None
    max_budget_override: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    comfort_priority: PreferencePriority | None = None
    brand_loyalty: PreferencePriority | None = None
    battery_life_priority: PreferencePriority | None = None
    unsupported_requirements: list[UnsupportedRequirement] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value

        normalized = " ".join(value.casefold().split())
        category = CATEGORY_ALIASES.get(normalized)
        if category is None:
            raise ValueError(f"Unsupported catalogue category: {value}")
        return category


class AssistantChatRequest(BaseModel):
    """A natural-language request from a shopper."""

    user_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=10, ge=1, le=25)

    @field_validator("message", mode="before")
    @classmethod
    def trim_and_require_message(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        message = value.strip()
        if not message:
            raise ValueError("Message cannot be empty")
        return message


class AssistantChatResponse(BaseModel):
    """Structured assistant answer and recommendation results."""

    user_id: int
    answer: str
    intent: AssistantIntent
    recommendations: list[RecommendedProduct]
    fallback_used: bool
    notes: list[str] = Field(default_factory=list)
