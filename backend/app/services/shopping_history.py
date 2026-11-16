"""Business logic for shopping interaction history."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.shopping_history import ShoppingHistory
from app.schemas.shopping_history import HistoryAction, ShoppingHistoryCreate, ShoppingHistoryRead
from app.services.product import get_product_by_sku
from app.services.profile import get_profile


def record_history(db: Session, payload: ShoppingHistoryCreate) -> ShoppingHistory:
    """Append an interaction. Does not delete or rewrite prior events."""
    get_profile(db, payload.user_id)
    product = get_product_by_sku(db, payload.product_id)

    event = ShoppingHistory(
        user_id=payload.user_id,
        product_id=product.id,
        action=payload.action.value,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_history(
    db: Session,
    user_id: int,
    *,
    action: HistoryAction | None = None,
) -> list[ShoppingHistory]:
    get_profile(db, user_id)
    stmt = (
        select(ShoppingHistory)
        .options(selectinload(ShoppingHistory.product))
        .where(ShoppingHistory.user_id == user_id)
        .order_by(ShoppingHistory.created_at.desc())
    )
    if action is not None:
        stmt = stmt.where(ShoppingHistory.action == action.value)
    return list(db.scalars(stmt).all())


def to_history_read(event: ShoppingHistory) -> ShoppingHistoryRead:
    product = event.product
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="History event is missing product relationship",
        )
    return ShoppingHistoryRead(
        id=event.id,
        user_id=event.user_id,
        product_id=product.product_id,
        product_db_id=product.id,
        product_name=product.name,
        action=HistoryAction(event.action),
        created_at=event.created_at,
    )
