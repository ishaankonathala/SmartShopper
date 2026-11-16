"""User profile API tests."""

from fastapi.testclient import TestClient


def test_create_and_get_profile(client: TestClient, sample_profile_payload: dict) -> None:
    create = client.post("/api/profiles", json=sample_profile_payload)
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "Ishaan"
    assert body["max_budget"] == 6500
    assert body["preferred_brands"] == ["SonyDemo"]
    user_id = body["id"]

    fetched = client.get(f"/api/profiles/{user_id}")
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "ishaan@example.com"


def test_update_profile(client: TestClient, sample_profile_payload: dict) -> None:
    user_id = client.post("/api/profiles", json=sample_profile_payload).json()["id"]
    updated = client.put(
        f"/api/profiles/{user_id}",
        json={"max_budget": 8000, "preferred_brands": ["SonyDemo", "BoseDemo"]},
    )
    assert updated.status_code == 200
    assert updated.json()["max_budget"] == 8000
    assert updated.json()["preferred_brands"] == ["SonyDemo", "BoseDemo"]
    # Explicit name unchanged
    assert updated.json()["name"] == "Ishaan"


def test_reject_negative_budget(client: TestClient, sample_profile_payload: dict) -> None:
    payload = {**sample_profile_payload, "max_budget": -10}
    response = client.post("/api/profiles", json=payload)
    assert response.status_code == 422


def test_reject_min_greater_than_max(client: TestClient, sample_profile_payload: dict) -> None:
    payload = {**sample_profile_payload, "min_budget": 9000, "max_budget": 5000}
    response = client.post("/api/profiles", json=payload)
    assert response.status_code == 422


def test_reject_empty_name(client: TestClient, sample_profile_payload: dict) -> None:
    payload = {**sample_profile_payload, "name": "   "}
    response = client.post("/api/profiles", json=payload)
    assert response.status_code == 422


def test_reject_invalid_email(client: TestClient, sample_profile_payload: dict) -> None:
    payload = {**sample_profile_payload, "email": "not-an-email"}
    response = client.post("/api/profiles", json=payload)
    assert response.status_code == 422


def test_profile_not_found(client: TestClient) -> None:
    response = client.get("/api/profiles/9999")
    assert response.status_code == 404


def test_update_budget_consistency(client: TestClient, sample_profile_payload: dict) -> None:
    user_id = client.post("/api/profiles", json=sample_profile_payload).json()["id"]
    response = client.put(f"/api/profiles/{user_id}", json={"min_budget": 9000})
    assert response.status_code == 422


def test_duplicate_email_conflict(client: TestClient, sample_profile_payload: dict) -> None:
    assert client.post("/api/profiles", json=sample_profile_payload).status_code == 201
    again = client.post("/api/profiles", json=sample_profile_payload)
    assert again.status_code == 409
