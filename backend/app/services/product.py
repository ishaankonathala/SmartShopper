"""Business logic for the demo product catalogue."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product


def list_products(
    db: Session,
    *,
    category: str | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    available_only: bool | None = None,
    include_inactive: bool = False,
) -> list[Product]:
    """Filter the catalogue. By default inactive products are hidden."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="min_price cannot exceed max_price",
        )

    stmt = select(Product)
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if category:
        stmt = stmt.where(Product.category == category)
    if brand:
        stmt = stmt.where(Product.brand == brand)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if available_only:
        stmt = stmt.where(Product.is_active.is_(True), Product.stock_quantity > 0)

    stmt = stmt.order_by(Product.category, Product.price)
    return list(db.scalars(stmt).all())


def get_product_by_sku(db: Session, product_id: str) -> Product:
    product = db.scalar(select(Product).where(Product.product_id == product_id))
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found",
        )
    return product


def get_product_by_db_id(db: Session, db_id: int) -> Product:
    product = db.get(Product, db_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product id {db_id} not found",
        )
    return product
