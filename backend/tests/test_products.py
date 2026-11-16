"""Product catalogue API tests."""

from fastapi.testclient import TestClient


def test_list_products_hides_inactive_by_default(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 10
    assert all(p["is_active"] for p in products)


def test_include_inactive(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/products", params={"include_inactive": True})
    assert response.status_code == 200
    products = response.json()
    assert any(not p["is_active"] for p in products)


def test_filter_category(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/products", params={"category": "Headphones"})
    assert response.status_code == 200
    products = response.json()
    assert products
    assert all(p["category"] == "Headphones" for p in products)


def test_filter_brand(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/products", params={"brand": "AudioNova"})
    assert response.status_code == 200
    assert all(p["brand"] == "AudioNova" for p in response.json())


def test_filter_price(seeded_client: TestClient) -> None:
    response = seeded_client.get(
        "/api/products",
        params={"min_price": 2000, "max_price": 7000},
    )
    assert response.status_code == 200
    for product in response.json():
        assert 2000 <= product["price"] <= 7000


def test_filter_available(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/products", params={"available": True})
    assert response.status_code == 200
    for product in response.json():
        assert product["is_available"] is True
        assert product["stock_quantity"] > 0


def test_get_product(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/products/SS-HP-001")
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == "SS-HP-001"
    assert "comfort_score" in body["attributes"]


def test_get_product_not_found(seeded_client: TestClient) -> None:
    assert seeded_client.get("/api/products/DOES-NOT-EXIST").status_code == 404


def test_invalid_price_range(seeded_client: TestClient) -> None:
    response = seeded_client.get(
        "/api/products",
        params={"min_price": 9000, "max_price": 1000},
    )
    assert response.status_code == 422
