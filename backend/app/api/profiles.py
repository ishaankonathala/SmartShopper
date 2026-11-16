"""User profile and Shopper DNA API routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.schemas.shopper_dna import ShopperDNARead, ShopperDNAUpdate
from app.services import profile as profile_service
from app.services import shopper_dna as dna_service

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
) -> ProfileRead:
    return ProfileRead.model_validate(profile_service.create_profile(db, payload))


@router.get("/{user_id}", response_model=ProfileRead)
def get_profile(user_id: int, db: Session = Depends(get_db)) -> ProfileRead:
    return ProfileRead.model_validate(profile_service.get_profile(db, user_id))


@router.put("/{user_id}", response_model=ProfileRead)
def update_profile(
    user_id: int,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
) -> ProfileRead:
    return ProfileRead.model_validate(profile_service.update_profile(db, user_id, payload))


@router.get("/{user_id}/dna", response_model=ShopperDNARead)
def get_shopper_dna(user_id: int, db: Session = Depends(get_db)) -> ShopperDNARead:
    return ShopperDNARead.model_validate(dna_service.get_dna(db, user_id))


@router.put("/{user_id}/dna", response_model=ShopperDNARead)
def update_shopper_dna(
    user_id: int,
    payload: ShopperDNAUpdate,
    db: Session = Depends(get_db),
) -> ShopperDNARead:
    return ShopperDNARead.model_validate(dna_service.update_dna(db, user_id, payload))
