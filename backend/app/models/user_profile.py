"""Explicit user shopping preferences (never AI-inferred)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.shopper_dna import ShopperDNA
    from app.models.shopping_history import ShoppingHistory


class UserProfile(Base):
    """Preferences the user stated explicitly — separate from Shopper DNA."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    max_budget: Mapped[float] = mapped_column(Float, nullable=False)
    min_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_categories: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    preferred_brands: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    disliked_attributes: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    dna: Mapped[ShopperDNA | None] = relationship(
        "ShopperDNA",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    history: Mapped[list[ShoppingHistory]] = relationship(
        "ShoppingHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
