"""Temporary preference simulations that never write to profile or DNA."""

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.schemas import (
    PreferenceSimulationArguments,
    PreferenceSimulationResult,
)
from app.agent.state import AgentState
from app.schemas.recommendation import RecommendationRequest
from app.services.recommendation import (
    explicitly_requests_children_headphones,
    generate_recommendations,
    preference_overrides_from_intent,
)

_SIMULATABLE_FIELDS = (
    "max_budget_override",
    "min_budget_override",
    "comfort_priority",
    "brand_loyalty",
    "battery_life_priority",
    "portability_priority",
)


def simulate_preferences(
    raw_arguments: BaseModel,
    state: AgentState,
    db: Session,
) -> PreferenceSimulationResult:
    arguments = PreferenceSimulationArguments.model_validate(raw_arguments)
    intent = state.constraints
    if intent.category is None:
        raise ValueError("A supported category is required to simulate preferences.")
    for field in _SIMULATABLE_FIELDS:
        proposed = getattr(arguments, field)
        if proposed is not None and proposed != getattr(intent, field):
            raise ValueError("Simulation values must match validated shopper preferences.")

    response = generate_recommendations(
        db,
        RecommendationRequest(
            user_id=state.user_id,
            category=intent.category,
            limit=state.request_limit,
            max_budget_override=intent.max_budget_override,
            min_budget_override=intent.min_budget_override,
            brand=intent.brand,
            min_rating=intent.min_rating,
            include_unverified_availability=intent.availability_requirement is None,
        ),
        preference_overrides=preference_overrides_from_intent(intent),
        required_connectivity=intent.connectivity_requirement,
        required_product_type=intent.product_type_requirement,
        min_battery_life_hours=intent.min_battery_life_hours,
        require_battery_life_data=bool(intent.require_battery_life_data),
        prioritize_children_headphones=explicitly_requests_children_headphones(
            state.objective
        ),
        excluded_product_ids=(
            state.previously_shown_product_ids
            if state.exclude_previous_products
            else ()
        ),
    )
    return PreferenceSimulationResult(
        recommendations=response,
        simulated_constraints=intent,
    )
