"""Deterministic task summarization and conservative user-memory extraction."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.agent_memory import AgentMemoryEpisode, AgentUserMemory
from backend.app.models.agent_task_session import AgentTaskResource, AgentTaskSession


ACTIVATION_CONFIDENCE = 0.75
INITIAL_CONFIDENCE = 0.55
REPEATED_EVIDENCE_INCREMENT = 0.10


def finalize_task_memory(
    db: Session,
    *,
    task: AgentTaskSession,
    outcome: str,
) -> AgentMemoryEpisode:
    existing = db.query(AgentMemoryEpisode).filter(AgentMemoryEpisode.task_id == task.id).first()
    if existing:
        return existing

    resources = (
        db.query(AgentTaskResource)
        .filter(AgentTaskResource.task_id == task.id)
        .order_by(AgentTaskResource.position.asc())
        .all()
    )
    structured = _structured_summary(task, resources)
    episode = AgentMemoryEpisode(
        id=str(uuid4()),
        user_id=task.user_id,
        conversation_id=task.conversation_id,
        task_id=task.id,
        task_type=task.task_type,
        summary=_summary_text(structured),
        structured_summary=structured,
        outcome=outcome,
    )
    db.add(episode)
    db.flush()
    for memory_type, memory_key, value in _candidate_memories(structured):
        _upsert_user_memory(
            db,
            user_id=task.user_id,
            task_id=task.id,
            memory_type=memory_type,
            memory_key=memory_key,
            value=value,
        )
    task.summary = episode.summary
    return episode


def get_active_user_memories(db: Session, user_id: int, limit: int = 20) -> list[AgentUserMemory]:
    """Return only activated durable memories suitable for prompt context."""
    return (
        db.query(AgentUserMemory)
        .filter(
            AgentUserMemory.user_id == user_id,
            AgentUserMemory.status == "active",
        )
        .order_by(AgentUserMemory.confidence.desc(), AgentUserMemory.updated_at.desc())
        .limit(limit)
        .all()
    )


def active_user_memories(db: Session, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        db.query(AgentUserMemory)
        .filter(AgentUserMemory.user_id == user_id, AgentUserMemory.status == "active")
        .order_by(AgentUserMemory.confidence.desc(), AgentUserMemory.last_observed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "memory_type": row.memory_type,
            "key": row.memory_key,
            "value": row.value,
            "confidence": row.confidence,
            "evidence_count": row.evidence_count,
        }
        for row in rows
    ]


def _structured_summary(task: AgentTaskSession, resources: list[AgentTaskResource]) -> dict[str, Any]:
    selected = task.selected_resource or {}
    return {
        "task_type": task.task_type,
        "slots": task.slots or {},
        "resource_count": len(resources),
        "resources": [
            {
                "position": item.position,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "name": _resource_name(item.snapshot or {}),
            }
            for item in resources
        ],
        "selected_resource": {
            "position": selected.get("index"),
            "resource_id": selected.get("resource_id"),
            "name": _resource_name(selected.get("snapshot") or {}),
        } if selected else None,
    }


def _summary_text(summary: dict[str, Any]) -> str:
    slots = summary.get("slots") or {}
    conditions = []
    city = slots.get("city") or slots.get("location")
    if city:
        conditions.append(str(city))
    styles = slots.get("styles") or slots.get("style_terms") or []
    conditions.extend(str(item) for item in styles if item)
    task_label = {
        "package_search": "方案搜索",
        "package_search": "方案搜索",
        "photographer_search": "摄影师搜索",
        "portfolio_item_search": "作品搜索",
        "project_search": "企划搜索",
        "resource_search": "资源搜索",
    }.get(summary.get("task_type"), str(summary.get("task_type") or "任务"))
    text = f"用户进行了一次{task_label}"
    if conditions:
        text += f"，主要条件为{'、'.join(conditions[:6])}"
    text += f"，查看了{int(summary.get('resource_count') or 0)}个平台资源"
    selected = summary.get("selected_resource") or {}
    if selected.get("name"):
        text += f"，重点查看了“{selected['name']}”"
    return text + "。"


def _candidate_memories(summary: dict[str, Any]):
    slots = summary.get("slots") or {}
    city = slots.get("city") or slots.get("location")
    if city:
        normalized = str(city).strip()
        if normalized:
            yield "location_interest", normalized.lower(), {"name": normalized}
    for style in slots.get("styles") or slots.get("style_terms") or []:
        normalized = str(style).strip()
        if normalized:
            yield "style_interest", normalized.lower(), {"name": normalized}


def _upsert_user_memory(
    db: Session,
    *,
    user_id: int,
    task_id: str,
    memory_type: str,
    memory_key: str,
    value: dict[str, Any],
) -> None:
    row = (
        db.query(AgentUserMemory)
        .filter(
            AgentUserMemory.user_id == user_id,
            AgentUserMemory.memory_type == memory_type,
            AgentUserMemory.memory_key == memory_key,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if row is None:
        db.add(AgentUserMemory(
            user_id=user_id,
            memory_type=memory_type,
            memory_key=memory_key,
            value=value,
            confidence=INITIAL_CONFIDENCE,
            evidence_count=1,
            source_task_ids=[task_id],
            status="candidate",
            last_observed_at=now,
        ))
        return
    source_ids = list(row.source_task_ids or [])
    if task_id not in source_ids:
        source_ids.append(task_id)
        row.evidence_count = int(row.evidence_count or 0) + 1
        row.confidence = min(0.95, float(row.confidence or INITIAL_CONFIDENCE) + REPEATED_EVIDENCE_INCREMENT)
    row.source_task_ids = source_ids[-20:]
    row.value = value
    row.last_observed_at = now
    if row.confidence >= ACTIVATION_CONFIDENCE:
        row.status = "active"


def _resource_name(snapshot: dict[str, Any]) -> str | None:
    return (
        snapshot.get("package_name")
        or snapshot.get("title")
        or snapshot.get("user_display_name")
        or snapshot.get("photographer_name")
    )
