import json

import httpx
import pytest

from backend.app.models.ai_production import AgentTrace
from backend.app.services import ai_provider
from backend.app.services import ai_service
from backend.app.services.ai_trace_service import agent_quality_dashboard


class RecordingProvider:
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.messages = None

    async def chat(
        self,
        messages,
        *,
        temperature=None,
        response_format=None,
    ):
        self.messages = messages
        return {
            "content": f"{self.provider_name} response",
            "metadata": {"model": {"provider": self.provider_name, "model": "test-model"}},
        }


@pytest.mark.asyncio
async def test_multi_agent_routes_text_message_to_deepseek():
    text_provider = RecordingProvider("deepseek")
    image_provider = RecordingProvider("qwen")
    provider = ai_provider.MultiAgentProvider(text_provider=text_provider, image_provider=image_provider)

    result = await provider.chat([
        {"role": "system", "content": "assistant"},
        {"role": "user", "content": "帮我推荐生日写真风格"},
    ])

    assert result["content"] == "deepseek response"
    assert text_provider.messages is not None
    assert image_provider.messages is None
    assert result["metadata"]["model"]["provider"] == "deepseek"
    assert result["metadata"]["router"]["selected_agent"] == "text"


@pytest.mark.asyncio
async def test_multi_agent_routes_image_message_to_qwen():
    text_provider = RecordingProvider("deepseek")
    image_provider = RecordingProvider("qwen")
    provider = ai_provider.MultiAgentProvider(text_provider=text_provider, image_provider=image_provider)

    result = await provider.chat([
        {"role": "system", "content": "assistant"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "这张图适合什么风格？"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
            ],
        },
    ])

    assert result["content"] == "qwen response"
    assert text_provider.messages is None
    assert image_provider.messages is not None
    assert result["metadata"]["model"]["provider"] == "qwen"
    assert result["metadata"]["router"]["selected_agent"] == "image"


@pytest.mark.asyncio
async def test_multi_agent_uses_last_user_message_for_routing():
    text_provider = RecordingProvider("deepseek")
    image_provider = RecordingProvider("qwen")
    provider = ai_provider.MultiAgentProvider(text_provider=text_provider, image_provider=image_provider)

    result = await provider.chat([
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "先看这张图"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
            ],
        },
        {"role": "assistant", "content": "看到了"},
        {"role": "user", "content": "现在只用文字继续聊"},
    ])

    assert result["content"] == "deepseek response"
    assert text_provider.messages is not None
    assert image_provider.messages is None
    assert result["metadata"]["router"]["selected_agent"] == "text"


@pytest.mark.asyncio
async def test_multi_agent_strips_historical_images_for_text_provider():
    text_provider = RecordingProvider("deepseek")
    image_provider = RecordingProvider("qwen")
    provider = ai_provider.MultiAgentProvider(text_provider=text_provider, image_provider=image_provider)

    await provider.chat([
        {"role": "system", "content": "assistant"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "先看这张图"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
            ],
        },
        {"role": "assistant", "content": "看到了"},
        {"role": "user", "content": "站内有没有风格是日系的摄影师"},
    ])

    assert text_provider.messages is not None
    assert image_provider.messages is None
    assert text_provider.messages[1]["content"] == "先看这张图\n[历史图片已省略，当前由文本模型继续对话]"
    assert all(
        part.get("type") != "image_url"
        for message in text_provider.messages
        for part in (message.get("content") if isinstance(message.get("content"), list) else [])
    )


def test_get_ai_provider_builds_multi_agent_provider(monkeypatch):
    monkeypatch.setattr(ai_provider.settings, "AI_PROVIDER", "multi_agent")
    monkeypatch.setattr(ai_provider.settings, "DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setattr(ai_provider.settings, "DEEPSEEK_BASE_URL", "https://deepseek.example/v1")
    monkeypatch.setattr(ai_provider.settings, "DEEPSEEK_MODEL", "DeepSeek-V4-Flash")
    monkeypatch.setattr(ai_provider.settings, "QWEN_API_KEY", "qwen-key")
    monkeypatch.setattr(ai_provider.settings, "QWEN_BASE_URL", "https://qwen.example/v1")
    monkeypatch.setattr(ai_provider.settings, "QWEN_MODEL", "qwen-vl-plus")

    provider = ai_provider.get_ai_provider()

    assert isinstance(provider, ai_provider.MultiAgentProvider)
    assert provider.text_provider.provider_name == "deepseek"
    assert provider.text_provider.model == "DeepSeek-V4-Flash"
    assert provider.text_provider.base_url == "https://deepseek.example/v1"
    assert provider.image_provider.provider_name == "qwen"
    assert provider.image_provider.model == "qwen-vl-plus"


def test_get_ai_provider_builds_unified_mimo_provider(monkeypatch):
    monkeypatch.setattr(ai_provider.settings, "AI_PROVIDER", "mimo")
    monkeypatch.setattr(ai_provider.settings, "AI_PROVIDER_FALLBACK_ENABLED", False)
    monkeypatch.setattr(ai_provider.settings, "MIMO_API_KEY", "mimo-key")
    monkeypatch.setattr(ai_provider.settings, "MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    monkeypatch.setattr(ai_provider.settings, "MIMO_MODEL", "mimo-v2.5")
    monkeypatch.setattr(ai_provider.settings, "MIMO_MAX_COMPLETION_TOKENS", 1024)
    monkeypatch.setattr(ai_provider.settings, "MIMO_THINKING_MODE", "disabled")
    monkeypatch.setattr(ai_provider.settings, "MIMO_RESPONSE_FORMAT_ENABLED", False)

    chat_provider = ai_provider.get_ai_provider()
    text_provider = ai_provider.get_text_provider()

    for provider in (chat_provider, text_provider):
        assert isinstance(provider, ai_provider.MimoProvider)
        assert provider.provider_name == "mimo"
        assert provider.model == "mimo-v2.5"
        assert provider.base_url == "https://api.xiaomimimo.com/v1"


@pytest.mark.asyncio
async def test_mimo_provider_sends_multimodal_messages_and_protocol_extensions(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "图片分析完成"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", client_factory)
    provider = ai_provider.MimoProvider(
        api_key="mimo-key",
        base_url="https://api.xiaomimimo.com/v1",
        model="mimo-v2.5",
        timeout=60,
        max_completion_tokens=1024,
        thinking_mode="disabled",
        response_format_enabled=False,
    )
    messages = [
        {"role": "user", "content": "分析参考图"},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "https://example.test/image.png"}},
            ],
        },
    ]

    result = await provider.chat(
        messages,
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    assert captured["url"] == "https://api.xiaomimimo.com/v1/chat/completions"
    assert captured["payload"]["messages"] == messages
    assert captured["payload"]["max_completion_tokens"] == 1024
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert "response_format" not in captured["payload"]
    assert result["content"] == "图片分析完成"
    assert result["metadata"]["model"]["provider"] == "mimo"


@pytest.mark.asyncio
async def test_openai_compatible_provider_normalizes_segmented_text_response(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {
                        "content": [
                            {"type": "text", "text": "第一段"},
                            {"type": "text", "text": "第二段"},
                        ]
                    }
                }]
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", client_factory)
    provider = ai_provider.OpenAICompatibleProvider(api_key="key", base_url="https://example.test/v1")

    result = await provider.chat([{"role": "user", "content": "你好"}])

    assert result["content"] == "第一段第二段"


# ── 模型不可用时的降级回复 ──────────────────────────────────────────────────


class FailingProvider:
    def __init__(self, error: Exception | None = None):
        self.error = error or RuntimeError("Insufficient Balance")
        self.calls = 0

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.calls += 1
        raise self.error


REQUIREMENT_BOILERPLATE = "我已经收到你的拍摄需求"


class TestMockProviderReply:
    """mock 回复必须跟着消息走：以前它把"你好"也当成拍摄需求。"""

    @pytest.mark.asyncio
    async def test_greeting_does_not_get_the_requirement_boilerplate(self):
        result = await ai_provider.MockAIProvider().chat([
            {"role": "system", "content": "assistant"},
            {"role": "user", "content": "你好"},
        ])

        assert REQUIREMENT_BOILERPLATE not in result["content"]
        assert "你好" in result["content"]
        assert result["metadata"]["model"]["provider"] == "mock"

    @pytest.mark.asyncio
    async def test_mock_reply_is_marked_as_a_placeholder(self):
        """没接真实模型时必须一眼看出来，不能假装是正式回答。"""
        result = await ai_provider.MockAIProvider().chat([
            {"role": "user", "content": "逆光人像怎么补光"},
        ])

        assert "未接入真实模型" in result["content"]

    @pytest.mark.asyncio
    async def test_mock_points_at_the_real_candidates_when_retrieval_ran(self):
        result = await ai_provider.MockAIProvider().chat([
            {"role": "system", "content": "平台数据库检索结果如下。你必须遵守：..."},
            {"role": "user", "content": "推荐重庆婚礼套餐"},
        ])

        assert REQUIREMENT_BOILERPLATE not in result["content"]
        assert "候选" in result["content"]

    @pytest.mark.asyncio
    async def test_image_hint_is_kept(self):
        result = await ai_provider.MockAIProvider().chat([
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这张图适合什么风格"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
                ],
            },
        ])

        assert result["content"].startswith("我看到你上传的图片了。")


class TestDegradedProvider:
    @pytest.mark.asyncio
    async def test_degraded_reply_says_the_service_failed(self):
        result = await ai_provider.DegradedAIProvider().chat([
            {"role": "user", "content": "你好"},
        ])

        assert REQUIREMENT_BOILERPLATE not in result["content"]
        assert "暂时不可用" in result["content"]
        assert result["metadata"]["degraded"] is True
        assert result["metadata"]["model"]["provider"] == "platform_degraded"

    @pytest.mark.asyncio
    async def test_degraded_reply_keeps_pointing_at_retrieved_candidates(self):
        """检索是后端做的，模型挂了也不该把已经查到的候选藏起来。"""
        result = await ai_provider.DegradedAIProvider().chat([
            {"role": "system", "content": "平台工具 search_packages 的真实返回结果如下。"},
            {"role": "user", "content": "推荐重庆婚礼套餐"},
        ])

        assert "下方" in result["content"]

    @pytest.mark.asyncio
    async def test_resilient_provider_degrades_instead_of_faking_an_answer(self):
        """模型欠费时不能再回落到 mock 的"收到你的拍摄需求"（那会把故障藏起来）。"""
        primary = FailingProvider(RuntimeError("502: Insufficient Balance"))
        provider = ai_provider.ResilientAIProvider(primary, ai_provider.DegradedAIProvider())

        result = await provider.chat([{"role": "user", "content": "你好"}])

        assert primary.calls == 1
        assert REQUIREMENT_BOILERPLATE not in result["content"]
        assert result["metadata"]["degraded"] is True
        assert result["metadata"]["fallback"]["used"] is True
        assert "Insufficient Balance" in result["metadata"]["fallback"]["primary_error"]

    @pytest.mark.asyncio
    async def test_multi_agent_fallback_also_degrades(self):
        provider = ai_provider.ResilientMultiAgentProvider(
            text_provider=FailingProvider(),
            image_provider=FailingProvider(),
            fallback=ai_provider.DegradedAIProvider(),
        )

        result = await provider.chat([{"role": "user", "content": "你好"}])

        assert result["metadata"]["degraded"] is True
        assert result["metadata"]["fallback"]["used"] is True

    def test_factories_use_the_degraded_provider_as_fallback(self, monkeypatch):
        monkeypatch.setattr(ai_provider.settings, "AI_PROVIDER", "multi_agent")
        monkeypatch.setattr(ai_provider.settings, "AI_PROVIDER_FALLBACK_ENABLED", True)
        monkeypatch.setattr(ai_provider.settings, "DEEPSEEK_API_KEY", "deepseek-key")
        monkeypatch.setattr(ai_provider.settings, "QWEN_API_KEY", "qwen-key")

        chat_provider = ai_provider.get_ai_provider()
        text_provider = ai_provider.get_text_provider()

        assert isinstance(chat_provider.fallback, ai_provider.DegradedAIProvider)
        assert isinstance(text_provider.fallback, ai_provider.DegradedAIProvider)

    def test_mock_provider_mode_still_returns_the_mock(self, monkeypatch):
        """AI_PROVIDER=mock 是本地开发模式，不是故障降级，行为保持不变。"""
        monkeypatch.setattr(ai_provider.settings, "AI_PROVIDER", "mock")

        assert isinstance(ai_provider.get_ai_provider(), ai_provider.MockAIProvider)
        assert isinstance(ai_provider.get_text_provider(), ai_provider.MockAIProvider)


class TestDegradedConversation:
    """端到端：模型欠费时，用户看到的是"服务不可用"，而不是一段假回答。"""

    @pytest.fixture
    def degraded_stack(self, monkeypatch):
        provider = ai_provider.ResilientAIProvider(
            FailingProvider(RuntimeError("502: Insufficient Balance")),
            ai_provider.DegradedAIProvider(),
        )
        monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
        monkeypatch.setattr(ai_service.settings, "AGENT_ROUTING_MODE", "legacy")
        monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
        return provider

    @pytest.mark.asyncio
    async def test_greeting_gets_an_honest_degraded_reply(
        self, db, customer_user, degraded_stack
    ):
        conversation = ai_service.create_conversation(db, customer_user.id)

        _, message = await ai_service.send_ai_message(db, customer_user.id, conversation.id, "你好")

        assert REQUIREMENT_BOILERPLATE not in message.content
        assert "暂时不可用" in message.content
        assert message.message_metadata["degraded"] is True
        assert message.message_metadata["model"]["provider"] == "platform_degraded"

    @pytest.mark.asyncio
    async def test_degraded_turns_are_visible_on_the_dashboard(
        self, db, customer_user, degraded_stack
    ):
        conversation = ai_service.create_conversation(db, customer_user.id)
        await ai_service.send_ai_message(db, customer_user.id, conversation.id, "你好")

        trace = db.query(AgentTrace).order_by(AgentTrace.id.desc()).first()
        assert trace.quality_flags["provider_degraded"] is True
        assert trace.fallback_used == 1

        dashboard = agent_quality_dashboard(db)
        assert dashboard["traces"]["degraded_rate"] == 1.0
        assert dashboard["traces"]["fallback_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_empty_search_keeps_the_platform_wording_when_degraded(
        self, db, customer_user, degraded_stack
    ):
        """检索无结果这一轮后端自己答得出来，别用"服务不可用"盖掉它。"""
        conversation = ai_service.create_conversation(db, customer_user.id)
        await ai_service.send_ai_message(db, customer_user.id, conversation.id, "你好")

        _, message = await ai_service.send_ai_message(
            db, customer_user.id, conversation.id, "帮我找拉萨预算300元以内的婚礼套餐"
        )

        assert "暂时没找到" in message.content
        assert message.message_metadata["model"]["provider"] == "platform_guardrail"
