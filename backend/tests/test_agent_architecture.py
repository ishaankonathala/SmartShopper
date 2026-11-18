"""Focused tests for bounded tool selection and execution."""

import json

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.orchestrator import (
    MAX_AGENT_TOOL_EXECUTIONS,
    AgentOrchestrator,
)
from app.agent.planner import AgentPlanner
from app.agent.schemas import (
    EmptyToolArguments,
    ProductComparisonArguments,
    ProductSearchArguments,
)
from app.agent.state import AgentState, ToolExecutionRecord
from app.agent.tool_registry import InvalidToolArgumentsError, UnknownToolError
from app.agent.tools import create_tool_registry
from app.models.amazon_catalogue_product import AmazonCatalogueProduct
from app.models.product import Product
from app.models.user_profile import UserProfile
from app.schemas.assistant import AssistantChatRequest, AssistantIntent
from app.schemas.profile import ProfileCreate
from app.services import profile as profile_service


class SequencePlannerClient:
    def __init__(self, selections: list[dict[str, object]]) -> None:
        self.selections = list(selections)
        self.calls: list[list[dict[str, str]]] = []

    def complete_json(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if not self.selections:
            raise AssertionError("Unexpected additional planning iteration.")
        return json.dumps(self.selections.pop(0))


def _create_profile(
    db: Session,
    *,
    name: str = "Shopper",
    max_budget: float = 6000,
    preferred_brands: list[str] | None = None,
) -> int:
    profile = profile_service.create_profile(
        db,
        ProfileCreate(
            name=name,
            max_budget=max_budget,
            preferred_brands=preferred_brands or [],
        ),
    )
    return profile.id


def _add_curated_product(
    db: Session,
    product_id: str,
    *,
    price: float = 3500,
    connectivity: str | None = "wireless",
    battery_hours: float | None = 30,
    brand: str = "TestAudio",
) -> None:
    attributes: dict[str, object] = {
        "connectivity": connectivity,
        "comfort_score": 75,
        "portability": 80,
    }
    if battery_hours is not None:
        attributes["battery_life_hours"] = battery_hours
    db.add(
        Product(
            product_id=product_id,
            name=f"Test headphones {product_id}",
            brand=brand,
            category="Headphones",
            price=price,
            rating=4.2,
            description="Catalogue test description.",
            attributes=attributes,
            stock_quantity=5,
            is_active=True,
        )
    )
    db.flush()


def _add_amazon_product(db: Session) -> None:
    db.add(
        AmazonCatalogueProduct(
            asin="B000000001",
            title="Wireless over-ear headphones",
            store="AmazonAudio",
            category="Headphones",
            price_inr=4200,
            rating=4.3,
            rating_count=125,
            image_url="https://example.test/headphones.jpg",
            description=["Wireless playback"],
            features=["30 hours battery life", "Bluetooth wireless"],
            source_metadata={"dataset": "test"},
        )
    )
    db.flush()


def _state(
    user_id: int,
    *,
    intent: AssistantIntent | None = None,
    previous_ids: list[str] | None = None,
    comparison: bool = False,
    limit: int = 5,
    fallback_search_allowed: bool = True,
) -> AgentState:
    return AgentState.create(
        objective="Find wireless headphones and compare the eligible options.",
        user_id=user_id,
        conversation_context=None,
        constraints=intent
        or AssistantIntent(
            category="Headphones",
            max_budget_override=5000,
            connectivity_requirement="wireless",
        ),
        previously_shown_product_ids=previous_ids or [],
        exclude_previous_products=False,
        request_limit=limit,
        comparison_requested=comparison,
        fallback_search_allowed=fallback_search_allowed,
    )


def test_state_is_request_scoped_and_keeps_context_and_constraints():
    first = _state(1)
    second = _state(2)

    assert first.execution_id != second.execution_id
    assert first.tool_results == second.tool_results == []
    assert first.constraints.max_budget_override == 5000
    assert first.user_id != second.user_id


def test_registry_only_resolves_registered_tools_and_validates_arguments():
    registry = create_tool_registry()

    assert registry.get("product_search").name == "product_search"
    with pytest.raises(UnknownToolError):
        registry.get("run_sql")
    with pytest.raises(InvalidToolArgumentsError):
        registry.validate_arguments("product_search", {"limit": 26})
    with pytest.raises(ValidationError):
        ProductComparisonArguments(product_ids=["same", "same"])
    with pytest.raises(InvalidToolArgumentsError):
        registry.validate_arguments("get_shopper_profile", {"user_id": 2})


def test_product_search_reuses_recommendations_and_preserves_strict_filters(
    db_session: Session,
):
    user_id = _create_profile(db_session)
    _add_amazon_product(db_session)
    _add_curated_product(db_session, "SS-OK", price=4000)
    _add_curated_product(db_session, "SS-OVER", price=6000)
    _add_curated_product(
        db_session,
        "SS-WIRED",
        price=3000,
        connectivity="wired",
    )
    registry = create_tool_registry()

    result = registry.execute(
        "product_search",
        ProductSearchArguments(limit=5),
        _state(user_id),
        db_session,
    )

    result_by_id = {product.product_id: product for product in result.products}
    assert set(result_by_id) == {"SS-OK", "amazon:B000000001"}
    assert result_by_id["SS-OK"].catalogue_source == "curated"
    assert result_by_id["amazon:B000000001"].catalogue_source == "amazon"
    assert all(product.price <= 5000 for product in result.products)


def test_profile_brand_loyalty_is_soft_but_explicit_brand_is_strict(
    db_session: Session,
):
    user_id = _create_profile(
        db_session,
        max_budget=5000,
        preferred_brands=["UnavailablePreferredBrand"],
    )
    _add_curated_product(
        db_session,
        "SS-ALT-BRAND",
        price=4200,
        connectivity="wireless",
        brand="EligibleBrand",
    )
    _add_curated_product(
        db_session,
        "SS-SONY",
        price=4300,
        connectivity="wireless",
        brand="Sony",
    )
    registry = create_tool_registry()

    soft_preference_result = registry.execute(
        "product_search",
        ProductSearchArguments(limit=5),
        _state(
            user_id,
            intent=AssistantIntent(
                category="Headphones",
                max_budget_override=5000,
                brand_loyalty=0,
                connectivity_requirement="wireless",
            ),
        ),
        db_session,
    )
    explicit_brand_result = registry.execute(
        "product_search",
        ProductSearchArguments(limit=5),
        _state(
            user_id,
            intent=AssistantIntent(
                category="Headphones",
                max_budget_override=5000,
                brand="Sony",
                connectivity_requirement="wireless",
            ),
        ),
        db_session,
    )

    assert {product.product_id for product in soft_preference_result.products} == {
        "SS-ALT-BRAND",
        "SS-SONY",
    }
    assert [product.product_id for product in explicit_brand_result.products] == [
        "SS-SONY"
    ]


def test_comparison_uses_only_real_products_and_marks_missing_fields(
    db_session: Session,
):
    user_id = _create_profile(db_session)
    _add_curated_product(db_session, "SS-CURATED", battery_hours=None)
    _add_amazon_product(db_session)
    registry = create_tool_registry()
    state = _state(
        user_id,
        previous_ids=["SS-CURATED", "amazon:B000000001"],
    )

    comparison = registry.execute(
        "product_comparison",
        ProductComparisonArguments(
            product_ids=["SS-CURATED", "amazon:B000000001"]
        ),
        state,
        db_session,
    )

    assert [product.product_id for product in comparison.products] == [
        "SS-CURATED",
        "amazon:B000000001",
    ]
    assert comparison.products[0].catalogue_source == "curated"
    assert comparison.products[1].catalogue_source == "amazon"
    assert "battery_life_hours" in comparison.missing_fields["SS-CURATED"]
    assert "battery_life_hours" not in comparison.missing_fields["amazon:B000000001"]
    with pytest.raises(ValueError, match="only use previously shown"):
        registry.execute(
            "product_comparison",
            ProductComparisonArguments(product_ids=["SS-CURATED", "other"]),
            state,
            db_session,
        )


def test_profile_tool_is_scoped_to_request_user_and_omits_email(db_session: Session):
    first_id = _create_profile(
        db_session,
        name="First",
        max_budget=4000,
        preferred_brands=["FirstBrand"],
    )
    second_id = _create_profile(
        db_session,
        name="Second",
        max_budget=9000,
        preferred_brands=["SecondBrand"],
    )
    registry = create_tool_registry()

    first = registry.execute(
        "get_shopper_profile",
        EmptyToolArguments(),
        _state(first_id),
        db_session,
    )
    second = registry.execute(
        "get_shopper_profile",
        EmptyToolArguments(),
        _state(second_id),
        db_session,
    )

    assert first.user_id == first_id
    assert first.max_budget == 4000
    assert first.preferred_brands == ["FirstBrand"]
    assert second.user_id == second_id
    assert second.max_budget == 9000
    assert "email" not in first.model_dump()


def test_assistant_routes_explicit_profile_questions_through_registered_tool(
    db_session: Session,
):
    from app.services.assistant_response import generate_assistant_response

    user_id = _create_profile(
        db_session,
        max_budget=4800,
        preferred_brands=["QuietSound"],
    )

    class MockPlannerClient:
        def complete_json(self, messages: list[dict[str, str]]) -> str:
            if "Extract shopping intent only." in messages[0]["content"]:
                return AssistantIntent().model_dump_json()
            return json.dumps(
                {"tool_name": "get_shopper_profile", "arguments": {}}
            )

    response = generate_assistant_response(
        db_session,
        AssistantChatRequest(
            user_id=user_id,
            message="What are my saved shopping preferences?",
        ),
        groq_client=MockPlannerClient(),
    )

    assert response.kind == "answer"
    assert "maximum budget ₹4,800" in response.answer
    assert "QuietSound" in response.answer
    assert response.agent_metadata is not None
    assert response.agent_metadata.tools_executed == [
        "get_shopper_profile",
        "evaluate_results",
    ]


def test_simulation_uses_temporary_values_without_mutating_profile(db_session: Session):
    user_id = _create_profile(db_session, max_budget=3000)
    _add_curated_product(db_session, "SS-SIM", price=6000)
    profile = db_session.get(UserProfile, user_id)
    original_budget = profile.max_budget
    original_dna = dict(profile.dna.inferred_preferences)
    state = _state(
        user_id,
        intent=AssistantIntent(
            category="Headphones",
            max_budget_override=6500,
            comfort_priority=90,
            connectivity_requirement="wireless",
        ),
    )

    result = create_tool_registry().execute(
        "simulate_preferences",
        {
            "max_budget_override": 6500,
            "comfort_priority": 90,
        },
        state,
        db_session,
    )

    assert [product.product_id for product in result.recommendations.products] == [
        "SS-SIM"
    ]
    assert result.simulated_constraints.max_budget_override == 6500
    assert profile.max_budget == original_budget
    assert profile.dna.inferred_preferences == original_dna
    with pytest.raises(ValueError, match="match validated shopper"):
        create_tool_registry().execute(
            "simulate_preferences",
            {"max_budget_override": 7000},
            state,
            db_session,
        )


def test_no_matches_remain_strict_and_evaluator_reports_missing_battery_data(
    db_session: Session,
):
    user_id = _create_profile(db_session)
    _add_curated_product(db_session, "SS-NOBATTERY", battery_hours=None)
    state = _state(
        user_id,
        intent=AssistantIntent(
            category="Headphones",
            max_budget_override=5000,
            min_battery_life_hours=40,
            require_battery_life_data=True,
            connectivity_requirement="wireless",
        ),
    )
    registry = create_tool_registry()
    search = registry.execute(
        "product_search",
        {"limit": 5},
        state,
        db_session,
    )
    state.tool_results.append(
        ToolExecutionRecord(
            tool_name="product_search",
            arguments={"limit": 5},
            result=search,
        )
    )
    evaluation = registry.execute(
        "evaluate_results",
        {"result_index": 0},
        state,
        db_session,
    )

    assert search.products == []
    assert evaluation.outcome == "no_matches"
    assert "battery_life_hours" in evaluation.missing_specifications
    assert evaluation.satisfied is True


def test_evaluator_rejects_products_missing_a_strict_specification(
    db_session: Session,
):
    user_id = _create_profile(db_session)
    _add_curated_product(db_session, "SS-MISSING-SPEC", battery_hours=None)
    registry = create_tool_registry()
    search_state = _state(user_id)
    recommendations = registry.execute(
        "product_search",
        {"limit": 5},
        search_state,
        db_session,
    )
    strict_state = _state(
        user_id,
        intent=AssistantIntent(
            category="Headphones",
            max_budget_override=5000,
            min_battery_life_hours=20,
            require_battery_life_data=True,
            connectivity_requirement="wireless",
        ),
    )
    strict_state.tool_results.append(
        ToolExecutionRecord(
            tool_name="product_search",
            arguments={"limit": 5},
            result=recommendations,
        )
    )

    evaluation = registry.execute(
        "evaluate_results",
        {"result_index": 0},
        strict_state,
        db_session,
    )

    assert evaluation.outcome == "constraint_violation"
    assert evaluation.satisfied is False
    assert "battery_life_hours" in evaluation.missing_specifications


def test_orchestrator_selects_search_then_comparison_and_evaluates_both(
    db_session: Session,
):
    user_id = _create_profile(db_session)
    _add_curated_product(db_session, "SS-A")
    _add_curated_product(db_session, "SS-B", price=3900)
    client = SequencePlannerClient(
        [
            {"tool_name": "product_search", "arguments": {"limit": 5}},
        ]
    )
    state = _state(user_id, comparison=True)

    result = AgentOrchestrator(client).run(state, db_session)

    assert result.recommendation_response is not None
    assert result.comparison_result is not None
    assert result.evaluation_result.outcome == "comparison_complete"
    assert result.state.tool_execution_count == 4
    assert result.state.tool_execution_count <= MAX_AGENT_TOOL_EXECUTIONS
    assert [record.tool_name for record in result.state.tool_results] == [
        "product_search",
        "evaluate_results",
        "product_comparison",
        "evaluate_results",
    ]
    assert len(client.calls) == 1


def test_planner_receives_product_and_comparison_observations(
    db_session: Session,
):
    user_id = _create_profile(db_session)
    _add_curated_product(db_session, "SS-NO-BATTERY", battery_hours=None)
    _add_curated_product(db_session, "SS-WITH-BATTERY", price=3900)
    state = _state(user_id, comparison=True)
    registry = create_tool_registry()
    search = registry.execute("product_search", {"limit": 5}, state, db_session)
    state.tool_results.append(
        ToolExecutionRecord(
            tool_name="product_search",
            arguments={"limit": 5},
            result=search,
        )
    )
    product_ids = [product.product_id for product in search.products]
    comparison = registry.execute(
        "product_comparison",
        {"product_ids": product_ids[:2]},
        state,
        db_session,
    )
    state.tool_results.append(
        ToolExecutionRecord(
            tool_name="product_comparison",
            arguments={"product_ids": product_ids[:2]},
            result=comparison,
            selection_source="policy",
        )
    )

    class CapturingPlannerClient:
        messages: list[dict[str, str]]

        def complete_json(self, messages: list[dict[str, str]]) -> str:
            self.messages = messages
            return json.dumps(
                {"tool_name": "evaluate_results", "arguments": {"result_index": 1}}
            )

    client = CapturingPlannerClient()
    AgentPlanner(client, registry).select_next_tool(state)
    observations = json.loads(client.messages[1]["content"])["tool_observations"]

    assert observations[0]["products"][0]["product_id"] == product_ids[0]
    comparison_observation = observations[1]
    missing_battery_product = next(
        product
        for product in comparison_observation["products"]
        if product["product_id"] == "SS-NO-BATTERY"
    )
    assert missing_battery_product["fields"]["price"] is not None
    assert (
        "battery_life_hours"
        in comparison_observation["missing_fields"]["SS-NO-BATTERY"]
    )
    assert missing_battery_product["fields"]["battery_life_hours"] is None


def test_duplicate_actions_are_prevented_and_execution_budget_is_bounded(
    db_session: Session,
):
    user_id = _create_profile(db_session)
    _add_curated_product(db_session, "SS-ONLY")
    duplicate_client = SequencePlannerClient(
        [
            {"tool_name": "product_search", "arguments": {"limit": 5}},
            {"tool_name": "product_search", "arguments": {"limit": 5}},
        ]
    )
    duplicate_result = AgentOrchestrator(duplicate_client).run(
        _state(user_id, comparison=True),
        db_session,
    )
    assert duplicate_result.state.tool_execution_count == 2
    assert duplicate_result.state.execution_status == "partial"
    assert "Repeated tool call prevented." in duplicate_result.state.completed_steps

    _add_curated_product(db_session, "SS-TWO")
    _add_curated_product(db_session, "SS-THREE")
    for number in range(4, 10):
        _add_curated_product(db_session, f"SS-{number:02d}")
    bounded_client = SequencePlannerClient(
        [
            {"tool_name": "product_search", "arguments": {"limit": 5}},
            {"tool_name": "evaluate_results", "arguments": {"result_index": 1}},
            {"tool_name": "product_search", "arguments": {"limit": 4}},
        ]
    )
    bounded_result = AgentOrchestrator(bounded_client).run(
        _state(user_id, comparison=True),
        db_session,
    )
    assert bounded_result.state.tool_execution_count <= MAX_AGENT_TOOL_EXECUTIONS
    assert bounded_result.state.execution_status == "completed"
    assert len(bounded_client.calls) == 1


def test_tool_failures_are_reported_without_crashing_or_exposing_details(
    db_session: Session,
):
    client = SequencePlannerClient(
        [
            {"tool_name": "get_shopper_profile", "arguments": {}},
            {"tool_name": "get_shopper_profile", "arguments": {}},
        ]
    )
    state = _state(999, fallback_search_allowed=False)

    result = AgentOrchestrator(client).run(state, db_session)

    assert result.state.execution_status == "partial"
    assert result.state.tool_results[0].error_code == "tool_execution_failed"
    assert result.state.tool_execution_count == 2
    assert "999" not in result.metadata.plan_summary
    failed_event = next(
        event
        for event in result.metadata.events
        if event.kind == "tool_execution" and event.status == "failed"
    )
    assert "999" not in failed_event.summary


def test_existing_assistant_api_returns_optional_agent_metadata(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import assistant_response as assistant_response_service

    profile_id = _create_profile(db_session)
    _add_curated_product(db_session, "SS-API")

    class MockGroqClient:
        def complete_json(self, messages: list[dict[str, str]]) -> str:
            system = messages[0]["content"]
            if "Extract shopping intent only." in system:
                return json.dumps(
                    {
                        "category": "Headphones",
                        "max_budget_override": 5000,
                        "min_budget_override": None,
                        "brand": None,
                        "min_rating": None,
                        "min_battery_life_hours": None,
                        "require_battery_life_data": None,
                        "availability_requirement": None,
                        "comfort_priority": None,
                        "brand_loyalty": None,
                        "battery_life_priority": None,
                        "portability_priority": None,
                        "connectivity_requirement": "wireless",
                        "product_type_requirement": None,
                        "unsupported_requirements": [],
                    }
                )
            if "Select exactly one next action from the registered tools." in system:
                return json.dumps(
                    {
                        "tool_name": "product_search",
                        "arguments": {"limit": 5},
                    }
                )
            return "{}"

    monkeypatch.setattr(
        assistant_response_service,
        "GroqClient",
        MockGroqClient,
    )
    response = client.post(
        "/api/assistant/chat",
        json={
            "user_id": profile_id,
            "message": "Wireless headphones under ₹5,000",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"][0]["product_id"] == "SS-API"
    assert body["agent_metadata"]["status"] == "completed"
    assert body["agent_metadata"]["tool_execution_count"] == 2
    assert body["agent_metadata"]["tools_executed"] == [
        "product_search",
        "evaluate_results",
    ]
    events = body["agent_metadata"]["events"]
    assert [event["kind"] for event in events] == [
        "understanding",
        "planning",
        "selection",
        "tool_execution",
        "evaluation",
        "completion",
    ]
    assert events[3]["status"] == "completed"
    assert "Test headphones SS-API" in events[3]["summary"]
    assert events[-1]["status"] == "completed"
