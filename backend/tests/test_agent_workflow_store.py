"""Workflow Store 持久化层测试（workflow 阶段 B）。

覆盖文档 §12 阶段 B 的验收面：
- run/step 序列化与状态迁移（含非法迁移拒绝）；
- 用户与会话 ownership 校验；
- 最大步骤数、deadline 过期与取消；
- capability 结果合并进 workflow context 并激活依赖步骤；
- 进程重启后从最后一个未完成步骤恢复（验收标准）。
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.models.ai_conversation import AIConversation
from backend.app.models.user import User
from backend.app.services.agent_workflow_contracts import WorkflowPlan
from backend.app.services.agent_workflow_store import (
    WorkflowStoreError,
    cancel_workflow_run,
    create_workflow_run,
    expire_workflow_run,
    get_ready_steps,
    get_workflow_run,
    list_workflow_events,
    load_workflow_run,
    mark_step_running,
    persist_step_result,
    recover_workflow_run,
    resume_step,
    retry_step,
    serialize_workflow_run,
    workflow_metadata,
)
from backend.app.services.ai_capability_contracts import CapabilityError, CapabilityResult
from backend.tests.conftest import TestingSessionLocal


@contextmanager
def expect_store_error(code: str, message_contains: str | None = None):
    """按 code 断言 WorkflowStoreError（message 仅供区分同码错误）。"""
    with pytest.raises(WorkflowStoreError) as exc_info:
        yield
    assert exc_info.value.code == code
    if message_contains:
        assert message_contains in exc_info.value.message


def _plan_dict() -> dict:
    """文档 §6 的示例计划：赏析 -> 检索 -> 汇总。"""
    return {
        "schema_version": "agent_workflow_plan_v2",
        "workflow_type": "image_appreciation_and_search",
        "steps": [
            {
                "id": "analyze",
                "capability": "vision.appreciate_image",
                "depends_on": [],
                "input_template": {"attachments": "$input.attachments"},
                "context_key": "image_analysis",
            },
            {
                "id": "search",
                "capability": "portfolio.search",
                "depends_on": ["analyze"],
                "input_template": {"query_text": "$context.image_analysis.search_query", "limit": 6},
            },
            {
                "id": "summarize",
                "capability": "agent.compose_response",
                "depends_on": ["analyze", "search"],
                "input_template": {
                    "analysis": "$steps.analyze.result",
                    "matches": "$steps.search.result",
                },
            },
        ],
    }


def _result(capability: str, status: str = "success", data: dict | None = None) -> CapabilityResult:
    return CapabilityResult(
        capability=capability,
        status=status,
        data=data or {},
        error=CapabilityError(code="capability_error", message="boom") if status == "failed" else None,
    )


@pytest.fixture
def conversation(db, customer_user) -> AIConversation:
    conv = AIConversation(user_id=customer_user.id, title="workflow")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@pytest.fixture
def other_user(db) -> User:
    user = User(email="other@test.com", phone="13800000099", hashed_password="x", display_name="他人", role="customer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def created(db, customer_user, conversation):
    return create_workflow_run(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        plan=_plan_dict(),
        input={"attachments": ["/static/ai/1/reference.jpg"]},
    )


def _steps_by_key(db, run):
    _, steps = load_workflow_run(db, run_id=run.id, user_id=run.user_id)
    return {step.step_key: step for step in steps}


def _event_types(db, run) -> list[str]:
    return [e.event_type for e in list_workflow_events(db, run_id=run.id, user_id=run.user_id)]


# ── 创建与计划校验 ────────────────────────────────────────────────────────────


def test_create_initializes_steps_and_created_event(db, customer_user, conversation):
    run = create_workflow_run(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        plan=_plan_dict(),
        input={"attachments": ["/static/ai/1/reference.jpg"]},
    )
    assert run.status == "running"
    assert run.context == {}
    assert run.input == {"attachments": ["/static/ai/1/reference.jpg"]}
    assert run.max_steps == 32

    steps = _steps_by_key(db, run)
    assert steps["analyze"].status == "ready"
    assert steps["search"].status == "pending"
    assert steps["summarize"].status == "pending"
    assert steps["analyze"].context_key == "image_analysis"
    assert steps["search"].context_key == "search"

    events = list_workflow_events(db, run_id=run.id, user_id=customer_user.id)
    assert [e.event_type for e in events] == ["workflow.created"]
    assert events[0].sequence == 1
    assert events[0].payload["step_count"] == 3


def test_create_rejects_invalid_plans(db, customer_user, conversation):
    cyclic = WorkflowPlan.model_validate(_plan_dict())
    cyclic.steps[1].depends_on = ["summarize"]
    with expect_store_error("invalid_plan", "cyclic_dependencies"):
        create_workflow_run(db, user_id=customer_user.id, conversation_id=conversation.id, plan=cyclic.model_dump())

    unknown = _plan_dict()
    unknown["steps"][1]["depends_on"] = ["nonexistent"]
    with expect_store_error("invalid_plan", "unknown_dependency"):
        create_workflow_run(db, user_id=customer_user.id, conversation_id=conversation.id, plan=unknown)

    duplicate = _plan_dict()
    duplicate["steps"][1]["id"] = "analyze"
    with expect_store_error("invalid_plan", "duplicate_step_id"):
        create_workflow_run(db, user_id=customer_user.id, conversation_id=conversation.id, plan=duplicate)

    self_dep = _plan_dict()
    self_dep["steps"][0]["depends_on"] = ["analyze"]
    with expect_store_error("invalid_plan", "self_dependency"):
        create_workflow_run(db, user_id=customer_user.id, conversation_id=conversation.id, plan=self_dep)

    no_steps = _plan_dict()
    no_steps["steps"] = []
    with expect_store_error("invalid_plan"):
        create_workflow_run(db, user_id=customer_user.id, conversation_id=conversation.id, plan=no_steps)

    with expect_store_error("too_many_steps"):
        create_workflow_run(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            plan=_plan_dict(),
            max_steps=2,
        )


def test_create_rejects_past_deadline(db, customer_user, conversation):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    with expect_store_error("invalid_deadline"):
        create_workflow_run(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            plan=_plan_dict(),
            deadline_at=past,
        )


# ── ownership ────────────────────────────────────────────────────────────────


def test_ownership_isolation(db, created, other_user, customer_user, conversation):
    with expect_store_error("not_found"):
        get_workflow_run(db, run_id=created.id, user_id=other_user.id)
    with expect_store_error("not_found"):
        load_workflow_run(db, run_id=created.id, user_id=other_user.id)
    with expect_store_error("not_found"):
        list_workflow_events(db, run_id=created.id, user_id=other_user.id)
    with expect_store_error("not_found"):
        cancel_workflow_run(db, run_id=created.id, user_id=other_user.id)

    other_conv = AIConversation(user_id=customer_user.id, title="other")
    db.add(other_conv)
    db.commit()
    db.refresh(other_conv)
    with expect_store_error("forbidden"):
        load_workflow_run(db, run_id=created.id, user_id=customer_user.id, conversation_id=other_conv.id)
    # 正确的会话归属可以正常加载
    load_workflow_run(db, run_id=created.id, user_id=customer_user.id, conversation_id=conversation.id)


# ── 步骤生命周期与 context 合并 ───────────────────────────────────────────────


def test_full_success_lifecycle_merges_context_and_completes_run(db, created):
    steps = _steps_by_key(db, created)
    assert get_ready_steps(list(steps.values())) == [steps["analyze"]]

    mark_step_running(db, run=created, step=steps["analyze"], resolved_input={"attachments": ["x"]})
    assert steps["analyze"].attempt == 1
    assert steps["analyze"].started_at is not None
    assert created.current_step_id == steps["analyze"].id

    persist_step_result(
        db,
        run=created,
        step=steps["analyze"],
        result=_result("vision.appreciate_image", data={"reply": "安静的室内人像", "search_query": "日系 窗边"}),
    )
    assert steps["analyze"].status == "completed"
    assert created.context["image_analysis"] == {"reply": "安静的室内人像", "search_query": "日系 窗边"}
    # 依赖 analyze 的 search 激活为 ready，summarize 仍等待 search
    assert steps["search"].status == "ready"
    assert steps["summarize"].status == "pending"
    assert created.status == "running"

    mark_step_running(db, run=created, step=steps["search"])
    persist_step_result(
        db,
        run=created,
        step=steps["search"],
        result=_result("portfolio.search", status="empty", data={"resource_type": "portfolio_items", "count": 0}),
    )
    assert steps["search"].status == "completed"  # empty 是合法成功结果
    assert created.context["search"]["count"] == 0
    assert steps["summarize"].status == "ready"

    mark_step_running(db, run=created, step=steps["summarize"])
    persist_step_result(
        db,
        run=created,
        step=steps["summarize"],
        result=_result("agent.compose_response", data={"reply": "最终回复"}),
    )
    assert created.status == "completed"
    assert created.completed_at is not None
    assert created.result["data"] == {"reply": "最终回复"}

    assert _event_types(db, created) == [
        "workflow.created",
        "workflow.step.started",
        "workflow.step.completed",
        "workflow.step.started",
        "workflow.step.completed",
        "workflow.step.started",
        "workflow.step.completed",
        "workflow.completed",
    ]
    sequences = [e.sequence for e in list_workflow_events(db, run_id=created.id, user_id=created.user_id)]
    assert sequences == list(range(1, 9))


def test_illegal_transitions_rejected(db, created):
    steps = _steps_by_key(db, created)
    with expect_store_error("invalid_transition"):  # pending 不能直接运行
        mark_step_running(db, run=created, step=steps["search"])
    with expect_store_error("invalid_transition"):
        persist_step_result(db, run=created, step=steps["search"], result=_result("portfolio.search"))

    mark_step_running(db, run=created, step=steps["analyze"])
    persist_step_result(db, run=created, step=steps["analyze"], result=_result("vision.appreciate_image"))
    with expect_store_error("invalid_transition"):  # completed 不能重跑
        mark_step_running(db, run=created, step=steps["analyze"])
    with expect_store_error("invalid_transition"):  # 只有 failed 可以 retry
        retry_step(db, run=created, step=steps["analyze"])
    with expect_store_error("invalid_transition"):  # ready 不能 resume
        resume_step(db, run=created, step=steps["search"])


def test_failed_result_fails_step_and_run(db, created):
    steps = _steps_by_key(db, created)
    mark_step_running(db, run=created, step=steps["analyze"])
    persist_step_result(
        db,
        run=created,
        step=steps["analyze"],
        result=_result("vision.appreciate_image", status="failed"),
    )
    assert steps["analyze"].status == "failed"
    assert steps["analyze"].error["code"] == "capability_error"
    assert created.status == "failed"
    assert created.error["code"] == "step_failed"
    # run 失败时非终态步骤一并取消，依赖步骤不会被激活
    assert steps["search"].status == "cancelled"
    assert steps["summarize"].status == "cancelled"
    with expect_store_error("already_terminal"):  # 失败 run 不能再启动新步骤
        mark_step_running(db, run=created, step=steps["search"])


def test_retry_step_revives_failed_run(db, created):
    steps = _steps_by_key(db, created)
    mark_step_running(db, run=created, step=steps["analyze"])
    persist_step_result(db, run=created, step=steps["analyze"], result=_result("vision.appreciate_image", status="failed"))

    retry_step(db, run=created, step=steps["analyze"])
    assert steps["analyze"].status == "ready"
    assert steps["analyze"].attempt == 1  # attempt 保留，下次执行递增
    assert created.status == "running"

    mark_step_running(db, run=created, step=steps["analyze"])
    assert steps["analyze"].attempt == 2
    assert "workflow.step.retried" in _event_types(db, created)


def test_waiting_user_then_resume(db, created):
    steps = _steps_by_key(db, created)
    mark_step_running(db, run=created, step=steps["analyze"])
    persist_step_result(
        db,
        run=created,
        step=steps["analyze"],
        result=_result("vision.appreciate_image", status="waiting_user"),
    )
    assert steps["analyze"].status == "waiting_user"
    assert created.status == "waiting_user"

    resume_step(db, run=created, step=steps["analyze"])
    assert steps["analyze"].status == "ready"
    assert created.status == "running"

    assert _event_types(db, created) == [
        "workflow.created",
        "workflow.step.started",
        "workflow.waiting_user",
        "workflow.step.resumed",
    ]


def test_waiting_async_then_resume(db, created):
    steps = _steps_by_key(db, created)
    mark_step_running(db, run=created, step=steps["analyze"])
    persist_step_result(
        db,
        run=created,
        step=steps["analyze"],
        result=_result("vision.appreciate_image", status="waiting_async"),
    )
    assert steps["analyze"].status == "waiting_async"
    assert created.status == "waiting_async"
    # 等待异步结果期间没有可执行步骤
    assert get_ready_steps(list(steps.values())) == []

    resume_step(db, run=created, step=steps["analyze"])
    assert created.status == "running"
    assert steps["analyze"].status == "ready"


# ── 取消与 deadline ──────────────────────────────────────────────────────────


def test_cancel_workflow_run(db, created):
    steps = _steps_by_key(db, created)
    run = cancel_workflow_run(db, run_id=created.id, user_id=created.user_id, reason="user_request")
    assert run.status == "cancelled"
    assert run.completed_at is not None
    assert steps["analyze"].status == "cancelled"
    assert steps["search"].status == "cancelled"

    events = list_workflow_events(db, run_id=created.id, user_id=created.user_id)
    assert [e.event_type for e in events] == ["workflow.created", "workflow.cancelled"]
    assert events[-1].payload["reason"] == "user_request"

    with expect_store_error("already_terminal"):
        cancel_workflow_run(db, run_id=created.id, user_id=created.user_id)


def test_expire_workflow_run(db, customer_user, conversation):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    run = create_workflow_run(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        plan=_plan_dict(),
        deadline_at=future,
    )
    assert expire_workflow_run(db, run=run) is False

    run.deadline_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert expire_workflow_run(db, run=run) is True
    assert run.status == "failed"
    assert run.error["code"] == "deadline_exceeded"
    assert _steps_by_key(db, run)["analyze"].status == "cancelled"

    # 终态 run 不会被再次过期处理
    assert expire_workflow_run(db, run=run) is False


# ── 崩溃恢复（阶段 B 验收标准）──────────────────────────────────────────────


def test_recover_after_restart_resumes_from_last_unfinished_step(db, customer_user, conversation):
    """模拟进程重启：session 1 执行到 search 步骤 running 时崩溃，
    新 session 加载并恢复后，从 search 步骤继续跑完全程。"""
    # ── session 1：创建 run，完成 analyze，把 search 置为 running 后“崩溃” ──
    run = create_workflow_run(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        plan=_plan_dict(),
        input={"attachments": ["/static/ai/1/reference.jpg"]},
    )
    _, steps = load_workflow_run(db, run_id=run.id, user_id=customer_user.id)
    analyze = steps[0]
    mark_step_running(db, run=run, step=analyze)
    persist_step_result(
        db,
        run=run,
        step=analyze,
        result=_result("vision.appreciate_image", data={"reply": "解读", "search_query": "日系"}),
    )
    search = steps[1]
    mark_step_running(db, run=run, step=search, resolved_input={"query_text": "日系"})
    db.commit()
    run_id, user_id = run.id, customer_user.id
    db.close()  # 进程重启

    # ── session 2：恢复并继续执行 ──
    db2 = TestingSessionLocal()
    try:
        run2, steps2, info = recover_workflow_run(db2, run_id=run_id, user_id=user_id)
        assert info["recovered"] is True
        assert info["reset_steps"] == ["search"]
        by_key = {s.step_key: s for s in steps2}
        assert by_key["search"].status == "ready"
        assert by_key["search"].attempt == 1  # attempt 保留
        assert by_key["analyze"].status == "completed"
        assert run2.context["image_analysis"]["search_query"] == "日系"  # 上一步结果仍在 context

        mark_step_running(db2, run=run2, step=by_key["search"])
        persist_step_result(
            db2,
            run=run2,
            step=by_key["search"],
            result=_result("portfolio.search", data={"resource_type": "portfolio_items", "count": 2}),
        )
        assert by_key["summarize"].status == "ready"
        mark_step_running(db2, run=run2, step=by_key["summarize"])
        persist_step_result(
            db2,
            run=run2,
            step=by_key["summarize"],
            result=_result("agent.compose_response", data={"reply": "完成"}),
        )
        assert run2.status == "completed"

        assert _event_types(db2, run2) == [
            "workflow.created",
            "workflow.step.started",
            "workflow.step.completed",
            "workflow.step.started",       # 崩溃前的 search 启动
            "workflow.step.recovered",     # 恢复重置
            "workflow.recovered",
            "workflow.step.started",
            "workflow.step.completed",
            "workflow.step.started",
            "workflow.step.completed",
            "workflow.completed",
        ]
    finally:
        db2.close()


def test_recover_waiting_user_run_keeps_waiting_state(db, created):
    steps = _steps_by_key(db, created)
    mark_step_running(db, run=created, step=steps["analyze"])
    persist_step_result(
        db,
        run=created,
        step=steps["analyze"],
        result=_result("vision.appreciate_image", status="waiting_user"),
    )
    db.commit()

    run2, steps2, info = recover_workflow_run(db, run_id=created.id, user_id=created.user_id)
    assert run2.status == "waiting_user"  # 等待用户是合法停点，恢复不应改变
    assert info["recovered"] is False
    assert steps2[0].status == "waiting_user"


def test_recover_terminal_run_is_noop(db, created):
    steps = _steps_by_key(db, created)
    for step in (steps["analyze"], steps["search"], steps["summarize"]):
        mark_step_running(db, run=created, step=step)
        persist_step_result(db, run=created, step=step, result=_result(step.capability))

    run2, _, info = recover_workflow_run(db, run_id=created.id, user_id=created.user_id)
    assert run2.status == "completed"
    assert info["recovered"] is False


# ── 序列化 ───────────────────────────────────────────────────────────────────


def test_serialize_workflow_run_and_metadata(db, created):
    snapshot = serialize_workflow_run(db, created)
    assert snapshot["schema_version"] == "agent_workflow_run_snapshot_v1"
    assert snapshot["workflow_type"] == "image_appreciation_and_search"
    assert [s["step_key"] for s in snapshot["steps"]] == ["analyze", "search", "summarize"]
    assert snapshot["steps"][0]["depends_on"] == []
    assert snapshot["steps"][1]["depends_on"] == ["analyze"]

    assert workflow_metadata(created) == {
        "workflow_run_id": created.id,
        "workflow_status": "running",
        "current_step_id": None,
    }
