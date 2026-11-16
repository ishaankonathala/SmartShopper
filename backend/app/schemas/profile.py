"""Pydantic schemas for explicit user profiles."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ProfileCreate(BaseModel):
    """Payload for creating an explicit shopping profile."""

    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: EmailStr | None = None
    max_budget: Annotated[float, Field(ge=0)]
    min_budget: Annotated[float | None, Field(default=None, ge=0)] = None
    preferred_categories: list[str] = Field(default_factory=list)
    preferred_brands: list[str] = Field(default_factory=list)
    disliked_attributes: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def budgets_consistent(self) -> ProfileCreate:
        if self.min_budget is not None and self.min_budget > self.max_budget:
            raise ValueError("Minimum budget cannot exceed maximum budget")
        return self


class ProfileUpdate(BaseModel):
    """Partial update for explicit profile fields only."""

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=120)] = None
    email: EmailStr | None = None
    max_budget: Annotated[float | None, Field(default=None, ge=0)] = None
    min_budget: Annotated[float | None, Field(default=None, ge=0)] = None
    preferred_categories: list[str] | None = None
    preferred_brands: list[str] | None = None
    disliked_attributes: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned


class ProfileRead(BaseModel):
    """Public profile representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None
    max_budget: float
    min_budget: float | None
    preferred_categories: list[str]
    preferred_brands: list[str]
    disliked_attributes: list[str]
    created_at: datetime
    updated_at: datetime
