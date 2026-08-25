"""把资源检索能力封装成 search_* 工具（阶段B §4.1）。

阶段A 的检索调用散落在 ai_service 的编排分支里：入参从意图槽位拼、资源类型从原文猜，
新增一种资源就要再加一条分支。本模块把它收敛成「一个工具名 + 一组严格入参 → 结构化结果」，
决策层只负责选工具和填条件，真实数据全部来自数据库。

- search_photographers / search_portfolio_items / search_packages
  复用 ai_retrieval_service.retrieve_references（混合检索 + 结构化条件 + 排除已推荐资源）；
- search_projects 复用 project_recommendation_service.recommend_projects（企划推荐，仅摄影师）。

返回值统一带上 retrieval-shaped 的 payload，让 ai_service 现有的 references /
citation_policy / search_context 构建逻辑可以直接复用，不需要第二套元数据格式。
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.services.ai_agent_contracts import build_ai_project_reference
from backend.app.services.ai_resource_context_service import CONTEXT_SCHEMA_VERSION
from backend.app.services.ai_retrieval_service import (
    REFERENCE_KEYS,
    RESOURCE_TYPE_LABELS,
    _effective_limit,
    retrieve_references,
)
from backend.app.services.ai_vision_service import build_vision_search_text
from backend.app.services.project_recommendation_service import recommend_projects


SEARCH_TOOL_SCHEMA_VERSION = "agent_search_tool_v1"

# 工具名 → metadata.references 里的资源键。
SEARCH_TOOL_RESOURCE_KEYS = {
    "search_photographers": "photographers",
    "search_portfolio_items": "portfolio_items",
    "search_packages": "packages",
    "search_projects": "projects",
}

# 走文档检索（retrieve_references）的工具；企划走独立的推荐服务。
DOCUMENT_SEARCH_TOOLS = ("search_photographers", "search_portfolio_items", "search_packages")

RESOURCE_LABELS = {**RESOURCE_TYPE_LABELS, "projects": "企划"}


def is_search_tool(tool_name: str | None) -> bool:
    """判断工具名是否为检索类工具。"""
    return (tool_name or "") in SEARCH_TOOL_RESOURCE_KEYS


def resource_key_for_tool(tool_name: str | None) -> str | None:
    """返回工具名对应的资源键。"""
    return SEARCH_TOOL_RESOURCE_KEYS.get(tool_name or "")


def search_tool_for_resource_types(resource_types: list[str] | None) -> str | None:
    """资源类型 → 工具名；只在单一资源类型时成立（影子对比与回退都靠它）。"""
    types = [item for item in resource_types or [] if item]
    if len(types) != 1:
        return None
    for tool_name, key in SEARCH_TOOL_RESOURCE_KEYS.items():
        if key == types[0]:
            return tool_name
    return None


def run_search_tool(
    db: Session,
    *,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    user: User | None = None,
    vision_analysis: dict[str, Any] | None = None,
    image_attachments: list[dict[str, Any]] | None = None,
    request_content: str | None = None,
) -> dict[str, Any]:
    """执行一次检索类工具调用。

    调用方必须先过 ai_tool_policy_service.authorize_tool_call，这里只负责执行：
    参数已经是校验并归一化过的，排除列表已由后端注入。
    """
    payload = dict(arguments or {})
    if tool_name in DOCUMENT_SEARCH_TOOLS:
        return _run_document_search(
            db,
            tool_name=tool_name,
            arguments=payload,
            vision_analysis=vision_analysis,
            image_attachments=image_attachments,
            request_content=request_content,
        )
    if tool_name == "search_projects":
        return _run_project_search(db, arguments=payload, user=user)
    return _tool_failure(tool_name, payload, "unsupported_search_tool")


def build_tool_result_prompt(tool_call: dict[str, Any] | None) -> str | None:
    """把工具返回结果交给最终 LLM（§4.5），并锁死“只能复述真实数据”。

    只用于 references 不走 build_retrieval_context 的资源（目前是企划）：
    那段 prompt 的措辞是围绕摄影师/作品/套餐写的，直接复用会让模型答错资源类型。
    """
    if not tool_call:
        return None
    result = tool_call.get("result") or {}
    label = RESOURCE_LABELS.get(str(result.get("resource_type") or ""), "资源")
    payload = {
        "tool": tool_call.get("tool"),
        "status": tool_call.get("status"),
        "criteria": result.get("criteria") or {},
        "count": result.get("count") or 0,
        "items": result.get("items") or [],
    }
    rules = (
        f"平台工具 {tool_call.get('tool')} 的真实返回结果如下。你必须遵守："
        f"只能推荐 items 里的真实{label}，逐个写出它们的真实标题；"
        "不要编造标题、预算、日期、状态或 ID，也不要推荐 items 之外的任何资源；"
        f"如果 items 为空，直说暂时没有符合条件的{label}，并最多追问 1 个可以放宽的条件；"
        "不要向用户展示内部打分、算法版本或匹配字段。\n"
    )
    return rules + json.dumps(payload, ensure_ascii=False)


# ── 文档检索类工具 ─────────────────────────────────────────────────────────


def _run_document_search(
    db: Session,
    *,
    tool_name: str,
    arguments: dict[str, Any],
    vision_analysis: dict[str, Any] | None,
    image_attachments: list[dict[str, Any]] | None,
    request_content: str | None,
) -> dict[str, Any]:
    """执行文档类资源的混合检索，返回统一结构的结果。"""
    resource_key = SEARCH_TOOL_RESOURCE_KEYS[tool_name]
    query_text = _query_text(tool_name, arguments)
    # 后端以原始用户请求为准覆盖模型给出的默认数量，避免视觉搜索文本
    # 重写后丢失“一份/一张/一组”等数量约束。
    limit = _effective_limit(
        request_content or query_text,
        int(arguments.get("limit") or 3),
    )
    effective_arguments = {**arguments, "limit": limit}
    exclude_ids = [str(item) for item in arguments.get("exclude_resource_ids") or []]
    criteria_overrides = _criteria_overrides(arguments)
    if vision_analysis:
        query_text = build_vision_search_text(query_text, vision_analysis)

    retrieval = retrieve_references(
        db,
        query_text,
        limit=limit,
        resource_types=[resource_key],
        vision_analysis=vision_analysis,
        image_attachments=image_attachments,
        criteria_overrides=criteria_overrides or None,
        exclude_resource_ids=exclude_ids,
    )
    if not retrieval:
        return _tool_failure(tool_name, effective_arguments, "empty_query_text")

    items = (retrieval.get("references") or {}).get(resource_key) or []
    return _tool_success(
        tool_name=tool_name,
        arguments=effective_arguments,
        resource_key=resource_key,
        items=items,
        criteria=retrieval.get("criteria") or {},
        diagnostics=retrieval.get("diagnostics") or {},
        retrieval=retrieval,
    )


def _criteria_overrides(arguments: dict[str, Any]) -> dict[str, Any]:
    """工具入参 → 检索层结构化条件（只映射 OVERRIDABLE_CRITERIA_FIELDS 允许的字段）。"""
    overrides: dict[str, Any] = {}
    if arguments.get("city"):
        overrides["location"] = str(arguments["city"]).strip()
    if arguments.get("styles"):
        overrides["style_terms"] = list(arguments["styles"])
    if arguments.get("budget_max") is not None:
        overrides["budget_max"] = float(arguments["budget_max"])
    if arguments.get("requires_makeup"):
        overrides["requires_makeup"] = True
    if arguments.get("photographer_name"):
        overrides["owner_display_name"] = str(arguments["photographer_name"]).strip()
    return overrides


def _query_text(tool_name: str, arguments: dict[str, Any]) -> str:
    """检索器需要一段非空文本做关键词与向量召回。

    优先用模型给的 query_text；没有时用结构化条件拼一段，绝不把用户原话直接塞进来——
    原话里的“这个不太满意”会被切成正向关键词（阶段A 修掉的那个 bug）。
    """
    text = str(arguments.get("query_text") or "").strip()
    if text:
        return text
    parts = [str(arguments.get("city") or "").strip()]
    parts.extend(str(style).strip() for style in arguments.get("styles") or [])
    parts.append(RESOURCE_LABELS.get(SEARCH_TOOL_RESOURCE_KEYS[tool_name], "资源"))
    return " ".join(part for part in parts if part)


# ── 企划检索工具 ───────────────────────────────────────────────────────────


def _run_project_search(
    db: Session,
    *,
    arguments: dict[str, Any],
    user: User | None,
) -> dict[str, Any]:
    """执行企划检索（仅摄影师可用），返回统一结构的结果。"""
    if user is None or (user.role or "") != "photographer":
        return _tool_failure("search_projects", arguments, "role_not_allowed")

    started_at = perf_counter()
    limit = int(arguments.get("limit") or 3)
    exclude_ids = {str(item) for item in arguments.get("exclude_resource_ids") or []}
    city = str(arguments.get("city") or "").strip() or None
    styles = [str(style).strip() for style in arguments.get("styles") or [] if str(style).strip()]
    recommendation = recommend_projects(
        db,
        user,
        None,
        # 多取一些再排除已看过的，避免“换一个”时因为排除掉旧结果而直接空手。
        max(limit + len(exclude_ids), limit),
        city,
        styles,
        _int_or_none(arguments.get("budget_min")),
        _int_or_none(arguments.get("budget_max")),
        None,
    )
    items = [
        reference
        for reference in (
            build_ai_project_reference(item) for item in recommendation.get("items") or []
        )
        if str(reference.get("id")) not in exclude_ids
    ][:limit]

    criteria = {
        "text": _query_text("search_projects", arguments),
        "terms": [],
        "location": city,
        "city": city,
        "budget_max": _float_or_none(arguments.get("budget_max")),
        "owner_user_id": None,
        "owner_display_name": None,
        "resource_types": ["projects"],
        "style_terms": styles,
        "requires_makeup": False,
        "package_includes": [],
        "limit": limit,
        "explicit_fields": sorted(_criteria_overrides(arguments).keys()),
        "inherited_fields": [],
        "exclude_resource_ids": sorted(exclude_ids),
    }
    diagnostics = {
        "result_counts": {"projects": len(items)},
        "candidate_counts": {"projects": len(recommendation.get("items") or [])},
        "latency_ms": round((perf_counter() - started_at) * 1000),
        "retrieval_mode": "project_recommendation",
        "algorithm_version": recommendation.get("algorithm_version"),
        "excluded_resource_ids": sorted(exclude_ids),
        "explicit_fields": criteria["explicit_fields"],
        "inherited_fields": [],
    }
    return _tool_success(
        tool_name="search_projects",
        arguments=arguments,
        resource_key="projects",
        items=items,
        criteria=criteria,
        diagnostics=diagnostics,
        retrieval=None,
    )


# ── 统一返回结构 ───────────────────────────────────────────────────────────


def _tool_success(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    resource_key: str,
    items: list[dict[str, Any]],
    criteria: dict[str, Any],
    diagnostics: dict[str, Any],
    retrieval: dict[str, Any] | None,
) -> dict[str, Any]:
    """构造检索成功的统一返回结构。"""
    payload = retrieval or {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "criteria": criteria,
        "references": {
            **{key: [] for key in REFERENCE_KEYS},
            resource_key: items,
        },
        "diagnostics": diagnostics,
    }
    return {
        "tool": tool_name,
        "status": "success" if items else "empty",
        "input": arguments,
        "result": {
            "schema_version": SEARCH_TOOL_SCHEMA_VERSION,
            "resource_type": resource_key,
            "count": len(items),
            "resource_ids": [_reference_id(item) for item in items],
            "items": items,
            "criteria": criteria,
            "diagnostics": diagnostics,
        },
        # ai_service 用它复用既有的 references / citation_policy / search_context 构建。
        "payload": payload,
        # retrieval 非空表示可以直接走 build_retrieval_context 的既有回答约束。
        "retrieval": retrieval,
        "policy": {
            "schema_version": SEARCH_TOOL_SCHEMA_VERSION,
            "risk_level": "read_only",
            "confirmation_policy": "none",
            "confirmation_count": 0,
        },
    }


def _tool_failure(tool_name: str, arguments: dict[str, Any], error_code: str) -> dict[str, Any]:
    """构造检索失败的统一返回结构。"""
    return {
        "tool": tool_name,
        "status": "failed",
        "input": arguments,
        "result": {
            "schema_version": SEARCH_TOOL_SCHEMA_VERSION,
            "resource_type": SEARCH_TOOL_RESOURCE_KEYS.get(tool_name),
            "count": 0,
            "resource_ids": [],
            "items": [],
            "error": error_code,
        },
        "payload": None,
        "retrieval": None,
        "policy": {
            "schema_version": SEARCH_TOOL_SCHEMA_VERSION,
            "risk_level": "read_only",
            "confirmation_policy": "none",
            "confirmation_count": 0,
        },
    }


def _reference_id(item: dict[str, Any]) -> Any:
    """从资源条目中提取资源 ID。"""
    return item.get("id") or item.get("user_id") or item.get("package_id")


def _int_or_none(value: Any) -> int | None:
    """将入参安全转换为整数，无效值返回 None。"""
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    """将入参安全转换为浮点数，无效值返回 None。"""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
