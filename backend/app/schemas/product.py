"""Pydantic schemas for the demo product catalogue."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductRead(BaseModel):
    """Public product representation (demo/mock catalogue)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: str
    name: str
    brand: str
    category: str
    price: float
    rating: float
    description: str
    attributes: dict[str, Any]
    stock_quantity: int
    is_active: bool
    image_url: str | None
    created_at: datetime
    is_available: bool = Field(
        description="True when the product is active and has stock > 0"
    )

    @classmethod
    def from_orm_product(cls, product: Any) -> ProductRead:
        return cls(
            id=product.id,
            product_id=product.product_id,
            name=product.name,
            brand=product.brand,
            category=product.category,
            price=product.price,
            rating=product.rating,
            description=product.description,
            attributes=product.attributes or {},
            stock_quantity=product.stock_quantity,
            is_active=product.is_active,
            image_url=product.image_url,
            created_at=product.created_at,
            is_available=bool(product.is_active and product.stock_quantity > 0),
        )
