"""Idempotent catalogue seeding — never touches user profiles or history."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.catalogue import DEMO_PRODUCTS
from app.models.product import Product


def seed_products(db: Session) -> dict[str, int]:
    """Insert missing demo products by SKU. Existing rows are left unchanged.

    Returns counts: inserted, skipped, total_in_seed_file.
    """
    inserted = 0
    skipped = 0

    for item in DEMO_PRODUCTS:
        existing = db.scalar(select(Product).where(Product.product_id == item["product_id"]))
        if existing is not None:
            skipped += 1
            continue

        db.add(
            Product(
                product_id=item["product_id"],
                name=item["name"],
                brand=item["brand"],
                category=item["category"],
                price=item["price"],
                rating=item["rating"],
                description=item["description"],
                attributes=dict(item["attributes"]),
                stock_quantity=item["stock_quantity"],
                is_active=item["is_active"],
                image_url=item["image_url"],
            )
        )
        inserted += 1

    if inserted:
        db.commit()

    return {
        "inserted": inserted,
        "skipped": skipped,
        "total_in_seed_file": len(DEMO_PRODUCTS),
    }
