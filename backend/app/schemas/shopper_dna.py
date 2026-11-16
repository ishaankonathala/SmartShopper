"""Pydantic schemas for inferred Shopper DNA preferences."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.dna_defaults import ALLOWED_PREFERENCE_SOURCES, PREFERENCE_DIMENSIONS

Score = Annotated[int, Field(ge=0, le=100)]


class ShopperDNAUpdate(BaseModel):
    """Update inferred preferences / confidence / sources.

    Does not touch explicit UserProfile fields.
    """

    inferred_preferences: dict[str, Score] | None = None
    confidence_scores: dict[str, Score] | None = None
    preference_sources: dict[str, str] | None = None

    @field_validator("inferred_preferences", "confidence_scores")
    @classmethod
    def known_dimensions_only(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        if value is None:
            return value
        unknown = set(value) - set(PREFERENCE_DIMENSIONS)
        if unknown:
            raise ValueError(
                f"Unknown preference dimensions: {sorted(unknown)}. "
                f"Allowed: {list(PREFERENCE_DIMENSIONS)}"
            )
        return value

    @field_validator("preference_sources")
    @classmethod
    def validate_sources(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return value
        unknown = set(value) - set(PREFERENCE_DIMENSIONS)
        if unknown:
            raise ValueError(f"Unknown preference dimensions: {sorted(unknown)}")
        invalid = {
            dim: source
            for dim, source in value.items()
            if source not in ALLOWED_PREFERENCE_SOURCES
        }
        if invalid:
            raise ValueError(
                f"Invalid preference sources: {invalid}. "
                f"Allowed: {sorted(ALLOWED_PREFERENCE_SOURCES)}"
            )
        return value

    @model_validator(mode="after")
    def at_least_one_field(self) -> ShopperDNAUpdate:
        if (
            self.inferred_preferences is None
            and self.confidence_scores is None
            and self.preference_sources is None
        ):
            raise ValueError("Provide at least one of inferred_preferences, confidence_scores, or preference_sources")
        return self


class ShopperDNARead(BaseModel):
    """Public Shopper DNA representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    inferred_preferences: dict[str, int]
    confidence_scores: dict[str, int]
    preference_sources: dict[str, str]
    updated_at: datetime
