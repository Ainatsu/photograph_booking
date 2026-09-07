"""Durable append-only task form revision operations."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.agent_task import AgentTaskFormRevision


def latest_form_revision(db: Session, *, task_id: str) -> AgentTaskFormRevision | None:
    return (
        db.query(AgentTaskFormRevision)
        .filter(AgentTaskFormRevision.task_id == str(task_id))
        .order_by(AgentTaskFormRevision.revision.desc(), AgentTaskFormRevision.id.desc())
        .first()
    )


def list_form_revisions(db: Session, *, task_id: str, user_id: int, conversation_id: int) -> list[AgentTaskFormRevision]:
    return (
        db.query(AgentTaskFormRevision)
        .filter(
            AgentTaskFormRevision.task_id == str(task_id),
            AgentTaskFormRevision.user_id == user_id,
            AgentTaskFormRevision.conversation_id == conversation_id,
        )
        .order_by(AgentTaskFormRevision.revision.asc())
        .all()
    )


def append_form_revision(
    db: Session,
    *,
    task_id: str,
    conversation_id: int,
    user_id: int,
    revision: int,
    operations: list[dict[str, Any]],
    resulting_form: dict[str, Any],
    source: str,
    source_message_id: int | None = None,
    idempotency_key: str | None = None,
    created_by: str = "agent",
) -> AgentTaskFormRevision:
    """Append exactly one revision, replaying an existing idempotency key."""
    if revision < 1:
        raise HTTPException(status_code=422, detail="revision must be positive")
    if idempotency_key:
        replay = (
            db.query(AgentTaskFormRevision)
            .filter(
                AgentTaskFormRevision.task_id == str(task_id),
                AgentTaskFormRevision.idempotency_key == str(idempotency_key),
            )
            .first()
        )
        if replay:
            if replay.user_id != user_id or replay.conversation_id != conversation_id:
                raise HTTPException(status_code=404, detail="form revision not found")
            return replay

    latest = latest_form_revision(db, task_id=str(task_id))
    expected = (latest.revision if latest else 0) + 1
    if revision != expected:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "revision_conflict",
                "task_id": str(task_id),
                "latest_revision": latest.revision if latest else 0,
                "latest_form": latest.resulting_form if latest else {},
            },
        )

    row = AgentTaskFormRevision(
        task_id=str(task_id),
        conversation_id=conversation_id,
        user_id=user_id,
        revision=revision,
        operations=operations or [],
        resulting_form=resulting_form or {},
        source=source,
        source_message_id=source_message_id,
        idempotency_key=str(idempotency_key) if idempotency_key else None,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row
