"""Bounded planning, registered tool execution, and deterministic evaluation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Final

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.planner import AgentPlanner
from app.agent.schemas import (
    EvaluationArguments,
    EvaluationResult,
    PreferenceSimulationResult,
    ProductComparisonResult,
    ShopperProfileResult,
    ToolSelection,
)
from app.agent.state import AgentState, ToolExecutionRecord, ToolSelectionSource
from app.agent.tool_registry import (
    InvalidToolArgumentsError,
    ToolRegistry,
    UnknownToolError,
)
from app.agent.tools import create_tool_registry
from app.schemas.assistant import AgentActivityEvent, AgentExecutionMetadata
from app.schemas.recommendation import RecommendationResponse
from app.services.groq_client import GroqClient, GroqClientError

MAX_AGENT_TOOL_EXECUTIONS: Final[int] = 5
MAX_AGENT_SELECTION_ITERATIONS: Final[int] = 3
_TOOL_TITLES = {
    "product_search": "Product Search",
    "product_comparison": "Product Comparison",
    "get_shopper_profile": "Shopper Profile",
    "simulate_preferences": "Preference Simulation",
    "evaluate_results": "Recommendation Evaluation",
}
_TOOL_ACTIVITY = {
    "product_search": "Searching eligible catalogue products.",
    "product_comparison": "Comparing available catalogue fields.",
    "get_shopper_profile": "Checking your saved shopping preferences.",
    "simulate_preferences": "Simulating temporary preference changes.",
    "evaluate_results": "Checking results against your requirements.",
}
logger = logging.getLogger(__name__)


def _intent_summary(state: AgentState) -> str:
    intent = state.constraints
    constraints: list[str] = []
    if intent.category:
        constraints.append(f"category {intent.category}")
    if intent.max_budget_override is not None:
        constraints.append(f"maximum budget ₹{intent.max_budget_override:,.0f}")
    if intent.min_budget_override is not None:
        constraints.append(f"minimum budget ₹{intent.min_budget_override:,.0f}")
    if intent.brand:
        constraints.append(f"brand {intent.brand}")
    if intent.min_rating is not None:
        constraints.append(f"minimum rating {intent.min_rating:g}/5")
    if intent.connectivity_requirement:
        constraints.append(f"{intent.connectivity_requirement} connectivity")
    if intent.product_type_requirement:
        constraints.append(f"product type {intent.product_type_requirement}")
    if intent.min_battery_life_hours is not None:
        constraints.append(
            f"at least {intent.min_battery_life_hours:g} hours battery life"
        )
    if intent.availability_requirement:
        constraints.append("verified availability")
    summary = (
        "Applied constraints: " + "; ".join(constraints) + "."
        if constraints
        else "No structured product constraints were available."
    )
    if state.comparison_requested:
        summary += " A product comparison was requested."
    if state.previously_shown_product_ids:
        summary += (
            f" Considering {len(state.previously_shown_product_ids)} "
            "previously shown product(s)."
        )
    return summary[:400]


def _tool_result_summary(record: ToolExecutionRecord) -> str:
    result = record.result
    if record.error_code is not None or not record.executed:
        return "The tool did not complete successfully; error details were not exposed."
    if isinstance(result, RecommendationResponse):
        products = [
            f"{product.name} (₹{product.price:,.0f}, rating {product.rating:g}/5)"
            for product in result.products[:3]
        ]
        summary = f"Returned {len(result.products)} eligible product(s)."
        if products:
            summary += " Shortlist: " + "; ".join(products) + "."
        if result.has_more:
            summary += " More eligible options are available."
        if any(product.catalogue_source == "amazon" for product in result.products):
            summary += (
                " Amazon prices are historical and illustrative; availability is unverified."
            )
        return summary[:400]
    if isinstance(result, PreferenceSimulationResult):
        return (
            f"Simulated preferences and returned "
            f"{len(result.recommendations.products)} eligible product(s). "
            "Saved profile and Shopper DNA were not changed."
        )
    if isinstance(result, ProductComparisonResult):
        products: list[str] = []
        for product in result.products:
            values: list[str] = []
            for field, label in (
                ("price", "₹"),
                ("rating", "rating "),
                ("battery_life_hours", "battery "),
                ("comfort_score", "comfort "),
                ("portability", "portability "),
            ):
                value = product.fields.get(field)
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                if field == "price":
                    values.append(f"₹{value:,.0f}")
                elif field == "rating":
                    values.append(f"rating {value:g}/5")
                elif field == "battery_life_hours":
                    values.append(f"battery {value:g} h")
                else:
                    values.append(f"{label}{value:g}/100")
            detail = f" ({', '.join(values)})" if values else ""
            products.append(f"{product.name}{detail}")
        missing_fields = sorted(
            {
                field.replace("_", " ")
                for fields in result.missing_fields.values()
                for field in fields
            }
        )
        summary = f"Compared {len(result.products)} catalogue product(s)"
        if products:
            summary += ": " + "; ".join(products)
        if missing_fields:
            summary += ". Unavailable catalogue fields: " + ", ".join(missing_fields)
        return summary[:397] + "..." if len(summary) > 400 else summary + "."
    if isinstance(result, ShopperProfileResult):
        return (
            "Retrieved the saved profile and "
            f"{len(result.inferred_preferences)} Shopper DNA preference dimension(s)."
        )
    if isinstance(result, EvaluationResult):
        if result.outcome == "no_matches":
            summary = "No products met every filter; no strict constraint was relaxed."
            if result.missing_specifications:
                missing = ", ".join(
                    field.replace("_", " ")
                    for field in result.missing_specifications
                )
                summary += f" Missing catalogue data: {missing}."
            return summary
        if result.outcome == "needs_comparison":
            return (
                f"Validated {result.eligible_product_count} eligible product(s); "
                "a requested comparison is still needed."
            )
        if result.outcome == "constraint_violation":
            details = list(result.issues[:2])
            if result.missing_specifications:
                missing = ", ".join(
                    field.replace("_", " ")
                    for field in result.missing_specifications
                )
                details.append(f"Missing catalogue data: {missing}.")
            return (
                "The returned products did not pass all strict constraint checks. "
                + " ".join(details)
            )[:400]
        if result.outcome == "comparison_complete":
            return "The comparison passed duplicate and catalogue checks."
        if result.outcome == "eligible_results":
            return (
                f"{result.eligible_product_count} eligible product(s) passed "
                "the strict catalogue checks."
            )
        if result.outcome == "profile_retrieved":
            return "The profile result was verified for this request."
        if result.outcome == "simulated_results":
            return "The temporary preference simulation passed catalogue checks."
        return f"Evaluation outcome: {result.outcome.replace('_', ' ')}."
    return "The tool completed without a displayable result summary."


def _activity_events(state: AgentState) -> list[AgentActivityEvent]:
    events = [
        AgentActivityEvent(
            sequence=1,
            kind="understanding",
            title="Understanding the request",
            status="completed",
            summary=_intent_summary(state),
            succeeded=True,
        )
    ]
    selected_records = [
        record
        for record in state.tool_results
        if record.selection_source != "evaluation"
    ]
    events.append(
        AgentActivityEvent(
            sequence=2,
            kind="planning",
            title="Planning the task",
            status=(
                "partial"
                if state.planning_failed or not selected_records
                else "completed"
            ),
            summary=(
                "The planner could not complete; bounded fallback handling was used where safe."
                if state.planning_failed
                else (
                    f"Selected {len(selected_records)} bounded action(s) using "
                    "the validated request and prior tool results."
                    if selected_records
                    else "No tool action was selected for this request."
                )
            ),
            succeeded=not state.planning_failed and bool(selected_records),
        )
    )

    for record in state.tool_results:
        title = _TOOL_TITLES.get(record.tool_name, "Agent Tool")
        succeeded = record.executed and record.error_code is None
        if record.selection_source != "evaluation":
            source_summary = {
                "planner": "Selected by the planner from the registered tools.",
                "policy": "Selected to satisfy an explicit comparison request.",
                "fallback": "Selected by the deterministic safe fallback.",
            }.get(record.selection_source, "Selected from the registered tools.")
            invalid_arguments = record.error_code == "invalid_arguments"
            events.append(
                AgentActivityEvent(
                    sequence=len(events) + 1,
                    kind="selection",
                    title=f"Selected: {title}",
                    status="failed" if invalid_arguments else "completed",
                    summary=(
                        "The selection was rejected because its arguments failed validation."
                        if invalid_arguments
                        else source_summary
                    ),
                    tool_name=record.tool_name,
                    succeeded=not invalid_arguments,
                )
            )
        if record.executed:
            is_evaluation = record.tool_name == "evaluate_results"
            purpose = _TOOL_ACTIVITY.get(
                record.tool_name,
                "Running the registered agent tool.",
            )
            result_summary = _tool_result_summary(record)
            summary = f"{purpose} {result_summary}"
            if len(summary) > 400:
                summary = summary[:397] + "..."
            event_status = "completed" if succeeded else "failed"
            if is_evaluation and isinstance(record.result, EvaluationResult):
                if record.result.outcome == "constraint_violation":
                    event_status = "failed"
                    succeeded = False
                elif record.result.outcome in {
                    "needs_comparison",
                    "missing_result",
                    "tool_failed",
                }:
                    event_status = "partial"
                    succeeded = False
            events.append(
                AgentActivityEvent(
                    sequence=len(events) + 1,
                    kind="evaluation" if is_evaluation else "tool_execution",
                    title=title,
                    status=event_status,
                    summary=summary,
                    tool_name=record.tool_name,
                    succeeded=succeeded,
                )
            )

    evaluation = state.latest_evaluation
    if evaluation is not None and evaluation.outcome == "no_matches":
        completion_status = "completed"
        completion_summary = (
            "The search completed; no eligible product matched the current catalogue and strict filters."
        )
        completion_succeeded = True
    elif state.execution_status == "unavailable":
        completion_status = "failed"
        completion_summary = "No safe agent action could be completed."
        completion_succeeded = False
    elif state.execution_status in {"partial", "fallback"}:
        completion_status = "partial"
        completion_summary = (
            "The request completed with a safe fallback or incomplete agent check."
        )
        completion_succeeded = False
    else:
        completion_status = "completed"
        completion_summary = "The catalogue-checked result is ready."
        completion_succeeded = True
    events.append(
        AgentActivityEvent(
            sequence=len(events) + 1,
            kind="completion",
            title="Recommendation ready",
            status=completion_status,
            summary=completion_summary,
            succeeded=completion_succeeded,
        )
    )
    return events


@dataclass(frozen=True)
class AgentRunResult:
    state: AgentState
    recommendation_response: RecommendationResponse | None
    comparison_result: ProductComparisonResult | None
    profile_result: ShopperProfileResult | None
    simulation_result: PreferenceSimulationResult | None
    evaluation_result: EvaluationResult | None

    @property
    def metadata(self) -> AgentExecutionMetadata:
        activities = list(
            dict.fromkeys(
                _TOOL_ACTIVITY[record.tool_name]
                for record in self.state.tool_results
                if record.executed and record.tool_name in _TOOL_ACTIVITY
            )
        )
        summary = " ".join(activities) or "Using the existing safe fallback."
        return AgentExecutionMetadata(
            execution_id=str(self.state.execution_id),
            status=self.state.execution_status,
            plan_summary=summary,
            tools_executed=[
                record.tool_name
                for record in self.state.tool_results
                if record.executed
            ],
            tool_execution_count=self.state.tool_execution_count,
            evaluation_outcome=(
                self.state.latest_evaluation.outcome
                if self.state.latest_evaluation is not None
                else "not_evaluated"
            ),
            activity=activities,
            events=_activity_events(self.state),
        )


class AgentOrchestrator:
    def __init__(
        self,
        client: GroqClient,
        registry: ToolRegistry | None = None,
    ) -> None:
        self._registry = registry or create_tool_registry()
        self._planner = AgentPlanner(client, self._registry)

    def run(self, state: AgentState, db: Session) -> AgentRunResult:
        state.remaining_execution_budget = min(
            state.remaining_execution_budget,
            MAX_AGENT_TOOL_EXECUTIONS,
        )
        seen_calls: set[str] = set()

        for _ in range(MAX_AGENT_SELECTION_ITERATIONS):
            if state.remaining_execution_budget <= 0:
                state.execution_status = "partial"
                break

            try:
                policy_selection = self._comparison_selection(state)
                if policy_selection is not None:
                    selection = policy_selection
                    selection_source = "policy"
                else:
                    selection = self._planner.select_next_tool(state)
                    selection_source = "planner"
            except (GroqClientError, ValidationError, ValueError, TypeError) as error:
                state.planning_failed = True
                logger.warning(
                    "Agent planning unavailable (%s).",
                    type(error).__name__,
                )
                state.execution_status = "fallback"
                self._run_safe_fallback(state, db, seen_calls)
                break

            state.current_plan = selection
            fingerprint = self._fingerprint(selection)
            if fingerprint in seen_calls:
                state.execution_status = "partial"
                state.completed_steps.append("Repeated tool call prevented.")
                break
            seen_calls.add(fingerprint)

            if state.remaining_execution_budget == 1 and selection.tool_name != "evaluate_results":
                state.execution_status = "partial"
                state.completed_steps.append("Execution budget reserved for evaluation.")
                break

            record_index = self._execute_selection(
                selection,
                state,
                db,
                selection_source=selection_source,
            )
            if record_index is None:
                continue
            record = state.tool_results[record_index]
            if selection.tool_name == "evaluate_results":
                if isinstance(record.result, EvaluationResult):
                    state.latest_evaluation = record.result
                    if record.result.satisfied:
                        state.execution_status = "completed"
                        break
                    if record.result.outcome == "constraint_violation":
                        state.execution_status = "partial"
                        break
                continue

            if state.remaining_execution_budget <= 0:
                state.execution_status = "partial"
                break
            evaluation_index = self._execute_selection(
                ToolSelection(
                    tool_name="evaluate_results",
                    arguments={"result_index": record_index},
                ),
                state,
                db,
                selection_source="evaluation",
            )
            evaluation_selection = ToolSelection(
                tool_name="evaluate_results",
                arguments={"result_index": record_index},
            )
            seen_calls.add(self._fingerprint(evaluation_selection))
            if evaluation_index is None:
                state.execution_status = "partial"
                break
            evaluation = state.tool_results[evaluation_index].result
            if isinstance(evaluation, EvaluationResult):
                state.latest_evaluation = evaluation
                if evaluation.satisfied:
                    state.execution_status = "completed"
                    break
                if evaluation.outcome == "constraint_violation":
                    state.execution_status = "partial"
                    break

        else:
            if state.execution_status == "completed":
                state.execution_status = "partial"

        if (
            state.fallback_search_allowed
            and state.constraints.category is not None
            and not self._has_recommendation_result(state)
            and state.remaining_execution_budget >= 2
        ):
            state.execution_status = "fallback"
            self._run_safe_fallback(state, db, seen_calls)

        if (
            state.execution_status == "completed"
            and state.latest_evaluation is not None
            and not state.latest_evaluation.satisfied
        ):
            state.execution_status = "partial"

        return self._result(state)

    @staticmethod
    def _has_recommendation_result(state: AgentState) -> bool:
        return any(
            isinstance(record.result, RecommendationResponse)
            or isinstance(record.result, PreferenceSimulationResult)
            for record in state.tool_results
        )

    @staticmethod
    def _comparison_selection(state: AgentState) -> ToolSelection | None:
        if not state.comparison_requested or any(
            record.error_code is None
            and isinstance(record.result, ProductComparisonResult)
            for record in state.tool_results
        ):
            return None

        product_ids: list[str] = []
        for record in reversed(state.tool_results):
            if isinstance(record.result, RecommendationResponse):
                product_ids = [
                    product.product_id for product in record.result.products
                ]
                break
            if isinstance(record.result, PreferenceSimulationResult):
                product_ids = [
                    product.product_id
                    for product in record.result.recommendations.products
                ]
                break
        if len(product_ids) < 2 and not state.fallback_search_allowed:
            product_ids = state.previously_shown_product_ids
        if len(product_ids) < 2:
            return None
        return ToolSelection(
            tool_name="product_comparison",
            arguments={"product_ids": product_ids[:2]},
        )

    @staticmethod
    def _fingerprint(selection: ToolSelection) -> str:
        return selection.tool_name + ":" + json.dumps(
            selection.arguments,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _execute_selection(
        self,
        selection: ToolSelection,
        state: AgentState,
        db: Session,
        *,
        selection_source: ToolSelectionSource = "planner",
    ) -> int | None:
        try:
            arguments = self._registry.validate_arguments(
                selection.tool_name,
                selection.arguments,
            )
        except (InvalidToolArgumentsError, UnknownToolError):
            state.tool_results.append(
                ToolExecutionRecord(
                    tool_name=selection.tool_name,
                    arguments={},
                    error_code="invalid_arguments",
                    executed=False,
                    selection_source=selection_source,
                )
            )
            state.completed_steps.append("Invalid tool arguments were rejected.")
            return None

        if state.remaining_execution_budget <= 0:
            state.execution_status = "partial"
            return None

        state.remaining_execution_budget -= 1
        state.tool_execution_count += 1
        normalized_arguments = arguments.model_dump(mode="json")
        try:
            result = self._registry.execute(
                selection.tool_name,
                arguments,
                state,
                db,
            )
        except Exception as error:
            logger.error(
                "Agent tool %s failed (%s).",
                selection.tool_name,
                type(error).__name__,
            )
            state.tool_results.append(
                ToolExecutionRecord(
                    tool_name=selection.tool_name,
                    arguments=normalized_arguments,
                    error_code="tool_execution_failed",
                    selection_source=selection_source,
                )
            )
        else:
            state.tool_results.append(
                ToolExecutionRecord(
                    tool_name=selection.tool_name,
                    arguments=normalized_arguments,
                    result=result,
                    selection_source=selection_source,
                )
            )
        state.completed_steps.append(_TOOL_ACTIVITY[selection.tool_name])
        return len(state.tool_results) - 1

    def _run_safe_fallback(
        self,
        state: AgentState,
        db: Session,
        seen_calls: set[str],
    ) -> None:
        if not state.fallback_search_allowed or state.constraints.category is None:
            state.execution_status = "unavailable"
            return
        selection = ToolSelection(
            tool_name="product_search",
            arguments={"limit": state.request_limit},
        )
        fingerprint = self._fingerprint(selection)
        if fingerprint in seen_calls or state.remaining_execution_budget < 2:
            state.execution_status = "partial"
            return
        seen_calls.add(fingerprint)
        record_index = self._execute_selection(
            selection,
            state,
            db,
            selection_source="fallback",
        )
        if record_index is None or state.remaining_execution_budget <= 0:
            state.execution_status = "partial"
            return
        evaluation_index = self._execute_selection(
            ToolSelection(
                tool_name="evaluate_results",
                arguments={"result_index": record_index},
            ),
            state,
            db,
            selection_source="evaluation",
        )
        if evaluation_index is not None:
            result = state.tool_results[evaluation_index].result
            if isinstance(result, EvaluationResult):
                state.latest_evaluation = result
                if result.satisfied:
                    state.execution_status = "fallback"
                    return
                if result.outcome == "constraint_violation":
                    state.execution_status = "partial"
                    return
        comparison_selection = self._comparison_selection(state)
        if comparison_selection is not None and state.remaining_execution_budget >= 2:
            comparison_index = self._execute_selection(
                comparison_selection,
                state,
                db,
                selection_source="policy",
            )
            if comparison_index is not None and state.remaining_execution_budget > 0:
                comparison_evaluation_index = self._execute_selection(
                    ToolSelection(
                        tool_name="evaluate_results",
                        arguments={"result_index": comparison_index},
                    ),
                    state,
                    db,
                    selection_source="evaluation",
                )
                if comparison_evaluation_index is not None:
                    result = state.tool_results[comparison_evaluation_index].result
                    if isinstance(result, EvaluationResult):
                        state.latest_evaluation = result
                        if result.satisfied:
                            state.execution_status = "fallback"
                            return
        state.execution_status = "partial"

    @staticmethod
    def _result(state: AgentState) -> AgentRunResult:
        recommendation_response = None
        recommendation_result_index = None
        comparison_result = None
        profile_result = None
        simulation_result = None
        for index, record in enumerate(state.tool_results):
            if record.error_code is not None:
                continue
            if isinstance(record.result, RecommendationResponse):
                recommendation_response = record.result
                recommendation_result_index = index
            elif isinstance(record.result, ProductComparisonResult):
                comparison_result = record.result
            elif isinstance(record.result, ShopperProfileResult):
                profile_result = record.result
            elif isinstance(record.result, PreferenceSimulationResult):
                simulation_result = record.result
                recommendation_response = record.result.recommendations
                recommendation_result_index = index

        def passes_recommendation_checks(result: EvaluationResult) -> bool:
            return (
                result.satisfied
                and result.outcome in {"eligible_results", "simulated_results"}
            ) or (
                state.comparison_requested
                and result.outcome == "needs_comparison"
                and not result.issues
            )

        recommendation_was_validated = False
        latest_evaluation = state.latest_evaluation
        if (
            recommendation_result_index is not None
            and latest_evaluation is not None
            and latest_evaluation.outcome == "no_matches"
            and recommendation_response is not None
            and not recommendation_response.products
        ):
            recommendation_was_validated = True
        elif recommendation_result_index is not None and latest_evaluation is not None:
            evaluations_for_recommendation = [
                record.result
                for record in state.tool_results
                if record.tool_name == "evaluate_results"
                and record.arguments.get("result_index") == recommendation_result_index
                and isinstance(record.result, EvaluationResult)
            ]
            if latest_evaluation.outcome in {"eligible_results", "simulated_results"}:
                recommendation_was_validated = any(
                    result is latest_evaluation
                    and passes_recommendation_checks(result)
                    for result in evaluations_for_recommendation
                )
            elif latest_evaluation.outcome == "comparison_complete":
                recommendation_was_validated = any(
                    passes_recommendation_checks(result)
                    for result in evaluations_for_recommendation
                )

        if not recommendation_was_validated:
            recommendation_response = None
            simulation_result = None

        return AgentRunResult(
            state=state,
            recommendation_response=recommendation_response,
            comparison_result=comparison_result,
            profile_result=profile_result,
            simulation_result=simulation_result,
            evaluation_result=state.latest_evaluation,
        )
