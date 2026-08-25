"""多轮资源检索上下文（search_context）。

资源检索子系统此前没有多轮记忆：用户第二轮说“这个我不太满意，换一个”时，
系统既继承不到上一轮的城市和风格，也不知道要排除上一轮已经推荐过的资源；
而“不太满意”这类对话控制词还会被当成正向检索关键词，把真实备选挤出相关性门槛。

本模块只做纯数据处理：
- 把本轮意图槽位翻译成检索层的结构化条件；
- 识别 refinement（换一个 / 再推荐一个 / 不满意）；
- 从上一轮 search_context 继承搜索条件，并给出需要排除的资源 ID；
- 把本轮检索结果重新落成新的 search_context。

消息 metadata 的读写由 ai_service 负责，条件的实际应用由 ai_retrieval_service 负责。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import AIMessage
from backend.app.services.ai_domain_synonyms import normalize_terms
from backend.app.services.ai_retrieval_service import (
    REFERENCE_KEYS,
    RESOURCE_TYPE_TERMS,
)


SEARCH_CONTEXT_SCHEMA_VERSION = "resource_search_context_v2"

# 向前回溯的 assistant 消息条数：允许中间夹着几轮闲聊仍能继承上一次搜索的条件。
SEARCH_CONTEXT_LOOKBACK = 6

# 要求替换上一轮结果的表达；命中任意一条即视为 refinement。
REFINEMENT_PHRASES = (
    "换一个",
    "换一位",
    "换一名",
    "换一批",
    "换一换",
    "换个",
    "换换",
    # “换成成都”“改成 2000 以内”是在同一次搜索里改条件，同样要继承资源类型和风格。
    "换成",
    "改成",
    "再推荐",
    "继续推荐",
    "继续找",
    "继续给",
    "再来一个",
    "再来一批",
    "再给我一个",
    "重新推荐",
    "重新找",
    "重新给",
    "下一个",
    "另一个",
    "另外一个",
    "别的",
    "其他的",
    "其它的",
    "还有其他",
    "还有别的",
    "还有没有",
    "还有吗",
    "不太满意",
    "不满意",
    "不喜欢",
    "不太喜欢",
    "不合适",
    "不太合适",
    "不够好",
    "不行",
    "不太行",
)

# 企划（拍摄需求）不在 RESOURCE_TYPE_TERMS 里，单独识别，避免被继承成套餐/摄影师。
PROJECT_RESOURCE_TERMS = ("企划", "拍摄需求", "约拍需求", "接活", "接单", "任务")

# search_context.slots 字段 → retrieval criteria 字段。
# 只映射 retrieval 允许被上游覆盖的字段（见 OVERRIDABLE_CRITERIA_FIELDS）。
_SLOT_TO_CRITERIA_FIELD = {
    "city": "location",
    "styles": "style_terms",
    "budget_max": "budget_max",
    "requires_makeup": "requires_makeup",
    "owner_user_id": "owner_user_id",
    "owner_display_name": "owner_display_name",
}

# 本轮没有显式给出时，可以直接沿用上一轮的槽位。
_INHERITABLE_SLOT_KEYS = (
    "city",
    "budget_max",
    "requires_makeup",
    "package_includes",
    "limit",
)

_EMPTY_VALUES = (None, "", [], {})


def slot_styles(slots: dict[str, Any] | None) -> list[str]:
    """槽位里的风格：规则分类器给 style（字符串或列表），LLM 分类器给 styles。"""
    payload = slots or {}
    raw = payload.get("styles") or payload.get("style") or []
    if isinstance(raw, str):
        raw = [raw]
    return normalize_terms([str(item).strip() for item in raw if str(item or "").strip()])


def criteria_from_slots(slots: dict[str, Any] | None) -> dict[str, Any] | None:
    """把本轮意图确认的槽位翻译成检索层的结构化条件。

    这一步让检索器不必再从原文重新猜条件：意图已经确认的城市、风格、预算
    直接作为 criteria 生效，反馈型原文（“这个不满意”）不会再覆盖它们。
    """
    payload = slots or {}
    overrides: dict[str, Any] = {}
    if payload.get("city"):
        overrides["location"] = str(payload["city"]).strip()
    styles = slot_styles(payload)
    if styles:
        overrides["style_terms"] = styles
    if payload.get("budget_max") not in _EMPTY_VALUES:
        try:
            overrides["budget_max"] = float(payload["budget_max"])
        except (TypeError, ValueError):
            pass
    if payload.get("requires_makeup"):
        overrides["requires_makeup"] = True
    return overrides or None


def matched_refinement_phrases(content: str | None) -> list[str]:
    """返回命中的 refinement 表述，用于审计和诊断。"""
    text = (content or "").strip()
    if not text:
        return []
    return [phrase for phrase in REFINEMENT_PHRASES if phrase in text]


def is_search_refinement(content: str | None) -> bool:
    """用户是否在要求“换一个/再推荐一个”，而不是发起一次全新搜索。"""
    return bool(matched_refinement_phrases(content))


def explicit_resource_types(content: str | None) -> list[str]:
    """只返回用户本轮明确点名的资源类型；没点名时返回空列表（不做 photographers 兜底）。"""
    text = (content or "").strip()
    if not text:
        return []
    if any(term in text for term in PROJECT_RESOURCE_TERMS):
        return ["projects"]
    return [
        key
        for key in REFERENCE_KEYS
        if any(term in text for term in RESOURCE_TYPE_TERMS[key])
    ]


def latest_search_context(
    db: Session,
    conversation_id: int,
    lookback: int = SEARCH_CONTEXT_LOOKBACK,
) -> dict[str, Any] | None:
    """取会话中最近一次成功检索留下的 search_context。"""
    rows = (
        db.query(AIMessage)
        .filter(
            AIMessage.conversation_id == conversation_id,
            AIMessage.role == "assistant",
        )
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .limit(max(1, lookback))
        .all()
    )
    for row in rows:
        context = (row.message_metadata or {}).get("search_context")
        if isinstance(context, dict) and context.get("slots"):
            return context
    return None


def resolve_refinement(
    content: str | None,
    previous: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """识别 refinement，并给出可继承的槽位与必须排除的资源 ID。"""
    if not previous:
        return None
    phrases = matched_refinement_phrases(content)
    if not phrases:
        return None
    previous_slots = previous.get("slots") or {}
    excluded = _unique([
        *(previous.get("seen_resource_ids") or []),
        *(previous.get("recommended_resource_ids") or []),
    ])
    return {
        "schema_version": SEARCH_CONTEXT_SCHEMA_VERSION,
        "matched_phrases": phrases,
        "inherited_slots": {
            key: value
            for key, value in previous_slots.items()
            if value not in _EMPTY_VALUES
        },
        "exclude_resource_ids": excluded,
        "previous_query_text": previous.get("query_text"),
        "previous_turn": previous.get("turn"),
    }


def retrieval_overrides(refinement: dict[str, Any] | None) -> dict[str, Any] | None:
    """把继承的槽位翻译成 retrieval criteria 字段名。"""
    if not refinement:
        return None
    slots = refinement.get("inherited_slots") or {}
    overrides = {
        field: slots[slot_name]
        for slot_name, field in _SLOT_TO_CRITERIA_FIELD.items()
        if slots.get(slot_name) not in _EMPTY_VALUES and slots.get(slot_name) is not False
    }
    return overrides or None


def apply_refinement_to_slots(
    slots: dict[str, Any] | None,
    refinement: dict[str, Any] | None,
    content: str | None,
) -> dict[str, Any]:
    """合并槽位：本轮显式表达优先，其余沿用上一轮搜索条件。"""
    merged = dict(slots or {})
    if not refinement:
        return merged
    inherited = refinement.get("inherited_slots") or {}

    for key in _INHERITABLE_SLOT_KEYS:
        if merged.get(key) in _EMPTY_VALUES and inherited.get(key) not in _EMPTY_VALUES:
            merged[key] = inherited[key]

    inherited_styles = inherited.get("styles") or []
    if inherited_styles and not slot_styles(merged):
        merged["styles"] = list(inherited_styles)

    # 资源类型：本轮点名了就用本轮的，没点名一律沿用上一轮，
    # 否则“再推荐一个”会被规则兜底成 photographers。
    explicit_types = explicit_resource_types(content)
    if explicit_types:
        merged["resource_types"] = explicit_types
    elif inherited.get("resource_types"):
        merged["resource_types"] = list(inherited["resource_types"])

    return merged


def build_search_context(
    *,
    retrieval: dict[str, Any] | None,
    intent: Any = None,
    previous: dict[str, Any] | None = None,
    refinement: dict[str, Any] | None = None,
    query_text: str | None = None,
    task_id: str | None = None,
    task_type: str | None = None,
    revision: int | None = None,
) -> dict[str, Any] | None:
    """把本轮检索结果落成新的 search_context，供下一轮继承和排除。"""
    if not retrieval:
        return None
    criteria = retrieval.get("criteria") or {}
    diagnostics = retrieval.get("diagnostics") or {}
    intent_slots = getattr(intent, "slots", None) or {}
    recommended = _recommended_resources(retrieval.get("references") or {})
    recommended_ids = [item["id"] for item in recommended]

    previous_seen = (previous or {}).get("seen_resource_ids") or (previous or {}).get(
        "recommended_resource_ids"
    ) or []
    # 只有连续追问才累积“已经看过”的资源；全新搜索重新开始。
    seen_ids = (
        _unique([*previous_seen, *recommended_ids]) if refinement else _unique(recommended_ids)
    )

    slots = {
        "resource_types": list(criteria.get("resource_types") or []),
        "city": criteria.get("city"),
        "styles": list(criteria.get("style_terms") or []),
        "budget_max": criteria.get("budget_max"),
        "requires_makeup": bool(criteria.get("requires_makeup")),
        "package_includes": list(criteria.get("package_includes") or []),
        "date": intent_slots.get("date"),
        "time": intent_slots.get("time"),
        "limit": criteria.get("limit"),
        "owner_user_id": criteria.get("owner_user_id"),
        "owner_display_name": criteria.get("owner_display_name"),
    }

    context: dict[str, Any] = {
        "schema_version": SEARCH_CONTEXT_SCHEMA_VERSION,
        "task_id": task_id,
        "task_type": task_type,
        "revision": revision,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "turn": int((previous or {}).get("turn") or 0) + 1,
        "status": "presenting_options" if recommended_ids else "no_results",
        "last_action": "refine" if refinement else "search",
        "intent": getattr(intent, "intent", None),
        "query_text": (query_text or criteria.get("text") or "").strip(),
        "slots": slots,
        "recommended_resources": recommended,
        "recommended_resource_ids": recommended_ids,
        "seen_resource_ids": seen_ids,
        "result_counts": diagnostics.get("result_counts") or {},
        "refinement": None,
    }
    if refinement:
        context["refinement"] = {
            "is_refinement": True,
            "matched_phrases": list(refinement.get("matched_phrases") or []),
            "explicit_fields": list(diagnostics.get("explicit_fields") or []),
            "inherited_fields": list(diagnostics.get("inherited_fields") or []),
            "excluded_resource_ids": list(diagnostics.get("excluded_resource_ids") or []),
            "previous_query_text": refinement.get("previous_query_text"),
        }
    return context


def active_search_task(previous: dict[str, Any] | None) -> dict[str, Any] | None:
    """把上一轮搜索状态交给意图分类器，让它知道存在一个持续进行的资源搜索。"""
    if not previous:
        return None
    slots = {
        key: value
        for key, value in (previous.get("slots") or {}).items()
        if value not in _EMPTY_VALUES and value is not False
    }
    if not slots:
        return None
    return {
        "task_type": "resource_search",
        "status": previous.get("status") or "presenting_options",
        "turn": previous.get("turn"),
        "slots": slots,
        # 只给名称不给 ID：分类器禁止输出平台实体 ID。
        "recommended_resource_names": [
            item.get("name")
            for item in previous.get("recommended_resources") or []
            if item.get("name")
        ],
    }


def refinement_empty_reply(refinement: dict[str, Any] | None) -> str:
    """追问“换一个”但确实没有备选时的回复。

    不复述用户的反馈词（“暂时没找到完全匹配‘不太满意’的上架资源”正是原来的 bug），
    而是说明已经排除了上一个结果，并引导放宽条件。
    """
    slots = (refinement or {}).get("inherited_slots") or {}
    conditions: list[str] = []
    if slots.get("city"):
        conditions.append(str(slots["city"]))
    conditions.extend(str(style) for style in slots.get("styles") or [] if style)
    if slots.get("budget_max"):
        conditions.append(f"预算{float(slots['budget_max']):g}元内")
    focus = "、".join(_unique(conditions)[:3])
    scope = f"同时满足{focus}的" if focus else ""
    return (
        f"除了刚才推荐的那个，暂时没有其他{scope}上架资源了。"
        "你可以放宽预算、城市或风格中的一项，或者告诉我更具体的偏好，我再帮你找找。"
    )


def _recommended_resources(references: dict[str, Any]) -> list[dict[str, Any]]:
    """收集本轮推荐过的资源，供后续轮次排除。"""
    # REFERENCE_KEYS 之外的资源键（阶段B 的 projects）也要记进来，
    # 否则“换一个企划”排除不掉上一轮推荐过的那个。
    keys = [*REFERENCE_KEYS, *sorted(set(references or {}) - set(REFERENCE_KEYS))]
    resources: list[dict[str, Any]] = []
    for key in keys:
        for item in references.get(key) or []:
            resource_id = item.get("id") or item.get("package_id") or item.get("user_id")
            if resource_id in (None, ""):
                continue
            resources.append({
                "resource_type": key,
                "id": resource_id,
                "name": (
                    item.get("package_name")
                    or item.get("title")
                    or item.get("user_display_name")
                    or ""
                ),
            })
    return resources


def _unique(values: list[Any]) -> list[Any]:
    """按首次出现顺序去重并返回列表。"""
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
