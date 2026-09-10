"""Workflow Runtime：Agent Workflow Run 的执行循环（workflow 阶段 C）。

实现文档 §7 的核心循环：选择 ready step -> 白名单模板解析 ->
经 capability registry 执行（超时与步骤内重试在此强制）-> persist_step_result
合并 context 并激活依赖 -> 循环直到完成、等待用户或失败。

关键设计：retryable 步骤的重试在 Runtime 内完成（record_step_attempt），
中途失败不落 step.result、不把 run 置为 failed——store 的失败传播会连带
取消 pending 依赖步骤且无法复活，所以只有最终结果才走 persist_step_result。
"""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from backend.app.models.agent_workflow import AgentWorkflowRun, AgentWorkflowStep
from backend.app.models.user import User
from backend.app.services.agent_workflow_contracts import (
    HARD_MAX_STEPS,
    TERMINAL_RUN_STATUSES,
)
from backend.app.services.agent_workflow_store import (
    expire_workflow_run,
    fail_workflow_run,
    get_ready_steps,
    load_workflow_run,
    mark_step_running,
    persist_step_result,
    record_step_attempt,
)
from backend.app.services.agent_workflow_templates import (
    TemplateResolutionError,
    build_step_view,
    resolve_input_template,
)
from backend.app.services.ai_capability_contracts import (
    CapabilityError,
    CapabilityProvenance,
    CapabilityResult,
)
from backend.app.services.ai_capability_registry import (
    execute_capability,
    get_capability_spec,
)

# 每个 retryable 步骤在宣告失败前的额外尝试次数。
DEFAULT_STEP_RETRIES = 2

_WAITING_RUN_STATUSES = frozenset({"waiting_async", "waiting_user"})

# 防御性循环上限：步骤数 *（重试 + 状态轮次）足够覆盖任何合法推进。
_MAX_LOOP_ITERATIONS = (HARD_MAX_STEPS + 1) * (DEFAULT_STEP_RETRIES + 3)


async def run_workflow(
    db: Session,
    *,
    run_id: str,
    user_id: int,
    max_retries: int = DEFAULT_STEP_RETRIES,
) -> AgentWorkflowRun:
    """执行 workflow run 直到终态、等待用户或等待异步结果。

    每轮迭代重新从库中加载 run 与 steps，模板解析与依赖推进始终基于
    最新落库状态；崩溃后可先 recover_workflow_run 再调用本入口续跑。
    """
    iterations = 0
    while True:
        run, steps = load_workflow_run(db, run_id=run_id, user_id=user_id)
        if run.status in TERMINAL_RUN_STATUSES:
            return run

        if expire_workflow_run(db, run=run):
            return run

        ready_steps = get_ready_steps(steps)
        if not ready_steps:
            if run.status in _WAITING_RUN_STATUSES:
                return run
            if all(step.status == "completed" for step in steps):
                return run
            fail_workflow_run(
                db,
                run=run,
                code="workflow_deadlock",
                message="no runnable step but workflow is neither waiting nor complete",
                detail={
                    "step_statuses": {step.step_key: step.status for step in steps},
                },
            )
            return run

        iterations += 1
        if iterations > _MAX_LOOP_ITERATIONS:
            fail_workflow_run(
                db,
                run=run,
                code="runtime_loop_exceeded",
                message="workflow runtime exceeded its defensive iteration budget",
            )
            return run

        await _execute_step(db, run=run, steps=steps, step=ready_steps[0], user_id=user_id, max_retries=max_retries)


async def _execute_step(
    db: Session,
    *,
    run: AgentWorkflowRun,
    steps: list[AgentWorkflowStep],
    step: AgentWorkflowStep,
    user_id: int,
    max_retries: int,
) -> CapabilityResult:
    """解析并执行单个 ready 步骤（含重试与超时），结果经 store 持久化。"""
    spec = get_capability_spec(step.capability)
    if spec is None:
        mark_step_running(db, run=run, step=step)
        result = _synthetic_failure(
            step.capability,
            error_code="unknown_capability",
            message=f"capability not registered: {step.capability}",
        )
        persist_step_result(db, run=run, step=step, result=result)
        return result

    try:
        resolved_input = resolve_input_template(
            step.input_template or {},
            run_input=run.input or {},
            run_context=run.context or {},
            step_view=build_step_view(steps),
        )
    except TemplateResolutionError as exc:
        mark_step_running(db, run=run, step=step)
        result = _synthetic_failure(
            step.capability,
            error_code="template_resolution_failed",
            message=f"{exc.code}: {exc.message}",
        )
        persist_step_result(db, run=run, step=step, result=result)
        return result

    idempotency_key = f"workflow:{run.id}:{step.step_key}" if spec.idempotent else None
    mark_step_running(db, run=run, step=step, resolved_input=resolved_input, idempotency_key=idempotency_key)

    # 幂等键跨 attempt 稳定：重试时工具层 replay，而不是重复写入。
    user = db.get(User, user_id) if spec.requires_user_context else None
    allowed_attempts = 1 + max_retries if spec.retryable else 1
    # run.input 由后端构造（非模型输出）：视觉分析与原始请求经此透传给
    # capability context，检索类 adapter 才能复用与主链路一致的视觉排序。
    run_input = run.input or {}

    while True:
        try:
            result = await asyncio.wait_for(
                execute_capability(
                    db,
                    name=step.capability,
                    input=dict(resolved_input),
                    user=user,
                    user_id=user_id,
                    conversation_id=run.conversation_id,
                    message_id=run.message_id,
                    attempt=step.attempt,
                    idempotency_key=idempotency_key,
                    vision_analysis=run_input.get("vision_analysis"),
                    image_attachments=run_input.get("image_attachments"),
                    request_content=run_input.get("content"),
                ),
                timeout=spec.timeout_seconds,
            )
        except asyncio.TimeoutError:
            # 被取消的协程可能在 session 里留下未提交写入，先回滚再落失败。
            db.rollback()
            result = _synthetic_failure(
                step.capability,
                error_code="capability_timeout",
                message=f"capability exceeded {spec.timeout_seconds}s timeout",
                retryable=spec.retryable,
                attempt=step.attempt,
            )

        if result.status != "failed":
            persist_step_result(db, run=run, step=step, result=result)
            return result

        retryable = bool(result.error and result.error.retryable) and spec.retryable
        if retryable and step.attempt < allowed_attempts:
            record_step_attempt(db, run=run, step=step)
            continue

        persist_step_result(db, run=run, step=step, result=result)
        return result


def _synthetic_failure(
    capability: str,
    *,
    error_code: str,
    message: str,
    retryable: bool = False,
    attempt: int = 1,
) -> CapabilityResult:
    """构造 Runtime 判定的失败信封（未注册能力/模板失败/超时）。"""
    return CapabilityResult(
        capability=capability,
        status="failed",
        error=CapabilityError(code=error_code, message=message, retryable=retryable),
        provenance=CapabilityProvenance(capability=capability, attempt=attempt),
    )
