"""Pydantic schemas for the AI shopping assistant intent and API contract."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.recommendation import RecommendedProduct

AssistantCategory = Literal[
    "Headphones",
    "Laptops",
    "Smartwatches",
    "Home Appliances",
    "Computers & Accessories",
    "Camera & Photo",
    "Headphones & Earbuds",
    "Television & Video",
    "Home Audio",
    "Car Electronics",
    "Portable Audio & Video",
    "Wearable Technology",
    "Other Electronics",
]
ConnectivityRequirement = Literal["wireless", "wired"]
ProductTypeRequirement = Literal["headphones", "earbuds", "sleep_headphones"]
AvailabilityRequirement = Literal["available"]
PreferencePriority = Annotated[int, Field(ge=0, le=100)]
UnsupportedRequirement = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
ProductIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]

CATEGORY_ALIASES: dict[str, AssistantCategory] = {
    "headphone": "Headphones",
    "headphones": "Headphones",
    "earbud": "Headphones",
    "earbuds": "Headphones",
    "earphone": "Headphones",
    "earphones": "Headphones",
    "laptop": "Laptops",
    "laptops": "Laptops",
    "ultrabook": "Laptops",
    "smartwatch": "Smartwatches",
    "smartwatches": "Smartwatches",
    "smart band": "Smartwatches",
    "smart bands": "Smartwatches",
    "home appliance": "Home Appliances",
    "home appliances": "Home Appliances",
    "computer": "Computers & Accessories",
    "computers": "Computers & Accessories",
    "computer accessories": "Computers & Accessories",
    "computers & accessories": "Computers & Accessories",
    "computers and accessories": "Computers & Accessories",
    "camera": "Camera & Photo",
    "cameras": "Camera & Photo",
    "camera and photo": "Camera & Photo",
    "camera & photo": "Camera & Photo",
    "headphones & earbuds": "Headphones & Earbuds",
    "headphones and earbuds": "Headphones & Earbuds",
    "television": "Television & Video",
    "televisions": "Television & Video",
    "tv": "Television & Video",
    "tvs": "Television & Video",
    "television and video": "Television & Video",
    "television & video": "Television & Video",
    "home audio": "Home Audio",
    "car electronics": "Car Electronics",
    "car audio": "Car Electronics",
    "portable audio": "Portable Audio & Video",
    "portable audio and video": "Portable Audio & Video",
    "portable audio & video": "Portable Audio & Video",
    "wearable": "Wearable Technology",
    "wearables": "Wearable Technology",
    "wearable technology": "Wearable Technology",
    "other electronics": "Other Electronics",
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
    min_budget_override: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    brand: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    ] | None = None
    min_rating: float | None = Field(default=None, ge=1, le=5, allow_inf_nan=False)
    min_battery_life_hours: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    require_battery_life_data: bool | None = None
    availability_requirement: AvailabilityRequirement | None = None
    comfort_priority: PreferencePriority | None = None
    brand_loyalty: PreferencePriority | None = None
    battery_life_priority: PreferencePriority | None = None
    portability_priority: PreferencePriority | None = None
    connectivity_requirement: ConnectivityRequirement | None = None
    product_type_requirement: ProductTypeRequirement | None = None
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
    conversation_context: AssistantIntent | None = None
    previous_product_ids: list[ProductIdentifier] = Field(
        default_factory=list,
        max_length=25,
    )

    @field_validator("message", mode="before")
    @classmethod
    def trim_and_require_message(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        message = value.strip()
        if not message:
            raise ValueError("Message cannot be empty")
        return message

    @field_validator("previous_product_ids")
    @classmethod
    def require_unique_previous_product_ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Previous product IDs must be unique")
        return value


AssistantResponseKind = Literal[
    "shopping",
    "acknowledgement",
    "clarification",
    "answer",
]


class AgentExecutionMetadata(BaseModel):
    """Safe, user-facing summary of a bounded agent run."""

    execution_id: str = Field(min_length=1, max_length=64)
    status: Literal["completed", "partial", "fallback", "unavailable"]
    plan_summary: Annotated[str, Field(max_length=500)]
    tools_executed: list[
        Literal[
            "product_search",
            "product_comparison",
            "get_shopper_profile",
            "simulate_preferences",
            "evaluate_results",
        ]
    ] = Field(default_factory=list, max_length=5)
    tool_execution_count: int = Field(ge=0, le=5)
    evaluation_outcome: Annotated[str, Field(max_length=64)]
    activity: list[Annotated[str, Field(max_length=120)]] = Field(
        default_factory=list,
        max_length=5,
    )
    events: list[AgentActivityEvent] = Field(default_factory=list, max_length=16)


class AgentActivityEvent(BaseModel):
    """Concise user-facing summary of an actual agent execution event."""

    sequence: int = Field(ge=1)
    kind: Literal[
        "understanding",
        "planning",
        "selection",
        "tool_execution",
        "evaluation",
        "completion",
    ]
    title: Annotated[str, Field(min_length=1, max_length=100)]
    status: Literal["completed", "failed", "partial"]
    summary: Annotated[str, Field(max_length=400)]
    tool_name: Literal[
        "product_search",
        "product_comparison",
        "get_shopper_profile",
        "simulate_preferences",
        "evaluate_results",
    ] | None = None
    succeeded: bool | None = None


class AssistantChatResponse(BaseModel):
    """Structured assistant answer and recommendation results."""

    user_id: int
    answer: str
    intent: AssistantIntent
    recommendations: list[RecommendedProduct]
    fallback_used: bool
    notes: list[str] = Field(default_factory=list)
    has_more: bool = False
    kind: AssistantResponseKind = "shopping"
    agent_metadata: AgentExecutionMetadata | None = None
