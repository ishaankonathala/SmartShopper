"""Recommendation engine tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _create_user(client: TestClient, payload: dict) -> int:
    response = client.post("/api/profiles", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_recommendations_use_dna_and_explicit_brand_preferences(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    seeded_client.put(
        f"/api/profiles/{user_id}/dna",
        json={
            "inferred_preferences": {
                "comfort_priority": 80,
                "brand_loyalty": 70,
                "price_sensitivity": 60,
                "quality_preference": 75,
                "portability_preference": 80,
                "battery_life_priority": 70,
            },
            "confidence_scores": {
                "comfort_priority": 60,
                "brand_loyalty": 50,
                "price_sensitivity": 50,
                "quality_preference": 60,
                "portability_preference": 70,
                "battery_life_priority": 50,
            },
            "preference_sources": {
                "comfort_priority": "manual",
                "brand_loyalty": "manual",
                "price_sensitivity": "manual",
                "quality_preference": "manual",
                "portability_preference": "manual",
                "battery_life_priority": "manual",
            },
        },
    )

    response = seeded_client.post(
        "/api/recommendations",
        json={
            "user_id": user_id,
            "category": "Headphones",
            "limit": 5,
            "require_available": True,
            "include_explanations": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == user_id
    assert body["requested_limit"] == 5
    assert body["products"]
    assert all("reasons" in product for product in body["products"])
    assert all(0 <= product["score"] <= 100 for product in body["products"])
    assert all(0 <= product["confidence"] <= 100 for product in body["products"])
    codes = {item["product_id"]: item["reason_code"] for item in body["excluded_products"]}
    assert codes.get("SS-HP-003") == "out_of_stock"
    assert codes.get("SS-HP-004") == "inactive_product"


def test_recommendations_hard_filter_budget_and_availability(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    response = seeded_client.post(
        "/api/recommendations",
        json={
            "user_id": user_id,
            "limit": 10,
            "require_available": True,
            "max_budget_override": 2500,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert all(product["price"] <= 2500 for product in body["products"])
    assert any(item["reason_code"] == "budget_exceeded" for item in body["excluded_products"])


def test_recommendations_exclude_inactive_and_disliked_attributes(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    seeded_client.put(
        f"/api/profiles/{user_id}",
        json={"disliked_attributes": ["noise_cancellation", "bulky"]},
    )

    response = seeded_client.post(
        "/api/recommendations",
        json={
            "user_id": user_id,
            "limit": 10,
            "require_available": True,
            "include_explanations": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["excluded_products"]
    assert any(item["reason_code"] in {"disliked_attribute", "inactive_product"} for item in body["excluded_products"]) 


def test_recommendations_can_hide_explanations(client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(client, sample_profile_payload)
    response = client.post(
        "/api/recommendations",
        json={"user_id": user_id, "limit": 3, "include_explanations": False},
    )
    assert response.status_code == 200
    for product in response.json()["products"]:
        assert product["reasons"] == []


def test_inactive_product_exclusion(seeded_client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "limit": 10, "require_available": True},
    )
    assert response.status_code == 200
    codes = {item["product_id"]: item["reason_code"] for item in response.json()["excluded_products"]}
    assert codes.get("SS-HP-004") == "inactive_product"


def test_out_of_stock_exclusion_when_required(seeded_client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "limit": 10, "require_available": True},
    )
    assert response.status_code == 200
    codes = {item["product_id"]: item["reason_code"] for item in response.json()["excluded_products"]}
    assert codes.get("SS-HP-003") == "out_of_stock"


def test_out_of_stock_inclusion_when_not_required(seeded_client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    response = seeded_client.post(
        "/api/recommendations",
        json={
            "user_id": user_id,
            "category": "Headphones",
            "limit": 10,
            "require_available": False,
            "max_budget_override": 100000,
        },
    )
    assert response.status_code == 200
    product_ids = {product["product_id"] for product in response.json()["products"]}
    assert "SS-HP-003" in product_ids


def test_category_mismatch_exclusion(seeded_client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "category": "Laptops", "limit": 10, "require_available": True},
    )
    assert response.status_code == 200
    reason_map = {item["product_id"]: item["reason_code"] for item in response.json()["excluded_products"]}
    assert any(code == "category_mismatch" for code in reason_map.values())
    assert "evaluating 14 candidate product(s)" in response.json()["explanation_summary"]


def test_no_preferred_brands_is_not_penalized(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    profile = seeded_client.get(f"/api/profiles/{user_id}")
    assert profile.status_code == 200
    seeded_client.put(f"/api/profiles/{user_id}", json={"preferred_brands": []})
    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "limit": 5, "require_available": True},
    )
    assert response.status_code == 200
    products = response.json()["products"]
    assert products
    assert all("brand_loyalty" not in product["attribute_breakdown"] for product in products)
    assert all("brand_loyalty" not in product["score_breakdown"] for product in products)


def test_low_confidence_dna_stays_near_neutral(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    seeded_client.put(
        f"/api/profiles/{user_id}/dna",
        json={
            "inferred_preferences": {"comfort_priority": 85, "brand_loyalty": 80},
            "confidence_scores": {"comfort_priority": 0, "brand_loyalty": 0},
            "preference_sources": {"comfort_priority": "manual", "brand_loyalty": "manual"},
        },
    )
    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "category": "Headphones", "limit": 5, "require_available": True},
    )
    assert response.status_code == 200
    assert all(product["score"] <= 60 for product in response.json()["products"])


def test_missing_or_malformed_attributes_do_not_crash(
    seeded_client: TestClient, sample_profile_payload: dict, db_session: Session
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    from app.models.product import Product

    product_row = db_session.query(Product).filter(Product.product_id == "SS-HP-001").first()
    product_row.attributes = {"comfort_score": "bad-value", "portability": "bad", "build_quality": "oops"}
    db_session.commit()

    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "category": "Headphones", "limit": 5, "require_available": True},
    )
    assert response.status_code == 200
    assert response.json()["products"]


def test_non_dictionary_attributes_do_not_crash_recommendations(
    seeded_client: TestClient, sample_profile_payload: dict, db_session: Session
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    from app.models.product import Product

    product_row = db_session.query(Product).filter(Product.product_id == "SS-HP-001").first()
    product_row.attributes = "malformed attributes"
    db_session.commit()

    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "category": "Headphones", "limit": 5, "require_available": True},
    )
    assert response.status_code == 200
    assert response.json()["products"]


def test_identical_requests_produce_identical_ordering(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    payload = {"user_id": user_id, "category": "Headphones", "limit": 5, "require_available": True}
    first = seeded_client.post("/api/recommendations", json=payload)
    second = seeded_client.post("/api/recommendations", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["products"] == second.json()["products"]


def test_budget_override_does_not_change_saved_profile(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    before = seeded_client.get(f"/api/profiles/{user_id}").json()
    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "limit": 5, "require_available": True, "max_budget_override": 1000},
    )
    assert response.status_code == 200
    after = seeded_client.get(f"/api/profiles/{user_id}").json()
    assert before["max_budget"] == after["max_budget"]


def test_recommendation_generation_does_not_mutate_saved_dna(
    seeded_client: TestClient, sample_profile_payload: dict
) -> None:
    user_id = _create_user(seeded_client, sample_profile_payload)
    before = seeded_client.get(f"/api/profiles/{user_id}/dna").json()
    response = seeded_client.post(
        "/api/recommendations",
        json={"user_id": user_id, "limit": 5, "require_available": True},
    )
    assert response.status_code == 200
    after = seeded_client.get(f"/api/profiles/{user_id}/dna").json()
    assert before == after


def test_invalid_limit_is_rejected(client: TestClient, sample_profile_payload: dict) -> None:
    user_id = _create_user(client, sample_profile_payload)
    response = client.post(
        "/api/recommendations",
        json={"user_id": user_id, "limit": 0},
    )
    assert response.status_code == 422


def test_recommendations_require_existing_profile(client: TestClient) -> None:
    response = client.post(
        "/api/recommendations",
        json={"user_id": 9999, "limit": 5},
    )
    assert response.status_code == 404
