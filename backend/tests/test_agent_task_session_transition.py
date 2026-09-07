from backend.app.models.agent_memory import AgentMemoryEpisode
from backend.app.models.agent_task_session import AgentTaskSession
from backend.app.services import ai_service
from backend.app.services import agent_working_memory_service as memory_service
from backend.app.services.agent_task_session_service import (
    apply_task_workspace_update,
    load_active_task_workspace,
    sync_working_memory,
)


def test_transition_creates_durable_task_before_workspace(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)

    task, memory, transition = apply_task_workspace_update(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="package_search",
        slots={"city": "大理"},
    )

    assert transition == "create"
    assert memory["task_id"] == task.id
    assert db.query(AgentTaskSession).filter_by(id=memory["task_id"]).one()


def test_transition_replaces_without_copying_old_slots(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    old_task, _, _ = apply_task_workspace_update(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="portfolio_item_search",
        slots={"styles": ["日系", "胶片"], "makeup": True},
    )

    new_task, memory, transition = apply_task_workspace_update(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="package_search",
        slots={"city": "大理"},
    )
    db.commit()

    assert transition == "replace"
    assert new_task.id != old_task.id
    assert memory["slots"] == {"city": "大理"}
    assert old_task.status == "paused"
    assert db.query(AgentMemoryEpisode).filter_by(task_id=old_task.id).count() == 1


def test_redis_loss_restores_only_active_task(db, customer_user, monkeypatch):
    conversation = ai_service.create_conversation(db, customer_user.id)
    values = {}
    monkeypatch.setattr(memory_service, "cache_get", values.get)
    monkeypatch.setattr(
        memory_service, "cache_set",
        lambda key, value, ttl=None: values.__setitem__(key, value),
    )
    monkeypatch.setattr(
        memory_service, "cache_delete",
        lambda *keys: [values.pop(key, None) for key in keys],
    )

    task, _, _ = apply_task_workspace_update(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="package_search",
        slots={"city": "大理"},
    )
    values.clear()

    restored = load_active_task_workspace(
        db, user_id=customer_user.id, conversation_id=conversation.id,
    )

    assert restored["task_id"] == task.id
    assert restored["slots"] == {"city": "大理"}


def test_sync_rejects_stale_workspace_revision(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    task, memory, _ = apply_task_workspace_update(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="package_search",
        slots={"city": "大理"},
    )
    db.commit()
    stale = dict(memory)
    stale["revision"] = 0
    task.revision = 2
    db.flush()
    try:
        sync_working_memory(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            memory=stale,
            expected_revision=stale["revision"],
        )
    except ValueError as exc:
        assert "revision conflict" in str(exc)
    else:
        raise AssertionError("stale workspace revision must be rejected")
