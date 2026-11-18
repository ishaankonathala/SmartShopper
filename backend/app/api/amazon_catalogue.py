"""Discover endpoints for the isolated Amazon metadata catalogue."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.amazon_catalogue import (
    AmazonCataloguePage,
    AmazonCatalogueProductRead,
)
from app.services import amazon_catalogue as catalogue_service

router = APIRouter(prefix="/discover", tags=["discover"])


@router.get("/products", response_model=AmazonCataloguePage)
def list_products(
    category: str | None = Query(default=None, min_length=1, max_length=120),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AmazonCataloguePage:
    products, total = catalogue_service.list_products(
        db,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )
    return AmazonCataloguePage(
        products=products,
        categories=catalogue_service.list_categories(db),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/products/{asin}", response_model=AmazonCatalogueProductRead)
def get_product(
    asin: str,
    db: Session = Depends(get_db),
) -> AmazonCatalogueProductRead:
    return catalogue_service.get_product(db, asin)
