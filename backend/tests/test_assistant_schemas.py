"""Assistant intent and chat schema tests."""

import pytest
from pydantic import ValidationError

from app.schemas.assistant import (
    AssistantCategory,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantIntent,
)
from app.schemas.recommendation import RecommendedProduct


def test_valid_assistant_request_trims_message_and_applies_default_limit() -> None:
    request = AssistantChatRequest(
        user_id=1,
        message="  Find comfortable headphones  ",
    )

    assert request.user_id == 1
    assert request.message == "Find comfortable headphones"
    assert request.limit == 10
    assert request.conversation_context is None
    assert request.previous_product_ids == []


def test_assistant_request_validates_structured_conversation_state_and_product_ids() -> None:
    request = AssistantChatRequest.model_validate(
        {
            "user_id": 1,
            "message": "Show me more options.",
            "conversation_context": {
                "category": "earbuds",
                "max_budget_override": 5000,
                "connectivity_requirement": "wireless",
                "product_type_requirement": "earbuds",
                "battery_life_priority": 80,
            },
            "previous_product_ids": ["SS-HP-002"],
        }
    )

    assert request.conversation_context is not None
    assert request.conversation_context.category == "Headphones"
    assert request.conversation_context.max_budget_override == 5000
    assert request.conversation_context.connectivity_requirement == "wireless"
    assert request.conversation_context.product_type_requirement == "earbuds"
    assert request.previous_product_ids == ["SS-HP-002"]


def test_assistant_request_rejects_duplicate_previous_product_ids() -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest(
            user_id=1,
            message="Show me more options.",
            previous_product_ids=["SS-HP-002", "SS-HP-002"],
        )


@pytest.mark.parametrize("message", ["", " ", "\n\t"])
def test_assistant_request_rejects_empty_or_whitespace_message(message: str) -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest(user_id=1, message=message)


def test_assistant_request_rejects_message_over_2000_characters() -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest(user_id=1, message="x" * 2001)


def test_assistant_request_accepts_message_at_maximum_length() -> None:
    request = AssistantChatRequest(user_id=1, message=f" {('x' * 2000)} ")

    assert len(request.message) == 2000


@pytest.mark.parametrize(
    "payload",
    [
        {"user_id": 0, "message": "Find headphones"},
        {"user_id": -1, "message": "Find headphones"},
        {"user_id": 1, "message": "Find headphones", "limit": 0},
        {"user_id": 1, "message": "Find headphones", "limit": 26},
    ],
)
def test_assistant_request_rejects_invalid_user_id_and_limit(payload: dict) -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest.model_validate(payload)


def test_valid_assistant_intent_normalizes_catalogue_category_aliases() -> None:
    intent = AssistantIntent(
        category="  earbuds ",
        max_budget_override=6500,
        comfort_priority=85,
        brand_loyalty=60,
        battery_life_priority=90,
    )

    assert intent.category == "Headphones"
    assert intent.max_budget_override == 6500
    assert intent.comfort_priority == 85
    assert intent.brand_loyalty == 60
    assert intent.battery_life_priority == 90


@pytest.mark.parametrize("connectivity", ["wireless", "wired"])
def test_assistant_intent_supports_connectivity_requirement(connectivity: str) -> None:
    intent = AssistantIntent(connectivity_requirement=connectivity)

    assert intent.connectivity_requirement == connectivity


def test_assistant_intent_rejects_unknown_connectivity_requirement() -> None:
    with pytest.raises(ValidationError):
        AssistantIntent(connectivity_requirement="unknown")


def test_assistant_intent_rejects_unknown_product_type_requirement() -> None:
    with pytest.raises(ValidationError):
        AssistantIntent(product_type_requirement="accessory")


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("earphones", "Headphones"),
        ("ultrabook", "Laptops"),
        ("smart band", "Smartwatches"),
        ("home appliance", "Home Appliances"),
    ],
)
def test_assistant_intent_accepts_explicit_catalogue_aliases(
    alias: str, expected: AssistantCategory
) -> None:
    assert AssistantIntent(category=alias).category == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("comfort_priority", -1),
        ("comfort_priority", 101),
        ("brand_loyalty", -1),
        ("brand_loyalty", 101),
        ("battery_life_priority", -1),
        ("battery_life_priority", 101),
    ],
)
def test_assistant_intent_rejects_out_of_range_preference_values(
    field: str, value: int
) -> None:
    with pytest.raises(ValidationError):
        AssistantIntent.model_validate({field: value})


def test_assistant_intent_rejects_negative_or_non_finite_budget() -> None:
    for budget in (-1, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            AssistantIntent(max_budget_override=budget)


def test_unsupported_requirements_are_separate_and_trimmed() -> None:
    intent = AssistantIntent(
        category="headphones",
        comfort_priority=80,
        unsupported_requirements=[" wireless "],
    )

    assert intent.category == "Headphones"
    assert intent.comfort_priority == 80
    assert intent.unsupported_requirements == ["wireless"]
    assert not hasattr(intent, "wireless")


def test_assistant_intent_rejects_unknown_category_and_empty_unsupported_requirement() -> None:
    with pytest.raises(ValidationError):
        AssistantIntent(category="Tablets")
    with pytest.raises(ValidationError):
        AssistantIntent(unsupported_requirements=["  "])


def test_assistant_intent_rejects_unmodeled_fields_instead_of_dropping_them() -> None:
    with pytest.raises(ValidationError):
        AssistantIntent.model_validate({"wireless": True})


def test_assistant_response_reuses_recommended_product_schema() -> None:
    recommendation = RecommendedProduct(
        product_id="SS-HP-001",
        name="AeroSoft Travel Headphones",
        brand="SonyDemo",
        category="Headphones",
        price=5999,
        rating=4.5,
        image_url=None,
        score=82,
        confidence=60,
        reasons=["Strong comfort score matches your comfort preference."],
        attribute_breakdown={"comfort_priority": 90},
        score_breakdown={"comfort_priority": 22.5},
    )

    response = AssistantChatResponse(
        user_id=1,
        answer="This headphone matches your comfort preference.",
        intent=AssistantIntent(category="Headphones", comfort_priority=80),
        recommendations=[recommendation],
        fallback_used=False,
    )

    assert response.recommendations[0] is recommendation
    assert response.fallback_used is False
    assert response.notes == []
    assert response.kind == "shopping"
    assert response.has_more is False
