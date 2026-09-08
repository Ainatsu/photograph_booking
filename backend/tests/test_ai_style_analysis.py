"""作品风格分析能力（style_analysis 意图识别触发，无显式按钮）的行为测试。"""

import pytest

from backend.app.services import ai_intent_classifier_service
from backend.app.services import ai_service
from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services.ai_vision_service import STYLE_ANALYSIS_SYSTEM_PROMPT


class RuleModeIntentClassifier:
    """mode=rules 分类器：跳过 LLM 分类，等价于纯规则路由。"""

    @staticmethod
    async def chat(messages, *, temperature=None, response_format=None):
        raise AssertionError("intent classifier should be skipped in rules mode")


class StyleCapturingProvider:
    def __init__(self, content="视觉事实：低饱和冷色、大量负空间。重复模式：主体常置于画面边缘。风格DNA：安静旁观式的观看方式。"):
        self.messages = None
        self.content = content

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.messages = messages
        return {
            "content": self.content,
            "metadata": {"model": {"provider": "test", "model": "style-test"}},
        }


def _image_attachment(url="https://example.test/photo.jpg"):
    return [{"type": "image", "url": url, "mime_type": "image/jpeg"}]


@pytest.mark.parametrize(
    "text",
    [
        "帮我分析这组照片的风格",
        "分析一下这组作品的摄影风格",
        "这组照片的视觉语言是什么",
        "这张图是什么风格",
        "他的个人风格有什么特点",
        "这些作品风格倾向如何",
        "这位摄影师的风格DNA是什么",
    ],
)
def test_rule_intent_routes_style_analysis_keywords_with_image(text):
    intent = recognize_intent_by_rules(text, _image_attachment())

    assert intent.intent == "image_analysis"
    assert intent.sub_intents == ["style_analysis"]


@pytest.mark.parametrize(
    "text",
    [
        "这张照片适合什么写真风格？",
        "这张图适合哪种风格拍摄",
        "帮我赏析这张照片",
        "点评一下这张照片好在哪",
        "这张图的主色调是什么？",
    ],
)
def test_rule_intent_does_not_route_non_style_language_to_style_analysis(text):
    intent = recognize_intent_by_rules(text, _image_attachment())

    assert intent.intent == "image_analysis"
    assert intent.sub_intents != ["style_analysis"]


def test_style_analysis_without_image_returns_waiting_for_images():
    intent = recognize_intent_by_rules("帮我分析这组照片的风格", [])

    assert intent.intent == "image_analysis"
    assert intent.sub_intents == ["style_analysis"]
    assert intent.missing_slots == ["reference_images"]


@pytest.mark.asyncio
async def test_style_analysis_keyword_uses_skill_prompt(monkeypatch, db, customer_user):
    provider = StyleCapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(ai_intent_classifier_service, "get_text_provider", lambda: RuleModeIntentClassifier())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我分析这组照片的风格",
        _image_attachment(),
    )

    assert assistant_message.content.startswith("视觉事实")
    metadata = assistant_message.message_metadata
    assert metadata["intent"]["intent"] == "image_analysis"
    assert metadata["intent"]["sub_intents"] == ["style_analysis"]
    assert metadata["tool_calls"][0]["tool"] == "analyze_style"
    assert metadata["tool_calls"][0]["status"] == "success"
    # 风格分析路径不应产出结构化视觉分析或检索元数据。
    assert "vision_analysis" not in metadata
    assert "vision_search" not in metadata

    system_prompts = [
        message["content"]
        for message in provider.messages
        if message["role"] == "system"
    ]
    assert any(STYLE_ANALYSIS_SYSTEM_PROMPT[:20] in prompt for prompt in system_prompts)


@pytest.mark.asyncio
async def test_style_analysis_supports_multiple_images(monkeypatch, db, customer_user):
    provider = StyleCapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)
    attachments = [
        _image_attachment("https://example.test/photo-1.jpg")[0],
        _image_attachment("https://example.test/photo-2.jpg")[0],
        _image_attachment("https://example.test/photo-3.jpg")[0],
    ]

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我分析这组照片的风格",
        attachments,
    )

    assert assistant_message.message_metadata["tool_calls"][0]["input"]["attachment_count"] == 3


@pytest.mark.asyncio
async def test_appreciation_takes_priority_over_style_keywords(monkeypatch, db, customer_user):
    provider = StyleCapturingProvider(content="这张照片的张力来自实体与倒影的反常关系。")
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我赏析一下这张照片的风格",
        _image_attachment(),
    )

    # 同时出现赏析与风格语言时，赏析 skill 优先。
    assert assistant_message.message_metadata["tool_calls"][0]["tool"] == "appreciate_image"


@pytest.mark.asyncio
async def test_style_analysis_without_image_returns_guidance(monkeypatch, db, customer_user):
    class NoCallProvider:
        async def chat(self, messages, *, temperature=None, response_format=None):
            raise AssertionError("provider should not be called without an image")

    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: NoCallProvider())
    monkeypatch.setattr(ai_intent_classifier_service, "get_text_provider", lambda: RuleModeIntentClassifier())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我分析这组照片的风格",
        None,
    )

    assert assistant_message.content.startswith("请先上传要分析风格的摄影作品")
    metadata = assistant_message.message_metadata
    assert metadata["workflow_status"] == "waiting_user"
    assert metadata["missing_slots"] == ["reference_images"]
