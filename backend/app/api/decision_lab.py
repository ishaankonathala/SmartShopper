"""Decision Lab simulation API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.decision_lab import DecisionLabRequest, DecisionLabResponse
from app.services.decision_lab import simulate_decision_lab

router = APIRouter(prefix="/decision-lab", tags=["decision-lab"])


@router.post("/simulate", response_model=DecisionLabResponse)
def simulate(
    payload: DecisionLabRequest,
    db: Session = Depends(get_db),
) -> DecisionLabResponse:
    return simulate_decision_lab(db, payload)
