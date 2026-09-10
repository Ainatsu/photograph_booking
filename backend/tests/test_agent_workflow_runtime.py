"""Workflow Runtime 执行循环测试（workflow 阶段 C）。

覆盖文档 §12 阶段 C 的验收面：
- 验收用例：三步 DAG analyze -> search -> compose 在不依赖 send_ai_message
  条件分支的情况下完整运行，第二步输入确实来自第一步结构化输出；
- 首步失败不执行后续步骤；retryable 步骤内重试（attempt/retried 事件）；
- 重试耗尽、超时、未注册能力、模板解析失败各自映射为 run 失败；
- deadlock 检测、waiting_user 提前返回、崩溃恢复后续跑。

测试向 CAPABILITY_REGISTRY 注入临时 fake capability（fixture 结束时清理），
不触碰真实 provider / 检索链路。
"""

import asyncio

import pytest
from pydantic import BaseModel, ConfigDict

from backend.app.models.ai_conversation import AIConversation
from backend.app.services.agent_workflow_runtime import run_workflow
from backend.app.services.agent_workflow_contracts import WORKFLOW_PLAN_SCHEMA_VERSION
from backend.app.services.agent_workflow_store import (
    create_workflow_run,
    list_workflow_events,
    load_workflow_run,
    mark_step_running,
    recover_workflow_run,
)
from backend.app.services.ai_capability_contracts import CapabilityResult
from backend.app.services.ai_capability_registry import CAPABILITY_REGISTRY, CapabilitySpec
from backend.tests.conftest import TestingSessionLocal


# ── fake capability 契约模型 ─────────────────────────────────────────────────


class _AnalyzeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = None


class _AnalyzeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    summary: str
    search_query: str


class _SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str
    limit: int = 6


class _SearchData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    query_text: str
    count: int


class _ComposeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: dict
    matches: dict


class _ComposeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    reply: str


# 记录 fake adapter 收到的调用，供断言数据流。
_ADAPTER_CALLS: list[dict] = []


def _reset_calls() -> list[dict]:
    _ADAPTER_CALLS.clear()
    return _ADAPTER_CALLS


async def _analyze_adapter(db, skill_input, *, context):
    _ADAPTER_CALLS.append({"capability": "test.analyze", "input": skill_input.model_dump(mode="json")})
    return {
        "schema_version": "test_analysis_v1",
        "summary": "窗边低饱和人像，安静氛围",
        "search_query": "日系 低饱和 窗边 自然光",
    }


async def _search_adapter(db, search_input, *, context):
    _ADAPTER_CALLS.append({"capability": "test.search", "input": search_input.model_dump(mode="json")})
    return {
        "schema_version": "test_search_v1",
        "query_text": search_input.query_text,
        "count": 2,
    }


async def _compose_adapter(db, compose_input, *, context):
    _ADAPTER_CALLS.append({"capability": "test.compose", "input": compose_input.model_dump(mode="json")})
    reply = f"{compose_input.analysis['summary']} / {compose_input.matches['query_text']}"
    return {"schema_version": "test_compose_v1", "reply": reply}


@pytest.fixture
def register():
    """向 CAPABILITY_REGISTRY 注入临时 capability，测试结束后清理。"""
    added: list[str] = []

    def _register(name: str, *, adapter, input_model, output_model, kind: str = "skill", **spec_kwargs) -> CapabilitySpec:
        spec = CapabilitySpec(
            name=name,
            kind=kind,
            input_model=input_model,
            output_model=output_model,
            adapter=adapter,
            **spec_kwargs,
        )
        CAPABILITY_REGISTRY[name] = spec
        added.append(name)
        return spec

    yield _register
    for name in added:
        CAPABILITY_REGISTRY.pop(name, None)


@pytest.fixture
def conversation(db, customer_user) -> AIConversation:
    conv = AIConversation(user_id=customer_user.id, title="runtime")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _three_step_plan() -> dict:
    """验收计划：analyze(context_key=image_analysis) -> search -> compose。"""
    return {
        "schema_version": "agent_workflow_plan_v2",
        "workflow_type": "image_appreciation_and_search",
        "steps": [
            {
                "id": "analyze",
                "capability": "test.analyze",
                "depends_on": [],
                "input_template": {"content": "$input.request"},
                "context_key": "image_analysis",
            },
            {
                "id": "search",
                "capability": "test.search",
                "depends_on": ["analyze"],
                "input_template": {"query_text": "$context.image_analysis.search_query", "limit": 6},
            },
            {
                "id": "compose",
                "capability": "test.compose",
                "depends_on": ["analyze", "search"],
                "input_template": {
                    "analysis": "$steps.analyze.result",
                    "matches": "$steps.search.result",
                },
            },
        ],
    }


def _register_defaults(register):
    register("test.analyze", adapter=_analyze_adapter, input_model=_AnalyzeInput, output_model=_AnalyzeData)
    register(
        "test.search",
        adapter=_search_adapter,
        input_model=_SearchInput,
        output_model=_SearchData,
        kind="tool",
    )
    register("test.compose", adapter=_compose_adapter, input_model=_ComposeInput, output_model=_ComposeData)


def _create_default_run(db, customer_user, conversation, plan: dict | None = None):
    return create_workflow_run(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        plan=plan or _three_step_plan(),
        input={"request": "帮我赏析这个图片并寻找类似的"},
    )


def _steps_by_key(db, run):
    _, steps = load_workflow_run(db, run_id=run.id, user_id=run.user_id)
    return {step.step_key: step for step in steps}


def _event_types(db, run) -> list[str]:
    return [e.event_type for e in list_workflow_events(db, run_id=run.id, user_id=run.user_id)]


# ── 验收用例：三步 DAG 完整运行 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_three_step_workflow_runs_to_completion(db, customer_user, conversation, register):
    _register_defaults(register)
    calls = _reset_calls()
    run = _create_default_run(db, customer_user, conversation)

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)

    assert finished.status == "completed"
    assert finished.result["capability"] == "test.compose"

    steps = _steps_by_key(db, run)
    assert [s.status for s in (steps["analyze"], steps["search"], steps["compose"])] == [
        "completed",
        "completed",
        "completed",
    ]

    # 第二步输入确实来自第一步结构化输出，而不是自然语言历史。
    assert steps["analyze"].resolved_input == {"content": "帮我赏析这个图片并寻找类似的"}
    assert steps["search"].resolved_input == {"query_text": "日系 低饱和 窗边 自然光", "limit": 6}
    assert steps["compose"].resolved_input == {
        "analysis": {
            "schema_version": "test_analysis_v1",
            "summary": "窗边低饱和人像，安静氛围",
            "search_query": "日系 低饱和 窗边 自然光",
        },
        "matches": {
            "schema_version": "test_search_v1",
            "query_text": "日系 低饱和 窗边 自然光",
            "count": 2,
        },
    }
    assert steps["search"].result["data"]["query_text"] == "日系 低饱和 窗边 自然光"

    # context 按 context_key / step id 合并出三个键。
    fresh_run, _ = load_workflow_run(db, run_id=run.id, user_id=customer_user.id)
    assert set(fresh_run.context) == {"image_analysis", "search", "compose"}
    assert fresh_run.context["image_analysis"]["search_query"] == "日系 低饱和 窗边 自然光"

    # compose 收到的是前两步的 data。
    compose_call = next(c for c in calls if c["capability"] == "test.compose")
    assert compose_call["input"]["analysis"]["search_query"] == "日系 低饱和 窗边 自然光"

    assert _event_types(db, run) == [
        "workflow.created",
        "workflow.step.started",
        "workflow.step.completed",
        "workflow.step.started",
        "workflow.step.completed",
        "workflow.step.started",
        "workflow.step.completed",
        "workflow.completed",
    ]


@pytest.mark.asyncio
async def test_idempotent_capability_gets_stable_workflow_key(db, customer_user, conversation, register):
    async def adapter(db, tool_input, *, context):
        _ADAPTER_CALLS.append({"capability": "test.idem", "context": dict(context)})
        return {"schema_version": "test_v1", "value": tool_input.value}

    class In_(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: str

    class Out_(BaseModel):
        model_config = ConfigDict(extra="forbid")
        schema_version: str
        value: str

    register("test.idem", adapter=adapter, input_model=In_, output_model=Out_, kind="tool", idempotent=True)
    _reset_calls()
    plan = {
        "schema_version": "agent_workflow_plan_v2",
        "workflow_type": "idem_test",
        "steps": [{"id": "one", "capability": "test.idem", "depends_on": [], "input_template": {"value": "$input.v"}}],
    }
    run = create_workflow_run(db, user_id=customer_user.id, conversation_id=conversation.id, plan=plan, input={"v": "x"})

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)

    assert finished.status == "completed"
    step = _steps_by_key(db, run)["one"]
    assert step.idempotency_key == f"workflow:{run.id}:one"
    assert _ADAPTER_CALLS[0]["context"]["idempotency_key"] == f"workflow:{run.id}:one"


# ── 失败传播与重试 ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_first_step_failure_skips_dependents(db, customer_user, conversation, register):
    async def failing_adapter(db, tool_input, *, context):
        raise RuntimeError("vision provider exploded")

    register("test.analyze", adapter=failing_adapter, input_model=_AnalyzeInput, output_model=_AnalyzeData)
    register("test.search", adapter=_search_adapter, input_model=_SearchInput, output_model=_SearchData)
    register("test.compose", adapter=_compose_adapter, input_model=_ComposeInput, output_model=_ComposeData)
    _reset_calls()
    run = _create_default_run(db, customer_user, conversation)

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)

    assert finished.status == "failed"
    assert finished.error["code"] == "step_failed"
    assert finished.error["step_key"] == "analyze"

    steps = _steps_by_key(db, run)
    assert steps["analyze"].status == "failed"
    assert steps["analyze"].error["code"] == "capability_error"
    # 依赖步骤未执行（cancelled，且没有任何 adapter 调用到达它们）。
    assert steps["search"].status == "cancelled"
    assert steps["compose"].status == "cancelled"
    assert _ADAPTER_CALLS == []

    events = _event_types(db, run)
    assert "workflow.step.failed" in events
    assert "workflow.failed" in events
    # 只有失败的 analyze 被启动过，依赖步骤从未执行。
    assert events.count("workflow.step.started") == 1


@pytest.mark.asyncio
async def test_retryable_failure_retries_then_succeeds(db, customer_user, conversation, register):
    state = {"calls": 0}

    async def flaky_adapter(db, tool_input, *, context):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("transient network error")
        return {"schema_version": "test_analysis_v1", "summary": "ok", "search_query": "日系 窗边"}

    register("test.analyze", adapter=flaky_adapter, input_model=_AnalyzeInput, output_model=_AnalyzeData, retryable=True)
    register("test.search", adapter=_search_adapter, input_model=_SearchInput, output_model=_SearchData, kind="tool")
    register("test.compose", adapter=_compose_adapter, input_model=_ComposeInput, output_model=_ComposeData)
    _reset_calls()
    run = _create_default_run(db, customer_user, conversation)

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id, max_retries=1)

    assert finished.status == "completed"
    assert state["calls"] == 2

    steps = _steps_by_key(db, run)
    assert steps["analyze"].status == "completed"
    assert steps["analyze"].attempt == 2
    # 中途失败不落 step.result，只有最终成功结果。
    assert steps["analyze"].result["status"] == "success"
    assert steps["search"].status == "completed"
    assert steps["compose"].status == "completed"

    events = _event_types(db, run)
    assert events.count("workflow.step.retried") == 1
    # 事件顺序：started -> retried -> completed。
    assert events.index("workflow.step.retried") < events.index("workflow.step.completed")


@pytest.mark.asyncio
async def test_retries_exhausted_fails_run_with_last_error(db, customer_user, conversation, register):
    state = {"calls": 0}

    async def always_failing(db, tool_input, *, context):
        state["calls"] += 1
        raise RuntimeError(f"attempt {state['calls']} failed")

    register("test.analyze", adapter=always_failing, input_model=_AnalyzeInput, output_model=_AnalyzeData, retryable=True)
    register("test.search", adapter=_search_adapter, input_model=_SearchInput, output_model=_SearchData)
    register("test.compose", adapter=_compose_adapter, input_model=_ComposeInput, output_model=_ComposeData)
    run = _create_default_run(db, customer_user, conversation)

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id, max_retries=2)

    assert finished.status == "failed"
    assert state["calls"] == 3  # 1 + max_retries
    steps = _steps_by_key(db, run)
    assert steps["analyze"].attempt == 3
    assert steps["analyze"].error["code"] == "capability_error"
    assert "attempt 3 failed" in steps["analyze"].error["message"]
    assert _event_types(db, run).count("workflow.step.retried") == 2


@pytest.mark.asyncio
async def test_timeout_fails_step_with_capability_timeout(db, customer_user, conversation, register):
    async def slow_adapter(db, tool_input, *, context):
        await asyncio.sleep(5)

    register("test.analyze", adapter=slow_adapter, input_model=_AnalyzeInput, output_model=_AnalyzeData, timeout_seconds=1)
    register("test.search", adapter=_search_adapter, input_model=_SearchInput, output_model=_SearchData)
    register("test.compose", adapter=_compose_adapter, input_model=_ComposeInput, output_model=_ComposeData)
    run = _create_default_run(db, customer_user, conversation)

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)

    assert finished.status == "failed"
    steps = _steps_by_key(db, run)
    assert steps["analyze"].status == "failed"
    assert steps["analyze"].error["code"] == "capability_timeout"
    assert "1s timeout" in steps["analyze"].error["message"]
    # 后续步骤被取消而不是执行。
    assert steps["search"].status == "cancelled"


@pytest.mark.asyncio
async def test_unknown_capability_fails_step(db, customer_user, conversation, register):
    # 只注册 search/compose，analyze 引用未注册能力。
    register("test.search", adapter=_search_adapter, input_model=_SearchInput, output_model=_SearchData)
    register("test.compose", adapter=_compose_adapter, input_model=_ComposeInput, output_model=_ComposeData)
    run = _create_default_run(db, customer_user, conversation)

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)

    assert finished.status == "failed"
    steps = _steps_by_key(db, run)
    assert steps["analyze"].status == "failed"
    assert steps["analyze"].error["code"] == "unknown_capability"


@pytest.mark.asyncio
async def test_template_resolution_failure_fails_step(db, customer_user, conversation, register):
    _register_defaults(register)
    plan = {
        "schema_version": "agent_workflow_plan_v2",
        "workflow_type": "image_appreciation_and_search",
        "steps": [
            {
                # context_key 故意命名为 analysis，search 模板引用 image_analysis 必然缺失。
                "id": "analyze",
                "capability": "test.analyze",
                "depends_on": [],
                "input_template": {"content": "$input.request"},
                "context_key": "analysis",
            },
            {
                "id": "search",
                "capability": "test.search",
                "depends_on": ["analyze"],
                "input_template": {"query_text": "$context.image_analysis.search_query", "limit": 6},
            },
        ],
    }
    run = _create_default_run(db, customer_user, conversation, plan=plan)

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)

    assert finished.status == "failed"
    steps = _steps_by_key(db, run)
    assert steps["analyze"].status == "completed"
    assert steps["search"].status == "failed"
    assert steps["search"].error["code"] == "template_resolution_failed"
    assert "missing_path" in steps["search"].error["message"]
    # 解析失败时不落 resolved_input。
    assert steps["search"].resolved_input == {}


# ── 等待、deadlock 与恢复 ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_waiting_user_returns_without_failing(db, customer_user, conversation, register, monkeypatch):
    from backend.app.services import agent_workflow_runtime as runtime_module

    register("test.analyze", adapter=_analyze_adapter, input_model=_AnalyzeInput, output_model=_AnalyzeData)
    plan = {
        "schema_version": "agent_workflow_plan_v2",
        "workflow_type": "wait_test",
        "steps": [{"id": "only", "capability": "test.analyze", "depends_on": [], "input_template": {"content": "$input.request"}}],
    }
    run = create_workflow_run(db, user_id=customer_user.id, conversation_id=conversation.id, plan=plan, input={"request": "r"})

    async def fake_execute(db, *, name, input, **kwargs):
        return CapabilityResult(
            capability=name,
            status="waiting_user",
            data={"schema_version": "test_v1"},
        )

    monkeypatch.setattr(runtime_module, "execute_capability", fake_execute)

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)

    assert finished.status == "waiting_user"
    steps = _steps_by_key(db, run)
    assert steps["only"].status == "waiting_user"
    assert "workflow.waiting_user" in _event_types(db, run)


@pytest.mark.asyncio
async def test_deadlock_detection_fails_run(db, customer_user, conversation, register):
    register("test.analyze", adapter=_analyze_adapter, input_model=_AnalyzeInput, output_model=_AnalyzeData)
    plan = {
        "schema_version": "agent_workflow_plan_v2",
        "workflow_type": "deadlock_test",
        "steps": [
            {"id": "a", "capability": "test.analyze", "depends_on": [], "input_template": {"content": "$input.request"}},
            {"id": "b", "capability": "test.analyze", "depends_on": ["a"], "input_template": {"content": "$input.request"}},
        ],
    }
    run = _create_default_run(db, customer_user, conversation, plan=plan)

    # 直接篡改库内状态：a 被卡回 pending，导致没有可运行步骤。
    steps = _steps_by_key(db, run)
    steps["a"].status = "pending"
    db.commit()

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)

    assert finished.status == "failed"
    assert finished.error["code"] == "workflow_deadlock"
    assert finished.error["step_statuses"] == {"a": "pending", "b": "pending"}


@pytest.mark.asyncio
async def test_crash_recovery_then_run_workflow_completes(db, customer_user, conversation, register):
    _register_defaults(register)
    _reset_calls()
    run = _create_default_run(db, customer_user, conversation)
    run_id, user_id = run.id, customer_user.id

    # 模拟进程崩溃：analyze 已 mark running 但结果未持久化，随后换一个
    # 全新 session（模拟重启）走恢复入口再续跑。
    _, steps = load_workflow_run(db, run_id=run_id, user_id=user_id)
    mark_step_running(db, run=run, step=steps[0], resolved_input={"content": "帮我赏析这个图片并寻找类似的"})
    db.close()

    with TestingSessionLocal() as session2:
        recover_workflow_run(session2, run_id=run_id, user_id=user_id)
        finished = await run_workflow(session2, run_id=run_id, user_id=user_id)
        assert finished.status == "completed"

    final_run, final_steps = load_workflow_run(db, run_id=run_id, user_id=user_id)
    steps = {step.step_key: step for step in final_steps}
    assert [s.status for s in (steps["analyze"], steps["search"], steps["compose"])] == [
        "completed",
        "completed",
        "completed",
    ]
    # 恢复后 analyze 重跑（attempt=2），search 的输入仍来自其结果。
    assert steps["analyze"].attempt == 2
    assert steps["search"].resolved_input == {"query_text": "日系 低饱和 窗边 自然光", "limit": 6}
    events = [e.event_type for e in list_workflow_events(db, run_id=run_id, user_id=user_id)]
    assert "workflow.recovered" in events
    assert "workflow.step.recovered" in events


@pytest.mark.asyncio
async def test_run_input_context_forwarded_to_capability(db, customer_user, conversation, register):
    """阶段E：run.input 里的 vision_analysis/request_content 透传给 adapter context。

    检索类 adapter 依赖 context.vision_analysis 复刻主链路的视觉驱动排序；
    run.input 由后端构造（非模型输出），透传是安全的。
    """
    captured: dict = {}

    class ProbeInput(BaseModel):
        query_text: str | None = None

    class ProbeOutput(BaseModel):
        schema_version: str
        reply: str

    async def probe_adapter(db, probe_input, *, context):
        captured.update(
            {
                "vision_analysis": context.get("vision_analysis"),
                "request_content": context.get("request_content"),
                "image_attachments": context.get("image_attachments"),
            }
        )
        return {"schema_version": "probe_v1", "reply": probe_input.query_text or ""}

    register(
        "test.context_probe",
        adapter=probe_adapter,
        input_model=ProbeInput,
        output_model=ProbeOutput,
    )
    run = create_workflow_run(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        plan={
            "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
            "workflow_type": "context_probe",
            "steps": [
                {
                    "id": "probe",
                    "capability": "test.context_probe",
                    "depends_on": [],
                    "input_template": {"query_text": "$input.content"},
                }
            ],
        },
        input={
            "content": "帮我找类似的",
            "vision_analysis": {"style": ["日系"]},
            "image_attachments": [{"type": "image", "url": "/static/a.jpg"}],
        },
    )

    finished = await run_workflow(db, run_id=run.id, user_id=customer_user.id)
    assert finished.status == "completed"
    assert captured["vision_analysis"] == {"style": ["日系"]}
    assert captured["request_content"] == "帮我找类似的"
    assert captured["image_attachments"] == [{"type": "image", "url": "/static/a.jpg"}]
