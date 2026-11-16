"""Shopper DNA API tests."""

from fastapi.testclient import TestClient


def _create_user(client: TestClient, payload: dict) -> int:
    return client.post("/api/profiles", json=payload).json()["id"]


def test_get_default_dna(client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(client, sample_profile_payload)
    response = client.get(f"/api/profiles/{user_id}/dna")
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == user_id
    assert body["inferred_preferences"]["comfort_priority"] == 50
    assert body["confidence_scores"]["comfort_priority"] == 0
    assert body["preference_sources"]["comfort_priority"] == "default"


def test_update_dna_preferences(client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(client, sample_profile_payload)
    response = client.put(
        f"/api/profiles/{user_id}/dna",
        json={
            "inferred_preferences": {"comfort_priority": 85, "brand_loyalty": 40},
            "confidence_scores": {"comfort_priority": 20, "brand_loyalty": 10},
            "preference_sources": {
                "comfort_priority": "manual",
                "brand_loyalty": "manual",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["inferred_preferences"]["comfort_priority"] == 85
    assert body["inferred_preferences"]["price_sensitivity"] == 50  # untouched default
    assert body["confidence_scores"]["comfort_priority"] == 20


def test_dna_rejects_out_of_range(client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(client, sample_profile_payload)
    response = client.put(
        f"/api/profiles/{user_id}/dna",
        json={"inferred_preferences": {"comfort_priority": 150}},
    )
    assert response.status_code == 422


def test_dna_rejects_unknown_dimension(client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(client, sample_profile_payload)
    response = client.put(
        f"/api/profiles/{user_id}/dna",
        json={"inferred_preferences": {"magic_score": 10}},
    )
    assert response.status_code == 422


def test_dna_update_does_not_overwrite_explicit_profile(
    client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(client, sample_profile_payload)
    client.put(
        f"/api/profiles/{user_id}/dna",
        json={"inferred_preferences": {"brand_loyalty": 99}},
    )
    profile = client.get(f"/api/profiles/{user_id}").json()
    assert profile["preferred_brands"] == ["SonyDemo"]
    assert profile["max_budget"] == 6500


def test_dna_missing_user(client: TestClient) -> None:
    assert client.get("/api/profiles/404/dna").status_code == 404
