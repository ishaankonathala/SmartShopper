"""Business logic for explicit user profiles."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dna_defaults import (
    DEFAULT_CONFIDENCE_SCORES,
    DEFAULT_INFERRED_PREFERENCES,
    DEFAULT_PREFERENCE_SOURCES,
)
from app.models.shopper_dna import ShopperDNA
from app.models.user_profile import UserProfile
from app.schemas.profile import ProfileCreate, ProfileUpdate


def create_profile(db: Session, payload: ProfileCreate) -> UserProfile:
    """Create a profile and attach default Shopper DNA (low confidence)."""
    profile = UserProfile(
        name=payload.name,
        email=str(payload.email) if payload.email else None,
        max_budget=payload.max_budget,
        min_budget=payload.min_budget,
        preferred_categories=list(payload.preferred_categories),
        preferred_brands=list(payload.preferred_brands),
        disliked_attributes=list(payload.disliked_attributes),
    )
    profile.dna = ShopperDNA(
        inferred_preferences=dict(DEFAULT_INFERRED_PREFERENCES),
        confidence_scores=dict(DEFAULT_CONFIDENCE_SCORES),
        preference_sources=dict(DEFAULT_PREFERENCE_SOURCES),
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile with this email already exists",
        ) from exc
    db.refresh(profile)
    return profile


def get_profile(db: Session, user_id: int) -> UserProfile:
    profile = db.get(UserProfile, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User profile {user_id} not found",
        )
    return profile


def update_profile(db: Session, user_id: int, payload: ProfileUpdate) -> UserProfile:
    profile = get_profile(db, user_id)
    data = payload.model_dump(exclude_unset=True)

    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])

    next_min = data.get("min_budget", profile.min_budget)
    next_max = data.get("max_budget", profile.max_budget)
    if next_min is not None and next_max is not None and next_min > next_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Minimum budget cannot exceed maximum budget",
        )

    for key, value in data.items():
        setattr(profile, key, value)

    profile.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile with this email already exists",
        ) from exc
    db.refresh(profile)
    return profile


def list_profiles(db: Session) -> list[UserProfile]:
    return list(db.scalars(select(UserProfile).order_by(UserProfile.id)).all())
