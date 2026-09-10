"""search_then_inspire 固定复合流程迁移到 Workflow Runtime（workflow 阶段 E）。

实现文档 §11.2/§12 阶段 E 的第一部分：把原先 ai_service.py 中
compound_workflow 条件分支的固定两步流程（检索作品 → 创建灵感）迁移为
普通 workflow definition，不再依赖 send_ai_message 的条件分支。

```text
portfolio.search → inspiration.generate（依赖 search 的结构化结果）
```

- 检索条件来自意图 slots 归一（城市/风格/预算/数量），第二步输入完全
  来自第一步通过 output schema 校验的 items，而不是自然语言历史；
- inspiration.generate 复用 create_inspiration_workflow：AgentTaskDraft
  草稿、灵感占位与异步生成 job 的行为、幂等键与 legacy 完全一致；
- 检索为空或无可用静态图是合法完成，返回 legacy 同款降级文案；
- workflow 事件镜像到对话事件流（复用 agent_workflow_event_mirror）。

触发与灰度：intent == compound_workflow 且 feature flag
AI_AGENT_WORKFLOW_SEARCH_THEN_INSPIRE_ENABLED 开启时接管；关闭时
ai_service 回落到既有 compound_workflow 分支。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.services.agent_workflow_contracts import (
    WORKFLOW_PLAN_SCHEMA_VERSION,
)
from backend.app.services.agent_workflow_event_mirror import (
    mirror_new_workflow_events,
)
from backend.app.services.agent_workflow_store import (
    create_workflow_run,
    load_workflow_run,
)

WORKFLOW_TYPE_SEARCH_THEN_INSPIRE = "search_then_inspire"

# 降级/完成结果里引用 workflow 的 metadata 键。
WORKFLOW_REF_SCHEMA_VERSION = "agent_workflow_ref_v1"

# 与 legacy compound_workflow 分支一致的检索数量。
_SEARCH_LIMIT = 3

_NO_USABLE_IMAGES_MESSAGE = "没有找到包含可用静态图片的匹配作品，请调整风格、城市或预算后重试。"


def build_search_then_inspire_plan() -> dict[str, Any]:
    """构造 agent_workflow_plan_v2 计划：search → inspire 两步 DAG。

    run.input 里的 search 子对象由 run_search_then_inspire_workflow 归一
    （所有键必定存在，None/[] 合法），避免模板 fail-closed。
    """
    return {
        "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
        "workflow_type": WORKFLOW_TYPE_SEARCH_THEN_INSPIRE,
        "steps": [
            {
                "id": "search",
                "capability": "portfolio.search",
                "depends_on": [],
                "input_template": {
                    "query_text": "$input.content",
                    "city": "$input.search.city",
                    "styles": "$input.search.styles",
                    "budget_min": "$input.search.budget_min",
                    "budget_max": "$input.search.budget_max",
                    "limit": "$input.search.limit",
                    "exclude_resource_ids": "$input.search.exclude_resource_ids",
                },
                "context_key": "search",
            },
            {
                "id": "inspire",
                "capability": "inspiration.generate",
                "depends_on": ["search"],
                "input_template": {
                    "reference_text": "$input.content",
                    "items": "$context.search.items",
                },
            },
        ],
    }


def _normalized_search_input(
    intent_slots: dict[str, Any] | None,
    exclude_resource_ids: list[str] | None,
) -> dict[str, Any]:
    """意图 slots → 检索入参归一：模板引用的键必须全部存在。"""
    slots = intent_slots or {}
    styles = slots.get("styles") or slots.get("style") or []
    if isinstance(styles, str):
        styles = [styles]
    limit = slots.get("limit")
    try:
        limit = int(limit) if limit is not None else _SEARCH_LIMIT
    except (TypeError, ValueError):
        limit = _SEARCH_LIMIT
    return {
        "city": slots.get("city"),
        "styles": [str(style) for style in styles if style],
        "budget_min": slots.get("budget_min"),
        "budget_max": slots.get("budget_max"),
        "limit": limit,
        "exclude_resource_ids": [
            str(item) for item in (exclude_resource_ids or []) if item
        ],
    }


async def run_search_then_inspire_workflow(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    content: str | None,
    intent_slots: dict[str, Any] | None,
    exclude_resource_ids: list[str] | None = None,
    turn_id: str | None = None,
) -> dict[str, Any]:
    """创建并执行 workflow run，返回 {content, metadata} 形状的助手回复结果。

    任何失败（检索失败、deadline、deadlock）都不向上抛异常：返回降级
    文案 + 带 workflow 引用的 metadata，对话主链路保持可用。
    """
    from backend.app.services.agent_workflow_runtime import run_workflow

    run = create_workflow_run(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        plan=build_search_then_inspire_plan(),
        input={
            "content": content or "",
            "search": _normalized_search_input(intent_slots, exclude_resource_ids),
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

    run, steps = load_workflow_run(db, run_id=run.id, user_id=user_id)
    _log_retrieval(db, user_id=user_id, conversation_id=conversation_id, message_id=message_id, run=run)

    return _result_from_run(run=run, steps=steps, content=content)


def _log_retrieval(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    run: Any,
) -> None:
    """审计对齐：与 legacy 检索路径一样 best-effort 落一次 log_retrieval_run。"""
    from backend.app.services.ai_observability_service import log_retrieval_run

    search_result = (run.context or {}).get("search") or {}
    retrieval = search_result.get("retrieval")
    if not retrieval:
        return
    try:
        log_retrieval_run(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            query_text=(search_result.get("criteria") or {}).get("text") or "",
            intent={},
            retrieval=retrieval,
        )
    except Exception:
        # 审计日志失败不能影响对话主链路（同 legacy 行为）。
        db.rollback()


# ── 结果组装 ─────────────────────────────────────────────────────────────────


def _result_from_run(
    *,
    run: Any,
    steps: list[Any],
    content: str | None,
) -> dict[str, Any]:
    """从 run 终态组装助手回复结果；失败/取消走降级文案。"""
    workflow_ref = {
        "schema_version": WORKFLOW_REF_SCHEMA_VERSION,
        "workflow_run_id": run.id,
        "workflow_type": run.workflow_type,
        "status": run.status,
    }
    search_result = (run.context or {}).get("search") or {}
    items = [
        item
        for item in (search_result.get("items") or [])
        if isinstance(item, dict)
    ]
    inspire_step = next(
        (step for step in steps if step.step_key == "inspire"),
        None,
    )
    inspire_data = (
        (inspire_step.result or {}).get("data")
        if inspire_step and isinstance(inspire_step.result, dict)
        else None
    ) or {}

    task_plan = _task_plan_snapshot(
        items=items,
        inspire_status=(
            inspire_step.status if inspire_step is not None else "failed"
        ),
        plan_status=_legacy_plan_status(run, inspire_data),
    )
    metadata: dict[str, Any] = {
        "task_plan": task_plan,
        "workflow": workflow_ref,
    }

    # 无可用静态图：合法完成但 inspire 无法推进，先于 completed 分支判断，
    # 否则会把 no_usable_images 的降级文案当成正常完成回复。
    if (inspire_data.get("error") or {}).get("code") == "no_usable_images":
        return {
            "content": _NO_USABLE_IMAGES_MESSAGE,
            "metadata": {**metadata, "workflow_status": "failed"},
        }

    if run.status == "completed":
        composed_content = (inspire_data.get("content") or "").strip()
        if composed_content:
            flow = inspire_data.get("inspiration_flow") or {}
            if flow:
                metadata["inspiration_flow"] = flow
            if inspire_data.get("active_task") is not None:
                metadata["active_task"] = inspire_data["active_task"]
            if flow.get("status") == "generating":
                metadata["workflow_sources"] = _workflow_sources(items)
            return {
                "content": composed_content,
                "metadata": metadata,
            }

    # 降级路径：检索步骤失败、run failed、inspire 输出缺失。
    error = run.error or {}
    reason = (
        (error.get("code") or "workflow_failed")
        if run.status == "failed"
        else run.status or "workflow_failed"
    )
    return {
        "content": "灵感创建没能完成，请稍后再试；也可以直接告诉我想找的风格或城市。",
        "metadata": {
            "model": {"provider": "platform_workflow", "model": "agent-workflow-runtime"},
            "task_plan": task_plan,
            "workflow": {**workflow_ref, "error": error},
            "degraded_reason": reason,
            "user_request": (content or "")[:200],
        },
    }


def _legacy_plan_status(run: Any, inspire_data: dict[str, Any]) -> str:
    """workflow 终态 → legacy TaskPlan 的 plan status（agent_task_sequence_v1）。"""
    if (inspire_data.get("error") or {}).get("code") == "no_usable_images":
        return "failed"
    if run.status == "completed":
        return "waiting_async_result"
    if run.status == "failed":
        return "failed"
    if run.status == "cancelled":
        return "cancelled"
    return "running"


def _task_plan_snapshot(
    *,
    items: list[dict[str, Any]],
    inspire_status: str,
    plan_status: str,
) -> dict[str, Any]:
    """构造与 legacy compound_workflow 分支兼容的 TaskPlan 快照（前端卡片消费）。"""
    from backend.app.services.ai_agent_contracts import TaskPlan, TaskStep

    no_usable = plan_status == "failed"
    # workflow 步骤的 completed 对应 legacy 的 waiting_async_result：
    # 灵感生成 job 已排队但仍在后台分批执行。
    inspire_step_status = "waiting_async_result" if inspire_status == "completed" else (
        inspire_status if inspire_status in {"failed", "cancelled", "waiting_async_result"} else "waiting_async_result"
    )
    plan = TaskPlan(
        workflow_type="search_then_inspire",
        status=plan_status,
        steps=[
            TaskStep(
                id="search",
                type="resource_search",
                order=1,
                status="completed",
                fields={"resource_types": ["portfolio_items"]},
                result={
                    "count": len(items),
                    "resource_ids": [
                        item.get("id") for item in items if item.get("id") is not None
                    ],
                },
            ),
            TaskStep(
                id="inspire",
                type="create_inspiration",
                order=2,
                depends_on=["search"],
                status="failed" if no_usable else inspire_step_status,
                error="no_usable_images" if no_usable else None,
            ),
        ],
    )
    return plan.as_dict()


def _workflow_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """与 legacy workflow_sources 一致：来源作品的 id/title 对。"""
    return [
        {"id": item.get("id"), "title": item.get("title") or ""}
        for item in items[:12]
        if isinstance(item, dict)
    ]
