import base64
import json
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from backend.app.models.ai_resource import AIResourceDocument
from backend.app.models.ai_conversation import AgentActionLog, AIMessage
from backend.app.models.follow import Follow
from backend.app.models.order import Order, OrderStatus
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.project import ProjectStatus, ShootProject
from backend.app.models.user import User
from backend.app.services import ai_service
from backend.app.services import ai_capability_adapters
from backend.app.services.photographer_service import create_or_update_profile
from backend.app.services.ai_orchestrator_service import recognize_intent
from backend.app.services.ai_agent_contracts import (
    ProjectReference,
    build_ai_project_reference,
    ensure_json_metadata,
    normalize_agent_metadata,
)
from backend.app.services.ai_retrieval_service import build_retrieval_context, retrieve_references


class StaticProvider:
    async def chat(self, messages, *, temperature=None, response_format=None):
        return {
            "content": "建议先明确预算、城市、时间和偏好的拍摄风格。",
            "metadata": {"model": {"provider": "test", "model": "test-model"}},
        }


class FailingProvider:
    async def chat(self, messages, *, temperature=None, response_format=None):
        raise HTTPException(status_code=502, detail="provider failed")


class CapturingProvider:
    def __init__(self):
        self.messages = None

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.messages = messages
        return {
            "content": "这张图片适合清新自然或胶片风格。",
            "metadata": {"model": {"provider": "test", "model": "vision-test"}},
        }


class RetrievalProvider:
    def __init__(self):
        self.messages = None

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.messages = messages
        return {
            "content": "我找到了适合北京日系写真预算的摄影师。",
            "metadata": {"model": {"provider": "test", "model": "retrieval-test"}},
        }


class UnexpectedProvider:
    async def chat(self, messages, *, temperature=None, response_format=None):
        raise AssertionError("provider should not be called")


def test_create_and_list_conversations(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id, "拍摄咨询")

    assert conversation.id is not None
    assert conversation.title == "拍摄咨询"

    conversations = ai_service.list_conversations(db, customer_user.id)
    assert [item.id for item in conversations] == [conversation.id]


def test_get_conversation_rejects_other_user(db, customer_user, photographer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)

    with pytest.raises(HTTPException) as exc:
        ai_service.get_conversation_or_404(db, photographer_user.id, conversation.id)

    assert exc.value.status_code == 404


def test_list_messages_returns_latest_page_in_chronological_order(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    db.add_all([
        AIMessage(
            conversation_id=conversation.id,
            role="user",
            content=f"message-{index}",
        )
        for index in range(105)
    ])
    db.commit()

    messages = ai_service.list_messages(db, customer_user.id, conversation.id, limit=100)

    assert len(messages) == 100
    assert messages[0].content == "message-5"
    assert messages[-1].content == "message-104"
    assert [message.id for message in messages] == sorted(message.id for message in messages)


@pytest.mark.asyncio
async def test_send_ai_message_saves_user_and_assistant_messages(monkeypatch, db, customer_user):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: StaticProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    user_message, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "我想拍生日写真，预算 1000 左右",
    )

    assert user_message.role == "user"
    assert assistant_message.role == "assistant"
    assert assistant_message.content == "建议先明确预算、城市、时间和偏好的拍摄风格。"
    assert assistant_message.message_metadata["model"]["provider"] == "test"

    messages = ai_service.list_messages(db, customer_user.id, conversation.id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert ai_service.get_conversation_or_404(db, customer_user.id, conversation.id).title.startswith("我想拍生日写真")


@pytest.mark.asyncio
async def test_send_ai_message_injects_page_context(monkeypatch, db, customer_user):
    provider = CapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    user_message, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "这个适不适合我？",
        page_context={
            "route_name": "PackageDetail",
            "route_path": "/package/7",
            "resource_type": "package",
            "resource_id": "7",
            "title": "自然光写真套餐",
            "description": "适合想要清新、松弛感人像的用户。",
            "price_label": "¥699",
            "unknown_internal_key": "should be dropped",
        },
    )

    assert user_message.message_metadata["page_context"]["title"] == "自然光写真套餐"
    assert "unknown_internal_key" not in user_message.message_metadata["page_context"]
    assert assistant_message.message_metadata["page_context"]["resource_type"] == "package"
    page_context_prompts = [
        message["content"]
        for message in provider.messages
        if message["role"] == "system" and "当前页面上下文如下" in message["content"]
    ]
    assert page_context_prompts
    assert "自然光写真套餐" in page_context_prompts[0]
    assert "unknown_internal_key" not in page_context_prompts[0]


@pytest.mark.asyncio
async def test_project_page_application_uses_intent_without_advice_form(
    monkeypatch,
    db,
    photographer_user,
    customer_user,
):
    monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: StaticProvider())
    project = ShootProject(
        customer_id=customer_user.id,
        title="毕业照企划",
        description="毕业典礼跟拍",
        category="graduation",
        city="成都",
        status=ProjectStatus.OPEN,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    conversation = ai_service.create_conversation(db, photographer_user.id)
    page_context = {
        "resource_type": "project",
        "resource_id": str(project.id),
        "title": project.title,
    }

    _, advice = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "我想应邀这个企划，你有没有什么建议",
        page_context=page_context,
    )
    assert "agent_form_card" not in (advice.message_metadata or {})

    _, application = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "我想申请这个企划",
        page_context=page_context,
    )
    card = (application.message_metadata or {}).get("agent_form_card") or {}
    assert card["task_type"] == "project_application"
    assert card["target"]["project_id"] == str(project.id)


@pytest.mark.asyncio
async def test_switching_referenced_projects_keeps_each_turn_bound_to_its_project(
    monkeypatch,
    db,
    customer_user,
):
    provider = CapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)
    first_project = ShootProject(
        customer_id=customer_user.id,
        title="毕业日跟拍",
        description="毕业典礼纪实跟拍",
        category="graduation",
        city="成都",
        budget_max=800,
        status=ProjectStatus.OPEN,
    )
    second_project = ShootProject(
        customer_id=customer_user.id,
        title="重庆跟拍活动",
        description="重庆城市活动纪实",
        category="event",
        city="重庆",
        budget_max=1600,
        status=ProjectStatus.OPEN,
    )
    decoy_project = ShootProject(
        customer_id=customer_user.id,
        title="成都春游跟拍",
        description="亲子春游活动",
        category="family",
        city="成都",
        budget_max=1000,
        status=ProjectStatus.OPEN,
    )
    db.add_all([first_project, second_project, decoy_project])
    db.commit()

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "你觉得我如果接这一个企划，我需要做哪些准备？",
        page_context={
            "resource_type": "project",
            "resource_id": str(first_project.id),
            "title": first_project.title,
        },
    )
    second_user_message, second_assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "那这个企划呢。给我些建议。",
        page_context={
            "resource_type": "project",
            "resource_id": str(second_project.id),
            "title": decoy_project.title,
            "description": decoy_project.description,
            "city": decoy_project.city,
        },
    )

    assert second_user_message.message_metadata["page_context"]["title"] == "重庆跟拍活动"
    assert second_user_message.message_metadata["page_context"]["city"] == "重庆"
    assert second_assistant_message.message_metadata["page_context"]["resource_id"] == str(second_project.id)

    user_turns = [message["content"] for message in provider.messages if message["role"] == "user"]
    assert "标题=毕业日跟拍" in user_turns[-2]
    assert "标题=重庆跟拍活动" in user_turns[-1]
    assert "成都春游跟拍" not in user_turns[-1]
    current_context_prompts = [
        message["content"]
        for message in provider.messages
        if message["role"] == "system" and '"resource_type": "project"' in message["content"]
    ]
    assert len(current_context_prompts) == 1
    assert "重庆跟拍活动" in current_context_prompts[0]
    assert "历史消息里的其他企划上下文已经失效" in current_context_prompts[0]


@pytest.mark.asyncio
async def test_referenced_work_image_is_sent_to_vision_provider(monkeypatch, db, customer_user):
    provider = CapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "这张图的主色调是什么？",
        page_context={
            "resource_type": "portfolio_item",
            "resource_id": "work-1",
            "title": "城市黄昏",
            "current_object": {
                "media_type": "image",
                "thumbnail_url": "https://example.test/work-thumb.jpg",
            },
        },
    )

    user_message = provider.messages[-1]
    assert user_message["role"] == "user"
    assert user_message["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "https://example.test/work-thumb.jpg"},
    }
    assert all(
        not (
            message["role"] != "user"
            and isinstance(message.get("content"), list)
            and any(part.get("type") == "image_url" for part in message["content"])
        )
        for message in provider.messages
    )
    assert assistant_message.message_metadata["intent"]["intent"] == "image_analysis"
    assert assistant_message.message_metadata["vision_analysis"]["attachments"][0]["url"] == "https://example.test/work-thumb.jpg"


@pytest.mark.asyncio
async def test_provider_failure_keeps_user_message(monkeypatch, db, customer_user):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: FailingProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    with pytest.raises(HTTPException) as exc:
        await ai_service.send_ai_message(db, customer_user.id, conversation.id, "先保存这条")

    assert exc.value.status_code == 502
    messages = db.query(AIMessage).filter(AIMessage.conversation_id == conversation.id).all()
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "先保存这条"


@pytest.mark.asyncio
async def test_failed_unanswered_turn_is_not_replayed_to_provider(monkeypatch, db, customer_user):
    provider = CapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)
    db.add_all([
        AIMessage(conversation_id=conversation.id, role="user", content="平台里有没有关于光影的作品。"),
        AIMessage(conversation_id=conversation.id, role="user", content="你好。"),
    ])
    db.commit()

    await ai_service.send_ai_message(db, customer_user.id, conversation.id, "我们聊点别的")

    provider_user_messages = [
        message["content"]
        for message in provider.messages
        if message["role"] == "user"
    ]
    assert "平台里有没有关于光影的作品。" not in provider_user_messages
    assert "你好。" not in provider_user_messages
    assert provider_user_messages[-1] == "我们聊点别的"


@pytest.mark.asyncio
async def test_retrieval_observability_failure_does_not_break_portfolio_search(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    provider = RetrievalProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(
        ai_service,
        "log_retrieval_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "平台里有没有作品。",
    )

    references = assistant_message.message_metadata["references"]
    assert references["portfolio_items"]
    assert references["photographers"] == []
    assert references["packages"] == []


@pytest.mark.asyncio
async def test_send_ai_message_converts_local_image_to_data_url(monkeypatch, db, customer_user, tmp_path):
    upload_root = tmp_path / "uploads"
    image_dir = upload_root / "ai"
    image_dir.mkdir(parents=True)
    image_bytes = b"fake-image-bytes"
    (image_dir / "sample.jpg").write_bytes(image_bytes)

    provider = CapturingProvider()
    monkeypatch.setattr(ai_service.settings, "UPLOAD_DIR", str(upload_root))
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "这张照片适合什么写真风格？",
        [{"type": "image", "url": "/static/ai/sample.jpg", "mime_type": "image/jpeg"}],
    )

    user_message = provider.messages[-1]
    image_part = user_message["content"][1]
    expected = base64.b64encode(image_bytes).decode("ascii")
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"] == f"data:image/jpeg;base64,{expected}"


@pytest.mark.asyncio
async def test_image_analysis_saves_structured_vision_metadata(monkeypatch, db, customer_user):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: CapturingProvider())
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: CapturingProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "这张照片适合什么写真风格？",
        [{"type": "image", "url": "https://example.test/ref.jpg", "mime_type": "image/jpeg"}],
    )

    metadata = assistant_message.message_metadata
    vision = metadata["vision_analysis"]
    assert metadata["intent"]["intent"] == "image_analysis"
    assert vision["schema_version"] == "vision_analysis_v1"
    assert "胶片" in vision["style"]
    assert "清新" in vision["search_terms"]
    assert "视觉标签" not in assistant_message.content
    assert "references" not in metadata


@pytest.mark.asyncio
async def test_image_driven_retrieval_uses_vision_terms(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    provider = CapturingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "找类似这张图风格的摄影师",
        [{"type": "image", "url": "https://example.test/ref.jpg", "mime_type": "image/jpeg"}],
    )

    metadata = assistant_message.message_metadata
    assert metadata["intent"]["intent"] == "resource_search"
    assert metadata["intent"]["route"] == "vision_retrieval"
    assert "vision_analysis" in metadata["intent"]["sub_intents"]
    assert "胶片" in metadata["vision_search"]["search_text"]
    assert metadata["retrieval"]["criteria"]["resource_types"] == ["photographers"]
    assert "胶片" in metadata["retrieval"]["criteria"]["terms"]
    assert metadata["references"]["photographers"][0]["user_id"] == photographer_profile.user_id
    assert "匹配的摄影师" in assistant_message.content
    assert "视觉标签" not in assistant_message.content


@pytest.mark.asyncio
async def test_text_followup_reuses_latest_vision_analysis_for_retrieval(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: CapturingProvider())
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: CapturingProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "这张照片适合什么写真风格？",
        [{"type": "image", "url": "https://example.test/ref.jpg", "mime_type": "image/jpeg"}],
    )

    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我找站内类似的摄影师吧。",
    )

    metadata = assistant_message.message_metadata
    assert metadata["vision_context"]["source"] == "previous_turn"
    assert metadata["tool_calls"][0]["tool"] == "reuse_vision_analysis"
    assert "胶片" in metadata["vision_search"]["search_text"]
    assert metadata["references"]["photographers"][0]["user_id"] == photographer_profile.user_id
    assert "暂时没找到" not in assistant_message.content
    assert "视觉标签" not in assistant_message.content


@pytest.mark.asyncio
async def test_complex_booking_plan_uses_vision_and_package_retrieval(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: CapturingProvider())
    monkeypatch.setattr(ai_capability_adapters, "get_ai_provider", lambda: CapturingProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我安排一次日系写真，参考这张图，预算 1000 内",
        [{"type": "image", "url": "https://example.test/ref.jpg", "mime_type": "image/jpeg"}],
    )

    metadata = assistant_message.message_metadata
    step_statuses = {
        step["id"]: step["status"]
        for step in metadata["task_plan"]["steps"]
    }

    assert metadata["intent"]["intent"] == "booking_flow"
    assert "vision_analysis" in metadata["intent"]["sub_intents"]
    assert metadata["task_plan"]["schema_version"] == "agent_task_plan_v1"
    assert step_statuses["vision_analysis"] == "completed"
    assert step_statuses["search_packages"] == "completed"
    assert step_statuses["select_package"] == "completed"
    assert step_statuses["select_time"] == "pending"
    assert metadata["task_state"]["task_type"] == "create_booking"
    assert metadata["task_state"]["status"] == "awaiting_date"
    assert metadata["task_state"]["slots"]["photographer_id"] == photographer_profile.user_id
    assert metadata["task_state"]["slots"]["package_name"] == "个人写真"
    assert metadata["references"]["packages"][0]["package_name"] == "个人写真"
    assert metadata["tool_calls"][0]["tool"] == "analyze_image"
    assert metadata["tool_calls"][1]["tool"] == "search_packages"
    assert "你想约哪一天" in assistant_message.content
    assert "视觉标签" not in assistant_message.content
    assert "暂时没找到" not in assistant_message.content


@pytest.mark.asyncio
async def test_booking_first_turn_keeps_inline_date_slot(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: CapturingProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)
    db.add(
        AIMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="已找到摄影师和套餐",
            message_metadata={
                "references": {
                    "photographers": [
                        {
                            "user_id": photographer_profile.user_id,
                            "user_display_name": "测试摄影师",
                        }
                    ],
                    "packages": [
                        {
                            "id": "package-test-1",
                            "photographer_id": photographer_profile.user_id,
                            "package_name": "个人写真",
                            "price": 699,
                            "duration": 120,
                        }
                    ],
                }
            },
        )
    )
    db.commit()

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我预约测试摄影师的日系写真，8月19日",
    )

    metadata = assistant_message.message_metadata or {}
    assert metadata["intent"]["intent"] == "booking_flow"
    assert metadata["intent"]["slots"]["date"] == "08-19"
    assert metadata["task_state"]["slots"]["date"] == "08-19"


@pytest.mark.asyncio
async def test_complex_booking_plan_resumes_after_date(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: CapturingProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我安排一次日系写真，参考这张图，预算 1000 内",
        [{"type": "image", "url": "https://example.test/ref.jpg", "mime_type": "image/jpeg"}],
    )

    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "7月3日",
    )

    metadata = assistant_message.message_metadata
    step_statuses = {
        step["id"]: step["status"]
        for step in metadata["task_plan"]["steps"]
    }

    assert metadata["task_state"]["status"] == "awaiting_confirmation"
    assert metadata["task_state"]["pending_action"]["tool"] == "create_booking"
    assert metadata["task_state"]["slots"]["photographer_id"] == photographer_profile.user_id
    assert metadata["task_state"]["slots"]["time"] == "12:00"
    assert step_statuses["select_time"] == "completed"
    assert step_statuses["confirm_booking"] == "completed"
    assert step_statuses["create_booking"] == "pending"
    assert "请确认" in assistant_message.content
    assert "时间：12:00" in assistant_message.content
    assert "暂时没找到" not in assistant_message.content


@pytest.mark.asyncio
async def test_complex_booking_plan_confirmation_creates_order(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: CapturingProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我安排一次日系写真，参考这张图，预算 1000 内",
        [{"type": "image", "url": "https://example.test/ref.jpg", "mime_type": "image/jpeg"}],
    )
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "7月3日",
    )
    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "确认预约",
    )

    order = db.query(Order).filter_by(customer_id=customer_user.id).one()
    action_log = db.query(AgentActionLog).filter_by(
        user_id=customer_user.id,
        conversation_id=conversation.id,
        tool_name="create_booking",
    ).one()
    step_statuses = {
        step["id"]: step["status"]
        for step in assistant_message.message_metadata["task_plan"]["steps"]
    }

    assert order.photographer_id == photographer_profile.user_id
    assert order.status == OrderStatus.PENDING
    assert "个人写真" in order.package_snapshot
    assert order.appointment_time.hour == 12
    assert action_log.status == "success"
    assert assistant_message.message_metadata["tool_calls"][0]["status"] == "success"
    assert assistant_message.message_metadata["task_state"]["status"] == "completed"
    assert step_statuses["create_booking"] == "completed"
    assert "预约已创建" in assistant_message.content


@pytest.mark.asyncio
async def test_send_ai_message_attaches_retrieval_references(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    provider = RetrievalProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我推荐北京日系写真摄影师，预算 700",
    )

    references = assistant_message.message_metadata["references"]
    assert references["photographers"][0]["user_id"] == photographer_profile.user_id
    assert references["packages"] == []
    assert references["portfolio_items"] == []
    assert assistant_message.message_metadata["retrieval"]["criteria"]["budget_max"] == 700
    assert assistant_message.message_metadata["retrieval"]["criteria"]["resource_types"] == ["photographers"]
    assert any("平台数据库检索结果如下" in item["content"] for item in provider.messages)


def test_retrieve_references_filters_to_requested_resource_type(db, photographer_profile):
    photographer_retrieval = retrieve_references(db, "帮我推荐北京日系写真摄影师，预算 700")
    package_retrieval = retrieve_references(db, "帮我找北京日系写真套餐，预算 700")

    assert photographer_retrieval is not None
    photographer_refs = photographer_retrieval["references"]
    assert photographer_refs["photographers"][0]["user_id"] == photographer_profile.user_id
    assert photographer_refs["portfolio_items"] == []
    assert photographer_refs["packages"] == []

    assert package_retrieval is not None
    package_refs = package_retrieval["references"]
    assert package_refs["photographers"] == []
    assert package_refs["portfolio_items"] == []
    assert package_refs["packages"][0]["package_name"] == "个人写真"


def test_orchestrator_recognizes_photographer_search_intent():
    intent = recognize_intent("站内有没有日系摄影师")

    assert intent.intent == "resource_search"
    assert intent.sub_intents == ["search_photographer"]
    assert intent.slots["resource_types"] == ["photographers"]
    assert intent.slots["style"] == "日系"


def test_named_photographer_package_query_returns_one_target_package(db, photographer_profile):
    photographer_profile.user.display_name = "测试摄影师1"
    photographer_profile.packages = [
        {
            "name": "日系写真含妆造",
            "price": 999,
            "duration": 120,
            "description": "包含基础化妆和日系自然光写真",
            "includes": ["基础化妆", "精修30张"],
            "styles": ["日系", "化妆"],
            "image_count": 30,
        },
        {
            "name": "日系写真简拍",
            "price": 699,
            "duration": 90,
            "description": "轻量拍摄",
            "includes": ["精修20张"],
            "styles": ["日系"],
            "image_count": 20,
        },
    ]
    other_user = User(
        email="other-photographer@test.com",
        hashed_password="$2b$12$dummyhash",
        display_name="不相干摄影师",
        role="photographer",
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)
    db.add(PhotographerProfile(
        user_id=other_user.id,
        location="北京",
        styles=["日系"],
        packages=[
            {
                "name": "别人家的化妆套餐",
                "price": 299,
                "duration": 60,
                "description": "包含化妆",
                "includes": ["化妆"],
                "styles": ["日系", "化妆"],
                "image_count": 10,
            }
        ],
    ))
    db.commit()

    retrieval = retrieve_references(
        db,
        "测试摄影师1有哪些套餐？你能推荐一个不。有没有带化妆的方案。",
    )

    references = retrieval["references"]
    assert references["photographers"] == []
    assert references["portfolio_items"] == []
    assert len(references["packages"]) == 1
    assert references["packages"][0]["package_name"] == "日系写真含妆造"
    assert references["packages"][0]["photographer_id"] == photographer_profile.user_id
    assert retrieval["criteria"]["owner_display_name"] == "测试摄影师1"
    assert retrieval["criteria"]["resource_types"] == ["packages"]


def test_orchestrator_recognizes_named_package_single_result_intent():
    intent = recognize_intent("测试摄影师1有哪些套餐，推荐一个带化妆的")

    assert intent.intent == "resource_search"
    assert intent.sub_intents == ["search_package"]
    assert intent.slots["resource_types"] == ["packages"]
    assert intent.slots["limit"] == 1
    assert intent.slots["requires_makeup"] is True
    assert intent.slots["photographer_name"] == "测试摄影师1"


@pytest.mark.parametrize(
    "content",
    (
        "为我找一份类似风格的作品",
        "推荐一张照片",
        "找一组样片",
        "给我1份案例",
    ),
)
def test_orchestrator_writes_resource_measure_word_to_single_result_slot(content):
    intent = recognize_intent(content)

    assert intent.intent == "resource_search"
    assert intent.slots["resource_types"] == ["portfolio_items"]
    assert intent.slots["limit"] == 1


def test_retrieve_references_accepts_orchestrator_resource_type(db, photographer_profile):
    retrieval = retrieve_references(db, "我想预约日系写真", resource_types=["packages"])

    assert retrieval["criteria"]["resource_types"] == ["packages"]
    assert retrieval["references"]["photographers"] == []
    assert retrieval["references"]["portfolio_items"] == []
    assert retrieval["references"]["packages"][0]["package_name"] == "个人写真"


def test_retrieve_references_filters_packages_by_city_budget_style_and_makeup(db, photographer_profile):
    photographer_profile.packages = [
        {
            "name": "北京日系含妆写真",
            "price": 899,
            "duration": 120,
            "description": "北京自然光日系写真，包含妆造",
            "includes": ["妆造", "精修30张"],
            "styles": ["日系", "自然光"],
            "image_count": 30,
        },
        {
            "name": "北京日系高价写真",
            "price": 1800,
            "duration": 120,
            "description": "北京自然光日系写真，包含妆造",
            "includes": ["妆造", "精修30张"],
            "styles": ["日系", "自然光"],
            "image_count": 30,
        },
        {
            "name": "北京复古含妆写真",
            "price": 799,
            "duration": 120,
            "description": "北京复古写真，包含妆造",
            "includes": ["妆造", "精修30张"],
            "styles": ["复古"],
            "image_count": 30,
        },
        {
            "name": "北京日系无妆写真",
            "price": 699,
            "duration": 90,
            "description": "北京日系写真，不含化妆",
            "includes": ["精修20张"],
            "styles": ["日系"],
            "image_count": 20,
        },
    ]
    shanghai_user = User(
        email="shanghai-photographer@test.com",
        hashed_password="$2b$12$dummyhash",
        display_name="上海摄影师",
        role="photographer",
    )
    db.add(shanghai_user)
    db.commit()
    db.refresh(shanghai_user)
    db.add(PhotographerProfile(
        user_id=shanghai_user.id,
        location="上海",
        styles=["日系"],
        packages=[
            {
                "name": "上海日系含妆写真",
                "price": 799,
                "duration": 120,
                "description": "上海日系写真，包含妆造",
                "includes": ["妆造", "精修30张"],
                "styles": ["日系"],
                "image_count": 30,
            }
        ],
    ))
    db.commit()

    retrieval = retrieve_references(db, "帮我找北京 1000 内日系带妆造套餐")
    packages = retrieval["references"]["packages"]

    assert [item["package_name"] for item in packages] == ["北京日系含妆写真"]
    assert retrieval["criteria"]["city"] == "北京"
    assert retrieval["criteria"]["budget_max"] == 1000
    assert retrieval["criteria"]["style_terms"] == ["日系"]
    assert retrieval["criteria"]["requires_makeup"] is True
    assert "妆造" in retrieval["criteria"]["package_includes"]


def test_retrieve_references_applies_single_limit_to_photographers(db, photographer_profile):
    other_user = User(
        email="second-photographer@test.com",
        hashed_password="$2b$12$dummyhash",
        display_name="第二位日系摄影师",
        role="photographer",
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)
    db.add(PhotographerProfile(
        user_id=other_user.id,
        location="北京",
        styles=["日系", "人像"],
        packages=[
            {
                "name": "日系写真",
                "price": 699,
                "duration": 120,
                "description": "日系写真",
                "includes": ["精修30张"],
                "styles": ["日系"],
                "image_count": 30,
            }
        ],
    ))
    db.commit()

    intent = recognize_intent("推荐一位北京日系摄影师")
    retrieval = retrieve_references(db, "推荐一位北京日系摄影师")

    assert intent.slots["limit"] == 1
    assert retrieval["criteria"]["limit"] == 1
    assert retrieval["criteria"]["resource_types"] == ["photographers"]
    assert len(retrieval["references"]["photographers"]) == 1
    assert retrieval["references"]["packages"] == []


@pytest.mark.asyncio
async def test_recommendation_count_correction_does_not_run_empty_retrieval_fallback(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "我只要一位，你推荐了两位。",
    )

    assert "暂时没找到" not in assistant_message.content
    assert "应该只推荐一位" in assistant_message.content
    assert assistant_message.message_metadata["model"]["model"] == "recommendation-count-correction"


@pytest.mark.asyncio
async def test_follow_intent_selects_second_photographer_from_previous_references(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    photographer_profile.user.display_name = "测试摄影师1"
    second_user = User(
        email="second-follow-photographer@test.com",
        hashed_password="$2b$12$dummyhash",
        display_name="测试摄影师2",
        bio="擅长日系人像和自然光写真。",
        role="photographer",
    )
    db.add(second_user)
    db.commit()
    db.refresh(second_user)
    db.add(PhotographerProfile(
        user_id=second_user.id,
        location="北京",
        styles=["日系", "人像"],
        packages=[
            {
                "name": "日系写真",
                "price": 699,
                "duration": 120,
                "description": "日系自然光写真",
                "includes": ["精修30张"],
                "styles": ["日系"],
                "image_count": 30,
            }
        ],
    ))
    db.commit()

    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: RetrievalProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, recommendation_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "站内有没有日系摄影师",
    )
    photographers = recommendation_message.message_metadata["references"]["photographers"]
    assert len(photographers) >= 2

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我关注第二个摄影师",
    )

    expected_target = photographers[1]
    metadata = assistant_message.message_metadata
    assert metadata["task_state"]["slots"]["photographer_id"] == expected_target["user_id"]
    assert metadata["suggested_actions"][0]["payload"]["photographer_id"] == expected_target["user_id"]

    _, named_assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "我要关注测试摄影师2",
    )

    named_metadata = named_assistant_message.message_metadata
    assert named_metadata["task_state"]["slots"]["photographer_id"] == second_user.id
    assert named_metadata["suggested_actions"][0]["payload"]["photographer_id"] == second_user.id


@pytest.mark.asyncio
async def test_follow_intent_requires_confirmation_from_previous_reference(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    provider = RetrievalProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "站内有没有日系摄影师",
    )

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我关注这个摄影师",
    )

    metadata = assistant_message.message_metadata
    assert metadata["intent"]["intent"] == "follow_photographer"
    assert metadata["intent"]["requires_confirmation"] is True
    assert metadata["task_state"]["status"] == "awaiting_confirmation"
    assert metadata["task_state"]["pending_action"]["tool"] == "follow_photographer"
    assert metadata["task_state"]["slots"]["photographer_id"] == photographer_profile.user_id
    assert metadata["suggested_actions"][0]["type"] == "confirm_follow_photographer"
    assert "请确认" in assistant_message.content


@pytest.mark.asyncio
async def test_confirm_follow_intent_executes_tool_and_logs_action(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    provider = RetrievalProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "站内有没有日系摄影师",
    )
    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "关注第一个",
    )
    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "确认关注",
    )

    follow = db.query(Follow).filter_by(
        follower_id=customer_user.id,
        following_id=photographer_profile.user_id,
    ).first()
    action_log = db.query(AgentActionLog).filter_by(
        user_id=customer_user.id,
        conversation_id=conversation.id,
        tool_name="follow_photographer",
    ).one()

    assert follow is not None
    assert action_log.status == "success"
    assert action_log.tool_input == {"photographer_id": photographer_profile.user_id}
    assert action_log.tool_result["followed"] is True
    assert assistant_message.message_metadata["tool_calls"][0]["status"] == "success"
    assert assistant_message.message_metadata["task_state"]["status"] == "completed"
    assert assistant_message.message_metadata["task_state"]["pending_action"] is None
    assert "已帮你关注" in assistant_message.content


@pytest.mark.asyncio
async def test_confirm_follow_is_idempotent_when_already_following(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: RetrievalProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)
    db.add(Follow(follower_id=customer_user.id, following_id=photographer_profile.user_id))
    db.commit()

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "站内有没有日系摄影师",
    )
    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我关注这个摄影师",
    )
    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "可以",
    )

    follows = db.query(Follow).filter_by(
        follower_id=customer_user.id,
        following_id=photographer_profile.user_id,
    ).all()

    assert len(follows) == 1
    assert assistant_message.message_metadata["tool_calls"][0]["result"]["followed"] is True
    assert assistant_message.message_metadata["tool_calls"][0]["result"]["created"] is False


@pytest.mark.asyncio
async def test_project_agent_generates_draft_and_asks_for_missing_slots(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "我想发一个北京日系写真企划，预算 800",
    )

    metadata = assistant_message.message_metadata
    assert metadata["intent"]["intent"] == "project_flow"
    assert metadata["project_draft"]["schema_version"] == "project_draft_v1"
    assert metadata["project_draft"]["project_payload"]["city"] == "北京"
    assert metadata["project_draft"]["project_payload"]["budget_max"] == 800
    assert metadata["task_state"]["status"] == "awaiting_details"
    assert set(metadata["task_state"]["missing_slots"]) == {"date", "people_count", "description"}
    assert metadata["suggested_actions"] == []


@pytest.mark.asyncio
async def test_project_agent_empty_publish_request_keeps_title_pending(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我发布个企划。",
    )

    metadata = assistant_message.message_metadata
    assert metadata["intent"]["intent"] == "project_flow"
    assert metadata["project_draft"]["project_payload"]["title"] == "待补充"
    assert assistant_message.content == "请直接在企划进度卡片中补充信息。"
    assert "标题：" not in assistant_message.content


@pytest.mark.asyncio
async def test_project_agent_structured_details_asks_for_reference_images_before_publish(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "城市，成都。\n"
        "地点：西南石油大学\n"
        "预算500\n"
        "时间2026年7月15日\n"
        "人数10000\n"
        "需求，为学校的毕业典礼拍摄记录形式的照片，用于新闻发布\n"
        "交付要求：交付30张以上的精修图，以及短视频",
    )

    metadata = assistant_message.message_metadata
    payload = metadata["project_draft"]["project_payload"]
    assert metadata["intent"]["intent"] == "project_flow"
    assert metadata["task_state"]["status"] == "awaiting_reference_images"
    assert metadata["task_state"]["pending_action"] is None
    assert [action["type"] for action in metadata["suggested_actions"]] == [
        "add_project_reference_images",
        "skip_project_reference_images",
    ]
    assert payload["city"] == "成都"
    assert payload["location_text"] == "西南石油大学"
    assert payload["budget_max"] == 500
    assert payload["description"] == "为学校的毕业典礼拍摄记录形式的照片，用于新闻发布"
    assert payload["deliverables"] == "交付30张以上的精修图，以及短视频"
    assert metadata["task_state"]["slots"]["people_count"] == 10000
    assert "进度卡片中添加参考图" in assistant_message.content
    assert db.query(ShootProject).filter_by(customer_id=customer_user.id).count() == 0


def test_orchestrator_extracts_fuzzy_project_slots_from_natural_language():
    intent = recognize_intent(
        "小龟J，帮我发布一个企划，我六月三十号想在西南石油大学拍毕业照，室内教室类型的，预算八百块钱。"
    )

    assert intent.intent == "project_flow"
    assert intent.slots["budget_max"] == 800
    assert intent.slots["date"] == "06-30"
    assert intent.slots["location_text"] == "西南石油大学"
    assert {"毕业照", "室内", "教室"}.issubset(set(intent.slots["style"]))
    assert set(intent.missing_slots) == {"city", "people_count", "description"}


def test_orchestrator_prefills_project_card_from_first_publish_request():
    intent = recognize_intent(
        "帮我发布一个校园毕业照企划，城市成都，地点西南石油大学，"
        "预算1000元，日期2026年8月20日，人数6人，"
        "需求是拍一组自然纪实的毕业纪念照片。"
    )

    assert intent.intent == "project_flow"
    assert intent.slots["title"] == "校园毕业照企划"
    assert intent.slots["city"] == "成都"
    assert intent.slots["location_text"] == "西南石油大学"
    assert intent.slots["budget_max"] == 1000
    assert intent.slots["date"] == "08-20"
    assert intent.slots["people_count"] == 6
    assert intent.slots["description"] == "拍一组自然纪实的毕业纪念照片。"


def test_orchestrator_does_not_extract_budget_from_date_time_only():
    intent = recognize_intent("6月30日15点，5人")

    assert intent.slots["date"] == "06-30"
    assert intent.slots["time"] == "15:00"
    assert intent.slots["people_count"] == 5
    assert "budget_max" not in intent.slots


def test_orchestrator_extracts_labeled_project_followup_slots():
    people_intent = recognize_intent("拍摄人数100人")
    style_intent = recognize_intent("拍摄风格：纪实")
    description_intent = recognize_intent("需求描述：记录活动现场、领导讲话和大合影")
    deliverables_intent = recognize_intent("交付要求：精修30张，底片全送")

    assert people_intent.slots["people_count"] == 100
    assert "budget_max" not in people_intent.slots
    assert style_intent.slots["style"] == "纪实"
    assert description_intent.slots["description"] == "记录活动现场、领导讲话和大合影"
    assert deliverables_intent.slots["deliverables"] == "精修30张，底片全送"


def test_orchestrator_routes_structured_project_details_to_project_flow():
    intent = recognize_intent(
        "城市，成都。\n"
        "地点：西南石油大学\n"
        "预算500\n"
        "时间2026年7月15日\n"
        "人数10000\n"
        "需求，为学校的毕业典礼拍摄记录形式的照片，用于新闻发布\n"
        "交付要求：交付30张以上的精修图，以及短视频"
    )

    assert intent.intent == "project_flow"
    assert intent.sub_intents == ["create_project"]
    assert intent.slots["city"] == "成都"
    assert intent.slots["location_text"] == "西南石油大学"
    assert intent.slots["budget_max"] == 500
    assert intent.slots["date"] == "07-15"
    assert intent.slots["people_count"] == 10000
    assert intent.slots["description"] == "为学校的毕业典礼拍摄记录形式的照片，用于新闻发布"
    assert intent.slots["deliverables"] == "交付30张以上的精修图，以及短视频"
    assert intent.missing_slots == []


def test_orchestrator_recognizes_package_publish_intent():
    intent = recognize_intent("帮我发布一个北京日系写真方案，价格699元，时长120分钟，精修30张，底片全送")

    assert intent.intent == "package_publish_flow"
    assert intent.sub_intents == ["publish_package"]
    assert intent.slots["package_name"] == "北京日系写真"
    assert intent.slots["budget_max"] == 699
    assert intent.slots["duration_minutes"] == 120
    assert intent.slots["image_count"] == 30
    assert "底片全送" in intent.slots["package_includes"]
    assert intent.missing_slots == ["package_description"]


def test_orchestrator_extracts_labeled_package_name_and_ignores_generic_city():
    intent = recognize_intent(
        "帮我新增一个方案。名称，单人日系胶片写真。城市不限，风格日系胶片。价格1000以下，"
        "时长不定，精修20张，包含：二十张精修，价格需要根据实际的城市、天气、时间等上下调整。"
    )

    assert intent.intent == "package_publish_flow"
    assert intent.slots["package_name"] == "单人日系胶片写真"
    assert "city" not in intent.slots
    assert intent.slots["budget_max"] == 1000
    assert intent.slots["image_count"] == 20
    assert "日系" in intent.slots["style"]
    assert "胶片" in intent.slots["style"]
    assert set(intent.missing_slots) == {"duration_minutes", "package_description"}


def test_orchestrator_extracts_chinese_price_after_price_keyword():
    intent = recognize_intent("价格五百。")

    assert intent.slots["budget_max"] == 500


@pytest.mark.asyncio
async def test_project_agent_collects_fuzzy_details_across_turns(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, draft_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "小龟J，帮我发布一个企划，我六月三十号想在西南石油大学拍毕业照，室内教室类型的，预算八百块钱。",
    )

    draft_metadata = draft_message.message_metadata
    assert draft_metadata["task_state"]["status"] == "awaiting_details"
    assert draft_metadata["project_draft"]["project_payload"]["location_text"] == "西南石油大学"
    assert draft_metadata["project_draft"]["project_payload"]["budget_max"] == 800
    assert set(draft_metadata["task_state"]["missing_slots"]) == {"city", "people_count", "description"}
    assert draft_message.content == "请直接在企划进度卡片中补充信息。"

    _, details_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "在成都，风格就是日系一些，预算八百，六月三十号，我和我室友六个人",
    )

    details_metadata = details_message.message_metadata
    assert details_metadata["task_state"]["status"] == "awaiting_details"
    assert details_metadata["task_state"]["missing_slots"] == ["description"]
    assert details_metadata["project_draft"]["project_payload"]["description"] == "待补充"

    _, reference_prompt_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "想拍一组毕业纪念照，主要记录室友互动、校园环境和正式合影。",
    )

    reference_prompt_metadata = reference_prompt_message.message_metadata
    payload = reference_prompt_metadata["project_draft"]["project_payload"]
    assert reference_prompt_metadata["task_state"]["status"] == "awaiting_reference_images"
    assert payload["city"] == "成都"
    assert payload["location_text"] == "西南石油大学"
    assert payload["budget_max"] == 800
    assert reference_prompt_metadata["task_state"]["slots"]["people_count"] == 6
    assert payload["description"] == "想拍一组毕业纪念照，主要记录室友互动、校园环境和正式合影。"
    assert payload["deliverables"] is None
    assert "日系" in payload["style_tags"]
    assert "毕业照" in payload["style_tags"]
    assert "-06-30T10:00:00" in payload["shoot_date_start"]
    assert reference_prompt_metadata["task_state"]["pending_action"] is None
    assert [action["type"] for action in reference_prompt_metadata["suggested_actions"]] == [
        "add_project_reference_images",
        "skip_project_reference_images",
    ]


@pytest.mark.asyncio
async def test_project_agent_understands_labeled_people_and_style_followups(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, draft_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我发布一个企划，我想在成都万象城拍摄，预算500，7月15日",
    )
    draft_metadata = draft_message.message_metadata
    assert set(draft_metadata["task_state"]["missing_slots"]) == {"style", "people_count", "description"}

    _, people_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "拍摄人数100人",
    )
    people_metadata = people_message.message_metadata
    assert people_metadata["task_state"]["slots"]["people_count"] == 100
    assert people_metadata["task_state"]["missing_slots"] == ["style", "description"]

    _, style_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "拍摄风格：纪实",
    )
    style_metadata = style_message.message_metadata
    assert style_metadata["task_state"]["missing_slots"] == ["description"]

    _, deliverables_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "交付要求：精修30张，底片全送",
    )
    deliverables_metadata = deliverables_message.message_metadata
    assert deliverables_metadata["task_state"]["status"] == "awaiting_details"
    assert deliverables_metadata["task_state"]["missing_slots"] == ["description"]
    assert deliverables_metadata["task_state"]["slots"]["deliverables"] == "精修30张，底片全送"
    assert deliverables_metadata["project_draft"]["project_payload"]["description"] == "待补充"

    _, reference_prompt_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "需求描述：公司活动跟拍，需要记录签到、舞台发言、观众互动和最后的大合影。",
    )
    reference_prompt_metadata = reference_prompt_message.message_metadata
    payload = reference_prompt_metadata["project_draft"]["project_payload"]

    assert reference_prompt_metadata["task_state"]["status"] == "awaiting_reference_images"
    assert reference_prompt_metadata["task_state"]["slots"]["people_count"] == 100
    assert payload["description"] == "公司活动跟拍，需要记录签到、舞台发言、观众互动和最后的大合影。"
    assert payload["deliverables"] == "精修30张，底片全送"
    assert "纪实" in payload["style_tags"]
    assert reference_prompt_metadata["suggested_actions"][0]["type"] == "add_project_reference_images"


@pytest.mark.asyncio
async def test_project_agent_updates_draft_and_can_cancel_flow(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我发布一个北京日系写真企划，预算800，12月20日上午10点，1人，需求描述：需要拍一组头像。",
    )
    _, confirmation_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "跳过参考图",
    )
    assert confirmation_message.message_metadata["task_state"]["status"] == "awaiting_confirmation"

    _, update_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "把标题改成成都活动跟拍，城市改成成都，预算改成1000，风格改为纪实，交付要求改成精修20张，底片全送",
    )

    update_metadata = update_message.message_metadata
    payload = update_metadata["project_draft"]["project_payload"]
    assert update_metadata["task_state"]["status"] == "awaiting_confirmation"
    assert payload["title"] == "成都活动跟拍"
    assert payload["city"] == "成都"
    assert payload["budget_max"] == 1000
    assert payload["style_tags"] == ["纪实"]
    assert payload["deliverables"] == "精修20张，底片全送"
    assert update_metadata["task_state"]["slots"]["reference_images_skipped"] is True
    assert update_metadata["suggested_actions"][0]["type"] == "confirm_create_project"

    _, cancel_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "取消",
    )

    cancel_metadata = cancel_message.message_metadata
    assert cancel_metadata["task_state"]["status"] == "cancelled"
    assert cancel_metadata["task_state"]["pending_action"] is None
    assert "普通聊天状态" in cancel_message.content
    assert db.query(ShootProject).filter_by(customer_id=customer_user.id).count() == 0


@pytest.mark.asyncio
async def test_project_agent_confirms_then_creates_project_and_logs_action(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "我想发一个北京日系写真企划，预算 800",
    )
    _, description_prompt_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "12月20日上午10点，1人",
    )

    description_prompt_metadata = description_prompt_message.message_metadata
    assert description_prompt_metadata["task_state"]["status"] == "awaiting_details"
    assert description_prompt_metadata["task_state"]["missing_slots"] == ["description"]

    _, reference_prompt_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "需要拍一组个人纪念写真，偏自然、有生活感，可以用于社交头像。",
    )

    reference_prompt_metadata = reference_prompt_message.message_metadata
    assert reference_prompt_metadata["task_state"]["status"] == "awaiting_reference_images"
    assert reference_prompt_metadata["suggested_actions"][0]["type"] == "add_project_reference_images"
    assert reference_prompt_metadata["suggested_actions"][1]["type"] == "skip_project_reference_images"

    _, confirmation_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "跳过参考图",
    )

    confirmation_metadata = confirmation_message.message_metadata
    assert confirmation_metadata["task_state"]["status"] == "awaiting_confirmation"
    assert confirmation_metadata["task_state"]["pending_action"]["tool"] == "create_project"
    assert confirmation_metadata["suggested_actions"][0]["type"] == "confirm_create_project"

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "确认发布企划",
    )

    project = db.query(ShootProject).filter_by(customer_id=customer_user.id).one()
    action_log = db.query(AgentActionLog).filter_by(
        user_id=customer_user.id,
        conversation_id=conversation.id,
        tool_name="create_project",
    ).one()

    assert project.status == ProjectStatus.OPEN
    assert project.city == "北京"
    assert project.budget_max == 800
    assert project.description == "需要拍一组个人纪念写真，偏自然、有生活感，可以用于社交头像。"
    assert project.deliverables is None
    assert action_log.status == "success"
    assert action_log.tool_input["publish"] is True
    assert action_log.tool_result["created"] is True
    assert action_log.tool_result["project_id"] == project.id
    assert assistant_message.message_metadata["tool_calls"][0]["status"] == "success"
    assert assistant_message.message_metadata["task_state"]["status"] == "completed"
    assert assistant_message.message_metadata["task_state"]["pending_action"] is None


@pytest.mark.asyncio
async def test_project_agent_publishes_directly_from_completed_progress_card(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我发布个企划。",
    )

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "标题：北京日系个人写真\n"
        "城市：北京\n"
        "地点：朝阳公园\n"
        "风格：日系、胶片\n"
        "预算：800元\n"
        "日期：2026年7月20日\n"
        "交付要求：精修12张，一周内交付\n"
        "需求描述：清新自然的双人纪念写真\n"
        "人数：2人\n"
        "不添加参考图。\n"
        "确认发布企划。",
        task_submission={
            "task_type": "create_project",
            "action": "publish",
            "slots": {
                "title": "北京日系个人写真",
                "city": "北京",
                "location_text": "朝阳公园",
                "location_name": "朝阳公园",
                "location_address": "北京市朝阳区朝阳公园南路1号",
                "location_latitude": 39.933,
                "location_longitude": 116.478,
                "location_place_id": "osm-123",
                "location_provider": "nominatim",
                "coordinate_system": "WGS84",
                "location_precision": "exact",
                "style": "日系、胶片",
                "budget_max": "800",
                "date": "2099-07-20",
                "time": "14:30",
                "people_count": "2",
                "description": "清新自然的双人纪念写真",
                "deliverables": "精修12张，一周内交付",
            },
            "skip_reference_images": True,
        },
    )

    projects = db.query(ShootProject).filter_by(customer_id=customer_user.id).all()
    assert len(projects) == 1
    assert projects[0].title == "北京日系个人写真"
    assert projects[0].city == "北京"
    assert projects[0].budget_max == 800
    assert projects[0].location_name == "朝阳公园"
    assert float(projects[0].location_latitude) == pytest.approx(39.933)
    assert projects[0].shoot_date_start.isoformat() == "2099-07-20T14:30:00"
    assert assistant_message.message_metadata["model"]["model"] == "create-project"
    assert assistant_message.message_metadata["task_state"]["status"] == "completed"
    assert assistant_message.message_metadata["task_state"]["pending_action"] is None


@pytest.mark.asyncio
async def test_project_agent_saves_incomplete_card_as_draft(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "保存为草稿",
        task_submission={
            "task_type": "create_project",
            "action": "save_draft",
            "slots": {
                "title": "校园毕业照企划",
                "style": "毕业照、纪实",
            },
            "skip_reference_images": True,
        },
    )

    project = db.query(ShootProject).filter_by(customer_id=customer_user.id).one()
    action_log = db.query(AgentActionLog).filter_by(
        user_id=customer_user.id,
        conversation_id=conversation.id,
        tool_name="create_project",
    ).one()

    assert project.status == ProjectStatus.DRAFT
    assert project.title == "校园毕业照企划"
    assert project.city == "待补充"
    assert action_log.tool_input["publish"] is False
    assert assistant_message.message_metadata["task_state"]["status"] == "completed"
    assert "草稿已保存" in assistant_message.content


@pytest.mark.asyncio
async def test_package_agent_publishes_directly_from_completed_editor_card(
    monkeypatch,
    db,
    photographer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, photographer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "发布方案",
        task_submission={
            "task_type": "publish_package",
            "action": "publish",
            "slots": {
                "package_name": "城市漫步胶片写真",
                "city": "香港",
                "style": ["胶片", "街拍", "自然光"],
                "price": "1280",
                "duration_minutes": "150",
                "image_count": "24",
                "package_includes": ["底片全送", "两套造型", "线上选片"],
                "package_description": "适合情侣或个人的城市漫步写真，强调自然互动与电影感。",
                "sample_images": ["/static/ai/package-sample.jpg"],
            },
            "skip_reference_images": False,
        },
    )

    profile = db.query(PhotographerProfile).filter_by(user_id=photographer_user.id).one()
    package = profile.packages[-1]
    action_log = db.query(AgentActionLog).filter_by(
        user_id=photographer_user.id,
        conversation_id=conversation.id,
        tool_name="publish_package",
    ).one()

    assert package["name"] == "城市漫步胶片写真"
    assert package["city"] == "香港"
    assert package["styles"] == ["胶片", "街拍", "自然光"]
    assert package["price"] == 1280
    assert package["duration"] == 150
    assert package["image_count"] == 24
    assert "底片全送" in package["includes"]
    assert package["samples"] == ["/static/ai/package-sample.jpg"]
    assert action_log.status == "success"
    assert assistant_message.message_metadata["model"]["model"] == "publish-package"
    assert assistant_message.message_metadata["task_state"]["status"] == "completed"


@pytest.mark.asyncio
async def test_project_agent_uses_chat_image_as_reference_image(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)
    image_url = "/static/ai/project-ref.jpg"

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "我想发一个北京日系写真企划，预算 800",
    )
    _, description_prompt_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "12月20日上午10点，1人",
        [{"type": "image", "url": image_url, "mime_type": "image/jpeg"}],
    )

    description_prompt_metadata = description_prompt_message.message_metadata
    assert description_prompt_metadata["task_state"]["status"] == "awaiting_details"
    assert description_prompt_metadata["task_state"]["missing_slots"] == ["description"]
    assert description_prompt_metadata["project_draft"]["project_payload"]["reference_images"] == [image_url]

    _, confirmation_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "需求描述：拍一组单人写真，需要自然表情和半身头像。",
    )

    confirmation_metadata = confirmation_message.message_metadata
    payload = confirmation_metadata["project_draft"]["project_payload"]
    assert confirmation_metadata["task_state"]["status"] == "awaiting_confirmation"
    assert payload["reference_images"] == [image_url]
    assert payload["description"] == "拍一组单人写真，需要自然表情和半身头像。"
    assert confirmation_metadata["task_state"]["pending_action"]["input"]["reference_images"] == [image_url]

    await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "确认发布企划",
    )

    project = db.query(ShootProject).filter_by(customer_id=customer_user.id).one()
    assert project.reference_images == [image_url]
    assert project.description == "拍一组单人写真，需要自然表情和半身头像。"


@pytest.mark.asyncio
async def test_package_agent_generates_draft_and_asks_for_missing_slots(
    monkeypatch,
    db,
    photographer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, photographer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "帮我发布一个日系写真方案，价格699元",
    )

    metadata = assistant_message.message_metadata
    assert metadata["intent"]["intent"] == "package_publish_flow"
    assert metadata["package_draft"]["schema_version"] == "package_draft_v1"
    assert metadata["package_draft"]["package_payload"]["name"] == "日系写真方案"
    assert metadata["package_draft"]["package_payload"]["price"] == 699
    assert metadata["package_draft"]["package_payload"]["description"] == "待补充"
    assert metadata["task_state"]["status"] == "awaiting_details"
    assert set(metadata["task_state"]["missing_slots"]) == {
        "duration_minutes",
        "image_count",
        "package_description",
    }
    assert metadata["suggested_actions"] == []


@pytest.mark.asyncio
async def test_package_agent_turns_price_followup_into_confirmation_button(
    monkeypatch,
    db,
    photographer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, photographer_user.id)

    await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "帮我发布一个毕业照单人方案，风格日系胶片，时长120分钟，精修20张",
    )
    _, assistant_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "价格五百。",
    )

    metadata = assistant_message.message_metadata
    payload = metadata["package_draft"]["package_payload"]
    assert metadata["intent"]["intent"] == "package_publish_flow"
    assert metadata["task_state"]["status"] == "awaiting_details"
    assert metadata["task_state"]["missing_slots"] == ["package_description"]
    assert payload["price"] == 500

    _, reference_prompt_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "简介：适合毕业季单人写真，偏自然、干净、有胶片氛围。",
    )

    reference_prompt_metadata = reference_prompt_message.message_metadata
    reference_payload = reference_prompt_metadata["package_draft"]["package_payload"]
    assert reference_prompt_metadata["task_state"]["status"] == "awaiting_reference_images"
    assert reference_payload["description"] == "适合毕业季单人写真，偏自然、干净、有胶片氛围。"
    assert reference_prompt_metadata["suggested_actions"][0]["type"] == "add_package_reference_images"
    assert reference_prompt_metadata["suggested_actions"][1]["type"] == "skip_package_reference_images"


@pytest.mark.asyncio
async def test_package_agent_uses_chat_image_as_package_sample_across_turns(
    monkeypatch,
    db,
    photographer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, photographer_user.id)
    image_url = "/static/ai/package-sample.jpg"

    await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "帮我发布一个毕业照单人方案，风格日系胶片，时长120分钟，精修20张",
    )
    _, image_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        None,
        [{"type": "image", "url": image_url, "mime_type": "image/jpeg"}],
    )

    image_metadata = image_message.message_metadata
    assert image_metadata["intent"]["intent"] == "package_publish_flow"
    assert image_metadata["task_state"]["status"] == "awaiting_details"
    assert image_metadata["task_state"]["slots"]["sample_images"] == [image_url]
    assert image_metadata["package_draft"]["package_payload"]["samples"] == [image_url]

    _, confirmation_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "价格五百。",
    )

    confirmation_metadata = confirmation_message.message_metadata
    payload = confirmation_metadata["package_draft"]["package_payload"]
    assert confirmation_metadata["task_state"]["status"] == "awaiting_details"
    assert confirmation_metadata["task_state"]["missing_slots"] == ["package_description"]
    assert payload["price"] == 500
    assert payload["samples"] == [image_url]

    _, confirmation_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "简介：适合毕业季拍摄，画面自然，有胶片质感。",
    )

    confirmation_metadata = confirmation_message.message_metadata
    payload = confirmation_metadata["package_draft"]["package_payload"]
    assert confirmation_metadata["task_state"]["status"] == "awaiting_confirmation"
    assert payload["description"] == "适合毕业季拍摄，画面自然，有胶片质感。"
    assert payload["samples"] == [image_url]
    assert confirmation_metadata["task_state"]["pending_action"]["input"]["samples"] == [image_url]

    await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "确认发布方案",
    )

    profile = db.query(PhotographerProfile).filter_by(user_id=photographer_user.id).one()
    package = profile.packages[0]
    assert package["samples"] == [image_url]
    assert "sample_thumbnails" in package


@pytest.mark.asyncio
async def test_package_agent_collects_details_then_publishes_and_logs_action(
    monkeypatch,
    db,
    photographer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, photographer_user.id)

    await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "帮我发布一个北京日系写真方案，价格699元，底片全送",
    )
    _, confirmation_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "时长120分钟，精修30张",
    )

    confirmation_metadata = confirmation_message.message_metadata
    assert confirmation_metadata["task_state"]["status"] == "awaiting_details"
    assert confirmation_metadata["task_state"]["missing_slots"] == ["package_description"]
    assert "底片全送" in confirmation_metadata["package_draft"]["package_payload"]["includes"]

    _, reference_prompt_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "简介：适合北京日系写真，包含轻松自然的人像拍摄。",
    )

    reference_prompt_metadata = reference_prompt_message.message_metadata
    assert reference_prompt_metadata["task_state"]["status"] == "awaiting_reference_images"
    assert reference_prompt_metadata["suggested_actions"][0]["type"] == "add_package_reference_images"

    _, confirmation_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "跳过参考图",
    )

    confirmation_metadata = confirmation_message.message_metadata
    assert confirmation_metadata["task_state"]["status"] == "awaiting_confirmation"
    assert confirmation_metadata["task_state"]["pending_action"]["tool"] == "publish_package"
    assert confirmation_metadata["suggested_actions"][0]["type"] == "confirm_publish_package"

    _, assistant_message = await ai_service.send_ai_message(
        db,
        photographer_user.id,
        conversation.id,
        "确认发布方案",
    )

    profile = db.query(PhotographerProfile).filter_by(user_id=photographer_user.id).one()
    package = profile.packages[0]
    action_log = db.query(AgentActionLog).filter_by(
        user_id=photographer_user.id,
        conversation_id=conversation.id,
        tool_name="publish_package",
    ).one()

    assert package["name"] == "北京日系写真方案"
    assert package["price"] == 699
    assert package["duration"] == 120
    assert package["image_count"] == 30
    assert package["description"] == "适合北京日系写真，包含轻松自然的人像拍摄。"
    assert "底片全送" in package["includes"]
    assert package.get("id")
    assert action_log.status == "success"
    assert action_log.tool_input["name"] == "北京日系写真方案"
    assert action_log.tool_input["description"] == "适合北京日系写真，包含轻松自然的人像拍摄。"
    assert action_log.tool_result["published"] is True
    assert action_log.tool_result["package_id"] == package["id"]
    assert assistant_message.message_metadata["tool_calls"][0]["status"] == "success"
    assert assistant_message.message_metadata["task_state"]["status"] == "completed"
    assert assistant_message.message_metadata["task_state"]["pending_action"] is None


@pytest.mark.asyncio
async def test_confirm_booking_action_label_executes_pending_booking(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)
    pending_input = {
        "photographer_id": photographer_profile.user_id,
        "package_display": "测试方案 499 元 时长 150 分钟",
        "appointment_date": "07-02",
        "appointment_time": "09:00",
        "duration_minutes": 150,
    }
    db.add(
        AIMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="我帮你整理了预约信息，请确认：",
            message_metadata={
                "suggested_actions": [
                    {
                        "type": "confirm_create_booking",
                        "label": "确认预约",
                        "requires_confirmation": True,
                    }
                ],
                "task_state": {
                    "task_type": "create_booking",
                    "status": "awaiting_confirmation",
                    "slots": {
                        "photographer_id": photographer_profile.user_id,
                        "date": "07-02",
                        "time": "09:00",
                        "duration_minutes": 150,
                    },
                    "pending_action": {
                        "tool": "create_booking",
                        "input": pending_input,
                    },
                },
            },
        )
    )
    db.commit()

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "确认预约",
    )

    order = db.query(Order).filter_by(customer_id=customer_user.id).one()
    action_log = db.query(AgentActionLog).filter_by(
        user_id=customer_user.id,
        conversation_id=conversation.id,
        tool_name="create_booking",
    ).one()

    assert order.photographer_id == photographer_profile.user_id
    assert order.status == OrderStatus.PENDING
    assert order.package_snapshot == pending_input["package_display"]
    assert order.appointment_time.hour == 9
    assert action_log.tool_input["appointment_time"].endswith("T09:00:00")
    assert action_log.status == "success"
    assert assistant_message.message_metadata["tool_calls"][0]["status"] == "success"
    assert assistant_message.message_metadata["task_state"]["status"] == "completed"
    assert assistant_message.message_metadata["suggested_actions"] == []
    assert "预约已创建" in assistant_message.content


def test_retrieve_references_rebuilds_ai_resource_index(db, photographer_profile):
    assert db.query(AIResourceDocument).count() == 0

    retrieval = retrieve_references(db, "帮我推荐北京日系写真摄影师，预算 700")

    assert retrieval["references"]["photographers"][0]["user_id"] == photographer_profile.user_id
    assert db.query(AIResourceDocument).count() == 4
    indexed_types = {
        item.resource_type
        for item in db.query(AIResourceDocument).all()
    }
    assert indexed_types == {"photographer", "portfolio_item", "package"}


def test_profile_update_refreshes_ai_resource_index(db, photographer_profile):
    retrieve_references(db, "帮我推荐北京日系写真摄影师，预算 700")

    create_or_update_profile(
        db,
        photographer_profile.user_id,
        {"equipment": "Hasselblad X2D + 80mm f/1.9"},
    )
    retrieval = retrieve_references(db, "帮我找 Hasselblad 摄影师")

    photographer = retrieval["references"]["photographers"][0]
    assert photographer["user_id"] == photographer_profile.user_id
    assert photographer["equipment"] == "Hasselblad X2D + 80mm f/1.9"
    indexed = db.query(AIResourceDocument).filter(
        AIResourceDocument.resource_type == "photographer"
    ).one()
    assert "Hasselblad X2D" in indexed.search_text


def test_retrieve_references_includes_user_bio(db, photographer_profile):
    retrieval = retrieve_references(db, "帮我推荐胶片感摄影师")

    photographer = retrieval["references"]["photographers"][0]
    assert photographer["user_id"] == photographer_profile.user_id
    assert photographer["user_bio"] == "擅长自然光日系人像，也喜欢用胶片质感记录校园写真。"
    assert photographer["equipment"] == "Canon R5 + 85mm f/1.2"
    assert photographer["package_summaries"][0]["price_label"] == "¥699"
    assert photographer["portfolio_summaries"][0]["description"] == "自然光、清新、校园氛围的日系写真。"


def test_retrieve_references_includes_portfolio_description(db, photographer_profile):
    retrieval = retrieve_references(db, "帮我找清新校园相关作品")

    portfolio_item = retrieval["references"]["portfolio_items"][0]
    assert portfolio_item["title"] == "春日写真"
    assert portfolio_item["description"] == "自然光、清新、校园氛围的日系写真。"
    assert portfolio_item["thumbnail_url"] == "/static/1_thumb.jpg"
    assert portfolio_item["media_type"] == "image"
    assert portfolio_item["photographer_bio"] == "擅长自然光日系人像，也喜欢用胶片质感记录校园写真。"
    assert portfolio_item["photographer_styles"] == ["日系", "复古", "人像", "婚纱"]
    assert portfolio_item["related_package_prices"][0]["price_label"] == "¥699"


def test_retrieve_references_includes_package_price_tags(db, photographer_profile):
    retrieval = retrieve_references(db, "帮我找千元内自然光套餐")

    package = retrieval["references"]["packages"][0]
    assert package["package_name"] == "个人写真"
    assert package["price"] == 699
    assert package["price_label"] == "¥699"
    assert "千元内" in package["price_tags"]
    assert "120分钟" in package["price_tags"]
    assert "精修30张" in package["price_tags"]
    assert package["city"] == "北京"
    assert package["samples"] == ["/static/sample.jpg"]
    assert package["photographer_bio"] == "擅长自然光日系人像，也喜欢用胶片质感记录校园写真。"


def test_build_retrieval_context_includes_schema_version(db, photographer_profile):
    retrieval = retrieve_references(db, "帮我推荐北京日系写真摄影师，预算 700")
    context = build_retrieval_context(retrieval)

    assert '"context_schema_version": "ai_context_v1"' in context
    assert '"user_bio": "擅长自然光日系人像，也喜欢用胶片质感记录校园写真。"' in context


def test_retrieve_references_searches_bio_and_description(db, photographer_profile):
    photographer_retrieval = retrieve_references(db, "帮我找胶片质感摄影师")
    portfolio_retrieval = retrieve_references(db, "帮我找校园氛围作品")

    assert photographer_retrieval["references"]["photographers"][0]["user_id"] == photographer_profile.user_id
    assert portfolio_retrieval["references"]["portfolio_items"][0]["title"] == "春日写真"


def test_retrieve_references_does_not_return_unmatched_resources(db, photographer_profile):
    retrieval = retrieve_references(db, "帮我找云朵相关作品")

    assert retrieval is not None
    references = retrieval["references"]
    assert references["photographers"] == []
    assert references["portfolio_items"] == []
    assert references["packages"] == []
    assert "云朵" in retrieval["criteria"]["terms"]


@pytest.mark.asyncio
async def test_send_ai_message_uses_guardrail_when_resource_search_has_no_matches(
    monkeypatch,
    db,
    customer_user,
    photographer_profile,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, assistant_message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "帮我找云朵相关作品",
    )

    # 首轮就无结果、且没有历史上下文时使用平台兜底话术
    assert "暂时没找到匹配的作品" in assistant_message.content
    # 兜底话术只描述结构化条件，不再把用户原话当成“完全匹配关键词”复述
    assert "云朵" not in assistant_message.content
    assert "云端漫步" not in assistant_message.content
    assert assistant_message.message_metadata["references"]["portfolio_items"] == []
    assert assistant_message.message_metadata["model"]["provider"] == "platform_guardrail"
    assert assistant_message.message_metadata["model"]["model"] == "empty-retrieval-fallback"


# ── 企划引用解析器 单元测试 ──────────────────────────────────────────────────


class TestLatestProjectReferences:
    """测试 _latest_project_references 从最近消息提取企划引用。"""

    def test_returns_empty_when_no_messages(self, db, customer_user):
        conv = ai_service.create_conversation(db, customer_user.id)
        result = ai_service._latest_project_references(db, conv.id)
        assert result == []

    def test_returns_projects_from_last_assistant_metadata(self, db, customer_user):
        conv = ai_service.create_conversation(db, customer_user.id)
        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="推荐如下",
            message_metadata={
                "references": {
                    "photographers": [],
                    "portfolio_items": [],
                    "packages": [],
                    "projects": [
                        {"id": 1, "title": "毕业照拍摄", "city": "成都"},
                        {"id": 2, "title": "婚礼跟拍", "city": "北京"},
                    ],
                }
            },
        )
        db.add(msg)
        db.commit()

        result = ai_service._latest_project_references(db, conv.id)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_ignores_user_messages(self, db, customer_user):
        conv = ai_service.create_conversation(db, customer_user.id)
        user_msg = AIMessage(
            conversation_id=conv.id,
            role="user",
            content="推荐企划",
            message_metadata={"references": {"projects": [{"id": 99}]}},
        )
        db.add(user_msg)
        db.commit()

        result = ai_service._latest_project_references(db, conv.id)
        assert result == []


class TestResolveProjectReference:
    """测试 _resolve_project_reference 序号/标题解析。"""

    def test_resolves_first_by_ordinal(self, db, customer_user):
        conv = ai_service.create_conversation(db, customer_user.id)
        # 需要先创建一个公开OPEN企划
        from backend.app.models.project import ShootProject, ProjectStatus
        project = ShootProject(
            customer_id=customer_user.id,
            title="毕业照拍摄",
            description="测试",
            category="写真",
            city="成都",
            visibility="public",
            status=ProjectStatus.OPEN,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="推荐",
            message_metadata={
                "references": {
                    "projects": [
                        {"id": project.id, "title": "毕业照拍摄", "city": "成都"},
                        {"id": 2, "title": "婚礼跟拍", "city": "北京"},
                    ],
                    "photographers": [],
                    "portfolio_items": [],
                    "packages": [],
                }
            },
        )
        db.add(msg)
        db.commit()

        result = ai_service._resolve_project_reference(db, conv.id, "第一个，帮我申请应邀")
        assert result is not None
        assert result["id"] == project.id
        assert result["title"] == "毕业照拍摄"
        assert result["valid"] is True

    def test_resolves_second_by_ordinal(self, db, customer_user):
        conv = ai_service.create_conversation(db, customer_user.id)
        from backend.app.models.project import ShootProject, ProjectStatus

        p1 = ShootProject(
            customer_id=customer_user.id, title="项目A", description="A",
            category="写真", city="成都", visibility="public", status=ProjectStatus.OPEN,
        )
        p2 = ShootProject(
            customer_id=customer_user.id, title="项目B", description="B",
            category="写真", city="北京", visibility="public", status=ProjectStatus.OPEN,
        )
        db.add_all([p1, p2])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)

        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="推荐",
            message_metadata={
                "references": {
                    "projects": [
                        {"id": p1.id, "title": "项目A"},
                        {"id": p2.id, "title": "项目B"},
                    ],
                    "photographers": [],
                    "portfolio_items": [],
                    "packages": [],
                }
            },
        )
        db.add(msg)
        db.commit()

        # "第二个，帮我申请应邀" → 应为第二项 p2，不是 ID=2
        result = ai_service._resolve_project_reference(db, conv.id, "第二个，帮我申请应邀")
        assert result is not None
        assert result["id"] == p2.id

    def test_returns_none_when_no_previous_references(self, db, customer_user):
        conv = ai_service.create_conversation(db, customer_user.id)
        result = ai_service._resolve_project_reference(db, conv.id, "第一个")
        assert result is None

    def test_returns_none_when_project_closed(self, db, customer_user):
        conv = ai_service.create_conversation(db, customer_user.id)
        from backend.app.models.project import ShootProject, ProjectStatus

        project = ShootProject(
            customer_id=customer_user.id,
            title="已关闭企划",
            description="测试",
            category="写真",
            city="成都",
            visibility="public",
            status=ProjectStatus.CLOSED,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="推荐",
            message_metadata={
                "references": {
                    "projects": [{"id": project.id, "title": "已关闭企划"}],
                    "photographers": [],
                    "portfolio_items": [],
                    "packages": [],
                }
            },
        )
        db.add(msg)
        db.commit()

        result = ai_service._resolve_project_reference(db, conv.id, "第一个")
        assert result is None

    def test_resolves_by_title_match(self, db, customer_user):
        conv = ai_service.create_conversation(db, customer_user.id)
        from backend.app.models.project import ShootProject, ProjectStatus

        project = ShootProject(
            customer_id=customer_user.id,
            title="毕业照拍摄企划",
            description="测试",
            category="写真",
            city="成都",
            visibility="public",
            status=ProjectStatus.OPEN,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="推荐",
            message_metadata={
                "references": {
                    "projects": [
                        {"id": project.id, "title": "毕业照拍摄企划"},
                        {"id": 2, "title": "婚礼跟拍"},
                    ],
                    "photographers": [],
                    "portfolio_items": [],
                    "packages": [],
                }
            },
        )
        db.add(msg)
        db.commit()

        result = ai_service._resolve_project_reference(db, conv.id, "毕业照拍摄企划，帮我申请")
        assert result is not None
        assert result["id"] == project.id


class TestLooksLikeProjectApplicationRequest:
    """测试 _looks_like_project_application_request 边界检测。"""

    def test_detects_apply_request(self):
        assert ai_service._looks_like_project_application_request("第一个，帮我发布一下应邀") is True
        assert ai_service._looks_like_project_application_request("第二个，帮我申请") is True
        assert ai_service._looks_like_project_application_request("这个帮我报名") is True
        assert ai_service._looks_like_project_application_request("我接这个") is True
        assert ai_service._looks_like_project_application_request("帮我提交方案") is True

    def test_does_not_detect_discovery_request(self):
        # 发现类关键词不应触发
        assert ai_service._looks_like_project_application_request("帮我找企划") is False
        assert ai_service._looks_like_project_application_request("推荐一个企划") is False
        assert ai_service._looks_like_project_application_request("有没有可应邀的企划") is False
        assert ai_service._looks_like_project_application_request("看看有什么") is False
        assert ai_service._looks_like_project_application_request("搜索企划") is False

    def test_handles_empty_content(self):
        assert ai_service._looks_like_project_application_request(None) is False
        assert ai_service._looks_like_project_application_request("") is False


class TestProjectApplicationIntent:
    """测试 _project_application_intent 构建。"""

    def test_builds_correct_intent(self):
        project = {"id": 42, "title": "测试企划"}
        intent = ai_service._project_application_intent(project)
        assert intent.intent == "resource_search"
        assert intent.sub_intents == ["prepare_project_application"]
        assert intent.route == "project_application"
        assert intent.slots["project_id"] == 42
        assert intent.slots["resource_types"] == ["projects"]
        assert intent.requires_confirmation is False
        assert intent.confidence > 0.9


class TestProjectApplicationAgentResult:
    """测试 _project_application_agent_result 生成结果。"""

    def test_builds_correct_result(self):
        project = {
            "id": 42,
            "title": "毕业照拍摄企划",
            "city": "成都",
        }
        result = ai_service._project_application_agent_result(project)
        assert "毕业照拍摄企划" in result["content"]
        assert result["metadata"]["selected_project"] == project
        actions = result["metadata"]["client_actions"]
        assert len(actions) == 1
        assert actions[0]["type"] == "open_project_application"
        assert actions[0]["project_id"] == 42
        assert result["metadata"]["task_state"]["task_type"] == "project_application"

    def test_result_metadata_matches_workflow_contract(self):
        project = {"id": 42, "title": "毕业照拍摄企划", "city": "成都"}

        metadata = normalize_agent_metadata(
            ai_service._project_application_agent_result(project)["metadata"]
        )

        assert metadata["task_state"]["status"] == "awaiting_details"
        assert metadata["client_actions"][0] == {
            "type": "open_project_application",
            "label": "填写应邀方案",
            "project_id": 42,
        }


# ── 集成测试 ──────────────────────────────────────────────────────────────────


class TestProjectDiscoveryIntegration:
    """测试 project_discovery 路由的集成行为。"""

    @pytest.mark.asyncio
    async def test_project_discovery_references_persist_after_persistence(
        self, monkeypatch, db, photographer_user
    ):
        """验证 project_discovery 返回的 references.projects 保存到数据库后仍存在。"""
        monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
        conv = ai_service.create_conversation(db, photographer_user.id)

        _, assistant_msg = await ai_service.send_ai_message(
            db, photographer_user.id, conv.id, "帮我找企划，我想接活",
        )
        metadata = assistant_msg.message_metadata or {}
        refs = metadata.get("references") or {}
        assert "projects" in refs
        # 刷新会话后重新读取
        db.expire_all()
        reloaded_msg = db.query(AIMessage).filter(AIMessage.id == assistant_msg.id).first()
        reloaded_metadata = reloaded_msg.message_metadata or {}
        reloaded_refs = reloaded_metadata.get("references") or {}
        assert "projects" in reloaded_refs

    @pytest.mark.asyncio
    async def test_project_application_from_recommendation_returns_valid_metadata(
        self, monkeypatch, db, customer_user, photographer_user, photographer_profile
    ):
        """验证推荐结果中的企划可按序号进入应邀填写入口。"""
        monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
        project = ShootProject(
            customer_id=customer_user.id,
            title="毕业照拍摄企划",
            description="毕业典礼纪实跟拍",
            category="graduation",
            city="成都",
            budget_max=1200,
            visibility="public",
            status=ProjectStatus.OPEN,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        conv = ai_service.create_conversation(db, photographer_user.id)

        _, recommendation = await ai_service.send_ai_message(
            db, photographer_user.id, conv.id, "帮我找企划，我想接活",
        )
        references = (recommendation.message_metadata or {}).get("references") or {}
        assert references["projects"][0]["id"] == project.id

        _, application_entry = await ai_service.send_ai_message(
            db, photographer_user.id, conv.id, "帮我应邀第一个",
        )

        metadata = application_entry.message_metadata or {}
        assert metadata["task_state"]["status"] == "awaiting_details"
        assert metadata["selected_project"]["id"] == project.id
        assert metadata["client_actions"][0] == {
            "type": "open_project_application",
            "label": "填写应邀方案",
            "project_id": project.id,
        }

    @pytest.mark.asyncio
    async def test_project_discovery_result_has_empty_other_references(
        self, monkeypatch, db, photographer_user
    ):
        """验证 project_discovery 的 photographers/packages/portfolio_items 均为空。"""
        monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
        conv = ai_service.create_conversation(db, photographer_user.id)

        _, assistant_msg = await ai_service.send_ai_message(
            db, photographer_user.id, conv.id, "帮我找企划，我想接活",
        )
        refs = assistant_msg.message_metadata.get("references") or {}
        assert refs.get("photographers") == []
        assert refs.get("packages") == []
        assert refs.get("portfolio_items") == []

    @pytest.mark.asyncio
    async def test_project_discovery_not_available_for_customer(
        self, monkeypatch, db, customer_user
    ):
        """验证非摄影师不能使用企划发现。"""
        monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
        conv = ai_service.create_conversation(db, customer_user.id)

        _, assistant_msg = await ai_service.send_ai_message(
            db, customer_user.id, conv.id, "帮我找企划",
        )
        assert "摄影师" in assistant_msg.content

    @pytest.mark.asyncio
    async def test_regular_search_still_runs_retrieval(
        self, monkeypatch, db, customer_user, photographer_profile
    ):
        """验证普通摄影师搜索仍然触发检索（project_discovery 不影响）。"""
        monkeypatch.setattr(ai_service, "get_ai_provider", lambda: RetrievalProvider())
        monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
        conv = ai_service.create_conversation(db, customer_user.id)

        _, assistant_msg = await ai_service.send_ai_message(
            db, customer_user.id, conv.id, "帮我推荐北京日系写真摄影师，预算 700",
        )
        metadata = assistant_msg.message_metadata or {}
        # 普通搜索应有 retrieval 记录
        assert "retrieval" in metadata
        refs = metadata.get("references") or {}
        assert len(refs.get("photographers", [])) > 0


class TestProjectReferenceMetadata:
    """企划引用必须是精简且可持久化的 JSON 对象。"""

    def test_decimal_coordinates_are_excluded_and_dates_are_json_strings(self):
        reference = build_ai_project_reference(
            {
                "id": 7,
                "title": "成都人像企划",
                "city": "成都",
                "budget_min": Decimal("800"),
                "budget_max": Decimal("1200"),
                "shoot_date_start": datetime(2026, 8, 1, 10, 30),
                "status": "open",
                "reference_images": ["/uploads/project.jpg"],
                "match_reason": "城市匹配",
                "location_latitude": Decimal("30.6586000"),
                "location_longitude": Decimal("104.0648000"),
                "location_address": "敏感地址不应进入引用",
                "customer_id": 99,
            }
        )

        assert set(reference) == {
            "id", "title", "city", "budget_min", "budget_max", "budget_label",
            "date_label", "status", "reference_images", "match_reason",
        }
        assert reference["budget_min"] == 800
        assert reference["date_label"] == "2026-08-01T10:30:00"
        assert "location_latitude" not in reference
        assert "location_longitude" not in reference
        json.dumps(reference, ensure_ascii=False, allow_nan=False)

    def test_contract_forbids_unexpected_fields(self):
        with pytest.raises(Exception):
            ProjectReference(
                id=1,
                title="测试",
                status="open",
                unexpected=object(),
            )

    def test_metadata_boundary_rejects_non_json_values(self):
        with pytest.raises(RuntimeError, match="not JSON serializable"):
            ensure_json_metadata({"references": {"projects": [{"id": Decimal("1")}]}})
