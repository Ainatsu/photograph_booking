"""预订流程迁移到 Workflow Runtime（workflow 阶段 E 第二部分）。

把原先 ai_service.py 中 booking_plan_result / booking_agent_result 的固定
分支拆成普通 workflow definition，并按文档 §11.1/§12 阶段 E 把需要确认的
写操作（create_booking）接入 waiting_user：

```text
package.search → booking.create（依赖 search 的结构化 items）
```

- `booking.create` 复刻 booking_agent_result 的阶段分支（缺套餐 → 缺日期
  → 待确认 → 创建），回复正文、task_state、pending_action、task_plan 全部
  复用 legacy 构造器，AgentTaskDraft 仍由 send_ai_message 的 task_state
  同步机制维护，确认策略沿用 _is_explicit_task_confirmation 显式短语；
- awaiting_* 阶段步骤状态为 waiting_user，run 持久化跨轮存在；用户补充
  日期或显式确认后 resume_step 继续执行，工具结果（订单）经既有
  create_booking 工具落库（policy 校验、action log、幂等与 legacy 一致）；
- 与 legacy 的已知差异：聊天中的显式确认（「确认预约」）会真正执行创建
  （legacy 在存在任务草稿时只提示走任务卡提交）；workflow 分支的回复不再
  被 Phase G 的任务进度 overlay 覆盖（结果链本就排除 booking_flow，overlay
  未排除属于遗留不一致）。

触发与灰度：intent == booking_flow 且 feature flag
AI_AGENT_WORKFLOW_BOOKING_ENABLED 开启时接管；关闭时回落既有分支。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.agent_workflow import AgentWorkflowRun
from backend.app.services.agent_workflow_contracts import (
    WORKFLOW_PLAN_SCHEMA_VERSION,
)
from backend.app.services.agent_workflow_event_mirror import (
    mirror_new_workflow_events,
)
from backend.app.services.agent_workflow_store import (
    cancel_workflow_run,
    create_workflow_run,
    load_workflow_run,
    resume_step,
)

WORKFLOW_TYPE_BOOKING = "booking_flow"

# 降级/完成结果里引用 workflow 的 metadata 键。
WORKFLOW_REF_SCHEMA_VERSION = "agent_workflow_ref_v1"

# 与 legacy 预订检索一致的默认数量。
_SEARCH_LIMIT = 3

# waiting run 的兜底过期时间：跨天补日期/确认的对话不受影响，
# 被取消任务遗留的孤儿 run 最多存活一周。
_BOOKING_DEADLINE = timedelta(days=7)

_DEGRADED_MESSAGE = "预约流程没能完成，请稍后再试；也可以直接告诉我想约的套餐和日期。"


def build_booking_plan() -> dict[str, Any]:
    """构造 agent_workflow_plan_v2 计划：search → create 两步 DAG。

    run.input 的 booking/search 子对象由本模块归一（所有键必定存在），
    多轮状态（slots/task_state/confirmed/first_turn）每轮更新后经模板
    重新解析，驱动 create 步骤的阶段分支。
    """
    return {
        "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
        "workflow_type": WORKFLOW_TYPE_BOOKING,
        "steps": [
            {
                "id": "search",
                "capability": "package.search",
                "depends_on": [],
                "input_template": {
                    "query_text": "$input.query_text",
                    "city": "$input.search.city",
                    "styles": "$input.search.styles",
                    "budget_min": "$input.search.budget_min",
                    "budget_max": "$input.search.budget_max",
                    "limit": "$input.search.limit",
                },
                "context_key": "packages",
            },
            {
                "id": "create",
                "capability": "booking.create",
                "depends_on": ["search"],
                "input_template": {
                    "user_request": "$input.content",
                    "items": "$context.packages.items",
                    "slots": "$input.booking.slots",
                    "intent_slots": "$input.intent_slots",
                    "task_state": "$input.booking.task_state",
                    "confirmed": "$input.booking.confirmed",
                    "first_turn": "$input.booking.first_turn",
                    "vision_analysis": "$input.vision_analysis",
                    "vision_reused_context": "$input.vision_reused_context",
                    "search_criteria": "$context.packages.criteria",
                },
            },
        ],
    }


def find_active_booking_run(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
) -> AgentWorkflowRun | None:
    """查找会话内未终结的预订 workflow run（waiting_user 等）。"""
    return (
        db.query(AgentWorkflowRun)
        .filter(
            AgentWorkflowRun.user_id == user_id,
            AgentWorkflowRun.conversation_id == conversation_id,
            AgentWorkflowRun.workflow_type == WORKFLOW_TYPE_BOOKING,
            AgentWorkflowRun.status.in_(["running", "waiting_user", "waiting_async"]),
        )
        .order_by(AgentWorkflowRun.created_at.desc(), AgentWorkflowRun.id.desc())
        .first()
    )


async def run_booking_workflow(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    content: str | None,
    intent: Any,
    vision_analysis: dict[str, Any] | None = None,
    vision_reused_context: bool = False,
    package_reference: dict | None = None,
    confirm_requested: bool = False,
    turn_id: str | None = None,
) -> dict[str, Any]:
    """创建（或恢复）预订 workflow run，返回 {content, metadata} 形状的回复。

    任何失败（检索失败、deadline、deadlock）都不向上抛异常：返回降级
    文案 + 带 workflow 引用的 metadata，对话主链路保持可用。
    """
    from backend.app.services.agent_workflow_runtime import run_workflow
    from backend.app.services.ai_booking_service import (
        _extract_booking_slots,
        _latest_booking_task_state,
        _merge_booking_slots,
        _normalize_package,
    )

    existing = find_active_booking_run(db, user_id=user_id, conversation_id=conversation_id)
    resumable = existing is not None and _latest_booking_task_state(
        db, conversation_id, user_id
    ) is not None
    if existing is not None and not resumable:
        # 任务草稿已被取消/终结：孤儿 run 取消后重新开始，避免在旧状态上续跑。
        cancel_workflow_run(db, run_id=existing.id, user_id=user_id, reason="booking_task_closed")
        existing = None

    if existing is None:
        slots = _merge_booking_slots(None, content)
        slots = _apply_package_reference(slots, package_reference, _normalize_package)
        run = create_workflow_run(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            plan=build_booking_plan(),
            input=_build_run_input(
                content=content,
                intent_slots=dict(intent.slots or {}),
                slots=slots,
                vision_analysis=vision_analysis,
                vision_reused_context=vision_reused_context,
            ),
            message_id=message_id,
            deadline_at=datetime.now(timezone.utc) + _BOOKING_DEADLINE,
            commit=True,
        )
        first_turn = True
    else:
        run = existing
        first_turn = False
        run, steps = load_workflow_run(db, run_id=run.id, user_id=user_id)
        create_step = next(step for step in steps if step.step_key == "create")
        previous_task_state = _waiting_task_state(create_step)
        # 上一轮 input 槽位（本轮前）与 waiting 结果里 adapter 富化过的
        # task_state.slots（含 selected_package/摄影师绑定）合并后再叠加
        # 本轮文本抽取，等价于 legacy 的 _merge_booking_slots 链。
        previous_slots = ((run.input or {}).get("booking") or {}).get("slots") or {}
        state_slots = (previous_task_state or {}).get("slots") or {}
        slots = _merge_booking_slots(
            {"slots": {**state_slots, **previous_slots}}, content
        )
        slots = _apply_package_reference(slots, package_reference, _normalize_package)
        # 审计对齐：action log 的 message_id 指向触发本轮执行的 user message。
        run.message_id = message_id
        run.input = {
            **(run.input or {}),
            "content": content or "",
            "booking": {
                "slots": slots,
                "task_state": previous_task_state,
                "confirmed": bool(confirm_requested),
                "first_turn": False,
            },
        }
        db.commit()
        resume_step(db, run=run, step=create_step)

    mirror_new_workflow_events(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        run=run,
        after_sequence=_mirrored_sequence(db, conversation_id=conversation_id, run_id=run.id),
        turn_id=turn_id,
    )
    run = await run_workflow(db, run_id=run.id, user_id=user_id)
    mirror_new_workflow_events(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        run=run,
        after_sequence=_mirrored_sequence(db, conversation_id=conversation_id, run_id=run.id),
        turn_id=turn_id,
    )

    run, steps = load_workflow_run(db, run_id=run.id, user_id=user_id)
    return _result_from_run(run=run, steps=steps, first_turn=first_turn)


# ── run.input 构造与多轮状态 ─────────────────────────────────────────────────


def _build_run_input(
    *,
    content: str | None,
    intent_slots: dict[str, Any],
    slots: dict[str, Any],
    vision_analysis: dict[str, Any] | None,
    vision_reused_context: bool,
) -> dict[str, Any]:
    """归一 run.input：模板引用的键必须全部存在，None/[] 合法。"""
    from backend.app.services.ai_vision_service import build_vision_search_text

    # 与 legacy 一致：有视觉分析时检索文本用视觉派生词，否则用原话。
    if vision_analysis:
        query_text = build_vision_search_text(content, vision_analysis)
    else:
        query_text = content or ""

    styles = intent_slots.get("styles") or intent_slots.get("style") or []
    if isinstance(styles, str):
        styles = [styles]
    limit = intent_slots.get("limit")
    try:
        limit = int(limit) if limit is not None else _SEARCH_LIMIT
    except (TypeError, ValueError):
        limit = _SEARCH_LIMIT

    return {
        "content": content or "",
        "query_text": query_text,
        "intent_slots": dict(intent_slots),
        "vision_analysis": dict(vision_analysis) if vision_analysis else None,
        "vision_reused_context": bool(vision_reused_context),
        "search": {
            "city": intent_slots.get("city"),
            "styles": [str(style) for style in styles if style],
            "budget_min": intent_slots.get("budget_min"),
            "budget_max": intent_slots.get("budget_max"),
            "limit": limit,
        },
        "booking": {
            "slots": dict(slots),
            "task_state": None,
            "confirmed": False,
            "first_turn": True,
        },
    }


def _apply_package_reference(
    slots: dict[str, Any],
    package_reference: dict | None,
    normalize_package: Any,
) -> dict[str, Any]:
    """资源卡片引用的套餐快照并入槽位（同 booking_agent_result L506-516）。"""
    if not package_reference:
        return slots
    snapshot = package_reference.get("snapshot") or {}
    package = normalize_package(snapshot)
    slots.update({
        "package_id": package.get("id"),
        "package_name": package.get("name"),
        "selected_package": package,
    })
    if package.get("photographer_id"):
        slots["photographer_id"] = package["photographer_id"]
        slots["photographer_name"] = snapshot.get("photographer_name")
    return slots


def _waiting_task_state(create_step: Any) -> dict[str, Any] | None:
    """读取 create 步骤上一轮 waiting 结果里的 task_state（含 task_plan）。"""
    result = create_step.result if isinstance(create_step.result, dict) else None
    data = (result or {}).get("data") or {}
    task_state = ((data.get("metadata") or {}).get("task_state")) or None
    return task_state if isinstance(task_state, dict) else None


def _mirrored_sequence(
    db: Session,
    *,
    conversation_id: int,
    run_id: str,
) -> int:
    """查询该 run 已镜像进对话事件流的最大 workflow sequence（跨轮去重）。"""
    from backend.app.models.ai_conversation import AIConversationEvent

    events = (
        db.query(AIConversationEvent)
        .filter(
            AIConversationEvent.conversation_id == conversation_id,
            AIConversationEvent.task_id == run_id,
        )
        .all()
    )
    sequences = [
        int((event.payload or {}).get("workflow_sequence") or 0)
        for event in events
    ]
    return max(sequences) if sequences else 0


# ── 结果组装 ─────────────────────────────────────────────────────────────────


def _result_from_run(
    *,
    run: Any,
    steps: list[Any],
    first_turn: bool,
) -> dict[str, Any]:
    """从 run 终态组装助手回复；create 步骤结果即最终回复。"""
    workflow_ref = {
        "schema_version": WORKFLOW_REF_SCHEMA_VERSION,
        "workflow_run_id": run.id,
        "workflow_type": run.workflow_type,
        "status": run.status,
    }
    create_step = next((step for step in steps if step.step_key == "create"), None)
    data = (
        (create_step.result or {}).get("data")
        if create_step is not None and isinstance(create_step.result, dict)
        else None
    ) or {}
    content = (data.get("content") or "").strip()

    if run.status in ("completed", "waiting_user") and content:
        metadata = {**(data.get("metadata") or {}), "workflow": workflow_ref}
        if first_turn:
            # 检索对齐：把 search 步骤的真实套餐写进 references/retrieval，
            # 与 legacy 检索轮的 Phase G 行为一致（后续轮的套餐引用依赖它）。
            # 首轮结束态是 waiting_user（create 步骤等待日期），两个分支都要带。
            search_result = (run.context or {}).get("packages") or {}
            metadata["references"] = {
                "packages": search_result.get("items") or [],
                "photographers": [],
                "portfolio_items": [],
            }
            metadata["retrieval"] = {
                "context_schema_version": "ai_retrieval_v1",
                "criteria": search_result.get("criteria") or {},
                "diagnostics": search_result.get("diagnostics") or {},
            }
        return {"content": content, "metadata": metadata}

    # 降级路径：search 步骤失败、run failed、create 输出缺失。
    error = run.error or {}
    reason = (
        (error.get("code") or "workflow_failed")
        if run.status == "failed"
        else run.status or "workflow_failed"
    )
    return {
        "content": _DEGRADED_MESSAGE,
        "metadata": {
            "model": {"provider": "platform_workflow", "model": "agent-workflow-runtime"},
            "workflow": {**workflow_ref, "error": error},
            "degraded_reason": reason,
            "user_request": ((run.input or {}).get("content") or "")[:200],
        },
    }
