"""Recommendation engine tests."""

import pytest
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
    products = response.json()["products"]
    assert all(product["score"] <= 60 for product in products)
    assert all(product["confidence"] == 0 for product in products)


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


def test_battery_preference_override_is_full_confidence_and_temporary(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    from app.schemas.recommendation import RecommendationRequest
    from app.services.recommendation import DIMENSION_WEIGHTS, generate_recommendations

    user_id = _create_user(seeded_client, sample_profile_payload)
    profile_before = seeded_client.get(f"/api/profiles/{user_id}").json()
    dna_before = seeded_client.get(f"/api/profiles/{user_id}/dna").json()
    request = RecommendationRequest(user_id=user_id, category="Headphones", limit=10)

    baseline = generate_recommendations(db_session, request)
    simulated = generate_recommendations(
        db_session,
        request,
        preference_overrides={"battery_life_priority": 100},
    )
    baseline_product = next(item for item in baseline.products if item.product_id == "SS-HP-001")
    simulated_product = next(item for item in simulated.products if item.product_id == "SS-HP-001")
    battery_feature = simulated_product.attribute_breakdown["battery_life_priority"]

    assert simulated_product.score_breakdown["battery_life_priority"] == pytest.approx(
        round(battery_feature * DIMENSION_WEIGHTS["battery_life_priority"], 2)
    )
    assert simulated_product.score_breakdown["battery_life_priority"] > (
        baseline_product.score_breakdown["battery_life_priority"]
    )
    assert simulated_product.confidence > baseline_product.confidence
    active_weight = sum(
        DIMENSION_WEIGHTS[dimension]
        for dimension in simulated_product.score_breakdown
    )
    expected_profile_confidence = round(
        100
        * DIMENSION_WEIGHTS["battery_life_priority"]
        / active_weight,
        2,
    )
    assert simulated_product.confidence == expected_profile_confidence
    assert seeded_client.get(f"/api/profiles/{user_id}").json() == profile_before
    assert seeded_client.get(f"/api/profiles/{user_id}/dna").json() == dna_before


def _catalogue_snapshot(db_session: Session):
    from app.models.product import Product

    return [
        Product(
            product_id=row.product_id,
            name=row.name,
            brand=row.brand,
            category=row.category,
            price=row.price,
            rating=row.rating,
            description=row.description,
            attributes=dict(row.attributes) if isinstance(row.attributes, dict) else row.attributes,
            stock_quantity=row.stock_quantity,
            is_active=row.is_active,
            image_url=row.image_url,
        )
        for row in db_session.query(Product).all()
    ]


@pytest.mark.parametrize(
    ("connectivity", "expected_connectivity"),
    [("wireless", "wireless"), ("wired", "wired")],
)
def test_connectivity_requirement_returns_only_explicitly_compatible_products(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    db_session: Session,
    connectivity: str,
    expected_connectivity: str,
) -> None:
    from app.schemas.recommendation import RecommendationRequest
    from app.services.recommendation import generate_recommendations

    user_id = _create_user(seeded_client, sample_profile_payload)
    response = generate_recommendations(
        db_session,
        RecommendationRequest(
            user_id=user_id,
            category="Headphones",
            limit=10,
            max_budget_override=10000,
        ),
        required_connectivity=connectivity,
    )

    assert response.products
    assert all(
        product.attributes["connectivity"] == expected_connectivity
        for product in _catalogue_snapshot(db_session)
        if product.product_id in {item.product_id for item in response.products}
    )
    assert all(
        product.product_id != "SS-HP-002" or expected_connectivity == "wireless"
        for product in response.products
    )


def test_unknown_connectivity_is_excluded_from_explicit_connectivity_request(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    from app.schemas.recommendation import RecommendationRequest
    from app.services.recommendation import generate_recommendations

    user_id = _create_user(seeded_client, sample_profile_payload)
    snapshot = _catalogue_snapshot(db_session)
    pulsebuds = next(product for product in snapshot if product.product_id == "SS-HP-002")
    pulsebuds.attributes.pop("connectivity")

    response = generate_recommendations(
        db_session,
        RecommendationRequest(
            user_id=user_id,
            category="Headphones",
            limit=10,
            max_budget_override=10000,
        ),
        required_connectivity="wireless",
        product_snapshot=snapshot,
    )

    assert all(product.product_id != "SS-HP-002" for product in response.products)
    excluded = {item.product_id: item.reason_code for item in response.excluded_products}
    assert excluded["SS-HP-002"] == "connectivity_unknown"


def test_headphone_battery_score_uses_only_headphone_category_data(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    from app.schemas.recommendation import RecommendationRequest
    from app.services.recommendation import DIMENSION_WEIGHTS, generate_recommendations

    user_id = _create_user(seeded_client, sample_profile_payload)
    request = RecommendationRequest(
        user_id=user_id,
        category="Headphones",
        limit=10,
        max_budget_override=10000,
    )
    snapshot = _catalogue_snapshot(db_session)
    baseline = generate_recommendations(
        db_session,
        request,
        preference_overrides={"battery_life_priority": 80},
        product_snapshot=snapshot,
    )
    watch = next(product for product in snapshot if product.category == "Smartwatches")
    watch.attributes["battery_life_hours"] = 10000
    changed = generate_recommendations(
        db_session,
        request,
        preference_overrides={"battery_life_priority": 80},
        product_snapshot=snapshot,
    )

    before_product = next(item for item in baseline.products if item.product_id == "SS-HP-002")
    after_product = next(item for item in changed.products if item.product_id == "SS-HP-002")
    assert before_product.attribute_breakdown["battery_life_priority"] == pytest.approx(
        round(18 / 35 * 100, 2)
    )
    assert after_product.attribute_breakdown["battery_life_priority"] == (
        before_product.attribute_breakdown["battery_life_priority"]
    )
    assert after_product.score_breakdown["battery_life_priority"] == (
        before_product.score_breakdown["battery_life_priority"]
    )
    assert after_product.score == before_product.score
    active_weight = sum(
        DIMENSION_WEIGHTS[dimension]
        for dimension in after_product.score_breakdown
    )
    assert after_product.score == round(
        sum(after_product.score_breakdown.values()) / active_weight,
        2,
    )


def test_missing_battery_data_is_penalized_and_explained_when_requested(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    from app.schemas.recommendation import RecommendationRequest
    from app.services.recommendation import generate_recommendations

    user_id = _create_user(seeded_client, sample_profile_payload)
    snapshot = _catalogue_snapshot(db_session)
    pulsebuds = next(product for product in snapshot if product.product_id == "SS-HP-002")
    pulsebuds.attributes.pop("battery_life_hours")

    response = generate_recommendations(
        db_session,
        RecommendationRequest(
            user_id=user_id,
            category="Headphones",
            limit=10,
            max_budget_override=10000,
        ),
        preference_overrides={"battery_life_priority": 80},
        product_snapshot=snapshot,
    )

    product = next(item for item in response.products if item.product_id == "SS-HP-002")
    assert product.attribute_breakdown["battery_life_priority"] == 0
    assert product.score_breakdown["battery_life_priority"] == 0
    assert "Battery life is not listed in catalogue data." in product.reasons
    assert 0 <= product.score <= 100


def test_missing_build_quality_is_not_claimed_from_catalogue_rating(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    from app.models.product import Product

    user_id = _create_user(seeded_client, sample_profile_payload)
    dna_response = seeded_client.put(
        f"/api/profiles/{user_id}/dna",
        json={
            "inferred_preferences": {"quality_preference": 90},
            "confidence_scores": {"quality_preference": 100},
            "preference_sources": {"quality_preference": "manual"},
        },
    )
    assert dna_response.status_code == 200
    product_row = (
        db_session.query(Product)
        .filter(Product.product_id == "SS-HP-001")
        .first()
    )
    product_row.attributes = {
        key: value
        for key, value in product_row.attributes.items()
        if key != "build_quality"
    }
    db_session.commit()

    response = seeded_client.post(
        "/api/recommendations",
        json={
            "user_id": user_id,
            "category": "Headphones",
            "limit": 5,
            "require_available": True,
        },
    )
    assert response.status_code == 200
    product = next(
        item
        for item in response.json()["products"]
        if item["product_id"] == "SS-HP-001"
    )

    assert any("build-quality data is unavailable" in reason for reason in product["reasons"])
    assert any("Catalogue rating 4.5/5 is listed" in reason for reason in product["reasons"])
    assert not any("good build quality" in reason.casefold() for reason in product["reasons"])


def test_explicit_battery_priority_drives_reasons_without_unrequested_portability(
    seeded_client: TestClient,
    sample_profile_payload: dict,
    db_session: Session,
) -> None:
    from app.schemas.recommendation import RecommendationRequest
    from app.services.recommendation import generate_recommendations

    user_id = _create_user(seeded_client, sample_profile_payload)
    response = generate_recommendations(
        db_session,
        RecommendationRequest(
            user_id=user_id,
            category="Headphones",
            limit=10,
            max_budget_override=10000,
        ),
        preference_overrides={"battery_life_priority": 80},
    )
    product = next(item for item in response.products if item.product_id == "SS-HP-002")

    assert "Catalogue lists 18 hours of battery life." in product.reasons
    assert not any("portability" in reason for reason in product.reasons)


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
