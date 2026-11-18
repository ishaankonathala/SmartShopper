"""Seeding idempotency, FK behaviour, and health regression."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.shopping_history import ShoppingHistory
from app.models.user_profile import UserProfile
from app.services.seed import seed_products


def test_seed_is_idempotent(db_session: Session) -> None:
    first = seed_products(db_session)
    second = seed_products(db_session)
    assert first["inserted"] == first["total_in_seed_file"]
    assert first["updated"] == 0
    assert second["inserted"] == 0
    assert second["updated"] == 0
    assert second["skipped"] == second["total_in_seed_file"]

    pulsebuds = db_session.query(Product).filter_by(product_id="SS-HP-002").one()
    assert pulsebuds.attributes["connectivity"] == "wireless"


def test_seed_backfills_missing_attributes_without_changing_user_data(
    db_session: Session,
) -> None:
    seed_products(db_session)
    pulsebuds = db_session.query(Product).filter_by(product_id="SS-HP-002").one()
    pulsebuds.name = "Curated PulseBuds"
    pulsebuds.price = 2600
    pulsebuds.rating = 4.8
    pulsebuds.attributes = {
        **pulsebuds.attributes,
        "battery_life_hours": 20,
        "custom_catalogue_note": "preserve this",
    }
    pulsebuds.attributes.pop("connectivity")

    profile = UserProfile(name="Seed regression", max_budget=5000)
    db_session.add(profile)
    db_session.flush()
    db_session.add(
        ShoppingHistory(
            user_id=profile.id,
            product_id=pulsebuds.id,
            action="purchased",
        )
    )
    db_session.commit()
    product_row_id = pulsebuds.id

    backfill = seed_products(db_session)

    db_session.expire_all()
    pulsebuds = db_session.query(Product).filter_by(product_id="SS-HP-002").one()
    assert backfill["inserted"] == 0
    assert backfill["updated"] == 1
    assert pulsebuds.id == product_row_id
    assert pulsebuds.product_id == "SS-HP-002"
    assert pulsebuds.name == "Curated PulseBuds"
    assert pulsebuds.price == 2600
    assert pulsebuds.rating == 4.8
    assert pulsebuds.attributes["connectivity"] == "wireless"
    assert pulsebuds.attributes["battery_life_hours"] == 20
    assert pulsebuds.attributes["custom_catalogue_note"] == "preserve this"
    assert db_session.query(ShoppingHistory).count() == 1

    repeated = seed_products(db_session)
    assert repeated["updated"] == 0


def test_foreign_key_rejects_orphan_history(db_session: Session) -> None:
    with db_session.begin_nested():
        try:
            db_session.execute(
                text(
                    "INSERT INTO shopping_history (user_id, product_id, action) "
                    "VALUES (999, 999, 'viewed')"
                )
            )
            db_session.flush()
            raised = False
        except Exception:
            raised = True
            db_session.rollback()
    assert raised


def test_health_still_works(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"


def test_profile_dna_relationship(client: TestClient, sample_profile_payload: dict) -> None:
    created = client.post("/api/profiles", json=sample_profile_payload).json()
    dna = client.get(f"/api/profiles/{created['id']}/dna").json()
    assert dna["user_id"] == created["id"]
