"""首个动态复合流程：赏析图片并寻找类似作品（workflow 阶段 D）。

覆盖：
- 触发判定（赏析+找类似、纯赏析、无图、纯检索）；
- send_ai_message 端到端：run 完成、第二步检索词来自第一步结构化输出、
  消息 metadata 携带 workflow 引用与真实资源引用；
- 空检索结果的明确降级说明；
- 视觉步骤失败的降级回复（run failed 不炸主链路）；
- workflow 事件镜像进对话事件流（SSE 断线补发游标）；
- feature flag 关闭时回落既有赏析链路。
"""

import pytest

from backend.app.models.ai_conversation import AIConversationEvent
from backend.app.models.agent_workflow import AgentWorkflowRun, AgentWorkflowStep
from backend.app.services import ai_capability_adapters
from backend.app.services import ai_service
from backend.app.services.agent_workflow_appreciation_search import (
    build_appreciation_search_plan,
    compose_appreciation_search,
    matches_appreciation_search_request,
)
from backend.app.services.ai_capability_registry import CAPABILITY_REGISTRY

ATTACHMENTS = [{"type": "image", "url": "https://example.test/reference.jpg", "mime_type": "image/jpeg"}]


class FencedVisionProvider:
    """返回围栏 JSON 视觉分析的 fake provider。"""

    async def chat(self, messages, *, temperature=None, response_format=None):
        content = (
            "```json\n"
            '{"summary": "窗边自然光低饱和人像", "style": ["日系", "低饱和"],'
            ' "scene": ["窗边", "室内"], "mood": ["安静"],'
            ' "search_terms": ["日系", "自然光"]}\n'
            "```"
        )
        return {
            "content": content,
            "metadata": {"model": {"provider": "test", "model": "vision-test"}},
        }


class AppreciationVisionProvider:
    """按 system prompt 区分赏析与结构化分析的 fake provider。"""

    async def chat(self, messages, *, temperature=None, response_format=None):
        system_text = "\n".join(
            message["content"] for message in messages if message.get("role") == "system"
        )
        if "摄影作品赏析者" in system_text:
            return {
                "content": "这幅作品通过窗边侧光与低饱和色彩形成安静氛围，视觉中心明确。",
                "metadata": {"model": {"provider": "test", "model": "vision-test"}},
            }
        return await FencedVisionProvider().chat(messages)


def _search_tool_success(*, items, tool_name="search_portfolio_items"):
    result = {
        "schema_version": "agent_search_tool_v1",
        "resource_type": "portfolio_items",
        "count": len(items),
        "resource_ids": [item.get("id") for item in items],
        "items": items,
        "criteria": {"resource_types": ["portfolio_items"], "text": "日系"},
        "diagnostics": {},
    }
    return {
        "tool": tool_name,
        "status": "success" if items else "empty",
        "input": {},
        "result": result,
        "payload": {
            "context_schema_version": "ai_retrieval_v1",
            "criteria": result["criteria"],
            "references": {"portfolio_items": items, "photographers": [], "packages": []},
            "diagnostics": {},
        },
        "retrieval": None,
        "policy": {"risk_level": "read_only"},
    }


# ── 触发判定 ──────────────────────────────────────────────────────────────────


def test_matcher_requires_image_appreciation_and_search_language():
    assert matches_appreciation_search_request("帮我赏析这个图片并寻找类似的", ATTACHMENTS)
    assert matches_appreciation_search_request("点评一下这张照片，帮我找相似的", ATTACHMENTS)
    # 纯赏析不带检索语言：走既有赏析链路。
    assert not matches_appreciation_search_request("帮我赏析这个图片", ATTACHMENTS)
    # 无图片附件：不触发 workflow。
    assert not matches_appreciation_search_request("帮我赏析这个图片并寻找类似的", None)
    assert not matches_appreciation_search_request("帮我赏析这个图片并寻找类似的", [])
    # 检索语言但无赏析语言：走既有图搜链路。
    assert not matches_appreciation_search_request("帮我找类似的作品", ATTACHMENTS)
    # 无文本。
    assert not matches_appreciation_search_request(None, ATTACHMENTS)
    assert not matches_appreciation_search_request("", ATTACHMENTS)


def test_plan_shape_and_capabilities_registered():
    from backend.app.services.agent_workflow_contracts import WorkflowPlan

    plan = WorkflowPlan.model_validate(build_appreciation_search_plan())
    assert plan.workflow_type == "image_appreciation_and_search"
    assert [step.id for step in plan.steps] == ["appreciate", "analyze", "search", "compose"]
    # 检索只依赖结构化分析；compose 汇总全部前序结果。
    assert plan.step_map()["search"].depends_on == ["analyze"]
    assert set(plan.step_map()["compose"].depends_on) == {"appreciate", "analyze", "search"}
    # 计划中的 capability 全部已注册。
    for step in plan.steps:
        assert step.capability in CAPABILITY_REGISTRY


# ── compose 纯函数 ────────────────────────────────────────────────────────────


def test_compose_includes_appreciation_basis_and_real_references():
    composed = compose_appreciation_search(
        user_request="帮我赏析并找类似",
        appreciation={"reply": "赏析正文。"},
        analysis={
            "search_query": "日系 窗边 低饱和",
            "style": ["日系"],
            "attachments": [{"url": "/static/x.jpg"}],
            "provider": {"provider": "test", "model": "m1"},
        },
        search={"items": [{"id": 1, "title": "日系样片"}, {"id": 2, "title": "窗边写真"}], "criteria": {}},
    )
    assert "赏析正文。" in composed["content"]
    assert "日系 窗边 低饱和" in composed["content"]
    assert "《日系样片》" in composed["content"]
    metadata = composed["metadata"]
    assert metadata["references"]["portfolio_items"][0]["id"] == 1
    assert metadata["citation_policy"]["allowed_resource_ids"]["portfolio_items"] == [1, 2]
    assert metadata["citation_policy"]["required"] is True
    assert [call["tool"] for call in metadata["tool_calls"]] == [
        "appreciate_image",
        "analyze_image",
        "search_portfolio_items",
    ]


def test_compose_empty_search_gives_explicit_degradation():
    composed = compose_appreciation_search(
        user_request="帮我赏析并找类似",
        appreciation={"reply": "赏析正文。"},
        analysis={"search_query": "不存在的风格"},
        search={"items": [], "criteria": {}},
    )
    assert "赏析正文。" in composed["content"]
    assert "暂时没有找到" in composed["content"]
    metadata = composed["metadata"]
    assert metadata["references"]["portfolio_items"] == []
    assert metadata["citation_policy"]["required"] is False


def test_compose_without_appreciation_still_composes():
    composed = compose_appreciation_search(
        user_request="找类似",
        appreciation={},
        analysis={"search_query": "日系"},
        search={"items": [{"id": 9, "title": "日系"}]},
    )
    assert "日系" in composed["content"]
    # 赏析缺失时 tool_calls 不含 appreciate_image。
    assert [call["tool"] for call in composed["metadata"]["tool_calls"]] == [
        "analyze_image",
        "search_portfolio_items",
    ]


# ── send_ai_message 端到端 ────────────────────────────────────────────────────


@pytest.fixture
def workflow_enabled(monkeypatch):
    monkeypatch.setattr(
        ai_service.settings,
        "AI_AGENT_WORKFLOW_APPRECIATION_SEARCH_ENABLED",
        True,
    )


@pytest.fixture
def fake_vision(monkeypatch):
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: AppreciationVisionProvider())


@pytest.fixture
def search_capture(monkeypatch):
    captured = {}

    def fake_run_search_tool(db, *, tool_name, arguments=None, **kwargs):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return _search_tool_success(items=[{"id": 101, "title": "日系样片", "tags": ["日系"]}])

    monkeypatch.setattr(ai_capability_adapters, "run_search_tool", fake_run_search_tool)
    return captured


@pytest.mark.asyncio
async def test_send_ai_message_runs_appreciation_and_search_workflow(
    db, customer_user, monkeypatch, workflow_enabled, fake_vision, search_capture
):
    # 聊天路径的 provider（标题生成等）不再被调用：workflow 分支不调 provider.chat。
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: FencedVisionProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    user_message, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我赏析这个图片并寻找类似的",
        ATTACHMENTS,
    )

    # ── run 状态与步骤 ──
    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "completed"
    assert run.workflow_type == "image_appreciation_and_search"
    assert run.message_id == user_message.id
    steps = {
        step.step_key: step
        for step in db.query(AgentWorkflowStep).filter(AgentWorkflowStep.workflow_run_id == run.id).all()
    }
    assert set(steps) == {"appreciate", "analyze", "search", "compose"}
    assert all(step.status == "completed" for step in steps.values())

    # ── 关键验收：第二步的检索词来自第一步结构化输出，而非对话历史 ──
    assert search_capture["tool_name"] == "search_portfolio_items"
    arguments = search_capture["arguments"]
    # fake 分析返回 style=日系/低饱和、scene=窗边/室内、search_terms=日系/自然光，
    # 派生 search_query 应包含这些结构化标签。
    for term in ("日系", "窗边"):
        assert term in arguments["query_text"]
    assert arguments["limit"] == 6

    # ── 助手消息：正文 + metadata ──
    assert "窗边侧光" in assistant_message.content
    assert "日系样片" in assistant_message.content
    metadata = assistant_message.message_metadata
    assert metadata["workflow"]["workflow_run_id"] == run.id
    assert metadata["workflow"]["status"] == "completed"
    assert metadata["references"]["portfolio_items"][0]["id"] == 101
    assert metadata["citation_policy"]["required"] is True
    assert metadata["vision_analysis"]["search_query"]
    assert metadata["retrieval"]["criteria"]["resource_types"] == ["portfolio_items"]

    # ── context 合并：三个前序步骤的结果键齐全 ──
    context = run.context or {}
    assert set(context) == {"appreciation", "image_analysis", "search", "compose"}
    assert context["image_analysis"]["search_query"]
    assert context["search"]["items"][0]["id"] == 101

    # ── workflow 事件镜像进对话事件流（SSE 消费）──
    mirror_events = (
        db.query(AIConversationEvent)
        .filter(
            AIConversationEvent.conversation_id == conversation.id,
            AIConversationEvent.task_id == run.id,
        )
        .order_by(AIConversationEvent.sequence.asc())
        .all()
    )
    mirrored_types = [event.type for event in mirror_events]
    assert "workflow.created" in mirrored_types
    assert "workflow.step.started" in mirrored_types
    assert "workflow.step.completed" in mirrored_types
    assert "workflow.completed" in mirrored_types
    # 每个镜像事件都携带 workflow 引用与原始 sequence，断线补发有游标可用。
    for event in mirror_events:
        payload = event.payload or {}
        assert payload["workflow_run_id"] == run.id
        assert payload["schema_version"] == "workflow_event_mirror_v1"
        assert isinstance(payload["workflow_sequence"], int)


@pytest.mark.asyncio
async def test_workflow_empty_search_still_completes_with_degradation_note(
    db, customer_user, monkeypatch, workflow_enabled, fake_vision
):
    monkeypatch.setattr(
        ai_capability_adapters,
        "run_search_tool",
        lambda db_, *, tool_name, arguments=None, **kwargs: _search_tool_success(items=[]),
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我赏析这个图片并寻找类似的",
        ATTACHMENTS,
    )

    # empty 是合法完成状态：run completed，回复带明确降级说明。
    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "completed"
    assert "暂时没有找到" in assistant_message.content
    metadata = assistant_message.message_metadata
    assert metadata["workflow"]["status"] == "completed"
    assert metadata["references"]["portfolio_items"] == []
    assert metadata["citation_policy"]["required"] is False


@pytest.mark.asyncio
async def test_workflow_vision_failure_degrades_without_raising(
    db, customer_user, monkeypatch, workflow_enabled, search_capture
):
    # 视觉 provider 抛异常 → capability failed → run failed，主链路返回降级文案。
    class ExplodingProvider:
        async def chat(self, messages, *, temperature=None, response_format=None):
            raise RuntimeError("vision provider down")

    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: ExplodingProvider())

    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我赏析这个图片并寻找类似的",
        ATTACHMENTS,
    )

    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "failed"
    assert run.error["code"] == "step_failed"
    steps = (
        db.query(AgentWorkflowStep)
        .filter(AgentWorkflowStep.workflow_run_id == run.id)
        .all()
    )
    # 首个视觉步骤（appreciate，计划顺序第一）失败，其余依赖步骤被取消；
    # 检索步骤从未执行。
    statuses = {step.step_key: step.status for step in steps}
    assert statuses["appreciate"] == "failed"
    assert statuses["analyze"] == "cancelled"
    assert statuses["search"] == "cancelled"
    assert "tool_name" not in search_capture  # 检索未被调用
    assert "没能完成" in assistant_message.content
    metadata = assistant_message.message_metadata
    assert metadata["workflow"]["status"] == "failed"
    assert metadata["degraded_reason"] == "step_failed"


@pytest.mark.asyncio
async def test_workflow_disabled_falls_back_to_legacy_vision_retrieval(
    db, customer_user, monkeypatch, fake_vision
):
    # flag 默认关闭：请求回落到既有链路（图搜优先于赏析，规则层该请求分类为
    # resource_search + 视觉分析），不创建 workflow run。
    monkeypatch.setattr(
        ai_service.settings,
        "AI_AGENT_WORKFLOW_APPRECIATION_SEARCH_ENABLED",
        False,
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我赏析这个图片并寻找类似的",
        ATTACHMENTS,
    )

    assert db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).count() == 0
    # 走既有视觉分析 + 检索链路：正文是图搜回复话术，metadata 无 workflow 引用。
    assert "我按这张图" in assistant_message.content
    assert "workflow" not in (assistant_message.message_metadata or {})
    assert assistant_message.message_metadata["vision_analysis"]["schema_version"] == "vision_analysis_v1"
