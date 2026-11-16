"""Recommendation API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation import generate_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
def get_recommendations(
    payload: RecommendationRequest,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    return generate_recommendations(db, payload)
