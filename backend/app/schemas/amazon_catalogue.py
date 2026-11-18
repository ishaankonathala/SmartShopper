"""API schemas for the isolated Amazon Discover catalogue."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AmazonCatalogueProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asin: str
    title: str
    store: str | None
    category: str
    price_inr: int = Field(ge=1)
    rating: float = Field(ge=1, le=5)
    rating_count: int = Field(ge=5)
    image_url: str
    description: list[str]
    features: list[str]
    source_metadata: dict[str, Any]
    created_at: datetime


class AmazonCataloguePage(BaseModel):
    products: list[AmazonCatalogueProductRead]
    categories: list[str]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
