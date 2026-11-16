"""Shopping history API tests."""

from fastapi.testclient import TestClient


def _setup_user(client: TestClient, payload: dict) -> int:
    return client.post("/api/profiles", json=payload).json()["id"]


def test_record_and_list_actions(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _setup_user(seeded_client, sample_profile_payload)
    actions = ["viewed", "liked", "purchased", "dismissed", "not_interested"]
    for action in actions:
        response = seeded_client.post(
            "/api/history",
            json={"user_id": user_id, "product_id": "SS-HP-001", "action": action},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["action"] == action
        assert body["product_id"] == "SS-HP-001"
        assert body["product_name"]

    history = seeded_client.get(f"/api/history/{user_id}")
    assert history.status_code == 200
    assert len(history.json()) == 5


def test_filter_history_by_action(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _setup_user(seeded_client, sample_profile_payload)
    seeded_client.post(
        "/api/history",
        json={"user_id": user_id, "product_id": "SS-HP-001", "action": "viewed"},
    )
    seeded_client.post(
        "/api/history",
        json={"user_id": user_id, "product_id": "SS-HP-002", "action": "liked"},
    )
    liked = seeded_client.get(f"/api/history/{user_id}", params={"action": "liked"})
    assert liked.status_code == 200
    assert len(liked.json()) == 1
    assert liked.json()[0]["action"] == "liked"


def test_reject_unsupported_action(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _setup_user(seeded_client, sample_profile_payload)
    response = seeded_client.post(
        "/api/history",
        json={"user_id": user_id, "product_id": "SS-HP-001", "action": "wishlisted"},
    )
    assert response.status_code == 422


def test_history_requires_existing_user(seeded_client: TestClient) -> None:
    response = seeded_client.post(
        "/api/history",
        json={"user_id": 9999, "product_id": "SS-HP-001", "action": "viewed"},
    )
    assert response.status_code == 404


def test_history_requires_existing_product(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _setup_user(seeded_client, sample_profile_payload)
    response = seeded_client.post(
        "/api/history",
        json={"user_id": user_id, "product_id": "MISSING", "action": "viewed"},
    )
    assert response.status_code == 404
