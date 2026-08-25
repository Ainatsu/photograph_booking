"""Redis-backed working memory for the active Agent task.

This is deliberately a working-memory layer, not the source of truth for
conversation history. Durable task snapshots remain in the database/message
metadata until the task-session tables are introduced.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from typing import Any
from uuid import uuid4

from backend.app.core.cache import cache_delete, cache_get, cache_set


WORKING_MEMORY_SCHEMA_VERSION = "agent_task_workspace_v2"
DEFAULT_TTL_SECONDS = 24 * 60 * 60
MAX_RESOURCE_SNAPSHOTS = 20
MAX_EVENTS = 30

ORDINAL_PATTERNS = (
    (re.compile(r"(?:第\s*)?(?:一|1)(?:\s*个|\s*位|\s*份|\s*条)?"), 1),
    (re.compile(r"(?:第\s*)?(?:二|两|2)(?:\s*个|\s*位|\s*份|\s*条)?"), 2),
    (re.compile(r"(?:第\s*)?(?:三|3)(?:\s*个|\s*位|\s*份|\s*条)?"), 3),
    (re.compile(r"(?:第\s*)?(?:四|4)(?:\s*个|\s*位|\s*份|\s*条)?"), 4),
    (re.compile(r"(?:第\s*)?(?:五|5)(?:\s*个|\s*位|\s*份|\s*条)?"), 5),
)
RESOURCE_REFERENCE_TERMS = (
    "方案", "套餐", "摄影师", "作品", "企划", "这个", "那个", "刚才", "上一个",
)
RESOURCE_INSPECTION_TERMS = (
    "详情", "详细", "注意", "备注", "写的", "包含", "包括", "价格", "多少钱", "时长",
    "交付", "交通", "天气", "限制", "比较", "区别", "适合", "怎么样",
)
TASK_EXIT_TERMS = (
    "取消搜索", "不找了", "不用找了", "结束这个任务", "结束任务", "退出任务", "换个话题",
)


def active_task_key(user_id: int, conversation_id: int) -> str:
    return f"agent:active-task:{int(user_id)}:{int(conversation_id)}"


def task_workspace_key(task_id: str) -> str:
    return f"agent:task-workspace:{task_id}"


def working_memory_key(user_id: int, conversation_id: int) -> str:
    """Legacy key retained for one-way compatibility/cleanup only."""
    return f"agent:working-memory:{int(user_id)}:{int(conversation_id)}"


def empty_working_memory(*, task_type: str = "chat", task_id: str | None = None,
                         user_id: int | None = None, conversation_id: int | None = None) -> dict[str, Any]:
    return {
        "schema_version": WORKING_MEMORY_SCHEMA_VERSION,
        "task_id": task_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "task_type": task_type,
        "status": "idle" if task_type == "chat" else "active",
        "turn": 0,
        "slots": {},
        "form": {},
        "resources": [],
        "selected_resource": None,
        "last_tool": None,
        "events": [],
        "updated_at": _now(),
    }


def get_active_task_id(user_id: int, conversation_id: int) -> str | None:
    pointer = cache_get(active_task_key(user_id, conversation_id))
    return str(pointer.get("task_id")) if isinstance(pointer, dict) and pointer.get("task_id") else None


def set_active_task_pointer(user_id: int, conversation_id: int, *, task_id: str,
                            task_type: str, revision: int = 0,
                            ttl: int = DEFAULT_TTL_SECONDS) -> None:
    cache_set(active_task_key(user_id, conversation_id), {
        "task_id": task_id, "task_type": task_type, "revision": revision,
    }, ttl=ttl)


def clear_active_task_pointer(user_id: int, conversation_id: int) -> None:
    cache_delete(active_task_key(user_id, conversation_id))


def get_working_memory(user_id: int, conversation_id: int, *, task_id: str | None = None,
                       task_type: str | None = None) -> dict[str, Any] | None:
    task_id = task_id or get_active_task_id(user_id, conversation_id)
    if not task_id:
        return None
    value = cache_get(task_workspace_key(task_id))
    if not isinstance(value, dict):
        return None
    if value.get("task_id") != task_id or value.get("user_id") not in (None, user_id) or value.get("conversation_id") not in (None, conversation_id):
        return None
    if task_type and value.get("task_type") != task_type:
        return None
    return value


def save_working_memory(
    user_id: int,
    conversation_id: int,
    memory: dict[str, Any],
    *,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    normalized = _normalize(memory)
    task_id = normalized.get("task_id")
    if not task_id:
        raise ValueError("working memory requires task_id")
    normalized["user_id"] = user_id
    normalized["conversation_id"] = conversation_id
    cache_set(task_workspace_key(str(task_id)), normalized, ttl=ttl)
    set_active_task_pointer(user_id, conversation_id, task_id=str(task_id),
                            task_type=str(normalized.get("task_type") or "chat"),
                            revision=int(normalized.get("revision") or normalized.get("turn") or 0), ttl=ttl)
    return normalized


def update_working_memory(
    user_id: int,
    conversation_id: int,
    *,
    task_id: str | None = None,
    task_type: str | None = None,
    status: str | None = None,
    slots: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    resources: list[dict[str, Any]] | None = None,
    selected_resource: dict[str, Any] | None = None,
    last_tool: dict[str, Any] | None = None,
    event: dict[str, Any] | None = None,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    explicit_memory = (
        get_working_memory(user_id, conversation_id, task_id=task_id)
        if task_id else None
    )
    if explicit_memory and task_type and explicit_memory.get("task_type") != task_type:
        raise ValueError("working memory task_type mismatch")
    memory = explicit_memory or get_working_memory(
        user_id, conversation_id, task_type=task_type
    ) or empty_working_memory(
        task_type=task_type or "chat", task_id=task_id or str(uuid4())
    )
    if task_id and memory.get("task_id") not in (None, task_id):
        raise ValueError("working memory task_id mismatch")
    if task_id:
        memory["task_id"] = task_id
    if task_type is not None:
        memory["task_type"] = task_type
    if status is not None:
        memory["status"] = status
    if slots:
        memory["slots"] = {**(memory.get("slots") or {}), **slots}
    if form:
        memory["form"] = {**(memory.get("form") or {}), **form}
    if resources is not None:
        memory["resources"] = resources
    if selected_resource is not None:
        memory["selected_resource"] = selected_resource
    if last_tool is not None:
        memory["last_tool"] = last_tool
    if event is not None:
        memory["events"] = [*(memory.get("events") or []), event]
    memory["turn"] = int(memory.get("turn") or 0) + 1
    memory["updated_at"] = _now()
    return save_working_memory(user_id, conversation_id, memory, ttl=ttl)


def clear_working_memory(user_id: int, conversation_id: int) -> None:
    task_id = get_active_task_id(user_id, conversation_id)
    clear_active_task_pointer(user_id, conversation_id)
    if task_id:
        cache_delete(task_workspace_key(task_id))
    cache_delete(working_memory_key(user_id, conversation_id))


def pause_working_memory(user_id: int, conversation_id: int) -> dict[str, Any] | None:
    memory = get_working_memory(user_id, conversation_id)
    if not memory:
        return None
    memory["status"] = "paused"
    memory["updated_at"] = _now()
    result = save_working_memory(user_id, conversation_id, memory)
    clear_active_task_pointer(user_id, conversation_id)
    return result


def is_task_exit_request(content: str | None) -> bool:
    text = (content or "").strip()
    return bool(text) and any(term in text for term in TASK_EXIT_TERMS)


def active_task_context(memory: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a compact task description safe for intent/decision models."""
    if not memory or memory.get("status") != "active":
        return None
    resources = []
    for item in memory.get("resources") or []:
        snapshot = item.get("snapshot") or {}
        resources.append({
            "index": item.get("index"),
            "resource_type": item.get("resource_type"),
            "name": (
                snapshot.get("package_name")
                or snapshot.get("title")
                or snapshot.get("user_display_name")
                or snapshot.get("photographer_name")
            ),
        })
    selected = memory.get("selected_resource") or {}
    return {
        "task_type": memory.get("task_type"),
        "status": memory.get("status"),
        "turn": memory.get("turn"),
        "slots": memory.get("slots") or {},
        "resources": resources,
        "selected_resource_index": selected.get("index"),
    }


def resolve_resource_reference(
    memory: dict[str, Any] | None,
    content: str | None,
) -> dict[str, Any] | None:
    """Resolve ordinal and current-resource references inside one active task."""
    if not memory or memory.get("status") != "active":
        return None
    text = (content or "").strip()
    resources = memory.get("resources") or []
    if not text or not resources:
        return None

    requested_index = None
    for pattern, index in ORDINAL_PATTERNS:
        if pattern.search(text):
            requested_index = index
            break

    explicit_reference = requested_index is not None
    if requested_index is None and any(term in text for term in RESOURCE_REFERENCE_TERMS):
        selected = memory.get("selected_resource") or {}
        requested_index = selected.get("index")
        if requested_index is None and len(resources) == 1:
            requested_index = resources[0].get("index") or 1

    if requested_index is None:
        return None
    if not explicit_reference and not any(term in text for term in RESOURCE_INSPECTION_TERMS):
        return None

    matched = next(
        (item for item in resources if int(item.get("index") or 0) == int(requested_index)),
        None,
    )
    if not matched:
        return None
    return deepcopy(matched)


def build_resource_reference_prompt(reference: dict[str, Any] | None) -> str | None:
    if not reference:
        return None
    payload = {
        "index": reference.get("index"),
        "resource_type": reference.get("resource_type"),
        "resource_id": reference.get("resource_id"),
        "snapshot": reference.get("snapshot") or {},
        "text_summary": reference.get("text_summary") or resource_text_summary(reference.get("snapshot") or {}),
    }
    return (
        "当前用户消息已由后端确定性解析为当前任务中的一个真实资源。"
        "回答必须以 snapshot 的字段为事实依据，优先直接复述摄影师或发布者写入的 description、"
        "includes、条款和限制；不得声称这些信息不存在，也不得用常识编造 snapshot 中没有的注意事项。"
        "如果用户询问注意事项，先完整归纳 snapshot 中明确写出的事项，再明确区分额外建议。"
        "不要向用户展示内部索引、resource_id、snapshot 或任务状态。\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def resource_text_summary(snapshot: dict[str, Any]) -> str:
    """Render a bounded factual summary for the final model prompt."""
    fields = (
        snapshot.get("package_name") or snapshot.get("title") or snapshot.get("name"),
        snapshot.get("price_label") or snapshot.get("price"),
        snapshot.get("description"),
        snapshot.get("includes"),
        snapshot.get("weather_policy"),
    )
    parts: list[str] = []
    for value in fields:
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = "、".join(str(item) for item in value)
        parts.append(str(value))
    return "；".join(parts)[:1200]


def _normalize(memory: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(memory)
    result["schema_version"] = WORKING_MEMORY_SCHEMA_VERSION
    result["slots"] = dict(result.get("slots") or {})
    result["form"] = dict(result.get("form") or {})
    result["resources"] = list(result.get("resources") or [])[-MAX_RESOURCE_SNAPSHOTS:]
    result["events"] = list(result.get("events") or [])[-MAX_EVENTS:]
    result["updated_at"] = result.get("updated_at") or _now()
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
