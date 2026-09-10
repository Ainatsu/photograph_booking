"""search_then_inspire 固定复合流程迁移到 Workflow Runtime（workflow 阶段 E）。

覆盖：
- 计划形状：两步 DAG（portfolio.search → inspiration.generate）且能力已注册；
- adapter 可用图过滤：跳过视频/无 url、12 张上限、无可用图返回 legacy 降级文案；
- send_ai_message 端到端（flag 开启）：run 完成、检索条件来自意图 slots 归一、
  第二步输入来自第一步结构化 items、AgentTaskDraft 与异步生成 job 落库、
  消息 metadata 携带 task_plan/inspiration_flow/workflow 引用、
  workflow 事件镜像进对话事件流；
- 无可用静态图：run 合法完成，返回 legacy 同款降级文案；
- feature flag 关闭时回落 legacy compound_workflow 分支，不创建 workflow run。
"""

import pytest

from backend.app.models.agent_task import AgentTaskDraft
from backend.app.models.agent_workflow import AgentWorkflowRun, AgentWorkflowStep
from backend.app.models.ai_conversation import AIConversationEvent
from backend.app.models.inspiration_generation import (
    InspirationGenerationBatch,
    InspirationGenerationJob,
)
from backend.app.services import ai_capability_adapters
from backend.app.services import ai_service
from backend.app.services.agent_workflow_search_then_inspire import (
    build_search_then_inspire_plan,
)
from backend.app.services.ai_capability_adapters import _usable_inspiration_images
from backend.app.services.ai_capability_registry import CAPABILITY_REGISTRY

SEARCH_ITEMS = [
    {"id": 101, "title": "日系样片", "url": "https://cdn.test/w1.jpg", "tags": ["日系"]},
    {"id": 102, "title": "窗边写真", "url": "https://cdn.test/w2.jpg", "tags": ["窗边"]},
]


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
        "retrieval": {
            "context_schema_version": "ai_retrieval_v1",
            "criteria": result["criteria"],
            "references": {"portfolio_items": items, "photographers": [], "packages": []},
            "diagnostics": {},
        },
        "policy": {"risk_level": "read_only"},
    }


# ── 计划形状 ──────────────────────────────────────────────────────────────────


def test_plan_shape_and_capabilities_registered():
    from backend.app.services.agent_workflow_contracts import WorkflowPlan

    plan = WorkflowPlan.model_validate(build_search_then_inspire_plan())
    assert plan.workflow_type == "search_then_inspire"
    assert [step.id for step in plan.steps] == ["search", "inspire"]
    assert plan.step_map()["search"].depends_on == []
    assert plan.step_map()["inspire"].depends_on == ["search"]
    assert plan.step_map()["search"].capability == "portfolio.search"
    assert plan.step_map()["inspire"].capability == "inspiration.generate"
    # 计划中的 capability 全部已注册。
    for step in plan.steps:
        assert step.capability in CAPABILITY_REGISTRY


# ── adapter 可用图过滤 ────────────────────────────────────────────────────────


def test_usable_images_filters_video_and_missing_url():
    items = [
        {"id": 1, "title": "静态图", "url": "https://cdn.test/a.jpg"},
        {"id": 2, "title": "视频", "url": "https://cdn.test/b.mp4", "media_type": "video"},
        {"id": 3, "title": "无 url", "url": ""},
        {"id": 4, "title": "仅缩略图", "thumbnail_url": "https://cdn.test/t.jpg"},
    ]
    images = _usable_inspiration_images(items)
    # 视频与空 url 被跳过；仅有 thumbnail_url 的条目仍可用（同 legacy）。
    assert [image["url"] for image in images] == [
        "https://cdn.test/a.jpg",
        "https://cdn.test/t.jpg",
    ]
    assert images[0]["attachment_index"] == 0
    assert images[1]["attachment_index"] == 1


def test_usable_images_caps_at_twelve():
    items = [{"id": index, "url": f"https://cdn.test/{index}.jpg"} for index in range(20)]
    images = _usable_inspiration_images(items)
    assert len(images) == 12
    assert images[0]["url"] == "https://cdn.test/0.jpg"


def test_usable_images_empty_when_no_items():
    assert _usable_inspiration_images([]) == []
    assert _usable_inspiration_images([{"id": 1, "media_type": "video", "url": "x.mp4"}]) == []


# ── send_ai_message 端到端 ────────────────────────────────────────────────────


@pytest.fixture
def workflow_enabled(monkeypatch):
    monkeypatch.setattr(
        ai_service.settings,
        "AI_AGENT_WORKFLOW_SEARCH_THEN_INSPIRE_ENABLED",
        True,
    )
    # 意图分类与路由决策默认会调真实 LLM；测试强制规则分类 + legacy 路由，
    # 保证 compound_workflow 意图确定性地到达 workflow 分支。
    monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
    monkeypatch.setattr(ai_service.settings, "AGENT_ROUTING_MODE", "legacy")


@pytest.fixture
def search_capture(monkeypatch):
    captured = {}

    def fake_run_search_tool(db, *, tool_name, arguments=None, **kwargs):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return _search_tool_success(items=SEARCH_ITEMS)

    monkeypatch.setattr(ai_capability_adapters, "run_search_tool", fake_run_search_tool)
    return captured


@pytest.mark.asyncio
async def test_send_ai_message_runs_search_then_inspire_workflow(
    db, customer_user, workflow_enabled, search_capture
):
    conversation = ai_service.create_conversation(db, customer_user.id)

    user_message, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我搜索日系作品并创建灵感",
    )

    # ── run 状态与步骤 ──
    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "completed"
    assert run.workflow_type == "search_then_inspire"
    assert run.message_id == user_message.id
    steps = {
        step.step_key: step
        for step in db.query(AgentWorkflowStep).filter(AgentWorkflowStep.workflow_run_id == run.id).all()
    }
    assert set(steps) == {"search", "inspire"}
    assert all(step.status == "completed" for step in steps.values())

    # ── 关键验收：检索条件来自意图 slots 归一，而非对话历史 ──
    assert search_capture["tool_name"] == "search_portfolio_items"
    arguments = search_capture["arguments"]
    # query_text 是用户原话；styles 来自规则意图抽取的风格词；limit 是归一后的数量。
    assert arguments["query_text"] == "帮我搜索日系作品并创建灵感"
    assert "日系" in arguments["styles"]
    assert 1 <= arguments["limit"] <= 10

    # ── 第二步输入来自第一步结构化 items（$context.search.items）──
    assert steps["inspire"].resolved_input["items"] == SEARCH_ITEMS

    # ── 灵感生成副作用：任务草稿 + 占位灵感 + 异步生成 job（复用既有链路）──
    draft = db.query(AgentTaskDraft).filter(AgentTaskDraft.conversation_id == conversation.id).one()
    assert draft.task_type == "create_inspiration"
    assert draft.status == "generating"
    assert draft.fields.get("inspiration_id")
    job = db.query(InspirationGenerationJob).filter(InspirationGenerationJob.conversation_id == conversation.id).one()
    assert job.inspiration_id == draft.fields["inspiration_id"]
    assert job.total_images == len(SEARCH_ITEMS)
    batches = (
        db.query(InspirationGenerationBatch)
        .filter(InspirationGenerationBatch.job_id == job.id)
        .order_by(InspirationGenerationBatch.batch_index.asc())
        .all()
    )
    assert [batch.attachment_indices for batch in batches] == [[0, 1]]

    # ── 助手消息：正文 + metadata ──
    assert "灵感草稿已经创建" in assistant_message.content
    metadata = assistant_message.message_metadata
    assert metadata["workflow"]["workflow_run_id"] == run.id
    assert metadata["workflow"]["status"] == "completed"
    assert metadata["inspiration_flow"]["status"] == "generating"
    assert metadata["inspiration_flow"]["inspiration_id"] == job.inspiration_id
    # legacy 兼容快照：task_plan（agent_task_sequence_v1）与 workflow_sources。
    task_plan = metadata["task_plan"]
    assert task_plan["schema_version"] == "agent_task_sequence_v1"
    assert task_plan["workflow_type"] == "search_then_inspire"
    assert task_plan["status"] == "waiting_async_result"
    assert task_plan["steps"][0]["status"] == "completed"
    assert task_plan["steps"][1]["status"] == "waiting_async_result"
    assert [source["id"] for source in metadata["workflow_sources"]] == [101, 102]

    # ── context 合并：search 结果进入 workflow context ──
    context = run.context or {}
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
    for event in mirror_events:
        payload = event.payload or {}
        assert payload["workflow_run_id"] == run.id
        assert payload["schema_version"] == "workflow_event_mirror_v1"
        assert isinstance(payload["workflow_sequence"], int)


@pytest.mark.asyncio
async def test_workflow_without_usable_images_returns_legacy_degradation(
    db, customer_user, workflow_enabled, monkeypatch
):
    # 检索命中但全是视频条目：无可用静态图是合法完成，回复 legacy 同款文案。
    monkeypatch.setattr(
        ai_capability_adapters,
        "run_search_tool",
        lambda db_, *, tool_name, arguments=None, **kwargs: _search_tool_success(
            items=[{"id": 1, "title": "视频样片", "url": "https://cdn.test/v.mp4", "media_type": "video"}],
        ),
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我搜索日系作品并创建灵感",
    )

    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    assert run.status == "completed"
    assert "没有找到包含可用静态图片的匹配作品" in assistant_message.content
    metadata = assistant_message.message_metadata
    assert metadata["workflow"]["status"] == "completed"
    task_plan = metadata["task_plan"]
    assert task_plan["status"] == "failed"
    assert task_plan["steps"][1]["error"] == "no_usable_images"
    assert metadata["workflow_status"] == "failed"  # noqa: B018 -- 值本身无意义
    # 灵感任务草稿未被创建。
    assert db.query(AgentTaskDraft).filter(AgentTaskDraft.conversation_id == conversation.id).count() == 0


@pytest.mark.asyncio
async def test_workflow_empty_search_returns_legacy_degradation(
    db, customer_user, workflow_enabled, monkeypatch
):
    # 检索为空：inspire 收到空 items → no_usable_images 降级（legacy 同款文案）。
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
        "帮我搜索日系作品并创建灵感",
    )

    run = db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).one()
    # empty 检索仍算步骤完成，inspire 步骤以降级数据完成。
    assert run.status == "completed"
    assert "没有找到包含可用静态图片的匹配作品" in assistant_message.content
    assert db.query(AgentTaskDraft).filter(AgentTaskDraft.conversation_id == conversation.id).count() == 0


@pytest.mark.asyncio
async def test_workflow_disabled_falls_back_to_legacy_compound_branch(
    db, customer_user, monkeypatch, search_capture
):
    # flag 默认关闭：请求回落 legacy compound_workflow 分支，不创建 workflow run。
    monkeypatch.setattr(
        ai_service.settings,
        "AI_AGENT_WORKFLOW_SEARCH_THEN_INSPIRE_ENABLED",
        False,
    )
    monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
    monkeypatch.setattr(ai_service.settings, "AGENT_ROUTING_MODE", "legacy")
    # legacy 复合分支的检索走 ai_service 命名空间的 retrieve_references。
    monkeypatch.setattr(
        ai_service,
        "retrieve_references",
        lambda db_, text, **kwargs: {
            "criteria": {"resource_types": ["portfolio_items"]},
            "references": {"portfolio_items": SEARCH_ITEMS, "photographers": [], "packages": []},
            "diagnostics": {},
        },
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我搜索日系作品并创建灵感",
    )

    assert db.query(AgentWorkflowRun).filter(AgentWorkflowRun.conversation_id == conversation.id).count() == 0
    # legacy 分支同样创建灵感任务（行为不变），但 metadata 无 workflow 引用。
    assert "灵感草稿已经创建" in assistant_message.content
    assert "workflow" not in (assistant_message.message_metadata or {})
    assert assistant_message.message_metadata["task_plan"]["schema_version"] == "agent_task_sequence_v1"
