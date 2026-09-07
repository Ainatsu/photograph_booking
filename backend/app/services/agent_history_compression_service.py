"""Deterministic, non-destructive compression of completed task history."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import AIConversation, AIMessage, AIConversationCompression
from backend.app.models.agent_task_session import AgentTaskSession
from backend.app.services.agent_long_term_memory_service import finalize_task_memory


HISTORY_COMPRESSION_THRESHOLD = 100
TERMINAL_TASK_STATUSES = {"paused", "completed", "cancelled", "abandoned"}


def compress_completed_task_history(
    db: Session,
    *,
    conversation: AIConversation,
    threshold: int = HISTORY_COMPRESSION_THRESHOLD,
) -> dict | None:
    """Create/update a compact episode once a conversation exceeds the threshold.

    Original messages remain untouched; callers can use the returned summary to
    build a smaller provider context window.
    """
    message_count = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation.id)
        .count()
    )
    if message_count <= threshold:
        return None
    task = (
        db.query(AgentTaskSession)
        .filter(
            AgentTaskSession.conversation_id == conversation.id,
            AgentTaskSession.status.in_(TERMINAL_TASK_STATUSES),
        )
        .order_by(AgentTaskSession.last_active_at.desc())
        .first()
    )
    if task is None:
        return None
    # Keep compression append-only. If summarization/finalization fails, the
    # caller can roll back this transaction without touching original messages.
    episode = finalize_task_memory(db, task=task, outcome=task.status)
    messages = (
        db.query(AIMessage).filter(AIMessage.conversation_id == conversation.id)
        .order_by(AIMessage.id.asc()).all()
    )
    latest = messages[-1]
    previous = db.query(AIConversationCompression).filter(
        AIConversationCompression.conversation_id == conversation.id
    ).order_by(AIConversationCompression.summary_version.desc()).first()
    if previous and previous.source_end_message_id == latest.id:
        return None
    version = (previous.summary_version if previous else 0) + 1
    retained_facts = [
        item for item in [
            (episode.structured_summary or {}).get("task_type"),
            (episode.structured_summary or {}).get("selected_resource"),
            (episode.structured_summary or {}).get("result"),
        ] if item
    ]
    compression = AIConversationCompression(
        conversation_id=conversation.id, user_id=conversation.user_id,
        summary_version=version, compression_reason="message_threshold",
        source_start_message_id=messages[0].id, source_end_message_id=latest.id,
        source_message_count=len(messages), summary=episode.summary,
        retained_facts=retained_facts, retained_task_ids=[task.id],
    )
    db.add(compression)
    db.flush()
    return {
        "task_id": task.id,
        "message_count": message_count,
        "summary": episode.summary,
        "structured_summary": episode.structured_summary,
        "preserve_original_messages": True,
        "summary_version": version,
        "compression_reason": compression.compression_reason,
        "retained_facts": retained_facts,
    }


def get_retained_context(db: Session, *, conversation_id: int, max_chars: int = 6000) -> dict | None:
    """Return the newest bounded retained context without loading full history."""
    record = db.query(AIConversationCompression).filter(
        AIConversationCompression.conversation_id == conversation_id
    ).order_by(AIConversationCompression.summary_version.desc()).first()
    if record is None:
        return None
    summary = (record.summary or "")[:max_chars]
    return {
        "summary_version": record.summary_version,
        "summary": summary,
        "retained_facts": list(record.retained_facts or [])[:20],
        "retained_task_ids": list(record.retained_task_ids or []),
        "source_message_count": record.source_message_count,
        "compression_reason": record.compression_reason,
        "source_end_message_id": record.source_end_message_id,
    }
