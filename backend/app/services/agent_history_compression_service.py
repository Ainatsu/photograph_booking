"""Deterministic, non-destructive compression of completed task history."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import AIConversation, AIMessage
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
    episode = finalize_task_memory(db, task=task, outcome=task.status)
    db.flush()
    return {
        "task_id": task.id,
        "message_count": message_count,
        "summary": episode.summary,
        "structured_summary": episode.structured_summary,
        "preserve_original_messages": True,
    }
