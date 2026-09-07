"""Build the explicit, provenance-labelled context envelope for Agent turns."""

from __future__ import annotations

import json
from typing import Any


def build_context_envelope(
    *,
    conversation: Any,
    current_request: dict[str, Any] | None,
    active_task: dict[str, Any] | None,
    recent_dialogue: list[dict[str, Any]] | None = None,
    task_resources: list[dict[str, Any]] | None = None,
    referenced_task_episodes: list[dict[str, Any]] | None = None,
    active_user_memories: list[dict[str, Any]] | None = None,
    retained_context: dict[str, Any] | None = None,
    max_context_chars: int = 24000,
) -> dict[str, Any]:
    """Return a bounded envelope whose source boundaries are explicit.

    Candidate memories are deliberately excluded by the caller's active-only input.
    The current request and active task are listed first so consumers can apply the
    documented precedence without relying on prompt ordering accidents.
    """
    envelope: dict[str, Any] = {
        "schema_version": 1,
        "conversation": {
            "id": getattr(conversation, "id", None),
            "user_id": getattr(conversation, "user_id", None),
            "status": getattr(conversation, "status", None),
            "title": getattr(conversation, "title", None),
        },
        "current_request": current_request or {},
        "active_task": active_task,
        "recent_dialogue": list(recent_dialogue or [])[-20:],
        "retained_context": retained_context,
        "task_resources": list(task_resources or [])[:20],
        "referenced_task_episodes": list(referenced_task_episodes or [])[:5],
        "active_user_memories": list(active_user_memories or [])[:20],
        "provenance": [
            {"field": "current_request", "source": "current_message", "priority": 100},
            *([{"field": "active_task", "source": "active_task", "priority": 90}] if active_task else []),
            *([{"field": "recent_dialogue", "source": "recent_dialogue", "priority": 50}] if recent_dialogue else []),
            *([{"field": "retained_context", "source": "history_compression", "priority": 30}] if retained_context else []),
            *([{"field": "referenced_task_episodes", "source": "explicit_history_request", "priority": 40}] if referenced_task_episodes else []),
            *([{"field": "active_user_memories", "source": "active_long_term_memory", "priority": 10}] if active_user_memories else []),
        ],
    }
    # Keep the envelope bounded for provider calls while retaining the newest
    # request/task fields at full fidelity.
    # Drop lowest-value collections first; current_request and active_task are
    # retained as the authoritative inputs for this turn.
    for key in ("recent_dialogue", "referenced_task_episodes", "active_user_memories", "task_resources"):
        while len(json.dumps(envelope, ensure_ascii=False)) > max_context_chars and envelope[key]:
            envelope[key].pop(0)
    if len(json.dumps(envelope, ensure_ascii=False)) > max_context_chars and envelope.get("retained_context"):
        retained = envelope["retained_context"]
        retained["summary"] = str(retained.get("summary") or "")[: max(0, max_context_chars // 4)]
        retained["retained_facts"] = list(retained.get("retained_facts") or [])[:5]
    return envelope


def build_context_envelope_prompt(envelope: dict[str, Any]) -> str:
    """Render the envelope with deterministic precedence and source boundaries."""
    return (
        "以下是本轮统一 Context Envelope。请严格遵守来源优先级："
        "current_request > active_task > recent_dialogue > referenced_task_episodes > active_user_memories。"
        "current_request 中用户本轮明确条件永远覆盖长期画像；长期画像只能作为弱参考。"
        "candidate 记忆未包含在此对象中，不得自行补入。"
        "retained_context 是历史压缩摘要，只能补充背景，不能覆盖当前请求或 active_task。"
        "referenced_task_episodes 只有在用户明确要求回顾/恢复历史时才会出现，"
        "它们不是当前 slots、工具参数或活动任务。每个事实必须按 provenance 解释来源。\n"
        + json.dumps(envelope, ensure_ascii=False)
    )
