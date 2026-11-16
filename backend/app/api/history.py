"""Shopping history API routes."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.shopping_history import (
    HistoryAction,
    ShoppingHistoryCreate,
    ShoppingHistoryRead,
)
from app.services import shopping_history as history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.post("", response_model=ShoppingHistoryRead, status_code=status.HTTP_201_CREATED)
def create_history(
    payload: ShoppingHistoryCreate,
    db: Session = Depends(get_db),
) -> ShoppingHistoryRead:
    event = history_service.record_history(db, payload)
    # Reload with product relationship for response shaping.
    events = history_service.list_history(db, payload.user_id)
    created = next(item for item in events if item.id == event.id)
    return history_service.to_history_read(created)


@router.get("/{user_id}", response_model=list[ShoppingHistoryRead])
def get_history(
    user_id: int,
    action: HistoryAction | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ShoppingHistoryRead]:
    events = history_service.list_history(db, user_id, action=action)
    return [history_service.to_history_read(event) for event in events]
