"""Persistence bridge between Redis working memory and durable task sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.core.cache import distributed_lock
from backend.app.models.agent_task_session import AgentTaskEvent, AgentTaskResource, AgentTaskSession
from backend.app.services.agent_long_term_memory_service import finalize_task_memory
from backend.app.services.agent_working_memory_service import (
    clear_active_task_pointer,
    empty_working_memory,
    get_working_memory,
    save_working_memory,
    update_working_memory,
)


ACTIVE = {"active"}


def load_active_task_workspace(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
) -> dict[str, Any] | None:
    task = (
        db.query(AgentTaskSession)
        .filter(
            AgentTaskSession.user_id == user_id,
            AgentTaskSession.conversation_id == conversation_id,
            AgentTaskSession.status == "active",
        )
        .order_by(AgentTaskSession.last_active_at.desc())
        .first()
    )
    if task is None:
        return None
    resources = (
        db.query(AgentTaskResource)
        .filter(AgentTaskResource.task_id == task.id)
        .order_by(AgentTaskResource.position.asc(), AgentTaskResource.id.asc())
        .all()
    )
    return {
        "schema_version": "agent_task_workspace_v2",
        "task_id": task.id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "task_type": task.task_type,
        "status": task.status,
        "turn": task.revision,
        "revision": task.revision,
        "slots": task.slots or {},
        "form": task.form or {},
        "resources": [
            {
                "index": item.position,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "snapshot": item.snapshot or {},
            }
            for item in resources
        ],
        "selected_resource": task.selected_resource,
        "last_tool": None,
        "events": [],
        "updated_at": task.last_active_at.isoformat() if task.last_active_at else None,
    }


def load_latest_working_memory(
    db: Session, *, user_id: int, conversation_id: int,
) -> dict[str, Any] | None:
    """Compatibility alias; paused tasks are intentionally never restored."""
    return load_active_task_workspace(db, user_id=user_id, conversation_id=conversation_id)


def sync_working_memory(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    memory: dict[str, Any],
    message_id: int | None = None,
) -> AgentTaskSession:
    task_type = str(memory.get("task_type") or "resource_search")
    memory_task_id = str(memory.get("task_id") or "") or None
    if not memory_task_id:
        raise ValueError("working memory must have a durable task_id before sync")
    task = db.query(AgentTaskSession).filter(
        AgentTaskSession.id == memory_task_id,
        AgentTaskSession.user_id == user_id,
        AgentTaskSession.conversation_id == conversation_id,
    ).first()
    if task is None:
        raise ValueError("working memory task_id does not exist in durable storage")
    if task.task_type != task_type:
        raise ValueError("working memory task_type does not match durable task")

    task.status = str(memory.get("status") or task.status or "active")
    task.revision = int(task.revision or 0) + 1
    task.slots = memory.get("slots") or {}
    task.form = memory.get("form") or {}
    task.selected_resource = memory.get("selected_resource")
    task.last_active_at = _now()
    if task.status not in ACTIVE:
        task.ended_at = task.ended_at or _now()

    # Replace the bounded resource snapshot for this task. This is intentional:
    # Redis is also bounded, and the task table should mirror the latest view.
    db.query(AgentTaskResource).filter(AgentTaskResource.task_id == task.id).delete(
        synchronize_session=False
    )
    for item in memory.get("resources") or []:
        db.add(AgentTaskResource(
            task_id=task.id,
            resource_type=str(item.get("resource_type") or "resource"),
            resource_id=str(item.get("resource_id")) if item.get("resource_id") is not None else None,
            position=int(item.get("index") or 0),
            snapshot=item.get("snapshot") or {},
            source_tool=(memory.get("last_tool") or {}).get("name"),
            is_selected=int((item.get("index") == (memory.get("selected_resource") or {}).get("index"))),
        ))

    event = next(reversed(memory.get("events") or []), None)
    if event:
        db.add(AgentTaskEvent(
            task_id=task.id,
            event_type=str(event.get("type") or "working_memory_update"),
            message_id=message_id or event.get("message_id"),
            payload=event,
        ))
    db.flush()
    memory["task_id"] = task.id
    memory["user_id"] = user_id
    memory["conversation_id"] = conversation_id
    memory["revision"] = task.revision
    return task


def apply_task_workspace_update(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    task_type: str,
    status: str = "active",
    slots: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    resources: list[dict[str, Any]] | None = None,
    selected_resource: dict[str, Any] | None = None,
    last_tool: dict[str, Any] | None = None,
    event: dict[str, Any] | None = None,
    message_id: int | None = None,
) -> tuple[AgentTaskSession, dict[str, Any], str]:
    """Atomically choose the durable task before mutating its Redis workspace."""
    lock_key = f"agent-task-transition:{int(user_id)}:{int(conversation_id)}"
    with distributed_lock(lock_key) as acquired:
        if not acquired:
            raise RuntimeError("agent task transition is already in progress")

        active_task = (
            db.query(AgentTaskSession)
            .filter(
                AgentTaskSession.user_id == user_id,
                AgentTaskSession.conversation_id == conversation_id,
                AgentTaskSession.status == "active",
            )
            .order_by(AgentTaskSession.last_active_at.desc())
            .first()
        )
        transition = "none"
        if active_task is None or active_task.task_type != task_type:
            if active_task is not None:
                active_task.status = "paused"
                active_task.ended_at = active_task.ended_at or _now()
                finalize_task_memory(db, task=active_task, outcome="paused")
                transition = "replace"
            else:
                transition = "create"
            task = AgentTaskSession(
                id=str(uuid4()),
                user_id=user_id,
                conversation_id=conversation_id,
                task_type=task_type,
                status="active",
                slots={},
                form={},
            )
            db.add(task)
            db.flush()
            memory = empty_working_memory(
                task_id=task.id,
                task_type=task_type,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            save_working_memory(user_id, conversation_id, memory)
        else:
            task = active_task
            memory = get_working_memory(
                user_id, conversation_id, task_id=task.id, task_type=task_type,
            ) or load_active_task_workspace(
                db, user_id=user_id, conversation_id=conversation_id,
            ) or empty_working_memory(
                task_id=task.id,
                task_type=task_type,
                user_id=user_id,
                conversation_id=conversation_id,
            )

        memory = update_working_memory(
            user_id,
            conversation_id,
            task_id=task.id,
            task_type=task_type,
            status=status,
            slots=slots,
            form=form,
            resources=resources,
            selected_resource=selected_resource,
            last_tool=last_tool,
            event=event,
        )
        task = sync_working_memory(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            memory=memory,
            message_id=message_id,
        )
        memory["revision"] = task.revision
        save_working_memory(user_id, conversation_id, memory)
        if task.status != "active":
            clear_active_task_pointer(user_id, conversation_id)
        return task, memory, transition


def pause_active_tasks(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    except_task_id: str | None = None,
) -> list[AgentTaskSession]:
    """Pause active tasks in a conversation, preserving durable episodes."""
    tasks = (
        db.query(AgentTaskSession)
        .filter(
            AgentTaskSession.user_id == user_id,
            AgentTaskSession.conversation_id == conversation_id,
            AgentTaskSession.status == "active",
        )
        .all()
    )
    for task in tasks:
        if task.id == except_task_id:
            continue
        task.status = "paused"
        task.ended_at = task.ended_at or _now()
        finalize_task_memory(db, task=task, outcome="paused")
    db.flush()
    return tasks


def _now() -> datetime:
    return datetime.now(timezone.utc)
