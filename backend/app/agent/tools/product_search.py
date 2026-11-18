"""Catalogue search tool backed by the deterministic recommendation service."""

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.schemas import ProductSearchArguments
from app.agent.state import AgentState
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation import (
    explicitly_requests_children_headphones,
    generate_recommendations,
    preference_overrides_from_intent,
)


def search_products(
    raw_arguments: BaseModel,
    state: AgentState,
    db: Session,
) -> RecommendationResponse:
    arguments = ProductSearchArguments.model_validate(raw_arguments)
    if state.constraints.category is None:
        raise ValueError("A supported category is required for catalogue search.")
    if arguments.limit > state.request_limit:
        raise ValueError("Search limit cannot exceed the user's requested limit.")

    excluded_ids: list[str] = []
    if state.exclude_previous_products:
        excluded_ids.extend(state.previously_shown_product_ids)
    for record in state.tool_results:
        if isinstance(record.result, RecommendationResponse):
            excluded_ids.extend(
                product.product_id for product in record.result.products
            )
    excluded_ids = list(dict.fromkeys(excluded_ids))

    intent = state.constraints
    return generate_recommendations(
        db,
        RecommendationRequest(
            user_id=state.user_id,
            category=intent.category,
            limit=arguments.limit,
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
        excluded_product_ids=excluded_ids,
    )
