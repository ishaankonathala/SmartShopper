"""Pydantic schemas for shopping interaction history."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class HistoryAction(str, Enum):
    viewed = "viewed"
    liked = "liked"
    purchased = "purchased"
    dismissed = "dismissed"
    not_interested = "not_interested"


class ShoppingHistoryCreate(BaseModel):
    """Record a user–product interaction.

    `product_id` is the public catalogue SKU (e.g. SS-HP-001), not the DB row id.
    """

    user_id: Annotated[int, Field(gt=0)]
    product_id: Annotated[str, Field(min_length=1, max_length=64)]
    action: HistoryAction


class ShoppingHistoryRead(BaseModel):
    """Public history event with resolved catalogue SKU."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    product_id: str
    product_db_id: int
    product_name: str
    action: HistoryAction
    created_at: datetime
