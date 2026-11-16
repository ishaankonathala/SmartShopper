"""Business logic for inferred Shopper DNA (never mutates explicit profile)."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.shopper_dna import ShopperDNA
from app.schemas.shopper_dna import ShopperDNAUpdate
from app.services.profile import get_profile


def get_dna(db: Session, user_id: int) -> ShopperDNA:
    """Return Shopper DNA for a user. Ensures the profile exists."""
    profile = get_profile(db, user_id)
    if profile.dna is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shopper DNA for user {user_id} not found",
        )
    return profile.dna


def update_dna(db: Session, user_id: int, payload: ShopperDNAUpdate) -> ShopperDNA:
    """Patch inferred preference maps only — explicit UserProfile is untouched."""
    dna = get_dna(db, user_id)

    if payload.inferred_preferences is not None:
        merged = dict(dna.inferred_preferences)
        merged.update(payload.inferred_preferences)
        dna.inferred_preferences = merged

    if payload.confidence_scores is not None:
        merged = dict(dna.confidence_scores)
        merged.update(payload.confidence_scores)
        dna.confidence_scores = merged

    if payload.preference_sources is not None:
        merged = dict(dna.preference_sources)
        merged.update(payload.preference_sources)
        dna.preference_sources = merged

    dna.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(dna)
    return dna
