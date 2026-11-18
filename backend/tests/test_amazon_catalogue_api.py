"""API tests for Amazon Discover search, category filtering, and details."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.amazon_catalogue_product import AmazonCatalogueProduct


def _add_amazon_product(
    db_session: Session,
    *,
    asin: str,
    title: str,
    category: str,
) -> None:
    db_session.add(
        AmazonCatalogueProduct(
            asin=asin,
            title=title,
            store="Example Store",
            category=category,
            price_inr=1699,
            rating=4.5,
            rating_count=100,
            image_url="https://m.media-amazon.com/images/I/41image.jpg",
            description=["A listed product description."],
            features=["A listed product feature."],
            source_metadata={
                "source": "Amazon Reviews 2023 Electronics metadata",
                "parent_asin": asin,
                "original_price_usd": "19.99",
                "usd_to_inr_rate": "85",
            },
        )
    )
    db_session.commit()


def test_discover_search_and_category_filter(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_amazon_product(
        db_session,
        asin="B000000001",
        title="Studio camera kit",
        category="Camera & Photo",
    )
    _add_amazon_product(
        db_session,
        asin="B000000002",
        title="Studio headphones",
        category="Headphones & Earbuds",
    )

    response = client.get(
        "/api/discover/products",
        params={"category": "Camera & Photo", "search": "studio"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [product["asin"] for product in body["products"]] == ["B000000001"]
    assert body["products"][0]["price_inr"] == 1699


def test_discover_categories_and_product_detail(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_amazon_product(
        db_session,
        asin="B000000001",
        title="Studio camera kit",
        category="Camera & Photo",
    )

    listing = client.get("/api/discover/products")
    detail = client.get("/api/discover/products/B000000001")

    assert listing.status_code == 200
    assert listing.json()["categories"] == ["Camera & Photo"]
    assert detail.status_code == 200
    assert detail.json()["asin"] == "B000000001"
    assert detail.json()["features"] == ["A listed product feature."]
    assert detail.json()["source_metadata"]["original_price_usd"] == "19.99"


def test_discover_product_detail_returns_not_found(client: TestClient) -> None:
    assert client.get("/api/discover/products/B999999999").status_code == 404
