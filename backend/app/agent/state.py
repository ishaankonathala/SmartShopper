"""Request-scoped state for a bounded assistant agent run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid4

from app.agent.schemas import ToolSelection
from app.agent.schemas import EvaluationResult
from app.schemas.assistant import AssistantChatResponse, AssistantIntent

ToolSelectionSource = Literal[
    "planner",
    "policy",
    "fallback",
    "evaluation",
]


@dataclass
class ToolExecutionRecord:
    tool_name: str
    arguments: dict[str, object]
    result: object | None = None
    error_code: str | None = None
    executed: bool = True
    selection_source: ToolSelectionSource = "planner"


@dataclass
class AgentState:
    objective: str
    user_id: int
    conversation_context: AssistantIntent | None
    constraints: AssistantIntent
    previously_shown_product_ids: list[str]
    exclude_previous_products: bool
    request_limit: int
    comparison_requested: bool = False
    fallback_search_allowed: bool = True
    execution_id: UUID = field(default_factory=uuid4)
    current_plan: ToolSelection | None = None
    planning_failed: bool = False
    completed_steps: list[str] = field(default_factory=list)
    tool_results: list[ToolExecutionRecord] = field(default_factory=list)
    remaining_execution_budget: int = 5
    tool_execution_count: int = 0
    latest_evaluation: EvaluationResult | None = None
    execution_status: Literal[
        "completed",
        "partial",
        "fallback",
        "unavailable",
    ] = "completed"
    final_response: AssistantChatResponse | None = None

    @classmethod
    def create(
        cls,
        *,
        objective: str,
        user_id: int,
        conversation_context: AssistantIntent | None,
        constraints: AssistantIntent,
        previously_shown_product_ids: list[str],
        exclude_previous_products: bool,
        request_limit: int,
        comparison_requested: bool = False,
        fallback_search_allowed: bool = True,
    ) -> AgentState:
        return cls(
            objective=objective,
            user_id=user_id,
            conversation_context=conversation_context,
            constraints=constraints,
            previously_shown_product_ids=list(previously_shown_product_ids),
            exclude_previous_products=exclude_previous_products,
            request_limit=request_limit,
            comparison_requested=comparison_requested,
            fallback_search_allowed=fallback_search_allowed,
        )
