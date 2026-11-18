"""Grounded assistant response service tests."""

import json

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.assistant import AssistantChatRequest, AssistantIntent
from app.schemas.recommendation import RecommendedProduct, RecommendationRequest
from app.services.assistant_response import (
    _GENERAL_EXPLANATION_WORDS,
    CHECK_NUMERIC_CLAIM,
    CHECK_PRODUCT_EXPLANATION_NOT_GROUNDED,
    CHECK_PRODUCT_ID_COUNT_MISMATCH,
    CHECK_PRODUCT_ID_MISSING,
    CHECK_PRODUCT_ID_ORDER_MISMATCH,
    CHECK_PRODUCT_ID_UNKNOWN,
    CHECK_PRODUCT_IDENTITY_REPEATED,
    CHECK_SUMMARY_NOT_GROUNDED,
    CHECK_UNSUPPORTED_REQUIREMENT_MENTIONED,
    CHECK_UNSUPPORTED_PRODUCT_CLAIM,
    DEMO_CATALOGUE_DISCLAIMER,
    EXPLANATION_SYSTEM_PROMPT,
    ExplanationCheckError,
    _GROUNDING_CHECK_CODES,
    _content_segments,
    _grounding_failure_note,
    _mentions_unsupported_requirement,
    _validate_explanation,
    generate_assistant_response,
)
from app.services.groq_client import GroqClient
from app.services.recommendation import DIMENSION_WEIGHTS, generate_recommendations

TEST_API_KEY = "test-groq-key-never-log"


def test_explanation_prompt_specifies_exact_response_structure() -> None:
    expected_structure = """{
  "summary": "A concise explanation of the recommendations.",
  "product_explanations": [
    {
      "product_id": "<product_id from products list>",
      "explanation": "A concise explanation grounded only in the supplied recommendation reasons."
    }
  ]
}"""
    prompt = " ".join(EXPLANATION_SYSTEM_PROMPT.split())

    assert expected_structure in EXPLANATION_SYSTEM_PROMPT
    assert "Each entry's product_id must be copied character-for-character" in prompt
    assert (
        "exactly one entry for each product in the recommendations list in the user message"
        in prompt
    )
    assert "Every entry must contain exactly product_id and explanation" in prompt
    assert "do not add any other JSON keys" in prompt
    assert "Return only a JSON object" in prompt
    assert "Never leave product_explanations empty" in prompt
    assert "never invent entries" in prompt
    assert "never use a product name in place of product_id" in prompt
    assert "SS-HP-" not in prompt
    assert "PulseBuds" not in prompt
    assert "do not invent product features or factual claims" in prompt


def _create_user(client, payload: dict) -> int:
    response = client.post("/api/profiles", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _validate_test_explanation(product_explanation: str):
    product = RecommendedProduct(
        product_id="SS-HP-TEST",
        name="Acme Comfort Headphones",
        brand="Acme",
        category="Headphones",
        price=100,
        rating=4.5,
        image_url=None,
        score=90,
        confidence=80,
        reasons=["Strong comfort score matches your comfort preference."],
        attribute_breakdown={},
        score_breakdown={},
    )
    raw_explanation = json.dumps(
        {
            "summary": "These results reflect the requested category and priorities.",
            "product_explanations": [
                {
                    "product_id": product.product_id,
                    "explanation": product_explanation,
                }
            ],
        }
    )
    return _validate_explanation(
        raw_explanation,
        [product],
        AssistantIntent(category="Headphones"),
    )


def _mock_groq_client(
    intent: AssistantIntent,
    *,
    explanation_mode: str = "valid",
    http_status: int | None = None,
    explanation_http_status: int | None = None,
    explanation_error_message: str = "Failed to validate JSON.",
    explanation_failed_generation: str | None = None,
) -> tuple[GroqClient, list[dict]]:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if http_status is not None:
            return httpx.Response(
                http_status,
                json={"error": {"message": "provider-private-detail"}},
            )
        messages = body["messages"]
        is_intent_request = "You extract shopping intent only." in messages[0]["content"]
        if explanation_http_status is not None and not is_intent_request:
            error = {
                "type": "invalid_request_error",
                "code": "json_validate_failed",
                "message": explanation_error_message,
            }
            if explanation_failed_generation is not None:
                error["failed_generation"] = explanation_failed_generation
            return httpx.Response(
                explanation_http_status,
                json={"error": error},
            )
        if is_intent_request:
            content = intent.model_dump_json()
        else:
            data = json.loads(messages[1]["content"])
            if explanation_mode == "timeout":
                raise httpx.ReadTimeout("simulated timeout", request=request)
            if explanation_mode == "programming_error":
                raise RuntimeError("simulated programming error")
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
                if explanation_mode == "missing_fields":
                    del response_data["summary"]
                elif explanation_mode == "incorrect_field_type":
                    response_data["summary"] = 123
                    response_data["api_key=gsk_TEST_SECRET"] = "Bearer test-sensitive-value"
                elif explanation_mode == "introduced_product":
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


def test_ungrounded_model_summary_is_rejected() -> None:
    product = _pulsebuds()
    raw = json.dumps(
        {
            "summary": "These headphones have exceptional noise cancellation.",
            "product_explanations": [
                {
                    "product_id": product.product_id,
                    "explanation": "Fits within your budget.",
                }
            ],
        }
    )

    with pytest.raises(ExplanationCheckError) as info:
        _validate_explanation(raw, [product], AssistantIntent(category="Headphones"))

    assert info.value.code == CHECK_UNSUPPORTED_PRODUCT_CLAIM


def test_explanation_accepts_exact_reason_wording() -> None:
    explanation = _validate_test_explanation(
        "Strong comfort score matches your comfort preference."
    )

    assert explanation.product_explanations[0].explanation == (
        "Strong comfort score matches your comfort preference."
    )


def test_explanation_accepts_safe_word_form_paraphrase() -> None:
    explanation = _validate_test_explanation("It is comfortable.")

    assert explanation.product_explanations[0].explanation == "It is comfortable."


@pytest.mark.parametrize(
    ("product_explanation", "expected_error"),
    [
        (
            "It is durable.",
            "Generated product explanation contains unsupported claims.",
        ),
        (
            "It has a touchscreen.",
            "Generated product explanation contains unsupported claims.",
        ),
        (
            "Acme Comfort Headphones are comfortable.",
            "Generated explanation repeats product identity details.",
        ),
        (
            "It has a battery life of 10 hours.",
            "Generated explanation contains unsupported numeric claims.",
        ),
    ],
)
def test_explanation_rejects_ungrounded_claims_and_preserves_strict_checks(
    product_explanation: str,
    expected_error: str,
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        _validate_test_explanation(product_explanation)


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


@pytest.mark.parametrize(
    ("explanation_mode", "expected_note", "private_details"),
    [
        (
            "invalid",
            "AI explanation failed response schema validation "
            "(error_count=1; loc=<root> type=json_invalid); "
            "deterministic explanation was used.",
            ("{malformed explanation",),
        ),
        (
            "missing_fields",
            "AI explanation failed response schema validation "
            "(error_count=1; loc=summary type=missing); "
            "deterministic explanation was used.",
            (),
        ),
        (
            "incorrect_field_type",
            "AI explanation failed response schema validation "
            "(error_count=2; loc=summary type=string_type; "
            "loc=[redacted] type=extra_forbidden); "
            "deterministic explanation was used.",
            ("gsk_TEST_SECRET", "test-sensitive-value"),
        ),
        (
            "introduced_product",
            "AI explanation failed content grounding validation "
            "(check=product_id_count_mismatch); deterministic explanation was used.",
            ("SS-FAKE-999", "An unranked item is also recommended."),
        ),
    ],
)
def test_explanation_validation_failures_have_safe_diagnostic_notes(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
    explanation_mode: str,
    expected_note: str,
    private_details: tuple[str, ...],
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
    assert expected_note in response.notes
    assert all(detail not in " ".join(response.notes) for detail in private_details)
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


@pytest.mark.parametrize(
    ("status_code", "status_description", "safe_message"),
    [
        (401, "unauthorized", "Groq authentication failed."),
        (403, "forbidden", "Groq denied access to the requested resource."),
        (404, "not found", "Groq could not find the requested resource."),
        (429, "rate limited", "Groq rate limit was reached."),
        (500, None, None),
    ],
)
def test_http_status_is_preserved_in_both_assistant_fallback_notes(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
    status_code: int,
    status_description: str | None,
    safe_message: str | None,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, calls = _mock_groq_client(
        AssistantIntent(category="Headphones"),
        http_status=status_code,
    )
    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Headphones."),
        groq_client=groq_client,
    )
    diagnostic = (
        f"Groq returned HTTP {status_code} ({status_description})"
        if status_description
        else f"Groq returned HTTP {status_code}"
    )
    if safe_message is not None:
        diagnostic += f": {safe_message}"

    assert response.fallback_used is True
    assert response.recommendations
    assert f"{diagnostic}; deterministic intent parsing was used." in response.notes
    assert f"{diagnostic}; a deterministic explanation was used." in response.notes
    assert "provider-private-detail" not in response.answer
    assert "provider-private-detail" not in " ".join(response.notes)
    assert len(calls) == 2


@pytest.mark.parametrize(
    ("provider_message", "safe_message", "sensitive_values"),
    [
        ("Failed to validate JSON.", "Failed to validate JSON.", ()),
        (
            "JSON validation failed; request prompt: Headphones under $500; "
            "api_key=gsk_exampleSecret123456789; "
            "request headers: Authorization: Bearer provider-token",
            "Groq rejected the request.",
            (
                "Headphones under $500",
                "gsk_exampleSecret123456789",
                "provider-token",
                "Authorization",
            ),
        ),
    ],
)
def test_explanation_http_failure_note_contains_only_safe_groq_details(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
    provider_message: str,
    safe_message: str,
    sensitive_values: tuple[str, ...],
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, calls = _mock_groq_client(
        AssistantIntent(category="Headphones"),
        explanation_http_status=400,
        explanation_error_message=provider_message,
        explanation_failed_generation='{"prompt":"DO_NOT_EXPOSE_PROMPT"}',
    )

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(user_id=user_id, message="Headphones."),
        groq_client=groq_client,
    )

    diagnostic = (
        "Groq returned HTTP 400 (type=invalid_request_error, "
        f"code=json_validate_failed): {safe_message}; "
        "a deterministic explanation was used."
    )
    assert response.fallback_used is True
    assert response.answer.startswith("Here are the highest-ranked matches")
    assert diagnostic in response.notes
    assert all(value not in " ".join(response.notes) for value in sensitive_values)
    assert "DO_NOT_EXPOSE_PROMPT" not in " ".join(response.notes)
    assert "failed_generation=" not in " ".join(response.notes)
    assert len(calls) == 2


def test_explanation_fallback_does_not_swallow_programming_errors(
    seeded_client,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    groq_client, _ = _mock_groq_client(
        AssistantIntent(category="Headphones"),
        explanation_mode="programming_error",
    )

    with pytest.raises(RuntimeError, match="simulated programming error"):
        generate_assistant_response(
            db_session,
            AssistantChatRequest(user_id=user_id, message="Headphones."),
            groq_client=groq_client,
        )


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


# ---------------------------------------------------------------------------
# Offline grounding regression tests. These call the validator directly with
# supplied recommendation reasons. They make no Groq or network calls.
# ---------------------------------------------------------------------------

PULSEBUDS_REASONS = [
    "Fits within your budget.",
    "High portability aligns with your portability preference.",
    "Matches your requested category 'Headphones'.",
]
BRAND_REASON = "Matches your preferred brand AudioNova."
SAFE_SUMMARY = "These results reflect your priorities."


def _pulsebuds(reasons: list[str] | None = None) -> RecommendedProduct:
    return RecommendedProduct(
        product_id="SS-HP-002",
        name="PulseBuds Compact",
        brand="AudioNova",
        category="Headphones",
        price=2499,
        rating=4.1,
        image_url=None,
        score=31.22,
        confidence=25,
        reasons=list(reasons if reasons is not None else PULSEBUDS_REASONS),
        attribute_breakdown={},
        score_breakdown={},
    )


def _validate_pulsebuds(
    explanation_text: str,
    *,
    summary: str = SAFE_SUMMARY,
    reasons: list[str] | None = None,
    intent: AssistantIntent | None = None,
):
    product = _pulsebuds(reasons)
    raw = json.dumps(
        {
            "summary": summary,
            "product_explanations": [
                {"product_id": product.product_id, "explanation": explanation_text}
            ],
        }
    )
    return _validate_explanation(
        raw,
        [product],
        intent or AssistantIntent(category="Headphones"),
    )


def _strip_final_period(text: str) -> str:
    return text.rstrip(".")


@pytest.mark.parametrize("reason", [*PULSEBUDS_REASONS, BRAND_REASON])
def test_each_individual_reason_is_accepted(reason: str) -> None:
    _validate_pulsebuds(reason, reasons=[*PULSEBUDS_REASONS, BRAND_REASON])


def test_all_reasons_separated_by_periods_are_accepted() -> None:
    text = " ".join(PULSEBUDS_REASONS)

    _validate_pulsebuds(text)


@pytest.mark.parametrize("separator", ["; ", "\n", "! ", "? ", ": "])
def test_reasons_separated_by_other_boundaries_are_accepted(separator: str) -> None:
    text = separator.join(_strip_final_period(reason) for reason in PULSEBUDS_REASONS)

    _validate_pulsebuds(text)


def test_reasons_separated_by_newlines_in_summary_are_accepted() -> None:
    summary = "\n".join(_strip_final_period(reason) for reason in PULSEBUDS_REASONS)

    _validate_pulsebuds("Fits within your budget.", summary=summary)


@pytest.mark.parametrize(
    ("reason", "summary"),
    [
        ("Fits within your budget.", "Fit within your budget."),
        (
            "High portability aligns with your portability preference.",
            "High portability align with your portability preference.",
        ),
        (
            "High portability aligns with your portability preference.",
            "High portability aligns with your portability preferences.",
        ),
        (
            "Matches your requested categories.",
            "Match your requested category.",
        ),
    ],
)
def test_summary_accepts_supported_word_form_variants(
    reason: str,
    summary: str,
) -> None:
    _validate_pulsebuds(reason, summary=summary, reasons=[reason])


@pytest.mark.parametrize(
    ("reason", "summary"),
    [
        ("Fits within your budget.", "Fit within your budget."),
        (
            "High portability aligns with your portability preference.",
            "High portability align with your portability preference.",
        ),
        (
            "High portability aligns with your portability preferences.",
            "High portability aligns with your portability preference.",
        ),
        (
            "Matches your requested categories.",
            "Match your requested category.",
        ),
    ],
)
def test_grounding_normalizes_only_explicit_word_forms(
    reason: str,
    summary: str,
) -> None:
    identity_sequences: list[list[str]] = []
    general_words = frozenset()

    assert _content_segments(
        reason,
        identity_sequences=identity_sequences,
        general_words=general_words,
    ) == _content_segments(
        summary,
        identity_sequences=identity_sequences,
        general_words=general_words,
    )


def test_summary_word_form_normalization_does_not_allow_unsupported_claims() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            "Fits within your budget.",
            summary="Fit within your budget. It is durable.",
            reasons=["Fits within your budget."],
        )

    assert info.value.code == CHECK_SUMMARY_NOT_GROUNDED


@pytest.mark.parametrize("separator", [". ", "; ", "\n"])
def test_invented_claim_between_valid_claims_is_rejected(separator: str) -> None:
    text = separator.join(
        [
            "Fits within your budget",
            "It is durable",
            "High portability aligns with your portability preference",
        ]
    )

    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(text)

    assert info.value.code == CHECK_PRODUCT_EXPLANATION_NOT_GROUNDED


def test_invented_claim_in_summary_between_valid_claims_is_rejected() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            "Fits within your budget",
            summary="Fits within your budget. It is durable. Matches your priorities.",
        )

    assert info.value.code == CHECK_SUMMARY_NOT_GROUNDED


def test_brand_named_in_a_supplied_reason_may_be_repeated() -> None:
    reasons = [BRAND_REASON, PULSEBUDS_REASONS[0]]

    _validate_pulsebuds(BRAND_REASON, reasons=reasons)
    _validate_pulsebuds("Preferred brand AudioNova. Fits within your budget.", reasons=reasons)


def test_brand_absent_from_all_supplied_reasons_is_rejected() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds("AudioNova fits within your budget.")

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_unsupplied_brand_in_summary_is_rejected() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            "Fits within your budget.",
            summary="These results come from AudioNova.",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_product_name_is_restricted_even_when_brand_is_allowed() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            "PulseBuds Compact fits within your budget.",
            reasons=[BRAND_REASON, *PULSEBUDS_REASONS],
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_product_name_is_restricted_even_when_it_appears_in_a_reason() -> None:
    reasons = ["PulseBuds Compact fits within your budget."]

    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds("PulseBuds Compact fits within your budget.", reasons=reasons)

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_partial_product_name_is_not_grounded_by_accident() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds("PulseBuds fits within your budget.")

    assert info.value.code == CHECK_PRODUCT_EXPLANATION_NOT_GROUNDED


@pytest.mark.parametrize(
    ("explanation_text", "expected_code"),
    [
        ("Fits within your budget. Rated 4.1.", CHECK_NUMERIC_CLAIM),
        ("Fits within your budget at 2499.", CHECK_NUMERIC_CLAIM),
        ("Fits within your budget and is wireless.", CHECK_UNSUPPORTED_PRODUCT_CLAIM),
        ("Fits within your budget. Options available.", CHECK_UNSUPPORTED_PRODUCT_CLAIM),
        ("It is durable.", CHECK_PRODUCT_EXPLANATION_NOT_GROUNDED),
        ("It has a touchscreen.", CHECK_PRODUCT_EXPLANATION_NOT_GROUNDED),
    ],
)
def test_existing_numeric_and_unsupported_feature_checks_still_apply(
    explanation_text: str,
    expected_code: str,
) -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(explanation_text)

    assert info.value.code == expected_code


def test_complete_unsupported_requirement_phrase_is_rejected_without_echoing_text() -> None:
    explanation_text = "Voice assistant integration is requested."
    intent = AssistantIntent(
        category="Headphones",
        unsupported_requirements=["voice assistant integration"],
    )

    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            explanation_text,
            reasons=[explanation_text],
            intent=intent,
        )

    assert info.value.code == CHECK_UNSUPPORTED_REQUIREMENT_MENTIONED
    assert str(info.value) == "Generated explanation mentions an unsupported requirement."
    assert explanation_text not in str(info.value)


def test_unrelated_individual_word_does_not_match_unsupported_phrase() -> None:
    explanation_text = "Noise levels match your preference."
    intent = AssistantIntent(
        category="Headphones",
        unsupported_requirements=["noise cancellation preference"],
    )

    _validate_pulsebuds(
        explanation_text,
        reasons=[explanation_text],
        intent=intent,
    )


@pytest.mark.parametrize(
    ("requirement", "generated_phrase"),
    [
        ("wireless connectivity", "wireless"),
        ("wireless", "wireless connectivity"),
        ("Bluetooth connectivity", "bluetooth"),
        ("Bluetooth", "Bluetooth connectivity"),
        ("noise cancellation preference", "noise-cancellation"),
        ("noise cancellation preference", "noise cancelling"),
        ("noise cancellation preference", "ANC"),
        ("noise cancelling preference", "noise cancellation"),
        ("sound quality requirement", "sound quality"),
        ("sound quality", "sound quality requirement"),
    ],
)
def test_existing_unsupported_requirement_aliases_are_matched(
    requirement: str,
    generated_phrase: str,
) -> None:
    assert _mentions_unsupported_requirement(
        f"Preference noted: {generated_phrase}.",
        [requirement],
    )


def test_existing_noise_cancellation_alias_is_rejected_by_validator() -> None:
    intent = AssistantIntent(
        category="Headphones",
        unsupported_requirements=["noise cancellation preference"],
    )

    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds("ANC", reasons=["ANC"], intent=intent)

    assert info.value.code == CHECK_UNSUPPORTED_REQUIREMENT_MENTIONED


@pytest.mark.parametrize(
    "explanation_text",
    [
        "Voice assistant integration is requested.",
        "Multipoint pairing is requested.",
    ],
)
def test_multiple_unsupported_requirements_are_checked_independently(
    explanation_text: str,
) -> None:
    intent = AssistantIntent(
        category="Headphones",
        unsupported_requirements=[
            "voice assistant integration",
            "multipoint pairing",
        ],
    )

    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            explanation_text,
            reasons=[explanation_text],
            intent=intent,
        )

    assert info.value.code == CHECK_UNSUPPORTED_REQUIREMENT_MENTIONED


@pytest.mark.parametrize(
    "explanation_text",
    [
        "That fits within your budget.",
        "Some options are within your budget.",
        "That is within your budget, and you can have it.",
    ],
)
def test_neutral_function_words_are_accepted(explanation_text: str) -> None:
    _validate_pulsebuds(explanation_text)


@pytest.mark.parametrize(
    "word",
    ["good", "great", "excellent", "durable", "premium", "powerful"],
)
def test_evaluative_words_remain_ungrounded(word: str) -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(f"This is a {word} option within your budget.")

    assert info.value.code == CHECK_PRODUCT_EXPLANATION_NOT_GROUNDED


def test_whitelist_does_not_include_evaluative_or_product_claim_words() -> None:
    forbidden = {"good", "great", "excellent", "durable", "premium", "powerful", "value", "wireless"}

    assert forbidden.isdisjoint(_GENERAL_EXPLANATION_WORDS)


def _validate_product_ids(
    products: list[RecommendedProduct],
    product_ids: list[str],
):
    raw = json.dumps(
        {
            "summary": SAFE_SUMMARY,
            "product_explanations": [
                {"product_id": product_id, "explanation": "Fits within your budget."}
                for product_id in product_ids
            ],
        }
    )
    return _validate_explanation(raw, products, AssistantIntent(category="Headphones"))


def test_empty_product_explanations_has_count_mismatch() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_product_ids([_pulsebuds()], [])

    assert info.value.code == CHECK_PRODUCT_ID_COUNT_MISMATCH
    assert str(info.value) == "Explanation count does not match the ranked recommendations."


def test_wrong_product_id_is_unknown() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_product_ids([_pulsebuds()], ["SS-FAKE-999"])

    assert info.value.code == CHECK_PRODUCT_ID_UNKNOWN
    assert str(info.value) == "Explanation contains an unknown product ID."
    assert "SS-FAKE-999" not in str(info.value)


@pytest.mark.parametrize("product_id_variant", [" SS-HP-002 ", "ss-hp-002"])
def test_product_id_comparison_does_not_trim_or_casefold(
    product_id_variant: str,
) -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_product_ids([_pulsebuds()], [product_id_variant])

    assert info.value.code == CHECK_PRODUCT_ID_UNKNOWN


def test_duplicate_entry_has_count_mismatch_when_count_differs() -> None:
    product = _pulsebuds()
    with pytest.raises(ExplanationCheckError) as info:
        _validate_product_ids([product], [product.product_id, product.product_id])

    assert info.value.code == CHECK_PRODUCT_ID_COUNT_MISMATCH


def test_duplicate_entry_with_matching_count_has_order_mismatch() -> None:
    products = _two_products()
    with pytest.raises(ExplanationCheckError) as info:
        _validate_product_ids(
            products,
            [products[0].product_id, products[0].product_id],
        )

    assert info.value.code == CHECK_PRODUCT_ID_ORDER_MISMATCH


def test_two_product_entries_in_reverse_order_have_order_mismatch() -> None:
    products = _two_products()
    with pytest.raises(ExplanationCheckError) as info:
        _validate_product_ids(
            products,
            [products[1].product_id, products[0].product_id],
        )

    assert info.value.code == CHECK_PRODUCT_ID_ORDER_MISMATCH


def test_missing_expected_product_precedes_unknown_id() -> None:
    products = _two_products()
    # A known ID is present, so the absent expected ID takes precedence over
    # the unknown ID filling the second slot.
    with pytest.raises(ExplanationCheckError) as info:
        _validate_product_ids(products, [products[0].product_id, "SS-FAKE-999"])

    assert info.value.code == CHECK_PRODUCT_ID_MISSING
    assert str(info.value) == "A ranked recommendation is missing an explanation."
    assert "SS-FAKE-999" not in str(info.value)


@pytest.mark.parametrize(
    "code",
    [
        CHECK_PRODUCT_ID_COUNT_MISMATCH,
        CHECK_PRODUCT_ID_MISSING,
        CHECK_PRODUCT_ID_UNKNOWN,
        CHECK_PRODUCT_ID_ORDER_MISMATCH,
    ],
)
def test_product_id_codes_are_allowlisted_and_notes_are_safe(code: str) -> None:
    note = _grounding_failure_note(code)

    assert code in _GROUNDING_CHECK_CODES
    assert note == (
        f"AI explanation failed content grounding validation "
        f"(check={code}); deterministic explanation was used."
    )
    assert all(
        private_value not in note
        for private_value in (
            "SS-HP-002",
            "SS-HP-003",
            "SS-FAKE-999",
            "private model text",
        )
    )


def test_exact_valid_product_id_passes() -> None:
    product = _pulsebuds()

    explanation = _validate_product_ids([product], [product.product_id])

    assert explanation.product_explanations[0].product_id == product.product_id


def test_grounding_note_contains_only_the_allowlisted_code() -> None:
    note = _grounding_failure_note(CHECK_NUMERIC_CLAIM)

    assert note == (
        "AI explanation failed content grounding validation "
        "(check=numeric_claim); deterministic explanation was used."
    )


def test_unknown_grounding_code_becomes_generic_note() -> None:
    note = _grounding_failure_note("Fits within your budget. It is durable.")

    assert note == (
        "AI explanation failed content grounding validation "
        "(check=unclassified); deterministic explanation was used."
    )
    assert "durable" not in note


def test_grounding_error_does_not_expose_generated_text() -> None:
    generated = "It is durable and has a touchscreen."

    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(f"Fits within your budget. {generated}")

    assert "durable" not in str(info.value)
    assert "touchscreen" not in str(info.value)
    assert info.value.code == CHECK_PRODUCT_EXPLANATION_NOT_GROUNDED


# ---------------------------------------------------------------------------
# Product-specific brand allowance. A brand may be mentioned only in the
# explanation of a product whose own reasons contain that brand.
# ---------------------------------------------------------------------------


def _two_products() -> list[RecommendedProduct]:
    product_a = RecommendedProduct(
        product_id="SS-HP-002",
        name="PulseBuds Compact",
        brand="AudioNova",
        category="Headphones",
        price=2499,
        rating=4.1,
        image_url=None,
        score=31.22,
        confidence=25,
        reasons=["Fits within your budget.", "Matches your preferred brand AudioNova."],
        attribute_breakdown={},
        score_breakdown={},
    )
    product_b = RecommendedProduct(
        product_id="SS-HP-003",
        name="Bass Surge",
        brand="SoundMax",
        category="Headphones",
        price=2199,
        rating=4.0,
        image_url=None,
        score=28.10,
        confidence=25,
        reasons=["Fits within your budget.", "Matches your preferred brand SoundMax."],
        attribute_breakdown={},
        score_breakdown={},
    )
    return [product_a, product_b]


def _validate_two_products(
    explanation_a: str,
    explanation_b: str,
    *,
    summary: str = SAFE_SUMMARY,
):
    products = _two_products()
    raw = json.dumps(
        {
            "summary": summary,
            "product_explanations": [
                {"product_id": products[0].product_id, "explanation": explanation_a},
                {"product_id": products[1].product_id, "explanation": explanation_b},
            ],
        }
    )
    return _validate_explanation(raw, products, AssistantIntent(category="Headphones"))


def test_each_product_may_mention_its_own_reason_brand() -> None:
    _validate_two_products(
        "Matches your preferred brand AudioNova.",
        "Matches your preferred brand SoundMax.",
    )


def test_product_b_is_rejected_when_it_mentions_product_a_brand() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_two_products(
            "Matches your preferred brand AudioNova.",
            "Preferred brand AudioNova. Fits within your budget.",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_brand_in_another_products_reasons_does_not_authorize_it() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_two_products(
            "Fits within your budget.",
            "Matches your preferred brand AudioNova.",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_product_names_remain_restricted_across_products() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_two_products(
            "Matches your preferred brand AudioNova.",
            "Bass Surge fits within your budget.",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_summary_may_not_name_any_brand() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_two_products(
            "Fits within your budget.",
            "Fits within your budget.",
            summary="Preferred brand AudioNova fits within your budget.",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_summary_rejects_brand_even_when_every_product_reason_mentions_it() -> None:
    shared_reason = "Matches your preferred brand AudioNova."
    products = _two_products()
    products[1].reasons.append(shared_reason)
    products[0].reasons.append(shared_reason)
    raw = json.dumps(
        {
            "summary": "Preferred brand AudioNova. Fits within your budget.",
            "product_explanations": [
                {"product_id": products[0].product_id, "explanation": "Fits within your budget."},
                {"product_id": products[1].product_id, "explanation": "Fits within your budget."},
            ],
        }
    )

    with pytest.raises(ExplanationCheckError) as info:
        _validate_explanation(raw, products, AssistantIntent(category="Headphones"))

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_product_may_name_only_its_own_brand_not_another_products_brand() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_two_products(
            "Matches your preferred brand SoundMax.",
            "Matches your preferred brand SoundMax.",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_own_brand_absent_from_own_reasons_is_rejected_even_if_other_reasons_have_it() -> None:
    products = _two_products()
    products[1].reasons = ["Fits within your budget.", "Matches your preferred brand AudioNova."]
    raw = json.dumps(
        {
            "summary": SAFE_SUMMARY,
            "product_explanations": [
                {"product_id": products[0].product_id, "explanation": "Fits within your budget."},
                {"product_id": products[1].product_id, "explanation": "AudioNova fits within your budget."},
            ],
        }
    )

    with pytest.raises(ExplanationCheckError) as info:
        _validate_explanation(raw, products, AssistantIntent(category="Headphones"))

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_product_name_split_between_summary_and_explanation_is_caught() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            "Compact fits within your budget.",
            summary="These results reflect PulseBuds.",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_product_name_split_across_two_product_explanations_is_caught() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_two_products(
            "Fits within your budget and PulseBuds.",
            "Compact matches your preferred brand SoundMax.",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_product_name_split_by_punctuation_is_caught() -> None:
    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            "Compact fits within your budget.",
            summary="These results reflect PulseBuds;",
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED


def test_product_name_in_a_supplied_reason_is_still_prohibited_in_combined_text() -> None:
    reasons = ["PulseBuds Compact fits within your budget."]

    with pytest.raises(ExplanationCheckError) as info:
        _validate_pulsebuds(
            "Fits within your budget.",
            summary="Fits within your budget. PulseBuds Compact.",
            reasons=reasons,
        )

    assert info.value.code == CHECK_PRODUCT_IDENTITY_REPEATED
