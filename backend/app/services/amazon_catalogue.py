"""Read-only queries for the isolated Amazon Discover catalogue."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.amazon_catalogue_product import AmazonCatalogueProduct


def list_products(
    db: Session,
    *,
    category: str | None = None,
    search: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> tuple[list[AmazonCatalogueProduct], int]:
    statement = select(AmazonCatalogueProduct)
    count_statement = select(func.count()).select_from(AmazonCatalogueProduct)

    if category:
        statement = statement.where(AmazonCatalogueProduct.category == category)
        count_statement = count_statement.where(
            AmazonCatalogueProduct.category == category
        )
    if search:
        statement = statement.where(
            AmazonCatalogueProduct.title.ilike(f"%{search.strip()}%")
        )
        count_statement = count_statement.where(
            AmazonCatalogueProduct.title.ilike(f"%{search.strip()}%")
        )

    total = int(db.scalar(count_statement) or 0)
    products = list(
        db.scalars(
            statement.order_by(
                AmazonCatalogueProduct.rating_count.desc(),
                AmazonCatalogueProduct.rating.desc(),
                AmazonCatalogueProduct.asin,
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return products, total


def list_categories(db: Session) -> list[str]:
    return list(
        db.scalars(
            select(AmazonCatalogueProduct.category)
            .distinct()
            .order_by(AmazonCatalogueProduct.category)
        ).all()
    )


def get_product(db: Session, asin: str) -> AmazonCatalogueProduct:
    product = db.scalar(
        select(AmazonCatalogueProduct).where(
            AmazonCatalogueProduct.asin == asin.strip().upper()
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amazon catalogue product not found",
        )
    return product
