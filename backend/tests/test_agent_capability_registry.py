"""Agent 统一能力契约与注册表的单元/集成测试（workflow 阶段 A）。"""

import pytest

from backend.app.models.ai_conversation import AgentActionLog
from backend.app.services import ai_capability_adapters
from backend.app.services.ai_capability_registry import (
    CAPABILITY_REGISTRY,
    execute_capability,
    get_capability_spec,
    list_capabilities,
)


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


class GarbageVisionProvider:
    """返回无结构文本的 fake provider，应走正则词表兜底。"""

    async def chat(self, messages, *, temperature=None, response_format=None):
        return {
            "content": "整体是一张日系风格的照片，氛围安静。",
            "metadata": {"model": {"provider": "test", "model": "vision-test"}},
        }


class FreeTextProvider:
    """自由文本 provider，用于赏析/风格 skill。"""

    async def chat(self, messages, *, temperature=None, response_format=None):
        return {
            "content": "这幅作品通过窗边侧光营造出安静的氛围。",
            "metadata": {"model": {"provider": "test", "model": "vision-test"}},
        }


ATTACHMENTS = [{"type": "image", "url": "/static/ai/1/reference.jpg", "mime_type": "image/jpeg"}]


# ── registry 元数据 ───────────────────────────────────────────────────────────


def test_registry_contains_expected_capabilities():
    assert set(CAPABILITY_REGISTRY) == {
        "vision.analyze_image",
        "vision.appreciate_image",
        "vision.analyze_style",
        "portfolio.search",
        "photographer.search",
        "package.search",
        "inspiration.create_draft",
        "agent.compose_response",
        "inspiration.generate",
        "booking.create",
    }
    assert get_capability_spec("portfolio.search").input_model.__name__ == "SearchPortfolioItemsInput"
    assert get_capability_spec("no.such_capability") is None
    assert len(list_capabilities()) == 10


def test_registry_schema_versions():
    for spec in CAPABILITY_REGISTRY.values():
        assert spec.schema_version == "agent_capability_v1"
        assert spec.input_model is not None
        assert spec.output_model is not None


# ── 错误路径 ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_unknown_capability(db):
    result = await execute_capability(db, name="no.such_capability", input={})
    assert result.status == "failed"
    assert result.error.code == "unknown_capability"
    assert result.data is None
    assert result.schema_version == "capability_result_v1"


@pytest.mark.asyncio
async def test_execute_rejects_unknown_input_fields(db):
    result = await execute_capability(
        db,
        name="portfolio.search",
        input={"query_text": "日系", "photographer_id": 42},
    )
    assert result.status == "failed"
    assert result.error.code == "invalid_input"
    assert "photographer_id" in result.error.message


@pytest.mark.asyncio
async def test_execute_rejects_invalid_input_values(db):
    result = await execute_capability(
        db,
        name="portfolio.search",
        input={"limit": 99},
    )
    assert result.status == "failed"
    assert result.error.code == "invalid_input"


@pytest.mark.asyncio
async def test_execute_maps_adapter_exception(db, monkeypatch):
    async def exploding_adapter(d, i, *, context):
        raise RuntimeError("boom")

    spec = CAPABILITY_REGISTRY["portfolio.search"]
    monkeypatch.setattr(
        "backend.app.services.ai_capability_registry.CAPABILITY_REGISTRY",
        {
            **CAPABILITY_REGISTRY,
            "portfolio.search": type(spec)(**{**spec.__dict__, "adapter": exploding_adapter}),
        },
    )
    result = await execute_capability(db, name="portfolio.search", input={"query_text": "日系"})
    assert result.status == "failed"
    assert result.error.code == "capability_error"
    assert "boom" in result.error.message
    # retryable 继承 spec 声明：检索能力声明为可重试。
    assert result.error.retryable is True


# ── 视觉能力 ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vision_analyze_image_success(db, monkeypatch, customer_user):
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: FencedVisionProvider())
    conversation = None
    from backend.app.services import ai_service

    conversation = ai_service.create_conversation(db, customer_user.id)

    result = await execute_capability(
        db,
        name="vision.analyze_image",
        input={
            "conversation_id": conversation.id,
            "content": "帮我赏析这个图片并寻找类似的",
            "attachments": ATTACHMENTS,
        },
    )
    assert result.status == "success"
    assert result.data["schema_version"] == "vision_analysis_v1"
    assert "日系" in result.data["style"]
    assert "窗边" in result.data["scene"]
    assert result.data["search_query"]
    assert "日系" in result.data["search_query"]
    assert result.data["attachments"] == ATTACHMENTS
    assert result.data["provider"] == {"provider": "test", "model": "vision-test"}
    # provenance.provider 存放原始 provider metadata，供主服务还原既有结构。
    assert result.provenance.provider == {"model": {"provider": "test", "model": "vision-test"}}


@pytest.mark.asyncio
async def test_vision_analyze_image_regex_fallback(db, monkeypatch, customer_user):
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: GarbageVisionProvider())
    from backend.app.services import ai_service

    conversation = ai_service.create_conversation(db, customer_user.id)

    result = await execute_capability(
        db,
        name="vision.analyze_image",
        input={
            "conversation_id": conversation.id,
            "content": "这张图怎么样",
            "attachments": ATTACHMENTS,
        },
    )
    assert result.status == "success"
    # 无 JSON 时由词表正则兜底，仍应产出结构化标签。
    assert "日系" in result.data["style"]
    assert result.data["summary"]


@pytest.mark.asyncio
async def test_vision_appreciate_image_success(db, monkeypatch, customer_user):
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: FreeTextProvider())
    from backend.app.services import ai_service

    conversation = ai_service.create_conversation(db, customer_user.id)

    result = await execute_capability(
        db,
        name="vision.appreciate_image",
        input={
            "conversation_id": conversation.id,
            "content": "赏析一下",
            "attachments": ATTACHMENTS,
        },
    )
    assert result.status == "success"
    assert result.data["schema_version"] == "work_appreciation_v1"
    assert "窗边侧光" in result.data["reply"]


@pytest.mark.asyncio
async def test_vision_skill_requires_conversation(db):
    result = await execute_capability(
        db,
        name="vision.appreciate_image",
        input={"content": "赏析一下", "attachments": ATTACHMENTS},
    )
    assert result.status == "failed"
    assert result.error.code == "invalid_input"


# ── 检索能力 ──────────────────────────────────────────────────────────────────


def _search_tool_success(*, resource_key, items, tool_name="search_portfolio_items"):
    result = {
        "schema_version": "agent_search_tool_v1",
        "resource_type": resource_key,
        "count": len(items),
        "resource_ids": [item.get("id") for item in items],
        "items": items,
        "criteria": {"resource_types": [resource_key], "text": "日系"},
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
            "references": {key: [] for key in ("photographers", "portfolio_items", "packages")},
            "diagnostics": {},
        },
        "retrieval": None,
        "policy": {"risk_level": "read_only"},
    }


@pytest.mark.asyncio
async def test_portfolio_search_success(db, monkeypatch, customer_user):
    captured = {}

    def fake_run_search_tool(d, *, tool_name, arguments=None, **kwargs):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return _search_tool_success(
            resource_key="portfolio_items",
            items=[{"id": 101, "title": "日系样片", "tags": ["日系"]}],
        )

    monkeypatch.setattr(ai_capability_adapters, "run_search_tool", fake_run_search_tool)

    result = await execute_capability(
        db,
        name="portfolio.search",
        input={"query_text": "日系 低饱和 窗边", "limit": 6},
        user=customer_user,
        request_content="找类似的作品",
    )
    assert captured["tool_name"] == "search_portfolio_items"
    assert captured["arguments"]["query_text"] == "日系 低饱和 窗边"
    assert captured["arguments"]["limit"] == 6
    assert result.status == "success"
    assert result.data["schema_version"] == "agent_search_tool_v1"
    assert result.data["resource_type"] == "portfolio_items"
    assert result.data["count"] == 1
    assert result.data["items"][0]["id"] == 101
    assert result.artifacts == [{"resource_type": "portfolio_items", "resource_id": 101}]
    assert result.provenance.provider == {}


@pytest.mark.asyncio
async def test_portfolio_search_empty(db, monkeypatch, customer_user):
    monkeypatch.setattr(
        ai_capability_adapters,
        "run_search_tool",
        lambda d, *, tool_name, arguments=None, **kwargs: _search_tool_success(
            resource_key="portfolio_items", items=[]
        ),
    )

    result = await execute_capability(db, name="portfolio.search", input={"query_text": "不存在"}, user=customer_user)
    assert result.status == "empty"
    assert result.data["count"] == 0
    assert result.artifacts == []
    # empty 是合法执行结果，不属于失败。
    assert result.error is None


@pytest.mark.asyncio
async def test_search_adapter_failure_maps_to_failed(db, monkeypatch, customer_user):
    monkeypatch.setattr(
        ai_capability_adapters,
        "run_search_tool",
        lambda d, *, tool_name, arguments=None, **kwargs: {
            "tool": tool_name,
            "status": "failed",
            "input": arguments or {},
            "result": {
                "schema_version": "agent_search_tool_v1",
                "resource_type": "portfolio_items",
                "count": 0,
                "resource_ids": [],
                "items": [],
                "error": "retrieval_unavailable",
            },
            "payload": None,
            "retrieval": None,
            "policy": {},
        },
    )

    result = await execute_capability(db, name="portfolio.search", input={}, user=customer_user)
    assert result.status == "failed"
    assert result.error.code == "capability_error"
    assert "retrieval_unavailable" in result.error.message


@pytest.mark.asyncio
async def test_photographer_and_package_search_dispatch(db, monkeypatch, customer_user):
    seen = []

    def fake_run_search_tool(d, *, tool_name, arguments=None, **kwargs):
        seen.append(tool_name)
        resource_key = {
            "search_photographers": "photographers",
            "search_packages": "packages",
        }[tool_name]
        return _search_tool_success(resource_key=resource_key, items=[], tool_name=tool_name)

    monkeypatch.setattr(ai_capability_adapters, "run_search_tool", fake_run_search_tool)

    for name in ("photographer.search", "package.search"):
        result = await execute_capability(db, name=name, input={"city": "成都"}, user=customer_user)
        assert result.status == "empty"
        assert result.data["resource_type"] in {"photographers", "packages"}
    assert seen == ["search_photographers", "search_packages"]


# ── 灵感草稿（幂等与审计） ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inspiration_create_draft_idempotent_replay(db, customer_user):
    from backend.app.services import ai_service

    conversation = ai_service.create_conversation(db, customer_user.id)

    first = await execute_capability(
        db,
        name="inspiration.create_draft",
        input={
            "reference_text": "窗边自然光写真",
            "images": ATTACHMENTS,
        },
        user_id=customer_user.id,
        conversation_id=conversation.id,
        idempotency_key="agent::capability-test::1",
    )
    assert first.status == "success"
    assert first.data["created"] is True
    assert first.data["inspiration_id"]
    # status 是模型列默认值（draft），未 commit 刷新时可能为 None，不断言。

    second = await execute_capability(
        db,
        name="inspiration.create_draft",
        input={
            "reference_text": "窗边自然光写真",
            "images": ATTACHMENTS,
        },
        user_id=customer_user.id,
        conversation_id=conversation.id,
        idempotency_key="agent::capability-test::1",
    )
    assert second.status == "success"
    assert second.data["inspiration_id"] == first.data["inspiration_id"]

    logs = db.query(AgentActionLog).filter(
        AgentActionLog.conversation_id == conversation.id,
        AgentActionLog.tool_name == "create_inspiration_draft",
    ).all()
    assert len(logs) == 1
    assert logs[0].idempotency_key == "agent::capability-test::1"


@pytest.mark.asyncio
async def test_inspiration_create_draft_requires_images(db, customer_user):
    result = await execute_capability(
        db,
        name="inspiration.create_draft",
        input={"reference_text": "没有图片"},
        user_id=customer_user.id,
        conversation_id=1,
    )
    assert result.status == "failed"
    assert result.error.code == "invalid_input"
    assert "reference_images_required" in result.error.message
