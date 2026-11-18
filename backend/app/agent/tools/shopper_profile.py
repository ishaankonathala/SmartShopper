"""Read-only retrieval of the current request user's saved profile."""

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.schemas import EmptyToolArguments, ShopperProfileResult
from app.agent.state import AgentState
from app.services import profile as profile_service
from app.services import shopper_dna as dna_service


def _string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _integer_values(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, int) and not isinstance(item, bool)
    }


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, str)
    }


def get_shopper_profile(
    _raw_arguments: BaseModel,
    state: AgentState,
    db: Session,
) -> ShopperProfileResult:
    EmptyToolArguments.model_validate(_raw_arguments)
    profile = profile_service.get_profile(db, state.user_id)
    dna = dna_service.get_dna(db, state.user_id)
    return ShopperProfileResult(
        user_id=state.user_id,
        max_budget=float(profile.max_budget),
        min_budget=(
            float(profile.min_budget)
            if profile.min_budget is not None
            else None
        ),
        preferred_categories=_string_values(profile.preferred_categories),
        preferred_brands=_string_values(profile.preferred_brands),
        disliked_attributes=_string_values(profile.disliked_attributes),
        inferred_preferences=_integer_values(dna.inferred_preferences),
        confidence_scores=_integer_values(dna.confidence_scores),
        preference_sources=_string_map(dna.preference_sources),
    )
