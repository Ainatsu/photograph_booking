"""Durable conversation event stream and SSE serialization helpers."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.models.ai_conversation import AIConversationEvent


def append_event(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
    task_id: str | None = None,
    turn_id: str | None = None,
) -> AIConversationEvent:
    """Persist one event and allocate the next per-conversation sequence."""
    # The unique cursor constraint makes concurrent writers retry safely.
    for _ in range(3):
        current = db.query(func.max(AIConversationEvent.sequence)).filter(
            AIConversationEvent.conversation_id == conversation_id
        ).scalar()
        event = AIConversationEvent(
            event_id=str(uuid.uuid4()), user_id=user_id, conversation_id=conversation_id,
            task_id=task_id, turn_id=turn_id, sequence=(current or 0) + 1,
            type=event_type, payload=payload or {},
        )
        db.add(event)
        try:
            db.commit()
            db.refresh(event)
            return event
        except IntegrityError:
            db.rollback()
    raise RuntimeError("unable to allocate conversation event sequence")


def list_events(db: Session, *, user_id: int, conversation_id: int, after_sequence: int = 0, limit: int = 200):
    return db.query(AIConversationEvent).filter(
        AIConversationEvent.user_id == user_id,
        AIConversationEvent.conversation_id == conversation_id,
        AIConversationEvent.sequence > after_sequence,
    ).order_by(AIConversationEvent.sequence.asc()).limit(limit).all()


def sse_frame(event: AIConversationEvent) -> str:
    payload = {
        "event_id": event.event_id, "conversation_id": event.conversation_id,
        "task_id": event.task_id, "turn_id": event.turn_id,
        "sequence": event.sequence, "type": event.type,
        "payload": event.payload or {},
        "created_at": event.created_at.isoformat() if event.created_at else datetime.now(timezone.utc).isoformat(),
    }
    return f"id: {event.event_id}\nevent: {event.type}\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


async def event_stream(*, user_id: int, conversation_id: int, after_sequence: int = 0):
    """Poll the durable stream so reconnects work across processes."""
    sequence = after_sequence
    try:
        while True:
            db = SessionLocal()
            try:
                events = list_events(db, user_id=user_id, conversation_id=conversation_id, after_sequence=sequence)
            finally:
                db.close()
            if events:
                for event in events:
                    sequence = event.sequence
                    yield sse_frame(event)
            else:
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        return
