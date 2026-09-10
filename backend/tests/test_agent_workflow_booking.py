"""预订流程迁移到 Workflow Runtime（workflow 阶段 E 第二部分）。

覆盖：
- 计划形状：两步 DAG（package.search → booking.create）且能力已注册；
- 三轮端到端（flag 开启）：
  T1 规划回复 + waiting_user（缺日期）、T2 补日期 → 确认等待
  （pending_action + task_plan 推进）、T3 显式确认 → 创建订单；
- 确认策略对齐：非显式确认（「好的」）不执行创建，重新询问确认；
- 审计对齐：AgentActionLog 恰好一条（create_booking 工具），run 跨轮复用；
- 空检索降级（awaiting_package）；
- feature flag 关闭时回落 legacy booking planner 分支，不创建 workflow run。
"""

import pytest

from backend.app.models.agent_workflow import AgentWorkflowRun, AgentWorkflowStep
from backend.app.models.ai_conversation import AIConversationEvent
from backend.app.models.order import Order
from backend.app.models.ai_conversation import AgentActionLog
from backend.app.services import ai_capability_adapters
from backend.app.services import ai_service
from backend.app.services.agent_workflow_booking import build_booking_plan
from backend.app.services.ai_capability_registry import CAPABILITY_REGISTRY

PACKAGE_ITEMS = [
    {
        "id": "package-test-1",
        "package_name": "个人写真",
        "price": 699,
        "duration": 120,
        "photographer_id": None,  # 由 fixture 动态填充
        "photographer_name": "测试摄影师",
        "includes": ["精修30张"],
        "image_count": 30,
    }
]


def _search_tool_success(*, items, tool_name="search_packages"):
    result = {
        "schema_version": "agent_search_tool_v1",
        "resource_type": "packages",
        "count": len(items),
        "resource_ids": [item.get("id") for item in items],
        "items": items,
        "criteria": {"resource_types": ["packages"], "text": "北京 日系"},
        "diagnostics": {},
    }
    return {
        "tool": tool_name,
        "status": "success" if items else "empty",
        "input": {},
        "result": result,
        "retrieval": {
            "criteria": result["criteria"],
            "references": {"packages": items, "photographers": [], "portfolio_items": []},
            "diagnostics": {},
        },
        "policy": {"risk_level": "read_only"},
    }


# ── 计划形状 ──────────────────────────────────────────────────────────────────


def test_plan_shape_and_capabilities_registered():
    from backend.app.services.agent_workflow_contracts import WorkflowPlan

    plan = WorkflowPlan.model_validate(build_booking_plan())
    assert plan.workflow_type == "booking_flow"
    assert [step.id for step in plan.steps] == ["search", "create"]
    assert plan.step_map()["search"].capability == "package.search"
    assert plan.step_map()["create"].capability == "booking.create"
    assert plan.step_map()["create"].depends_on == ["search"]
    for step in plan.steps:
        assert step.capability in CAPABILITY_REGISTRY


# ── 端到端（flag 开启） ───────────────────────────────────────────────────────


@pytest.fixture
def workflow_enabled(monkeypatch):
    monkeypatch.setattr(
        ai_service.settings,
        "AI_AGENT_WORKFLOW_BOOKING_ENABLED",
        True,
    )
    # 意图分类与路由决策默认会调真实 LLM；测试强制规则分类 + legacy 路由。
    monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
    monkeypatch.setattr(ai_service.settings, "AGENT_ROUTING_MODE", "legacy")


@pytest.fixture
def search_capture(monkeypatch, photographer_profile):
    captured = {}

    def fake_run_search_tool(db, *, tool_name, arguments=None, **kwargs):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        items = [
            {**item, "photographer_id": photographer_profile.user_id}
            for item in PACKAGE_ITEMS
        ]
        return _search_tool_success(items=items)

    monkeypatch.setattr(ai_capability_adapters, "run_search_tool", fake_run_search_tool)
    return captured


def _run_steps(db, run_id):
    return {
        step.step_key: step
        for step in db.query(AgentWorkflowStep).filter(AgentWorkflowStep.workflow_run_id == run_id).all()
    }


@pytest.mark.asyncio
async def test_booking_three_turn_workflow_with_waiting_user(
    db, customer_user, photographer_profile, workflow_enabled, search_capture
):
    conversation = ai_service.create_conversation(db, customer_user.id)

    # ── T1：预订意图（无日期）→ 规划回复 + run waiting_user ──
    _, am1 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "我想预约北京的日系摄影，帮我找套餐",
    )
    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "waiting_user"
    assert run.workflow_type == "booking_flow"
    steps = _run_steps(db, run.id)
    assert steps["search"].status == "completed"
    assert steps["create"].status == "waiting_user"
    # 检索条件来自意图 slots 归一；create 输入来自 search 的结构化 items。
    assert search_capture["tool_name"] == "search_packages"
    assert search_capture["arguments"]["query_text"] == "我想预约北京的日系摄影，帮我找套餐"
    assert steps["create"].resolved_input["items"][0]["id"] == "package-test-1"

    assert "我先把这次拍摄拆成几个步骤" in am1.content
    metadata1 = am1.message_metadata
    assert metadata1["workflow"]["workflow_run_id"] == run.id
    assert metadata1["workflow"]["status"] == "waiting_user"
    assert metadata1["task_state"]["status"] == "awaiting_date"
    assert metadata1["task_state"]["task_type"] == "create_booking"
    assert metadata1["task_plan"]["schema_version"] == "agent_task_plan_v1"
    # 检索对齐：真实套餐写入 references（后续轮的套餐引用依赖它）。
    assert metadata1["references"]["packages"][0]["id"] == "package-test-1"

    # workflow 事件镜像进对话事件流（SSE 消费）。
    mirror_events = (
        db.query(AIConversationEvent)
        .filter(
            AIConversationEvent.conversation_id == conversation.id,
            AIConversationEvent.task_id == run.id,
        )
        .all()
    )
    mirrored_types = [event.type for event in mirror_events]
    assert "workflow.created" in mirrored_types
    assert "workflow.waiting_user" in mirrored_types

    # ── T2：补日期 → 确认等待（pending_action + task_plan 推进）──
    _, am2 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "约12月20日",
    )
    # 同一个 run 被 resume，而不是新建。
    assert db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).count() == 1
    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "waiting_user"
    steps = _run_steps(db, run.id)
    assert steps["create"].status == "waiting_user"
    assert steps["create"].attempt == 2

    assert "我帮你整理了预约信息" in am2.content
    metadata2 = am2.message_metadata
    assert metadata2["task_state"]["status"] == "awaiting_confirmation"
    assert metadata2["task_state"]["pending_action"]["tool"] == "create_booking"
    assert metadata2["task_state"]["pending_action"]["input"]["appointment_date"] == "12-20"
    assert metadata2["task_state"]["pending_action"]["input"]["package_id"] == "package-test-1"
    # task_plan 推进：select_date / confirm_booking 完成。
    step_status = {step["id"]: step["status"] for step in metadata2["task_plan"]["steps"]}
    assert step_status["select_date"] == "completed"
    assert step_status["confirm_booking"] == "completed"
    assert step_status["create_booking"] == "pending"
    # 镜像事件跨轮去重（resumed 事件新增，旧事件不重复）。
    resumed = [
        event for event in mirror_events
        if event.type == "workflow.step.resumed"
    ] or (
        db.query(AIConversationEvent)
        .filter(
            AIConversationEvent.conversation_id == conversation.id,
            AIConversationEvent.task_id == run.id,
        )
        .all()
    )
    assert any(event.type == "workflow.step.resumed" for event in resumed)

    # ── T3：显式确认 → 创建订单，run completed ──
    _, am3 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "确认预约",
    )
    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "completed"
    steps = _run_steps(db, run.id)
    assert steps["create"].status == "completed"

    assert "预约已创建" in am3.content
    order = db.query(Order).filter(Order.customer_id == customer_user.id).one()
    assert order.photographer_id == photographer_profile.user_id
    # 审计对齐：create_booking 工具恰好落一条 action log（幂等键由工具层生成）。
    action_logs = (
        db.query(AgentActionLog)
        .filter(
            AgentActionLog.user_id == customer_user.id,
            AgentActionLog.conversation_id == conversation.id,
            AgentActionLog.tool_name == "create_booking",
        )
        .all()
    )
    assert len(action_logs) == 1
    metadata3 = am3.message_metadata
    assert metadata3["task_state"]["status"] == "completed"
    assert metadata3["workflow"]["status"] == "completed"
    # 完成轮不应再带 pending_action。
    assert metadata3["task_state"].get("pending_action") is None


@pytest.mark.asyncio
async def test_generic_confirmation_does_not_execute_booking(
    db, customer_user, photographer_profile, workflow_enabled, search_capture
):
    conversation = ai_service.create_conversation(db, customer_user.id)
    await ai_service.send_ai_message(db, customer_user.id, conversation.id, "我想预约北京的日系摄影，帮我找套餐")
    await ai_service.send_ai_message(db, customer_user.id, conversation.id, "约12月20日")

    # 泛化确认（「好的」）不是显式确认短语：重新询问确认，不创建订单。
    _, am = await ai_service.send_ai_message(db, customer_user.id, conversation.id, "好的")

    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "waiting_user"
    assert "我帮你整理了预约信息" in am.content
    assert (am.message_metadata or {}).get("task_state", {}).get("status") == "awaiting_confirmation"
    assert db.query(Order).filter(Order.customer_id == customer_user.id).count() == 0
    assert (
        db.query(AgentActionLog)
        .filter(
            AgentActionLog.conversation_id == conversation.id,
            AgentActionLog.tool_name == "create_booking",
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_booking_without_packages_waits_for_package(
    db, customer_user, workflow_enabled, monkeypatch
):
    # 检索为空：create 步骤解析不到摄影师/套餐 → awaiting_package 降级。
    monkeypatch.setattr(
        ai_capability_adapters,
        "run_search_tool",
        lambda db_, *, tool_name, arguments=None, **kwargs: _search_tool_success(items=[]),
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, am = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "我想预约拍照，帮我找套餐",
    )

    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "waiting_user"
    assert "你想预约哪个套餐" in am.content
    assert (am.message_metadata or {}).get("task_state", {}).get("status") == "awaiting_package"


@pytest.mark.asyncio
async def test_booking_disabled_falls_back_to_legacy_planner(
    db, customer_user, photographer_profile, monkeypatch
):
    # flag 默认关闭：请求回落 legacy booking planner 分支，不创建 workflow run。
    monkeypatch.setattr(
        ai_service.settings,
        "AI_AGENT_WORKFLOW_BOOKING_ENABLED",
        False,
    )
    monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
    monkeypatch.setattr(ai_service.settings, "AGENT_ROUTING_MODE", "legacy")
    monkeypatch.setattr(
        ai_service,
        "retrieve_references",
        lambda db_, text, **kwargs: {
            "criteria": {"resource_types": ["packages"]},
            "references": {
                "packages": [
                    {
                        "id": "package-test-1",
                        "package_name": "个人写真",
                        "price": 699,
                        "duration": 120,
                        "photographer_id": photographer_profile.user_id,
                        "photographer_name": "测试摄影师",
                    }
                ],
                "photographers": [],
                "portfolio_items": [],
            },
            "diagnostics": {},
        },
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, am = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "我想预约北京的日系摄影，帮我找套餐",
    )

    assert db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).count() == 0
    assert "我先把这次拍摄拆成几个步骤" in am.content
    assert "workflow" not in (am.message_metadata or {})
    assert am.message_metadata["task_state"]["status"] == "awaiting_date"
