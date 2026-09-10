"""首个动态复合流程：图片赏析并寻找类似作品（workflow 阶段 D）。

实现文档 §9/§15 的最小链路：

```text
vision.appreciate_image ┐
vision.analyze_image ────┼→ portfolio.search → agent.compose_response
```

- 赏析与结构化分析互不依赖（可并行推进），检索只依赖结构化分析；
- 检索词来自第一步通过 output schema 校验的结构化结果（$context.image_analysis），
  而不是自然语言对话历史；
- compose 汇总两路结果生成最终回复：赏析正文 + 检索依据 + 真实资源引用；
  空结果时给出明确降级说明；
- 视觉步骤失败由 Runtime 判定 run failed，本模块返回降级文案；
- workflow 事件（workflow.created / step.started / ... / completed）镜像到
   ai_event_service 的 durable 对话事件流，SSE 断线重连按 sequence 补发。

触发与灰度：matches_appreciation_search_request 只命中「赏析 + 找类似」的
带图请求；feature flag AI_AGENT_WORKFLOW_APPRECIATION_SEARCH_ENABLED 关闭时
ai_service 回落到既有视觉分析 + 检索链路。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.services.ai_orchestrator_service import _is_work_appreciation_intent
from backend.app.services.agent_workflow_contracts import (
    WORKFLOW_PLAN_SCHEMA_VERSION,
)
from backend.app.services.agent_workflow_event_mirror import (
    WORKFLOW_EVENT_MIRROR_SCHEMA_VERSION,
    mirror_new_workflow_events,
)
from backend.app.services.agent_workflow_store import create_workflow_run

WORKFLOW_TYPE_IMAGE_APPRECIATION_AND_SEARCH = "image_appreciation_and_search"

# 降级/完成结果里引用 workflow 的 metadata 键。
WORKFLOW_REF_SCHEMA_VERSION = "agent_workflow_ref_v1"

# 「赏析 + 找类似」的检索语言：只有明确出现赏析意图时才视为复合请求。
_SEARCH_LANGUAGE_TERMS = (
    "寻找类似",
    "找类似",
    "找相似",
    "寻找相似",
    "相似的",
    "类似的",
    "同款",
    "类似风格",
    "相似风格",
)

_SEARCH_LIMIT = 6


def matches_appreciation_search_request(
    content: str | None,
    attachments: list[dict[str, Any]] | None,
) -> bool:
    """判断请求是否为「赏析图片并寻找类似作品」复合意图。

    规则保守：必须带图片附件、文本含显式赏析语言、且出现明确的
    类似/相似检索语言。纯赏析（无检索语言）和纯图搜（无赏析语言）
    都继续走既有链路。
    """
    if not content or not _has_image_attachments(attachments):
        return False
    if not _is_work_appreciation_intent(content):
        return False
    return any(term in content for term in _SEARCH_LANGUAGE_TERMS)


def _has_image_attachments(attachments: list[dict[str, Any]] | None) -> bool:
    return any(
        isinstance(item, dict) and item.get("type") == "image" and item.get("url")
        for item in attachments or []
    )


def build_appreciation_search_plan() -> dict[str, Any]:
    """构造 agent_workflow_plan_v2 计划：appreciate / analyze 并行 → search → compose。"""
    return {
        "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
        "workflow_type": WORKFLOW_TYPE_IMAGE_APPRECIATION_AND_SEARCH,
        "steps": [
            {
                "id": "appreciate",
                "capability": "vision.appreciate_image",
                "depends_on": [],
                "input_template": {
                    "conversation_id": "$input.conversation_id",
                    "content": "$input.content",
                    "attachments": "$input.attachments",
                },
                "context_key": "appreciation",
            },
            {
                "id": "analyze",
                "capability": "vision.analyze_image",
                "depends_on": [],
                "input_template": {
                    "conversation_id": "$input.conversation_id",
                    "content": "$input.content",
                    "attachments": "$input.attachments",
                },
                "context_key": "image_analysis",
            },
            {
                "id": "search",
                "capability": "portfolio.search",
                "depends_on": ["analyze"],
                "input_template": {
                    "query_text": "$context.image_analysis.search_query",
                    "styles": "$context.image_analysis.style",
                    "limit": _SEARCH_LIMIT,
                },
            },
            {
                "id": "compose",
                "capability": "agent.compose_response",
                "depends_on": ["appreciate", "analyze", "search"],
                "input_template": {
                    "user_request": "$input.content",
                    "appreciation": "$context.appreciation",
                    "analysis": "$context.image_analysis",
                    "search": "$context.search",
                },
            },
        ],
    }


async def run_appreciation_and_search_workflow(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    content: str | None,
    attachments: list[dict[str, Any]] | None,
    turn_id: str | None = None,
) -> dict[str, Any]:
    """创建并执行 workflow run，返回 {content, metadata} 形状的助手回复结果。

    任何失败（视觉步骤失败、deadline、deadlock）都不向上抛异常：返回降级
    文案 + 带 workflow 引用的 metadata，对话主链路保持可用。
    """
    from backend.app.services.agent_workflow_runtime import run_workflow

    run = create_workflow_run(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        plan=build_appreciation_search_plan(),
        input={
            "conversation_id": conversation_id,
            "content": content,
            "attachments": list(attachments or []),
        },
        message_id=message_id,
        commit=True,
    )
    mirrored_sequence = mirror_new_workflow_events(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        run=run,
        after_sequence=0,
        turn_id=turn_id,
    )

    run = await run_workflow(db, run_id=run.id, user_id=user_id)

    mirror_new_workflow_events(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        run=run,
        after_sequence=mirrored_sequence,
        turn_id=turn_id,
    )

    return _result_from_run(
        run=run,
        content=content,
        attachments=attachments,
    )


# ── compose 逻辑（agent.compose_response adapter 复用） ──────────────────────


def compose_appreciation_search(
    *,
    user_request: str | None,
    appreciation: dict[str, Any] | None,
    analysis: dict[str, Any] | None,
    search: dict[str, Any] | None,
) -> dict[str, Any]:
    """汇总赏析与检索的结构化结果，生成最终回复正文与 metadata。

    纯代码组装，不调用 LLM：回复里的每个资源引用都来自 search 步骤
    通过 output schema 校验的 items。
    """
    appreciation = appreciation or {}
    analysis = analysis or {}
    search = search or {}

    appreciation_reply = (appreciation.get("reply") or "").strip()
    search_query = (analysis.get("search_query") or "").strip()
    items = [item for item in (search.get("items") or []) if isinstance(item, dict)]

    parts: list[str] = []
    if appreciation_reply:
        parts.append(appreciation_reply)

    basis = (
        f"我以「{search_query}」为视觉线索检索了平台样片"
        if search_query
        else "我按这张图的整体风格检索了平台样片"
    )
    if items:
        listing = "\n".join(
            f"- 《{item.get('title') or '未命名作品'}》"
            for item in items[:_SEARCH_LIMIT]
        )
        parts.append(
            f"{basis}，找到 {len(items)} 个风格相近的作品：\n{listing}\n\n"
            "想缩小范围的话，告诉我城市或预算即可。"
        )
    else:
        # 空结果是合法完成：给出明确降级说明，而不是沉默。
        parts.append(
            f"{basis}，暂时没有找到风格足够相近的作品。"
            "可以补充城市或预算，或者换一张参考图再试一次。"
        )

    return {
        "schema_version": "agent_compose_response_v1",
        "content": "\n\n".join(part for part in parts if part.strip()),
        "metadata": compose_appreciation_search_metadata(
            user_request=user_request,
            appreciation_reply=appreciation_reply,
            analysis=analysis,
            search=search,
            items=items,
        ),
    }


def compose_appreciation_search_metadata(
    *,
    user_request: str | None,
    appreciation_reply: str,
    analysis: dict[str, Any],
    search: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """组装与既有视觉/检索路径兼容的消息 metadata（供前端卡片与引用策略消费）。"""
    attachment_count = len(
        [
            item
            for item in (analysis.get("attachments") or [])
            if isinstance(item, dict) and item.get("url")
        ]
    )
    search_query = (analysis.get("search_query") or "").strip()

    tool_calls: list[dict[str, Any]] = []
    if appreciation_reply:
        tool_calls.append(
            {
                "tool": "appreciate_image",
                "status": "success",
                "input": {"content": user_request, "attachment_count": attachment_count},
                "result": {"schema_version": "work_appreciation_v1"},
            }
        )
    tool_calls.append(
        {
            "tool": "analyze_image",
            "status": "success",
            "input": {"content": user_request, "attachment_count": attachment_count},
            "result": {
                "schema_version": analysis.get("schema_version"),
                "style": analysis.get("style") or [],
                "scene": analysis.get("scene") or [],
                "mood": analysis.get("mood") or [],
                "makeup": analysis.get("makeup") or [],
                "search_terms": analysis.get("search_terms") or [],
            },
        }
    )
    resource_ids = [item.get("id") for item in items if item.get("id") is not None]
    tool_calls.append(
        {
            "tool": "search_portfolio_items",
            "status": "success" if items else "empty",
            "input": {"query_text": search_query, "limit": _SEARCH_LIMIT},
            "result": {"count": len(items), "resource_ids": resource_ids},
        }
    )

    references = {"portfolio_items": items, "photographers": [], "packages": []}
    criteria = dict(search.get("criteria") or {})
    criteria.setdefault("resource_types", ["portfolio_items"])

    return {
        "model": dict(analysis.get("provider") or {}),
        "vision_analysis": analysis,
        "vision_context": {"source": "current_image"},
        "tool_calls": tool_calls,
        "vision_search": {
            "schema_version": "vision_search_v1",
            "search_text": search_query,
            "resource_types": ["portfolio_items"],
            "filters": {
                "style": analysis.get("style") or [],
                "scene": analysis.get("scene") or [],
                "mood": analysis.get("mood") or [],
                "makeup": analysis.get("makeup") or [],
            },
        },
        "references": references,
        "retrieval": {
            "context_schema_version": "ai_retrieval_v1",
            "criteria": criteria,
            "diagnostics": dict(search.get("diagnostics") or {}),
        },
        "citation_policy": {
            "schema_version": "resource_citation_v1",
            "required": bool(items),
            "allowed_resource_ids": {
                "portfolio_items": resource_ids,
                "photographers": [],
                "packages": [],
            },
        },
    }


# ── 事件镜像与结果组装 ────────────────────────────────────────────────────────


def _result_from_run(
    *,
    run: Any,
    content: str | None,
    attachments: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """从 run 终态组装助手回复结果；失败/取消走降级文案。"""
    workflow_ref = {
        "schema_version": WORKFLOW_REF_SCHEMA_VERSION,
        "workflow_run_id": run.id,
        "workflow_type": run.workflow_type,
        "status": run.status,
    }
    if run.status == "completed" and isinstance(run.result, dict):
        data = run.result.get("data") or {}
        composed_content = (data.get("content") or "").strip()
        if composed_content:
            return {
                "content": composed_content,
                "metadata": {
                    **(data.get("metadata") or {}),
                    "workflow": workflow_ref,
                },
            }

    # 降级路径：视觉步骤失败、run failed、compose 输出缺失。
    error = run.error or {}
    reason = (error.get("code") or "workflow_failed") if run.status == "failed" else run.status or "workflow_failed"
    return {
        "content": (
            "这轮赏析找相似没能完成，请稍后再试；"
            "也可以先单独赏析这张图，或直接告诉我想找的风格。"
        ),
        "metadata": {
            "model": {"provider": "platform_workflow", "model": "agent-workflow-runtime"},
            "workflow": {**workflow_ref, "error": error},
            "degraded_reason": reason,
            "user_request": (content or "")[:200],
            "attachment_count": len(attachments or []),
        },
    }
