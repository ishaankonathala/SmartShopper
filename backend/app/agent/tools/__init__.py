"""Registered shopping-agent tools."""

from app.agent.schemas import (
    EmptyToolArguments,
    EvaluationArguments,
    EvaluationResult,
    PreferenceSimulationArguments,
    PreferenceSimulationResult,
    ProductComparisonArguments,
    ProductComparisonResult,
    ProductSearchArguments,
    ShopperProfileResult,
)
from app.agent.tool_registry import ToolDefinition, ToolRegistry
from app.schemas.recommendation import RecommendationResponse
from app.agent.tools.evaluator import evaluate_results
from app.agent.tools.preference_simulation import simulate_preferences
from app.agent.tools.product_comparison import compare_products
from app.agent.tools.product_search import search_products
from app.agent.tools.shopper_profile import get_shopper_profile


def create_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="product_search",
            description="Search both catalogues using the validated shopping constraints.",
            input_model=ProductSearchArguments,
            result_model=RecommendationResponse,
            handler=search_products,
        )
    )
    registry.register(
        ToolDefinition(
            name="product_comparison",
            description="Compare two or three previously shown or searched catalogue products.",
            input_model=ProductComparisonArguments,
            result_model=ProductComparisonResult,
            handler=compare_products,
        )
    )
    registry.register(
        ToolDefinition(
            name="get_shopper_profile",
            description="Read the current request user's saved profile and Shopper DNA without changes.",
            input_model=EmptyToolArguments,
            result_model=ShopperProfileResult,
            handler=get_shopper_profile,
        )
    )
    registry.register(
        ToolDefinition(
            name="simulate_preferences",
            description="Run hypothetical recommendations using only the user's validated temporary preferences.",
            input_model=PreferenceSimulationArguments,
            result_model=PreferenceSimulationResult,
            handler=simulate_preferences,
        )
    )
    registry.register(
        ToolDefinition(
            name="evaluate_results",
            description="Deterministically check the latest tool result against constraints and data availability.",
            input_model=EvaluationArguments,
            result_model=EvaluationResult,
            handler=evaluate_results,
        )
    )
    return registry


__all__ = ["create_tool_registry"]
