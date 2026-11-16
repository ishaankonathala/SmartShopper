"""Seeding idempotency, FK behaviour, and health regression."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.seed import seed_products


def test_seed_is_idempotent(db_session: Session) -> None:
    first = seed_products(db_session)
    second = seed_products(db_session)
    assert first["inserted"] == first["total_in_seed_file"]
    assert second["inserted"] == 0
    assert second["skipped"] == second["total_in_seed_file"]


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
