"""Deterministic evaluation of agent results against strict shopper constraints."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.schemas import (
    EvaluationArguments,
    EvaluationResult,
    PreferenceSimulationResult,
    ProductComparisonResult,
    ShopperProfileResult,
)
from app.agent.state import AgentState, ToolExecutionRecord
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendation import (
    _matches_category,
    candidate_battery_life_hours,
    candidate_product_type,
    load_recommendation_products,
)


def _record_result(
    state: AgentState,
    index: int,
) -> ToolExecutionRecord | None:
    if index >= len(state.tool_results):
        return None
    return state.tool_results[index]


def _recommendation_result(
    record: ToolExecutionRecord,
) -> RecommendationResponse | None:
    if isinstance(record.result, RecommendationResponse):
        return record.result
    if isinstance(record.result, PreferenceSimulationResult):
        return record.result.recommendations
    return None


def _check_recommendations(
    state: AgentState,
    db: Session,
    record: ToolExecutionRecord,
    response: RecommendationResponse,
) -> EvaluationResult:
    products = response.products
    ids = [product.product_id for product in products]
    duplicates = sorted({product_id for product_id in ids if ids.count(product_id) > 1})
    if state.exclude_previous_products:
        duplicates = sorted(
            set(duplicates).union(
                set(ids).intersection(state.previously_shown_product_ids)
            )
        )

    candidates = load_recommendation_products(db, ids)
    candidates_by_id = {candidate.product_id: candidate for candidate in candidates}
    issues: list[str] = []
    missing_specifications: set[str] = set()
    intent = state.constraints

    if len(candidates_by_id) != len(products):
        issues.append("A returned product could not be resolved in the catalogue.")

    for product in products:
        candidate = candidates_by_id.get(product.product_id)
        if candidate is None:
            continue
        if intent.category and not _matches_category(candidate, intent.category):
            issues.append("A product did not match the requested category.")
        if (
            intent.max_budget_override is not None
            and product.price > intent.max_budget_override
        ):
            issues.append("A product exceeded the maximum budget.")
        if (
            intent.min_budget_override is not None
            and product.price < intent.min_budget_override
        ):
            issues.append("A product was below the minimum budget.")
        if intent.brand and (candidate.brand or "").casefold() != intent.brand.casefold():
            issues.append("A product did not match the requested brand.")
        if intent.min_rating is not None and product.rating < intent.min_rating:
            issues.append("A product was below the minimum rating.")
        if (
            intent.availability_requirement == "available"
            and candidate.availability_status != "available"
        ):
            issues.append("A product did not have verified availability.")

        attributes = candidate.attributes if isinstance(candidate.attributes, dict) else {}
        if intent.connectivity_requirement is not None:
            if attributes.get("connectivity") is None:
                missing_specifications.add("connectivity")
                issues.append("A product did not list the required connectivity.")
            elif attributes.get("connectivity") != intent.connectivity_requirement:
                issues.append("A product did not match the connectivity requirement.")
        if intent.product_type_requirement is not None:
            product_type = candidate_product_type(candidate)
            if product_type is None:
                missing_specifications.add("product_type")
                issues.append("A product did not list the required product type.")
            elif product_type != intent.product_type_requirement:
                issues.append("A product did not match the product type requirement.")

        battery_hours = candidate_battery_life_hours(candidate)
        if intent.min_battery_life_hours is not None:
            if battery_hours is None:
                missing_specifications.add("battery_life_hours")
                issues.append("A product did not list the required battery specification.")
            elif battery_hours < intent.min_battery_life_hours:
                issues.append("A product was below the minimum battery requirement.")
        if intent.require_battery_life_data and battery_hours is None:
            missing_specifications.add("battery_life_hours")
            issues.append("A product did not list the required battery specification.")

    if duplicates:
        issues.append("Duplicate or previously shown product identifiers were returned.")
    if issues:
        outcome = "constraint_violation"
        satisfied = False
    elif not products:
        outcome = "no_matches"
        satisfied = True
        for excluded in response.excluded_products:
            if excluded.reason_code == "battery_life_unlisted":
                missing_specifications.add("battery_life_hours")
            elif excluded.reason_code == "connectivity_unknown":
                missing_specifications.add("connectivity")
            elif excluded.reason_code == "product_type_unknown":
                missing_specifications.add("product_type")
    elif state.comparison_requested and not any(
        previous.tool_name == "product_comparison"
        and previous.error_code is None
        and isinstance(previous.result, ProductComparisonResult)
        for previous in state.tool_results
    ):
        outcome = "needs_comparison"
        satisfied = False
    else:
        outcome = (
            "simulated_results"
            if record.tool_name == "simulate_preferences"
            else "eligible_results"
        )
        satisfied = True

    return EvaluationResult(
        satisfied=satisfied,
        outcome=outcome,
        eligible_product_count=len(products),
        missing_specifications=sorted(missing_specifications),
        duplicate_product_ids=duplicates,
        catalogue_sources=sorted({product.catalogue_source for product in products}),
        availability_statuses=sorted(
            {product.availability_status for product in products}
        ),
        price_provenance=sorted(
            {
                "historical_illustrative"
                if product.price_is_historical
                else "catalogue_price"
                for product in products
            }
        ),
        issues=list(dict.fromkeys(issues)),
    )


def _evaluate_record(
    state: AgentState,
    db: Session,
    index: int,
) -> EvaluationResult:
    record = _record_result(state, index)
    if record is None:
        return EvaluationResult(
            satisfied=False,
            outcome="missing_result",
            issues=["The requested tool result was not available."],
        )
    if record.error_code is not None or record.result is None:
        return EvaluationResult(
            satisfied=False,
            outcome="tool_failed",
            issues=["A required tool did not complete successfully."],
        )

    response = _recommendation_result(record)
    if response is not None:
        return _check_recommendations(state, db, record, response)
    if isinstance(record.result, ProductComparisonResult):
        ids = [product.product_id for product in record.result.products]
        duplicate_ids = sorted({product_id for product_id in ids if ids.count(product_id) > 1})
        return EvaluationResult(
            satisfied=len(ids) >= 2 and not duplicate_ids,
            outcome="comparison_complete" if len(ids) >= 2 and not duplicate_ids else "constraint_violation",
            eligible_product_count=len(ids),
            missing_specifications=sorted(
                {
                    field
                    for missing in record.result.missing_fields.values()
                    for field in missing
                }
            ),
            duplicate_product_ids=duplicate_ids,
            catalogue_sources=sorted(
                {product.catalogue_source for product in record.result.products}
            ),
            availability_statuses=sorted(
                {product.availability_status for product in record.result.products}
            ),
            price_provenance=sorted(
                {
                    "historical_illustrative"
                    if product.price_is_historical
                    else "catalogue_price"
                    for product in record.result.products
                }
            ),
        )
    if isinstance(record.result, ShopperProfileResult):
        allowed = state.constraints.category is None
        return EvaluationResult(
            satisfied=allowed,
            outcome="profile_retrieved" if allowed else "missing_result",
            issues=[] if allowed else ["Profile retrieval did not address the product objective."],
        )
    return EvaluationResult(
        satisfied=False,
        outcome="missing_result",
        issues=["The tool returned a result that cannot satisfy this objective."],
    )


def evaluate_results(
    raw_arguments: BaseModel,
    state: AgentState,
    db: Session,
) -> EvaluationResult:
    arguments = EvaluationArguments.model_validate(raw_arguments)
    return _evaluate_record(state, db, arguments.result_index)
