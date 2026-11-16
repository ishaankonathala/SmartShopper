"""Inferred preference profile — separate from explicit UserProfile fields."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user_profile import UserProfile


class ShopperDNA(Base):
    """Behaviour/default preference scores with confidence and source metadata.

    Explicit UserProfile fields are never stored here. Preference values use a
    0–100 scale. Confidence near 0 means the value is a default or weak guess.
    """

    __tablename__ = "shopper_dna"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    inferred_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence_scores: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    preference_sources: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[UserProfile] = relationship("UserProfile", back_populates="dna")
