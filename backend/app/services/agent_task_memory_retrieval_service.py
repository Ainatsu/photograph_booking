"""Explicit, bounded retrieval and resume operations for historical Agent tasks."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from backend.app.core.cache import distributed_lock
from backend.app.models.agent_memory import AgentMemoryEpisode
from backend.app.models.agent_task_session import AgentTaskEvent, AgentTaskSession
from backend.app.services.agent_long_term_memory_service import finalize_task_memory
from backend.app.services.agent_task_session_service import load_active_task_workspace
from backend.app.services.agent_working_memory_service import save_working_memory


TaskMemoryMode = Literal["none", "summary", "resume"]
SUMMARY_TERMS = ("之前做过什么", "以前做过什么", "历史任务", "之前的任务", "上次找过什么")
RESUME_TERMS = ("继续上次", "继续之前", "恢复上次", "接着上次", "继续刚才", "恢复之前")
STOP_WORDS = {
    "继续", "上次", "之前", "刚才", "恢复", "接着", "任务", "方案", "搜索", "帮我", "一下", "的",
}


def task_memory_mode(content: str | None) -> TaskMemoryMode:
    text = (content or "").strip()
    if not text:
        return "none"
    if any(term in text for term in RESUME_TERMS):
        return "resume"
    if any(term in text for term in SUMMARY_TERMS):
        return "summary"
    return "none"


def list_recent_task_episodes(
    db: Session, *, user_id: int, limit: int = 10,
) -> list[dict[str, Any]]:
    rows = (
        db.query(AgentMemoryEpisode)
        .filter(AgentMemoryEpisode.user_id == user_id)
        .order_by(AgentMemoryEpisode.created_at.desc())
        .limit(max(1, min(limit, 20)))
        .all()
    )
    return [_serialize_episode(row) for row in rows]


def search_task_episodes(
    db: Session,
    *,
    user_id: int,
    query: str,
    task_types: list[str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows_query = db.query(AgentMemoryEpisode).filter(AgentMemoryEpisode.user_id == user_id)
    if task_types:
        rows_query = rows_query.filter(AgentMemoryEpisode.task_type.in_(task_types))
    rows = rows_query.order_by(AgentMemoryEpisode.created_at.desc()).limit(100).all()
    terms = _query_terms(query)
    scored = []
    for recency, row in enumerate(rows):
        haystack = _episode_search_text(row)
        score = sum(3 if term in row.summary else 1 for term in terms if term in haystack)
        if not terms or score:
            scored.append((score, -recency, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [_serialize_episode(row) for _, _, row in scored[:max(1, min(limit, 10))]]


def get_task_episode(
    db: Session, *, user_id: int, task_id: str,
) -> dict[str, Any] | None:
    row = db.query(AgentMemoryEpisode).filter(
        AgentMemoryEpisode.user_id == user_id,
        AgentMemoryEpisode.task_id == task_id,
    ).first()
    return _serialize_episode(row) if row else None


def build_task_episode_prompt(episodes: list[dict[str, Any]]) -> str | None:
    """Build a bounded, provenance-labelled prompt for explicit history recall."""
    if not episodes:
        return None
    payload = [
        {
            "task_id": item.get("task_id"),
            "task_type": item.get("task_type"),
            "summary": item.get("summary"),
            "outcome": item.get("outcome"),
        }
        for item in episodes[:5]
    ]
    return (
        "以下是后端仅因用户明确请求回顾历史任务而检索到的任务摘要。"
        "它们是历史事实，不是当前任务的 slots、工具参数或活动工作区。"
        "不得把其中的条件自动合并到当前请求；如用户要求继续某项任务，应先确认具体任务。\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def resume_task(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    task_id: str,
    message_id: int | None = None,
) -> tuple[AgentTaskSession, dict[str, Any]]:
    lock_key = f"agent-task-transition:{int(user_id)}:{int(conversation_id)}"
    with distributed_lock(lock_key) as acquired:
        if not acquired:
            raise RuntimeError("agent task transition is already in progress")
        task = db.query(AgentTaskSession).filter(
            AgentTaskSession.id == task_id,
            AgentTaskSession.user_id == user_id,
            AgentTaskSession.conversation_id == conversation_id,
            AgentTaskSession.status == "paused",
        ).first()
        if task is None:
            raise ValueError("resumable task not found")

        active_tasks = db.query(AgentTaskSession).filter(
            AgentTaskSession.user_id == user_id,
            AgentTaskSession.conversation_id == conversation_id,
            AgentTaskSession.status == "active",
        ).all()
        for active in active_tasks:
            if active.id == task.id:
                continue
            active.status = "paused"
            active.ended_at = active.ended_at or _now()
            finalize_task_memory(db, task=active, outcome="paused")

        task.conversation_id = conversation_id
        task.status = "active"
        task.ended_at = None
        task.last_active_at = _now()
        task.revision = int(task.revision or 0) + 1
        db.add(AgentTaskEvent(
            task_id=task.id,
            event_type="task_resumed",
            message_id=message_id,
            payload={"type": "task_resumed", "conversation_id": conversation_id},
        ))
        db.flush()
        memory = load_active_task_workspace(
            db, user_id=user_id, conversation_id=conversation_id,
        )
        if memory is None or memory.get("task_id") != task.id:
            raise RuntimeError("resumed task workspace could not be rebuilt")
        save_working_memory(user_id, conversation_id, memory)
        return task, memory


def _serialize_episode(row: AgentMemoryEpisode) -> dict[str, Any]:
    return {
        "episode_id": row.id,
        "task_id": row.task_id,
        "task_type": row.task_type,
        "summary": row.summary,
        "structured_summary": row.structured_summary or {},
        "outcome": row.outcome,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _episode_search_text(row: AgentMemoryEpisode) -> str:
    return " ".join((
        row.task_type or "",
        row.summary or "",
        json.dumps(row.structured_summary or {}, ensure_ascii=False),
        row.outcome or "",
    )).lower()


def _query_terms(query: str) -> list[str]:
    chunks = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_-]{2,}", (query or "").lower())
    terms = []
    for chunk in chunks:
        reduced = chunk
        for stop_word in STOP_WORDS:
            reduced = reduced.replace(stop_word, " ")
        for part in reduced.split():
            part = part.strip("，。！？、：:；;（）()[]【】").lstrip("的")
            if len(part) >= 2:
                terms.append(part)
    return terms


def _now() -> datetime:
    return datetime.now(timezone.utc)
