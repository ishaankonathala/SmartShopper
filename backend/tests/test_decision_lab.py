"""Decision Lab simulation API tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.recommendation import RecommendationResponse, RecommendedProduct


def _create_user(client: TestClient, payload: dict | None = None) -> int:
    response = client.post(
        "/api/profiles",
        json=payload
        or {
            "name": "Decision Lab User",
            "max_budget": 6500,
            "min_budget": 1000,
            "preferred_categories": ["Headphones"],
            "preferred_brands": ["SonyDemo"],
            "disliked_attributes": [],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _simulate(client: TestClient, user_id: int, **overrides) -> dict:
    response = client.post(
        "/api/decision-lab/simulate",
        json={"user_id": user_id, **overrides},
    )
    assert response.status_code == 200
    return response.json()


def _comparison(response: dict, product_id: str) -> dict:
    return next(
        item for item in response["comparisons"] if item["product_id"] == product_id
    )


def test_valid_simulation_returns_rank_and_score_comparisons(seeded_client: TestClient) -> None:
    user_id = _create_user(seeded_client)
    result = _simulate(seeded_client, user_id, comfort_priority=85)

    assert result["user_id"] == user_id
    assert result["baseline_budget"] == 6500
    assert result["simulated_budget"] == 6500
    assert result["comparisons"]
    assert all("explanation" in item for item in result["comparisons"])


def test_no_overrides_produce_identical_states(seeded_client: TestClient) -> None:
    user_id = _create_user(seeded_client)
    result = _simulate(seeded_client, user_id)

    assert result["comparisons"]
    for item in result["comparisons"]:
        assert item["baseline"] == item["simulated"]
        if item["baseline"]["status"] == "recommended":
            assert item["rank_movement"] == 0
            assert item["score_difference"] == 0
        else:
            assert item["rank_movement"] is None
            assert item["score_difference"] is None


def test_budget_override_excludes_products_without_changing_baseline(
    seeded_client: TestClient,
) -> None:
    user_id = _create_user(seeded_client)
    result = _simulate(seeded_client, user_id, max_budget_override=1000)

    assert result["baseline_budget"] == 6500
    assert result["simulated_budget"] == 1000
    comparison = _comparison(result, "SS-HP-002")
    assert comparison["baseline"]["status"] == "recommended"
    assert comparison["simulated"]["status"] == "excluded"
    assert comparison["simulated"]["exclusion_reason_code"] == "budget_exceeded"
    assert comparison["rank_movement"] is None
    assert comparison["score_difference"] is None


def test_comfort_override_changes_score_with_default_zero_confidence(
    seeded_client: TestClient,
) -> None:
    user_id = _create_user(seeded_client)
    dna_before = seeded_client.get(f"/api/profiles/{user_id}/dna").json()
    assert dna_before["confidence_scores"]["comfort_priority"] == 0

    result = _simulate(seeded_client, user_id, comfort_priority=100)
    comparison = _comparison(result, "SS-HP-001")
    assert comparison["baseline"]["status"] == "recommended"
    assert comparison["simulated"]["status"] == "recommended"
    assert comparison["score_difference"] > 0


def test_brand_loyalty_override_changes_score_for_preferred_brand(
    seeded_client: TestClient,
) -> None:
    user_id = _create_user(seeded_client)
    result = _simulate(seeded_client, user_id, brand_loyalty=100)

    comparison = _comparison(result, "SS-HP-001")
    assert comparison["score_difference"] > 0


def test_both_dna_overrides_can_be_applied_together(seeded_client: TestClient) -> None:
    user_id = _create_user(seeded_client)
    result = _simulate(
        seeded_client,
        user_id,
        comfort_priority=100,
        brand_loyalty=100,
    )

    assert _comparison(result, "SS-HP-001")["score_difference"] > 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("comfort_priority", -1),
        ("comfort_priority", 101),
        ("brand_loyalty", -1),
        ("brand_loyalty", 101),
    ],
)
def test_dna_override_range_validation(
    client: TestClient, field: str, value: int
) -> None:
    response = client.post(
        "/api/decision-lab/simulate",
        json={"user_id": 1, field: value},
    )
    assert response.status_code == 422


def test_negative_budget_override_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/decision-lab/simulate",
        json={"user_id": 1, "max_budget_override": -1},
    )
    assert response.status_code == 422


def test_missing_user_returns_not_found(seeded_client: TestClient) -> None:
    response = seeded_client.post(
        "/api/decision-lab/simulate",
        json={"user_id": 9999, "comfort_priority": 50},
    )
    assert response.status_code == 404


def test_overrides_leave_other_dna_dimensions_and_saved_data_unchanged(
    seeded_client: TestClient,
) -> None:
    user_id = _create_user(seeded_client)
    dna_update = {
        "inferred_preferences": {
            "comfort_priority": 65,
            "brand_loyalty": 70,
            "price_sensitivity": 30,
            "quality_preference": 80,
            "portability_preference": 45,
            "battery_life_priority": 90,
        },
        "confidence_scores": {
            "comfort_priority": 20,
            "brand_loyalty": 25,
            "price_sensitivity": 70,
            "quality_preference": 60,
            "portability_preference": 50,
            "battery_life_priority": 85,
        },
        "preference_sources": {
            dimension: "manual"
            for dimension in (
                "comfort_priority",
                "brand_loyalty",
                "price_sensitivity",
                "quality_preference",
                "portability_preference",
                "battery_life_priority",
            )
        },
    }
    update = seeded_client.put(f"/api/profiles/{user_id}/dna", json=dna_update)
    assert update.status_code == 200
    profile_before = seeded_client.get(f"/api/profiles/{user_id}").json()
    dna_before = seeded_client.get(f"/api/profiles/{user_id}/dna").json()

    result = seeded_client.post(
        "/api/decision-lab/simulate",
        json={
            "user_id": user_id,
            "max_budget_override": 7000,
            "comfort_priority": 100,
            "brand_loyalty": 0,
        },
    )
    assert result.status_code == 200

    profile_after = seeded_client.get(f"/api/profiles/{user_id}").json()
    dna_after = seeded_client.get(f"/api/profiles/{user_id}/dna").json()
    assert profile_after == profile_before
    assert dna_after == dna_before

    unchanged_dimensions = (
        "price_sensitivity",
        "quality_preference",
        "portability_preference",
        "battery_life_priority",
    )
    for dimension in unchanged_dimensions:
        assert dna_after["inferred_preferences"][dimension] == dna_before["inferred_preferences"][dimension]
        assert dna_after["confidence_scores"][dimension] == dna_before["confidence_scores"][dimension]
        assert dna_after["preference_sources"][dimension] == dna_before["preference_sources"][dimension]


def test_products_excluded_in_simulation_are_reported_with_reason(
    seeded_client: TestClient,
) -> None:
    user_id = _create_user(seeded_client)
    result = _simulate(seeded_client, user_id, max_budget_override=1000)
    comparison = _comparison(result, "SS-HP-002")

    assert comparison["simulated"]["status"] == "excluded"
    assert comparison["simulated"]["exclusion_reason_code"] == "budget_exceeded"
    assert comparison["simulated"]["exclusion_reason"]


def test_outside_top_ten_product_is_marked_without_invented_rank_or_score(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _create_user(client)

    def product(product_id: str, name: str, score: float) -> RecommendedProduct:
        return RecommendedProduct(
            product_id=product_id,
            name=name,
            brand="Demo",
            category="Headphones",
            price=1000,
            rating=4,
            image_url=None,
            score=score,
            confidence=50,
            reasons=[],
            attribute_breakdown={},
            score_breakdown={},
        )

    baseline = RecommendationResponse(
        user_id=user_id,
        generated_at="2026-01-01T00:00:00Z",
        requested_limit=10,
        products=[
            product("SKU-A", "Product A", 90),
            product("SKU-B", "Product B", 80),
        ],
        excluded_products=[],
        explanation_summary="baseline",
    )
    simulated = RecommendationResponse(
        user_id=user_id,
        generated_at="2026-01-01T00:00:00Z",
        requested_limit=10,
        products=[product("SKU-B", "Product B", 85)],
        excluded_products=[],
        explanation_summary="simulated",
    )
    calls = 0

    def fake_generate_recommendations(*args, **kwargs) -> RecommendationResponse:
        nonlocal calls
        calls += 1
        return baseline if calls == 1 else simulated

    monkeypatch.setattr(
        "app.services.decision_lab.generate_recommendations",
        fake_generate_recommendations,
    )

    response = client.post(
        "/api/decision-lab/simulate",
        json={"user_id": user_id, "comfort_priority": 0},
    )
    assert response.status_code == 200
    comparison = _comparison(response.json(), "SKU-A")
    assert comparison["baseline"]["status"] == "recommended"
    assert comparison["simulated"]["status"] == "outside_limit"
    assert comparison["simulated"]["rank"] is None
    assert comparison["simulated"]["score"] is None


def test_decision_lab_reuses_catalogue_snapshot_for_over_ten_products(
    seeded_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _create_user(
        seeded_client,
        {
            "name": "Snapshot Test User",
            "max_budget": 10000,
            "min_budget": 0,
            "preferred_categories": [],
            "preferred_brands": ["PreferredLab"],
            "disliked_attributes": [],
        },
    )
    dna_update = seeded_client.put(
        f"/api/profiles/{user_id}/dna",
        json={
            "inferred_preferences": {"brand_loyalty": 0},
            "confidence_scores": {"brand_loyalty": 100},
            "preference_sources": {"brand_loyalty": "manual"},
        },
    )
    assert dna_update.status_code == 200

    products = list(db_session.scalars(select(Product)).all())
    for product in products:
        product.is_active = True
        product.stock_quantity = 1
        product.price = 1000
        product.rating = 4
        product.attributes = {
            "comfort_score": 50,
            "battery_life_hours": 20,
            "build_quality": 50,
            "portability": 50,
        }
    db_session.add(
        Product(
            product_id="ZZ-DL-001",
            name="Preferred Lab Product",
            brand="PreferredLab",
            category="Headphones",
            price=1000,
            rating=4,
            description="Catalogue snapshot integration test product",
            attributes={
                "comfort_score": 50,
                "battery_life_hours": 20,
                "build_quality": 50,
                "portability": 50,
            },
            stock_quantity=1,
            is_active=True,
        )
    )
    db_session.commit()

    from app.services import decision_lab as decision_lab_service

    original_generate = decision_lab_service.generate_recommendations
    snapshots: list[list[Product]] = []

    def track_snapshot(db, recommendation_request, **kwargs):
        snapshot = kwargs.get("product_snapshot")
        snapshots.append(snapshot)
        return original_generate(db, recommendation_request, **kwargs)

    monkeypatch.setattr(
        decision_lab_service,
        "generate_recommendations",
        track_snapshot,
    )
    response = seeded_client.post(
        "/api/decision-lab/simulate",
        json={"user_id": user_id, "brand_loyalty": 100},
    )

    assert response.status_code == 200
    assert len(snapshots) == 2
    assert snapshots[0] is snapshots[1]
    assert len(snapshots[0]) > 10

    comparisons = response.json()["comparisons"]
    preferred_product = _comparison(response.json(), "ZZ-DL-001")
    assert preferred_product["baseline"]["status"] == "outside_limit"
    assert preferred_product["simulated"]["status"] == "recommended"
    assert any(
        item["baseline"]["status"] == "recommended"
        and item["simulated"]["status"] == "outside_limit"
        for item in comparisons
    )


def test_rank_movement_and_score_difference_use_defined_directions(
    seeded_client: TestClient,
) -> None:
    user_id = _create_user(seeded_client)
    result = _simulate(seeded_client, user_id, comfort_priority=0)

    assert any(item["rank_movement"] > 0 for item in result["comparisons"] if item["rank_movement"] is not None)
    assert any(item["rank_movement"] < 0 for item in result["comparisons"] if item["rank_movement"] is not None)
    assert any(
        item["score_difference"] is not None and item["score_difference"] < 0
        for item in result["comparisons"]
    )
    for item in result["comparisons"]:
        baseline = item["baseline"]
        simulated = item["simulated"]
        if baseline["rank"] is not None and simulated["rank"] is not None:
            assert item["rank_movement"] == baseline["rank"] - simulated["rank"]
        else:
            assert item["rank_movement"] is None
        if baseline["score"] is not None and simulated["score"] is not None:
            assert item["score_difference"] == round(simulated["score"] - baseline["score"], 2)
        else:
            assert item["score_difference"] is None


def test_identical_simulation_requests_are_deterministic(seeded_client: TestClient) -> None:
    user_id = _create_user(seeded_client)
    payload = {"user_id": user_id, "comfort_priority": 80, "brand_loyalty": 20}

    first = seeded_client.post("/api/decision-lab/simulate", json=payload)
    second = seeded_client.post("/api/decision-lab/simulate", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_brand_loyalty_override_notes_absent_preferred_brands(
    seeded_client: TestClient,
) -> None:
    user_id = _create_user(seeded_client)
    update = seeded_client.put(
        f"/api/profiles/{user_id}",
        json={"preferred_brands": []},
    )
    assert update.status_code == 200

    result = _simulate(seeded_client, user_id, brand_loyalty=90)
    assert any("no preferred brands" in note for note in result["notes"])
