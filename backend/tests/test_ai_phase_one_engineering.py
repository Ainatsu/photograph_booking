from pathlib import Path

import pytest

from backend.app.models.ai_conversation import AgentActionLog, AgentRetrievalLog
from backend.app.services import ai_service
from backend.app.services.ai_agent_contracts import (
    AgentIntent,
    normalize_agent_metadata,
)
from backend.app.services.ai_agent_tool_service import follow_photographer
from backend.app.services.ai_evaluation_service import evaluate_intent_cases, load_golden_cases
from backend.app.services.ai_tool_policy_service import ToolPolicyError, prepare_tool_execution


class StaticProvider:
    async def chat(self, messages, *, temperature=None, response_format=None):
        return {
            "content": "已根据站内资源完成检索。",
            "metadata": {"model": {"provider": "test", "model": "static"}},
        }


def test_agent_intent_is_pydantic_contract():
    intent = AgentIntent(
        intent="resource_search",
        route="retrieval",
        slots={"city": "深圳", "budget_max": 1500, "custom_slot": "kept"},
    )

    payload = intent.as_dict()

    assert payload["schema_version"] == "agent_intent_v2"
    assert payload["slots"]["budget_max"] == 1500
    assert payload["slots"]["custom_slot"] == "kept"


def test_workflow_metadata_is_validated_and_versioned():
    metadata = normalize_agent_metadata({
        "task_state": {
            "task_type": "create_booking",
            "status": "awaiting_confirmation",
            "slots": {"photographer_id": 2, "date": "08-15"},
            "pending_action": {
                "tool": "create_booking",
                "input": {"photographer_id": 2},
            },
        }
    })

    assert metadata["workflow_schema_version"] == "agent_workflow_v1"
    assert metadata["task_state"]["schema_version"] == "agent_workflow_v1"
    assert metadata["task_state"]["status"] == "awaiting_confirmation"


def test_tool_policy_blocks_unconfirmed_write(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)

    with pytest.raises(ToolPolicyError, match="confirmation_required"):
        prepare_tool_execution(
            db,
            tool_name="follow_photographer",
            tool_input={"photographer_id": 2},
            user_id=customer_user.id,
            conversation_id=conversation.id,
            confirmation_count=0,
        )


def test_tool_idempotency_replays_existing_action(
    db,
    customer_user,
    photographer_user,
):
    conversation = ai_service.create_conversation(db, customer_user.id)

    first = follow_photographer(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        message_id=None,
        photographer_id=photographer_user.id,
    )
    second = follow_photographer(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        message_id=None,
        photographer_id=photographer_user.id,
    )

    assert first["status"] == "success"
    assert second["policy"]["replayed"] is True
    assert db.query(AgentActionLog).filter_by(tool_name="follow_photographer").count() == 1


@pytest.mark.asyncio
async def test_retrieval_run_is_logged(monkeypatch, db, customer_user, photographer_profile):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: StaticProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我找日系摄影师",
    )

    log = db.query(AgentRetrievalLog).one()
    assert log.intent["intent"] == "resource_search"
    assert log.result_counts["photographers"] >= 1
    assert log.latency_ms >= 0


def test_phase_one_golden_dataset_meets_threshold():
    dataset = Path(__file__).resolve().parents[1] / "evals" / "agent_phase1_golden.jsonl"
    report = evaluate_intent_cases(load_golden_cases(dataset))

    assert report["accuracy"] >= 0.90, report
