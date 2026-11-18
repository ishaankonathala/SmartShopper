"""AI shopping assistant API tests using mocked Groq HTTP transport."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.assistant as assistant_api
import app.services.assistant_response as assistant_response_service
from app.core.config import Settings
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse, AssistantIntent
from app.services.assistant_response import DEMO_CATALOGUE_DISCLAIMER
from app.services.groq_client import GroqClient


def _create_user(client: TestClient, payload: dict) -> int:
    response = client.post("/api/profiles", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _install_mock_groq(
    monkeypatch: pytest.MonkeyPatch,
    *,
    invalid_response: bool = False,
) -> list[dict]:
    calls: list[dict] = []
    intent = {
        "category": "Headphones",
        "max_budget_override": 6000,
        "comfort_priority": 85,
        "unsupported_requirements": ["wireless connectivity"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        messages = body["messages"]
        if invalid_response:
            content = "{invalid JSON"
        elif "You extract shopping intent only." in messages[0]["content"]:
            content = json.dumps(intent)
        else:
            request_data = json.loads(messages[1]["content"])
            content = json.dumps(
                {
                    "summary": "These results reflect the requested category and priorities.",
                    "product_explanations": [
                        {
                            "product_id": product["product_id"],
                            "explanation": (
                                "Its listed reasons align with the stated preferences "
                                "and requested category."
                            ),
                        }
                        for product in request_data["recommendations"]
                    ],
                }
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    client = GroqClient(
        settings=Settings(
            _env_file=None,
            groq_api_key="test-only-key",
            groq_model="test-model",
        ),
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(assistant_response_service, "GroqClient", lambda: client)
    return calls


def test_assistant_chat_returns_structured_grounded_response(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    calls = _install_mock_groq(monkeypatch)

    response = seeded_client.post(
        "/api/assistant/chat",
        json={
            "user_id": user_id,
            "message": "Wireless comfortable headphones under ₹6,000.",
            "limit": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == user_id
    assert body["answer"].startswith("These results reflect")
    assert DEMO_CATALOGUE_DISCLAIMER in body["answer"]
    assert body["intent"] == {
        "category": "Headphones",
        "max_budget_override": 6000,
        "comfort_priority": 85,
        "brand_loyalty": None,
        "battery_life_priority": None,
        "unsupported_requirements": ["wireless connectivity"],
    }
    assert body["recommendations"]
    assert len(body["recommendations"]) <= 2
    assert all(
        {
            "product_id",
            "name",
            "brand",
            "price",
            "rating",
            "score",
            "reasons",
        }
        <= product.keys()
        for product in body["recommendations"]
    )
    assert body["fallback_used"] is False
    assert any("Unverified request details" in note for note in body["notes"])
    assert len(calls) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_id": 1},
        {"message": "Headphones"},
        {"user_id": 0, "message": "Headphones"},
        {"user_id": 1, "message": "   "},
        {"user_id": 1, "message": "Headphones", "limit": 26},
    ],
)
def test_assistant_chat_rejects_missing_or_invalid_request_fields(
    client: TestClient,
    payload: dict,
) -> None:
    response = client.post("/api/assistant/chat", json=payload)

    assert response.status_code == 422


def test_assistant_chat_returns_not_found_for_nonexistent_user(
    seeded_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_mock_groq(monkeypatch)

    response = seeded_client.post(
        "/api/assistant/chat",
        json={"user_id": 9999, "message": "Headphones."},
    )

    assert response.status_code == 404
    assert len(calls) == 0


def test_assistant_chat_uses_deterministic_fallback_for_invalid_groq_response(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    calls = _install_mock_groq(monkeypatch, invalid_response=True)

    response = seeded_client.post(
        "/api/assistant/chat",
        json={"user_id": user_id, "message": "Headphones under ₹6,000."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is True
    assert body["recommendations"]
    assert "highest-ranked matches" in body["answer"]
    assert DEMO_CATALOGUE_DISCLAIMER in body["answer"]
    assert any("deterministic explanation" in note for note in body["notes"])
    assert len(calls) == 2


def test_assistant_chat_delegates_to_existing_response_service(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Session, AssistantChatRequest]] = []
    expected = AssistantChatResponse(
        user_id=42,
        answer="Service-generated response.",
        intent=AssistantIntent(category="Headphones"),
        recommendations=[],
        fallback_used=True,
        notes=["service note"],
    )

    def service_spy(
        db: Session,
        payload: AssistantChatRequest,
    ) -> AssistantChatResponse:
        calls.append((db, payload))
        return expected

    monkeypatch.setattr(assistant_api, "generate_assistant_response", service_spy)
    response = client.post(
        "/api/assistant/chat",
        json={"user_id": 42, "message": "Headphones."},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == expected.answer
    assert response.json()["notes"] == expected.notes
    assert len(calls) == 1
    assert isinstance(calls[0][0], Session)
    assert calls[0][1] == AssistantChatRequest(user_id=42, message="Headphones.")
