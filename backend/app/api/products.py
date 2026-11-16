"""Product catalogue API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.product import ProductRead
from app.services import product as product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(
    category: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    available: bool | None = Query(
        default=None,
        description="If true, only active products with stock > 0",
    ),
    include_inactive: bool = Query(
        default=False,
        description="Include inactive catalogue entries (demo / admin use)",
    ),
    db: Session = Depends(get_db),
) -> list[ProductRead]:
    products = product_service.list_products(
        db,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        available_only=available,
        include_inactive=include_inactive,
    )
    return [ProductRead.from_orm_product(p) for p in products]


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: str, db: Session = Depends(get_db)) -> ProductRead:
    product = product_service.get_product_by_sku(db, product_id)
    return ProductRead.from_orm_product(product)
