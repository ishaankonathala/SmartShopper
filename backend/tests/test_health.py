"""Health endpoint verification."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert payload["app"] == "SmartShopper"
    assert "version" in payload


def test_root_marker(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["app"] == "SmartShopper"
