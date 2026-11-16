"""Decision Lab baseline-versus-simulation service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.decision_lab import (
    DecisionLabProductComparison,
    DecisionLabProductState,
    DecisionLabRequest,
    DecisionLabResponse,
)
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.profile import get_profile
from app.services.recommendation import (
    PreferenceOverrideDimension,
    generate_recommendations,
)


def _product_states(
    response: RecommendationResponse,
) -> tuple[dict[str, tuple[int, float]], dict[str, tuple[str, str]], dict[str, str]]:
    recommended = {
        product.product_id: (rank, product.score)
        for rank, product in enumerate(response.products, start=1)
    }
    excluded = {
        product.product_id: (product.reason_code, product.message)
        for product in response.excluded_products
    }
    names = {
        product.product_id: product.name
        for product in response.products
    }
    names.update(
        {
            product.product_id: product.name
            for product in response.excluded_products
            if product.product_id not in names
        }
    )
    return recommended, excluded, names


def _state_for(
    product_id: str,
    recommended: dict[str, tuple[int, float]],
    excluded: dict[str, tuple[str, str]],
) -> DecisionLabProductState:
    if product_id in recommended:
        rank, score = recommended[product_id]
        return DecisionLabProductState(status="recommended", rank=rank, score=score)
    if product_id in excluded:
        reason_code, reason = excluded[product_id]
        return DecisionLabProductState(
            status="excluded",
            exclusion_reason_code=reason_code,
            exclusion_reason=reason,
        )
    return DecisionLabProductState(status="outside_limit")


def _explain_comparison(
    baseline: DecisionLabProductState,
    simulated: DecisionLabProductState,
    rank_movement: int | None,
    score_difference: float | None,
) -> str:
    if baseline.status == "excluded" and simulated.status == "excluded":
        if baseline.exclusion_reason_code == simulated.exclusion_reason_code:
            return f"Excluded in both runs: {simulated.exclusion_reason}"
        return (
            f"Baseline exclusion: {baseline.exclusion_reason} "
            f"Simulation exclusion: {simulated.exclusion_reason}"
        )

    if baseline.status == "recommended" and simulated.status == "recommended":
        if rank_movement == 0:
            explanation = f"Stayed at rank {baseline.rank}."
        elif rank_movement is not None and rank_movement > 0:
            place = "place" if rank_movement == 1 else "places"
            explanation = f"Moved up {rank_movement} {place} to rank {simulated.rank}."
        else:
            movement = abs(rank_movement or 0)
            place = "place" if movement == 1 else "places"
            explanation = f"Moved down {movement} {place} to rank {simulated.rank}."

        if score_difference == 0:
            return f"{explanation} Score was unchanged."
        if score_difference is not None and score_difference > 0:
            return f"{explanation} Score increased by {score_difference:.2f}."
        if score_difference is not None:
            return f"{explanation} Score decreased by {abs(score_difference):.2f}."
        return explanation

    if simulated.status == "excluded":
        return f"Excluded in the simulation: {simulated.exclusion_reason}"
    if baseline.status == "excluded" and simulated.status == "recommended":
        return (
            f"Now recommended at rank {simulated.rank}; baseline exclusion: "
            f"{baseline.exclusion_reason}"
        )
    if baseline.status == "recommended" and simulated.status == "outside_limit":
        return "Not present in the simulated top 10."
    if baseline.status == "outside_limit" and simulated.status == "recommended":
        return f"Entered the simulated top 10 at rank {simulated.rank}."
    if baseline.status == "excluded":
        return f"Baseline exclusion: {baseline.exclusion_reason} Not in the simulated top 10."
    if simulated.status == "excluded":
        return f"Not in the baseline top 10. Simulation exclusion: {simulated.exclusion_reason}"
    return "Not present in either top 10 recommendation list."


def simulate_decision_lab(
    db: Session,
    request: DecisionLabRequest,
) -> DecisionLabResponse:
    """Compare saved-preference recommendations with temporary overrides."""
    profile = get_profile(db, request.user_id)
    product_snapshot = list(db.scalars(select(Product)).all())

    baseline_response = generate_recommendations(
        db,
        RecommendationRequest(user_id=request.user_id),
        product_snapshot=product_snapshot,
    )

    preference_overrides: dict[PreferenceOverrideDimension, int] = {}
    if request.comfort_priority is not None:
        preference_overrides["comfort_priority"] = request.comfort_priority
    if request.brand_loyalty is not None:
        preference_overrides["brand_loyalty"] = request.brand_loyalty

    simulated_response = generate_recommendations(
        db,
        RecommendationRequest(
            user_id=request.user_id,
            max_budget_override=request.max_budget_override,
        ),
        preference_overrides=preference_overrides,
        product_snapshot=product_snapshot,
    )

    baseline_ranked, baseline_excluded, baseline_names = _product_states(baseline_response)
    simulated_ranked, simulated_excluded, simulated_names = _product_states(simulated_response)

    product_ids = (
        set(baseline_ranked)
        | set(baseline_excluded)
        | set(simulated_ranked)
        | set(simulated_excluded)
    )
    ordered_product_ids = list(dict.fromkeys(
        [product.product_id for product in baseline_response.products]
        + [product.product_id for product in simulated_response.products]
    ))
    ordered_product_ids.extend(sorted(product_ids - set(ordered_product_ids)))

    comparisons: list[DecisionLabProductComparison] = []
    for product_id in ordered_product_ids:
        baseline_state = _state_for(product_id, baseline_ranked, baseline_excluded)
        simulated_state = _state_for(product_id, simulated_ranked, simulated_excluded)
        rank_movement = None
        if baseline_state.rank is not None and simulated_state.rank is not None:
            rank_movement = baseline_state.rank - simulated_state.rank

        score_difference = None
        if baseline_state.score is not None and simulated_state.score is not None:
            score_difference = round(simulated_state.score - baseline_state.score, 2)

        name = (
            baseline_names.get(product_id)
            or simulated_names.get(product_id)
        )
        comparisons.append(
            DecisionLabProductComparison(
                product_id=product_id,
                name=name or product_id,
                baseline=baseline_state,
                simulated=simulated_state,
                rank_movement=rank_movement,
                score_difference=score_difference,
                explanation=_explain_comparison(
                    baseline_state,
                    simulated_state,
                    rank_movement,
                    score_difference,
                ),
            )
        )

    notes: list[str] = []
    if "brand_loyalty" in preference_overrides and not profile.preferred_brands:
        notes.append(
            "The brand loyalty override has no scoring effect because no preferred brands are set."
        )

    return DecisionLabResponse(
        user_id=request.user_id,
        baseline_budget=profile.max_budget,
        simulated_budget=(
            request.max_budget_override
            if request.max_budget_override is not None
            else profile.max_budget
        ),
        comparisons=comparisons,
        notes=notes,
    )
