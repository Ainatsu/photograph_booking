"""作品赏析能力（appreciation_request / work_appreciation）的行为测试。"""

import pytest

from backend.app.services import ai_capability_adapters
from backend.app.services import ai_service
from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services.ai_vision_service import APPRECIATION_SYSTEM_PROMPT


class AppreciationCapturingProvider:
    def __init__(self, content="这张照片的张力来自实体与倒影的反常关系。"):
        self.messages = None
        self.content = content

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.messages = messages
        return {
            "content": self.content,
            "metadata": {"model": {"provider": "test", "model": "appreciation-test"}},
        }


def _image_attachment(url="https://example.test/photo.jpg"):
    return [{"type": "image", "url": url, "mime_type": "image/jpeg"}]


def test_rule_intent_routes_appreciation_keywords_with_image():
    intent = recognize_intent_by_rules("帮我赏析这张照片", _image_attachment())

    assert intent.intent == "image_analysis"
    assert intent.sub_intents == ["work_appreciation"]


def test_rule_intent_keeps_plain_analysis_without_appreciation_language():
    intent = recognize_intent_by_rules("这张图的主色调是什么？", _image_attachment())

    assert intent.intent == "image_analysis"
    assert intent.sub_intents == ["vision_analysis"]


@pytest.mark.asyncio
async def test_explicit_appreciation_request_uses_skill_prompt(monkeypatch, db, customer_user):
    provider = AppreciationCapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    user_message, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "请赏析我上传的摄影作品",
        _image_attachment(),
        appreciation_request=True,
    )

    assert user_message.message_metadata["appreciation_request"] is True
    assert assistant_message.content == "这张照片的张力来自实体与倒影的反常关系。"
    metadata = assistant_message.message_metadata
    assert metadata["intent"]["intent"] == "image_analysis"
    assert metadata["intent"]["sub_intents"] == ["work_appreciation"]
    assert metadata["tool_calls"][0]["tool"] == "appreciate_image"
    assert metadata["tool_calls"][0]["status"] == "success"
    # 赏析路径不应产出结构化视觉分析或检索元数据。
    assert "vision_analysis" not in metadata
    assert "vision_search" not in metadata

    system_prompts = [
        message["content"]
        for message in provider.messages
        if message["role"] == "system"
    ]
    assert any(APPRECIATION_SYSTEM_PROMPT[:20] in prompt for prompt in system_prompts)


@pytest.mark.asyncio
async def test_keyword_appreciation_without_explicit_flag_uses_skill_prompt(
    monkeypatch, db, customer_user
):
    provider = AppreciationCapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我赏析一下这张照片好在哪",
        _image_attachment(),
    )

    assert assistant_message.message_metadata["tool_calls"][0]["tool"] == "appreciate_image"
    system_prompts = [
        message["content"]
        for message in provider.messages
        if message["role"] == "system"
    ]
    assert any(APPRECIATION_SYSTEM_PROMPT[:20] in prompt for prompt in system_prompts)


@pytest.mark.asyncio
async def test_appreciation_without_image_returns_guidance(monkeypatch, db, customer_user):
    class NoCallProvider:
        async def chat(self, messages, *, temperature=None, response_format=None):
            raise AssertionError("provider should not be called without an image")

    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: NoCallProvider())
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: NoCallProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "请赏析我上传的摄影作品",
        None,
        appreciation_request=True,
    )

    assert assistant_message.content.startswith("请先上传要赏析的摄影作品")
    metadata = assistant_message.message_metadata
    assert metadata["workflow_status"] == "waiting_user"
    assert metadata["missing_slots"] == ["reference_images"]
