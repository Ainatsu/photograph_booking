"""Workflow Store：Agent Workflow Run 的持久化与状态迁移（workflow 阶段 B）。

职责（见 docs/agent-workflow-orchestration-implementation.md §5/§7/§12 阶段 B）：
- 创建 run/step 并持久化 agent_workflow_plan_v2 计划；
- 强制 run/step 状态机的合法迁移，非法跳转直接拒绝；
- 将 capability_result_v1 的 data 按 context_key 合并进 run.context；
- 校验用户与会话 ownership，提供取消、deadline 过期与崩溃恢复；
- 每次状态变化写入按 run 递增 sequence 的 durable event。

执行循环、模板解析和重试策略归阶段 C 的 Runtime，本模块只提供状态原语。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.agent_workflow import AgentWorkflowEvent, AgentWorkflowRun, AgentWorkflowStep
from backend.app.services.agent_workflow_contracts import (
    DEFAULT_MAX_STEPS,
    HARD_MAX_STEPS,
    TERMINAL_RUN_STATUSES,
    TERMINAL_STEP_STATUSES,
    WORKFLOW_EVENT_CANCELLED,
    WORKFLOW_EVENT_COMPLETED,
    WORKFLOW_EVENT_CREATED,
    WORKFLOW_EVENT_FAILED,
    WORKFLOW_EVENT_RECOVERED,
    WORKFLOW_EVENT_STEP_COMPLETED,
    WORKFLOW_EVENT_STEP_FAILED,
    WORKFLOW_EVENT_STEP_RECOVERED,
    WORKFLOW_EVENT_STEP_RETRIED,
    WORKFLOW_EVENT_STEP_RESUMED,
    WORKFLOW_EVENT_STEP_STARTED,
    WORKFLOW_EVENT_STEP_WAITING_ASYNC,
    WORKFLOW_EVENT_WAITING_USER,
    WORKFLOW_PLAN_SCHEMA_VERSION,
    WORKFLOW_RUN_SNAPSHOT_SCHEMA_VERSION,
    WorkflowPlan,
    WorkflowStepSpec,
)
from backend.app.services.ai_capability_contracts import CapabilityResult


class WorkflowStoreError(Exception):
    """Workflow Store 的统一错误，code 供调用方分支处理。"""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code
        self.message = message or code


# ── 状态机 ─────────────────────────────────────────────────────────────────────
# running→ready 仅允许发生在崩溃恢复（recover_workflow_run），不放入通用迁移表。

STEP_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"ready", "failed", "cancelled"}),
    "ready": frozenset({"running", "failed", "cancelled"}),
    "running": frozenset({"completed", "waiting_async", "waiting_user", "failed", "cancelled"}),
    "waiting_async": frozenset({"ready", "cancelled"}),
    "waiting_user": frozenset({"ready", "cancelled"}),
    "completed": frozenset(),
    # failed→ready 仅通过 retry_step（保留 attempt 计数）。
    "failed": frozenset({"ready"}),
    "cancelled": frozenset(),
}

RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "running": frozenset({"waiting_async", "waiting_user", "completed", "failed", "cancelled"}),
    "waiting_async": frozenset({"running", "completed", "failed", "cancelled"}),
    "waiting_user": frozenset({"running", "completed", "failed", "cancelled"}),
    # failed→running 仅通过 retry_step 复活失败 run。
    "failed": frozenset({"running"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

_SUCCESS_STATUSES = frozenset({"success", "empty"})


# ── 创建 ──────────────────────────────────────────────────────────────────────


def create_workflow_run(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    plan: dict[str, Any] | WorkflowPlan,
    input: dict[str, Any] | None = None,
    message_id: int | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    deadline_at: datetime | None = None,
    planner_revision: int = 0,
    commit: bool = True,
) -> AgentWorkflowRun:
    """按 agent_workflow_plan_v2 计划创建 run 与全部 step。"""
    if not (1 <= max_steps <= HARD_MAX_STEPS):
        raise WorkflowStoreError("invalid_max_steps", f"max_steps must be within 1..{HARD_MAX_STEPS}")
    if isinstance(plan, WorkflowPlan):
        validated = plan
    else:
        try:
            validated = WorkflowPlan.model_validate(plan or {})
        except Exception as exc:
            raise WorkflowStoreError("invalid_plan", str(exc)[:500]) from exc
    if len(validated.steps) > max_steps:
        raise WorkflowStoreError("too_many_steps", f"plan has {len(validated.steps)} steps, max_steps={max_steps}")
    if deadline_at is not None and _as_aware(deadline_at) <= _now():
        raise WorkflowStoreError("invalid_deadline", "deadline_at must be in the future")

    run = AgentWorkflowRun(
        id=str(uuid4()),
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        workflow_type=validated.workflow_type,
        status="running",
        input=dict(input or {}),
        context={},
        planner_revision=planner_revision,
        max_steps=max_steps,
        deadline_at=deadline_at,
    )
    db.add(run)
    db.flush()

    for position, spec in enumerate(validated.steps):
        db.add(_build_step(run, spec=spec, position=position))
    db.flush()

    append_workflow_event(
        db,
        run=run,
        event_type=WORKFLOW_EVENT_CREATED,
        payload={
            "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
            "workflow_type": validated.workflow_type,
            "step_count": len(validated.steps),
            "max_steps": max_steps,
            "deadline_at": deadline_at.isoformat() if deadline_at else None,
        },
    )
    if commit:
        db.commit()
    return run


def _build_step(run: AgentWorkflowRun, *, spec: WorkflowStepSpec, position: int) -> AgentWorkflowStep:
    return AgentWorkflowStep(
        id=str(uuid4()),
        workflow_run_id=run.id,
        step_key=spec.id,
        capability=spec.capability,
        depends_on=list(spec.depends_on),
        input_template=dict(spec.input_template),
        context_key=spec.effective_context_key,
        position=position,
        status="ready" if not spec.depends_on else "pending",
    )


# ── 读取与 ownership ──────────────────────────────────────────────────────────


def get_workflow_run(db: Session, *, run_id: str, user_id: int) -> AgentWorkflowRun:
    """按 id 加载 run，并校验用户 ownership（他人 run 一律按不存在处理）。"""
    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.id == run_id).first()
    if run is None or run.user_id != user_id:
        raise WorkflowStoreError("not_found", f"workflow run not found: {run_id}")
    return run


def load_workflow_run(
    db: Session,
    *,
    run_id: str,
    user_id: int,
    conversation_id: int | None = None,
) -> tuple[AgentWorkflowRun, list[AgentWorkflowStep]]:
    """加载 run 及按计划顺序排列的 steps。传入 conversation_id 时一并校验。"""
    run = get_workflow_run(db, run_id=run_id, user_id=user_id)
    if conversation_id is not None and run.conversation_id != conversation_id:
        raise WorkflowStoreError("forbidden", "workflow run does not belong to this conversation")
    steps = _load_steps(db, run.id)
    return run, steps


def _load_steps(db: Session, run_id: str) -> list[AgentWorkflowStep]:
    return (
        db.query(AgentWorkflowStep)
        .filter(AgentWorkflowStep.workflow_run_id == run_id)
        .order_by(AgentWorkflowStep.position.asc(), AgentWorkflowStep.id.asc())
        .all()
    )


def get_ready_steps(steps: list[AgentWorkflowStep]) -> list[AgentWorkflowStep]:
    """按计划顺序返回处于 ready 状态的步骤（供 Runtime 选择执行）。"""
    return [step for step in steps if step.status == "ready"]


def list_workflow_events(
    db: Session,
    *,
    run_id: str,
    user_id: int,
    after_sequence: int = 0,
) -> list[AgentWorkflowEvent]:
    """按 sequence 升序返回事件，支持断线补发游标。"""
    get_workflow_run(db, run_id=run_id, user_id=user_id)
    return (
        db.query(AgentWorkflowEvent)
        .filter(
            AgentWorkflowEvent.workflow_run_id == run_id,
            AgentWorkflowEvent.sequence > after_sequence,
        )
        .order_by(AgentWorkflowEvent.sequence.asc())
        .all()
    )


# ── 步骤执行与结果持久化 ─────────────────────────────────────────────────────


def mark_step_running(
    db: Session,
    *,
    run: AgentWorkflowRun,
    step: AgentWorkflowStep,
    resolved_input: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    commit: bool = True,
) -> AgentWorkflowStep:
    """ready → running：记录解析后的输入、attempt 与幂等键。"""
    _require_run_active(run)
    _transition_step(step, "running")
    step.attempt += 1
    step.started_at = step.started_at or _now()
    step.resolved_input = dict(resolved_input or {})
    if idempotency_key is not None:
        step.idempotency_key = idempotency_key
    run.current_step_id = step.id
    append_workflow_event(
        db,
        run=run,
        step=step,
        event_type=WORKFLOW_EVENT_STEP_STARTED,
        payload={"step_key": step.step_key, "capability": step.capability, "attempt": step.attempt},
    )
    if commit:
        db.commit()
    return step


def persist_step_result(
    db: Session,
    *,
    run: AgentWorkflowRun,
    step: AgentWorkflowStep,
    result: CapabilityResult,
    commit: bool = True,
) -> AgentWorkflowStep:
    """持久化 capability_result_v1：落库、合并 context、推进依赖与 run 状态。"""
    if step.status != "running":
        raise WorkflowStoreError("invalid_transition", f"step {step.step_key} is {step.status}, expected running")
    envelope = result.as_dict()
    step.result = envelope
    step.completed_at = _now()

    if result.status in _SUCCESS_STATUSES:
        _transition_step(step, "completed")
        _merge_result_into_context(run, step, result)
        append_workflow_event(
            db,
            run=run,
            step=step,
            event_type=WORKFLOW_EVENT_STEP_COMPLETED,
            payload={"step_key": step.step_key, "capability": step.capability, "status": result.status},
        )
        steps = _load_steps(db, run.id)
        _activate_ready_dependents(steps)
        if all(item.status == "completed" for item in steps):
            run.result = envelope
            _transition_run(run, "completed")
            run.completed_at = _now()
            append_workflow_event(
                db,
                run=run,
                event_type=WORKFLOW_EVENT_COMPLETED,
                payload={"workflow_type": run.workflow_type},
            )
    elif result.status == "waiting_async":
        _transition_step(step, "waiting_async")
        _transition_run(run, "waiting_async")
        append_workflow_event(
            db,
            run=run,
            step=step,
            event_type=WORKFLOW_EVENT_STEP_WAITING_ASYNC,
            payload={"step_key": step.step_key, "capability": step.capability},
        )
    elif result.status == "waiting_user":
        _transition_step(step, "waiting_user")
        _transition_run(run, "waiting_user")
        append_workflow_event(
            db,
            run=run,
            step=step,
            event_type=WORKFLOW_EVENT_WAITING_USER,
            payload={"step_key": step.step_key, "capability": step.capability},
        )
    else:
        _fail_step_and_run(db, run=run, step=step, result=result)

    if commit:
        db.commit()
    return step


def retry_step(
    db: Session,
    *,
    run: AgentWorkflowRun,
    step: AgentWorkflowStep,
    commit: bool = True,
) -> AgentWorkflowStep:
    """failed → ready：保留 attempt 计数，复活失败的 run。重试上限归阶段 C Runtime。"""
    if step.status != "failed":
        raise WorkflowStoreError("invalid_transition", f"step {step.step_key} is {step.status}, expected failed")
    _transition_step(step, "ready")
    if run.status == "failed":
        _transition_run(run, "running")
    append_workflow_event(
        db,
        run=run,
        step=step,
        event_type=WORKFLOW_EVENT_STEP_RETRIED,
        payload={"step_key": step.step_key, "attempt": step.attempt},
    )
    if commit:
        db.commit()
    return step


def resume_step(
    db: Session,
    *,
    run: AgentWorkflowRun,
    step: AgentWorkflowStep,
    commit: bool = True,
) -> AgentWorkflowStep:
    """waiting_async/waiting_user → ready：异步结果回传或用户确认后继续执行。"""
    if step.status not in {"waiting_async", "waiting_user"}:
        raise WorkflowStoreError(
            "invalid_transition",
            f"step {step.step_key} is {step.status}, expected waiting_async/waiting_user",
        )
    from_status = step.status or ""
    _transition_step(step, "ready")
    if run.status in {"waiting_async", "waiting_user"}:
        _transition_run(run, "running")
    append_workflow_event(
        db,
        run=run,
        step=step,
        event_type=WORKFLOW_EVENT_STEP_RESUMED,
        payload={"step_key": step.step_key, "from_status": from_status},
    )
    if commit:
        db.commit()
    return step


# ── Runtime 重试支持 ─────────────────────────────────────────────────────────


def record_step_attempt(
    db: Session,
    *,
    run: AgentWorkflowRun,
    step: AgentWorkflowStep,
    commit: bool = True,
) -> AgentWorkflowStep:
    """running 态记录一次重试尝试：attempt += 1 并写 retried 事件，不迁移状态。

    供阶段 C Runtime 在步骤内部重试时使用：中途失败不落 step.result、
    不经过 failed 状态（run 一旦 failed 会连带取消 pending 依赖步骤且无法复活），
    只有最终结果才走 persist_step_result。
    """
    if step.status != "running":
        raise WorkflowStoreError("invalid_transition", f"step {step.step_key} is {step.status}, expected running")
    step.attempt += 1
    append_workflow_event(
        db,
        run=run,
        step=step,
        event_type=WORKFLOW_EVENT_STEP_RETRIED,
        payload={"step_key": step.step_key, "attempt": step.attempt, "reason": "runtime_retry"},
    )
    if commit:
        db.commit()
    return step


def fail_workflow_run(
    db: Session,
    *,
    run: AgentWorkflowRun,
    code: str,
    message: str,
    detail: dict[str, Any] | None = None,
    commit: bool = True,
) -> AgentWorkflowRun:
    """把 run 置为 failed 并取消非终态步骤（deadlock 等运行时判定的失败）。"""
    _fail_run(db, run=run, code=code, message=message, detail=detail)
    if commit:
        db.commit()
    return run


# ── 取消、失败与 deadline ────────────────────────────────────────────────────


def cancel_workflow_run(
    db: Session,
    *,
    run_id: str,
    user_id: int,
    reason: str | None = None,
    commit: bool = True,
) -> AgentWorkflowRun:
    """取消整个 run：非终态步骤一并置为 cancelled。"""
    run = get_workflow_run(db, run_id=run_id, user_id=user_id)
    if run.status in TERMINAL_RUN_STATUSES:
        raise WorkflowStoreError("already_terminal", f"workflow run is {run.status}")
    _transition_run(run, "cancelled")
    run.completed_at = _now()
    cancelled_keys: list[str] = []
    for step in _load_steps(db, run.id):
        if step.status not in TERMINAL_STEP_STATUSES:
            _transition_step(step, "cancelled")
            cancelled_keys.append(step.step_key)
    append_workflow_event(
        db,
        run=run,
        event_type=WORKFLOW_EVENT_CANCELLED,
        payload={"reason": reason, "cancelled_steps": cancelled_keys},
    )
    if commit:
        db.commit()
    return run


def expire_workflow_run(db: Session, *, run: AgentWorkflowRun, commit: bool = True) -> bool:
    """超过 deadline 的非终态 run 置为 failed（deadline_exceeded）。"""
    if run.status in TERMINAL_RUN_STATUSES or run.deadline_at is None:
        return False
    if _now() <= _as_aware(run.deadline_at):
        return False
    _fail_run(
        db,
        run=run,
        code="deadline_exceeded",
        message="workflow run exceeded its deadline",
    )
    if commit:
        db.commit()
    return True


def _fail_step_and_run(db: Session, *, run: AgentWorkflowRun, step: AgentWorkflowStep, result: CapabilityResult) -> None:
    error = result.error.model_dump(mode="json") if result.error else {"code": "capability_error", "message": ""}
    step.error = error
    _transition_step(step, "failed")
    append_workflow_event(
        db,
        run=run,
        step=step,
        event_type=WORKFLOW_EVENT_STEP_FAILED,
        payload={"step_key": step.step_key, "capability": step.capability, "error": error},
    )
    _fail_run(
        db,
        run=run,
        code="step_failed",
        message=f"step {step.step_key} ({step.capability}) failed",
        detail={"step_key": step.step_key, "capability": step.capability, "error": error},
    )


def _fail_run(
    db: Session,
    *,
    run: AgentWorkflowRun,
    code: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None:
    if run.status in TERMINAL_RUN_STATUSES:
        return
    _transition_run(run, "failed")
    run.error = {"code": code, "message": message, **(detail or {})}
    run.completed_at = _now()
    for step in _load_steps(db, run.id):
        if step.status not in TERMINAL_STEP_STATUSES:
            _transition_step(step, "cancelled")
    append_workflow_event(
        db,
        run=run,
        event_type=WORKFLOW_EVENT_FAILED,
        payload={"code": code, "message": message},
    )


# ── 崩溃恢复 ─────────────────────────────────────────────────────────────────


def recover_workflow_run(
    db: Session,
    *,
    run_id: str,
    user_id: int,
    commit: bool = True,
) -> tuple[AgentWorkflowRun, list[AgentWorkflowStep], dict[str, Any]]:
    """进程重启后的恢复入口：running 步骤重置为 ready，从最后一个未完成步骤继续。

    - running → ready：进程崩溃时遗留的执行中步骤（保留 attempt 计数）；
    - pending → ready：依赖已全部完成却被中断在激活之前的步骤（防御性重算）；
    - waiting_* 状态与对应 run 状态保持不动，等待异步结果或用户输入。
    """
    run, steps = load_workflow_run(db, run_id=run_id, user_id=user_id)
    info: dict[str, Any] = {"run_id": run.id, "recovered": False, "reset_steps": []}
    if run.status in TERMINAL_RUN_STATUSES:
        return run, steps, info

    for step in steps:
        if step.status == "running":
            # 崩溃恢复专属迁移：running→ready 只在这里合法。
            step.status = "ready"
            info["reset_steps"].append(step.step_key)
            append_workflow_event(
                db,
                run=run,
                step=step,
                event_type=WORKFLOW_EVENT_STEP_RECOVERED,
                payload={"step_key": step.step_key, "attempt": step.attempt},
            )
    _activate_ready_dependents(steps)

    if run.status == "running" and all(item.status == "completed" for item in steps):
        _transition_run(run, "completed")
        run.completed_at = _now()
        append_workflow_event(db, run=run, event_type=WORKFLOW_EVENT_COMPLETED, payload={})
    elif run.status in {"waiting_async", "waiting_user"} and not any(
        item.status in {"waiting_async", "waiting_user"} for item in steps
    ):
        # 没有任何步骤在等待，说明 run 状态是崩溃前的残留，回到 running。
        _transition_run(run, "running")

    if info["reset_steps"]:
        info["recovered"] = True
        append_workflow_event(
            db,
            run=run,
            event_type=WORKFLOW_EVENT_RECOVERED,
            payload={"reset_steps": info["reset_steps"]},
        )
    if commit:
        db.commit()
    return run, steps, info


# ── 序列化 ───────────────────────────────────────────────────────────────────


def serialize_workflow_run(
    db: Session,
    run: AgentWorkflowRun,
    steps: list[AgentWorkflowStep] | None = None,
) -> dict[str, Any]:
    """导出 run 快照（agent_workflow_run_snapshot_v1），供 API 与调试使用。"""
    if steps is None:
        steps = _load_steps(db, run.id)
    return {
        "schema_version": WORKFLOW_RUN_SNAPSHOT_SCHEMA_VERSION,
        "workflow_run_id": run.id,
        "workflow_type": run.workflow_type,
        "status": run.status,
        "user_id": run.user_id,
        "conversation_id": run.conversation_id,
        "message_id": run.message_id,
        "current_step_id": run.current_step_id,
        "planner_revision": run.planner_revision,
        "max_steps": run.max_steps,
        "deadline_at": run.deadline_at.isoformat() if run.deadline_at else None,
        "error": run.error,
        "input": run.input or {},
        "context": run.context or {},
        "result": run.result,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "steps": [
            {
                "step_id": step.id,
                "step_key": step.step_key,
                "capability": step.capability,
                "depends_on": step.depends_on or [],
                "context_key": step.context_key,
                "position": step.position,
                "status": step.status,
                "attempt": step.attempt,
                "error": step.error,
            }
            for step in steps
        ],
    }


def workflow_metadata(run: AgentWorkflowRun) -> dict[str, Any]:
    """写入 AIMessage.message_metadata 的 workflow 引用（文档 §11.3）。"""
    return {
        "workflow_run_id": run.id,
        "workflow_status": run.status,
        "current_step_id": run.current_step_id,
    }


# ── 内部工具 ─────────────────────────────────────────────────────────────────


def _transition_step(step: AgentWorkflowStep, new_status: str) -> None:
    allowed = STEP_TRANSITIONS.get(step.status or "", frozenset())
    if new_status not in allowed:
        raise WorkflowStoreError(
            "invalid_transition",
            f"step {step.step_key} cannot transition {step.status} -> {new_status}",
        )
    step.status = new_status


def _transition_run(run: AgentWorkflowRun, new_status: str) -> None:
    allowed = RUN_TRANSITIONS.get(run.status or "", frozenset())
    if new_status not in allowed:
        raise WorkflowStoreError(
            "invalid_transition",
            f"workflow run cannot transition {run.status} -> {new_status}",
        )
    run.status = new_status


def _require_run_active(run: AgentWorkflowRun) -> None:
    if run.status in TERMINAL_RUN_STATUSES:
        raise WorkflowStoreError("already_terminal", f"workflow run is {run.status}")


def _merge_result_into_context(run: AgentWorkflowRun, step: AgentWorkflowStep, result: CapabilityResult) -> None:
    """把通过 output schema 校验的 data 按 context_key 合并进 run.context。

    JSON 列不追踪原地修改，必须整体重新赋值。
    """
    context = dict(run.context or {})
    context[step.context_key or step.step_key] = result.data or {}
    run.context = context


def _activate_ready_dependents(steps: list[AgentWorkflowStep]) -> None:
    """依赖已全部完成的 pending 步骤激活为 ready。"""
    status_map = {step.step_key: step.status for step in steps}
    for step in steps:
        if step.status != "pending":
            continue
        deps = step.depends_on or []
        if all(status_map.get(dep) == "completed" for dep in deps):
            _transition_step(step, "ready")


def append_workflow_event(
    db: Session,
    *,
    run: AgentWorkflowRun,
    event_type: str,
    step: AgentWorkflowStep | None = None,
    payload: dict[str, Any] | None = None,
) -> AgentWorkflowEvent:
    """追加事件；sequence 按 run 内当前最大值递增，保证断线补发有序。"""
    current_max = (
        db.query(AgentWorkflowEvent.sequence)
        .filter(AgentWorkflowEvent.workflow_run_id == run.id)
        .order_by(AgentWorkflowEvent.sequence.desc())
        .first()
    )
    sequence = (current_max[0] if current_max else 0) + 1
    event = AgentWorkflowEvent(
        workflow_run_id=run.id,
        step_id=step.id if step is not None else None,
        event_type=event_type,
        payload=dict(payload or {}),
        sequence=sequence,
    )
    db.add(event)
    db.flush()
    return event


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _now() -> datetime:
    return datetime.now(timezone.utc)
