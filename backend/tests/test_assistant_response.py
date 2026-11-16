"""Grounded assistant response service tests."""

import json

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.assistant import AssistantChatRequest, AssistantIntent
from app.schemas.recommendation import RecommendationRequest
from app.services.assistant_response import (
    DEMO_CATALOGUE_DISCLAIMER,
    generate_assistant_response,
)
from app.services.groq_client import GroqClient
from app.services.recommendation import DIMENSION_WEIGHTS, generate_recommendations

TEST_API_KEY = "test-groq-key-never-log"


def _create_user(client, payload: dict) -> int:
    response = client.post("/api/profiles", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _mock_groq_client(
    intent: AssistantIntent,
    *,
    explanation_mode: str = "valid",
) -> tuple[GroqClient, list[dict]]:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        messages = body["messages"]
        if "You extract shopping intent only." in messages[0]["content"]:
            content = intent.model_dump_json()
        else:
            data = json.loads(messages[1]["content"])
            if explanation_mode == "timeout":
                raise httpx.ReadTimeout("simulated timeout", request=request)
            if explanation_mode == "invalid":
                content = "{malformed explanation"
            else:
                explanations = [
                    {
                        "product_id": product["product_id"],
                        "explanation": (
                            "Its listed reasons align with the stated preferences "
                            "and requested category."
                        ),
                    }
                    for product in data["recommendations"]
                ]
                if explanation_mode == "grounded_reason":
                    for product, item in zip(
                        data["recommendations"],
                        explanations,
                        strict=True,
                    ):
                        item["explanation"] = next(
                            (
                                reason
                                for reason in product["reasons"]
                                if reason.startswith("Strong comfort score")
                            ),
                            "Fits within your budget.",
                        )
                response_data = {
                    "summary": "These results reflect the requested category and priorities.",
                    "product_explanations": explanations,
                }
                if explanation_mode == "introduced_product":
                    response_data["product_explanations"].append(
                        {
                            "product_id": "SS-FAKE-999",
                            "explanation": "An unranked item is also recommended.",
                        }
                    )
                elif explanation_mode == "extra_recommendation":
                    response_data["recommendations"] = [
                        {"product_id": "SS-FAKE-999", "name": "Invented Product"}
                    ]
                elif explanation_mode == "hallucinated_product_name":
                    response_data["summary"] = "These results are better than Galaxy Ultra."
                elif explanation_mode == "invented_lowercase_name":
                    response_data["summary"] = "These results include galaxy ultra."
                elif explanation_mode == "unsupported_claim":
                    response_data["summary"] = "These options are wireless and available now."
                elif explanation_mode.startswith(("product_", "brand_")):
                    identity_type, casing = explanation_mode.split("_", maxsplit=1)
                    identity = data["recommendations"][0][
                        "name" if identity_type == "product" else "brand"
                    ]
                    if casing == "lower":
                        identity = identity.lower()
                    elif casing == "upper":
                        identity = identity.upper()
                    else:
                        identity = "".join(
                            character.upper() if index % 2 else character.lower()
                            for index, character in enumerate(identity)
                        )
                    response_data["summary"] = f"These results include {identity}."
                elif explanation_mode == "unsupported_durability":
                    response_data["summary"] = "These options are durable."
                elif explanation_mode == "unsupported_performance":
                    response_data["summary"] = "These options deliver fast performance."
                elif explanation_mode == "unsupported_feature":
                    response_data["summary"] = "These options include a touchscreen."
                content = json.dumps(response_data)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    return (
        GroqClient(
            settings=Settings(groq_api_key=TEST_API_KEY, groq_model="test-model"),
            transport=httpx.MockTransport(handler),
        ),
        calls,
    )


def test_successful_intent_extraction_recommendations_and_grounded_explanation(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    intent = AssistantIntent(
        category="Headphones",
        comfort_priority=85,
        battery_life_priority=75,
    )
    groq_client, calls = _mock_groq_client(intent)
    request = AssistantChatRequest(user_id=user_id, message="Comfortable headphones.")

    response = generate_assistant_response(db_session, request, groq_client=groq_client)

    direct = generate_recommendations(
        db_session,
        RecommendationRequest(
            user_id=user_id,
            category="Headphones",
            limit=request.limit,
        ),
        preference_overrides={
            "comfort_priority": 85,
            "battery_life_priority": 75,
        },
    )
    assert response.user_id == user_id
    assert response.intent == intent
    assert response.recommendations
    assert [item.product_id for item in response.recommendations] == [
        item.product_id for item in direct.products
    ]
    assert response.answer.startswith("These results reflect")
    assert DEMO_CATALOGUE_DISCLAIMER in response.answer
    assert response.fallback_used is False
    assert len(calls) == 2
    supplied = json.loads(calls[1]["messages"][1]["content"])
    assert supplied["recommendations"][0]["product_id"] == response.recommendations[0].product_id
    assert supplied["recommendations"][0]["name"] == response.recommendations[0].name
    assert supplied["recommendations"][0]["brand"] == response.recommendations[0].brand
    assert supplied["recommendations"][0]["price"] == response.recommendations[0].price
    assert supplied["recommendations"][0]["rating"] == response.recommendations[0].rating
    assert supplied["recommendations"][0]["score"] == response.recommendations[0].score
    assert supplied["recommendations"][0]["reasons"] == response.recommendations[0].reasons


def test_legitimate_general_explanation_is_accepted(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, _ = _mock_groq_client(AssistantIntent(category="Headphones"))

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Headphones."),
        groq_client=groq_client,
    )

    assert response.fallback_used is False
    assert response.answer.startswith("These results reflect")
    assert DEMO_CATALOGUE_DISCLAIMER in response.answer


def test_explanation_grounded_in_recommendation_reason_is_accepted(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, _ = _mock_groq_client(
        AssistantIntent(category="Headphones", comfort_priority=100),
        explanation_mode="grounded_reason",
    )

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Comfortable headphones.", limit=1),
        groq_client=groq_client,
    )

    assert response.fallback_used is False
    assert "Strong comfort score matches your comfort preference." in response.answer
    assert DEMO_CATALOGUE_DISCLAIMER in response.answer


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("comfort_priority", 90),
        ("brand_loyalty", 80),
        ("battery_life_priority", 100),
    ],
)
def test_temporary_preference_overrides_reach_recommendation_engine(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
    field: str,
    value: int,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    intent = AssistantIntent(category="Headphones", **{field: value})
    groq_client, _ = _mock_groq_client(intent)

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Headphones."),
        groq_client=groq_client,
    )
    product = next(item for item in response.recommendations if item.product_id == "SS-HP-001")
    feature_value = product.attribute_breakdown[field]
    expected_contribution = round(
        feature_value * DIMENSION_WEIGHTS[field] * value / 100,
        2,
    )

    assert product.score_breakdown[field] == expected_contribution


def test_budget_override_is_used_only_for_current_recommendations(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    profile_before = seeded_client.get(f"/api/profiles/{user_id}").json()
    intent = AssistantIntent(category="Headphones", max_budget_override=2600)
    groq_client, _ = _mock_groq_client(intent)

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Headphones under ₹2,600."),
        groq_client=groq_client,
    )

    assert [item.product_id for item in response.recommendations] == ["SS-HP-002"]
    assert response.recommendations[0].price <= intent.max_budget_override
    assert seeded_client.get(f"/api/profiles/{user_id}").json() == profile_before


@pytest.mark.parametrize("explanation_mode", ["timeout", "invalid"])
def test_groq_explanation_failure_uses_deterministic_fallback(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
    explanation_mode: str,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, _ = _mock_groq_client(
        AssistantIntent(category="Headphones"),
        explanation_mode=explanation_mode,
    )

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Headphones."),
        groq_client=groq_client,
    )

    assert response.recommendations
    assert response.fallback_used is True
    assert any("deterministic explanation" in note for note in response.notes)
    assert DEMO_CATALOGUE_DISCLAIMER in response.answer
    assert response.recommendations[0].name in response.answer


def test_missing_category_asks_for_clarification_without_recommendations(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, calls = _mock_groq_client(AssistantIntent())

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Help me shop."),
        groq_client=groq_client,
    )

    assert response.recommendations == []
    assert "What type of product" in response.answer
    assert any("category" in note for note in response.notes)
    assert response.fallback_used is True
    assert len(calls) == 1


def test_no_matching_recommendations_returns_explanation_and_exclusion_note(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, calls = _mock_groq_client(
        AssistantIntent(category="Headphones", max_budget_override=0)
    )

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(
            user_id=user_id,
            message="Headphones with no budget.",
        ),
        groq_client=groq_client,
    )

    assert response.recommendations == []
    assert "couldn't find any eligible Headphones" in response.answer
    assert any("budget_exceeded" in note for note in response.notes)
    assert DEMO_CATALOGUE_DISCLAIMER in response.answer
    assert response.fallback_used is True
    assert len(calls) == 1


@pytest.mark.parametrize(
    "explanation_mode",
    [
        "introduced_product",
        "extra_recommendation",
        "hallucinated_product_name",
        "invented_lowercase_name",
        "unsupported_claim",
        "product_lower",
        "product_upper",
        "product_mixed",
        "brand_lower",
        "brand_upper",
        "brand_mixed",
        "unsupported_durability",
        "unsupported_performance",
        "unsupported_feature",
    ],
)
def test_groq_cannot_introduce_unverified_products_or_claims(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
    explanation_mode: str,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, _ = _mock_groq_client(
        AssistantIntent(category="Headphones"),
        explanation_mode=explanation_mode,
    )
    expected = generate_recommendations(
        db_session,
        RecommendationRequest(user_id=user_id, category="Headphones"),
    )

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Headphones."),
        groq_client=groq_client,
    )

    expected_ids = [item.product_id for item in expected.products]
    assert [item.product_id for item in response.recommendations] == expected_ids
    assert "SS-FAKE-999" not in response.answer
    assert "Invented Product" not in response.answer
    assert "Galaxy Ultra" not in response.answer
    assert response.fallback_used is True
    assert DEMO_CATALOGUE_DISCLAIMER in response.answer


def test_assistant_recommendations_do_not_mutate_profile_or_shopper_dna(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    profile_before = seeded_client.get(f"/api/profiles/{user_id}").json()
    dna_before = seeded_client.get(f"/api/profiles/{user_id}/dna").json()
    groq_client, _ = _mock_groq_client(
        AssistantIntent(
            category="Headphones",
            max_budget_override=6000,
            comfort_priority=100,
            brand_loyalty=100,
            battery_life_priority=100,
        )
    )

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Comfortable headphones."),
        groq_client=groq_client,
    )

    assert response.recommendations
    assert seeded_client.get(f"/api/profiles/{user_id}").json() == profile_before
    assert seeded_client.get(f"/api/profiles/{user_id}/dna").json() == dna_before
