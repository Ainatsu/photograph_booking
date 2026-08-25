"""Regression tests for conservative long-term Agent memory extraction."""

from uuid import uuid4

from backend.app.models.agent_task_session import AgentTaskSession
from backend.app.models.agent_memory import AgentMemoryEpisode, AgentUserMemory
from backend.app.services import ai_service
from backend.app.services.agent_long_term_memory_service import finalize_task_memory
from backend.app.services.agent_task_session_service import apply_task_workspace_update
from backend.app.services.agent_history_compression_service import compress_completed_task_history
from backend.app.models.ai_conversation import AIMessage


def _task(db, user_id, conversation_id, task_type="package_search", city="香港"):
    task = AgentTaskSession(
        id=str(uuid4()),
        user_id=user_id,
        conversation_id=conversation_id,
        task_type=task_type,
        status="paused",
        slots={"city": city, "styles": ["日系"]},
        form={},
    )
    db.add(task)
    db.flush()
    return task


def test_memory_candidate_requires_repeated_task_evidence(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    first = _task(db, customer_user.id, conversation.id)
    finalize_task_memory(db, task=first, outcome="paused")
    db.commit()

    memory = db.query(AgentUserMemory).filter_by(memory_type="location_interest").one()
    assert memory.status == "candidate"
    assert memory.confidence == 0.55

    second = _task(db, customer_user.id, conversation.id)
    finalize_task_memory(db, task=second, outcome="paused")
    db.commit()
    memory = db.query(AgentUserMemory).filter_by(memory_type="location_interest").one()
    assert round(memory.confidence, 2) == 0.65
    assert memory.status == "candidate"

    third = _task(db, customer_user.id, conversation.id)
    finalize_task_memory(db, task=third, outcome="paused")
    db.commit()
    memory = db.query(AgentUserMemory).filter_by(memory_type="location_interest").one()
    assert round(memory.confidence, 2) == 0.75
    assert memory.status == "active"


def test_finalize_task_memory_is_idempotent(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    task = _task(db, customer_user.id, conversation.id)
    first = finalize_task_memory(db, task=task, outcome="paused")
    second = finalize_task_memory(db, task=task, outcome="paused")
    db.commit()

    assert first.id == second.id
    assert db.query(AgentMemoryEpisode).filter_by(task_id=task.id).count() == 1
    memories = db.query(AgentUserMemory).all()
    assert memories
    assert all(memory.evidence_count == 1 for memory in memories)


def test_new_task_type_pauses_previous_task_and_keeps_episode(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    first, first_memory, first_transition = apply_task_workspace_update(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="package_search",
        status="active",
        slots={"city": "香港"},
    )
    second, second_memory, second_transition = apply_task_workspace_update(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="photographer_search",
        status="active",
        slots={"city": "北京"},
    )
    db.commit()
    assert first.id != second.id
    assert first_transition == "create"
    assert second_transition == "replace"
    assert first_memory["slots"] == {"city": "香港"}
    assert second_memory["slots"] == {"city": "北京"}
    assert first.status == "paused"
    assert db.query(AgentMemoryEpisode).filter_by(task_id=first.id).count() == 1


def test_history_compression_requires_threshold_and_terminal_task(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    task = _task(db, customer_user.id, conversation.id)
    for index in range(101):
        db.add(AIMessage(conversation_id=conversation.id, role="user", content=f"message {index}"))
    db.flush()
    result = compress_completed_task_history(db, conversation=conversation)
    db.commit()
    assert result["message_count"] == 101
    assert result["preserve_original_messages"] is True
    assert db.query(AIMessage).filter_by(conversation_id=conversation.id).count() == 101
