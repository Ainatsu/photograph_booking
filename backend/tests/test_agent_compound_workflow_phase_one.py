import pytest
from pydantic import ValidationError

from backend.app.services.ai_agent_contracts import TaskPlan, TaskStep
from backend.app.services.ai_orchestrator_service import (
    recognize_intent_by_rules,
    should_run_retrieval,
)


def test_search_then_inspire_is_fixed_portfolio_chain():
    intent = recognize_intent_by_rules("搜索日系作品并创建灵感")
    assert intent.intent == "compound_workflow"
    assert intent.slots["resource_types"] == ["portfolio_items"]
    assert should_run_retrieval(intent)
    assert intent.missing_slots == []


def test_inspiration_without_style_waits_for_user():
    intent = recognize_intent_by_rules("帮我创建灵感")
    assert intent.intent == "create_inspiration_flow"
    assert intent.missing_slots == ["reference_images"]


def test_plan_rejects_reordered_or_untrusted_steps():
    with pytest.raises(ValidationError):
        TaskPlan(
            workflow_type="search_then_inspire",
            steps=[
                TaskStep(id="inspire", type="create_inspiration", order=1),
                TaskStep(id="search", type="resource_search", order=2),
            ],
        )
