"""Phase-one image generation contract and mock workflow tests."""

from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import HTTPException
from PIL import Image

from backend.app.core.config import settings
from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.models.image_generation import ImageGenerationJob
from backend.app.schemas.ai import AIImageGenerationRequest
from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services import ai_service
from backend.app.services.image_generation_job_service import (
    cancel_image_generation_job,
    get_image_generation_job,
    process_next_image_generation_job,
    retry_image_generation_job,
)
from backend.app.services.image_generation_provider import MockImageGenerationProvider
from backend.app.services.image_generation_workflow_service import create_image_generation_job


def _conversation_message(db, user_id: int, content: str) -> tuple[AIConversation, AIMessage]:
    conversation = AIConversation(user_id=user_id, title="image generation")
    db.add(conversation)
    db.flush()
    message = AIMessage(conversation_id=conversation.id, role="user", content=content)
    db.add(message)
    db.commit()
    db.refresh(conversation)
    db.refresh(message)
    return conversation, message


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 100), (120, 90, 70)).save(output, "PNG")
    return output.getvalue()


def test_rules_distinguish_generation_edit_and_analysis():
    generated = recognize_intent_by_rules("生成一张黄昏海边的胶片人像")
    edited = recognize_intent_by_rules(
        "保留人物姿势，把这张图改成黄昏逆光",
        [{"type": "image", "url": "/static/ai/1/reference.png"}],
    )
    analyzed = recognize_intent_by_rules(
        "帮我分析这张图的色调",
        [{"type": "image", "url": "/static/ai/1/reference.png"}],
    )
    consultation = recognize_intent_by_rules("海边拍摄时背景颜色改成什么更协调？")

    assert generated.intent == "image_generation_flow"
    assert generated.sub_intents == ["text_to_image"]
    assert edited.intent == "image_generation_flow"
    assert edited.sub_intents == ["image_to_image"]
    assert analyzed.intent == "image_analysis"
    assert consultation.intent == "chat"


@pytest.mark.asyncio
async def test_mock_text_to_image_job_completes_and_is_idempotent(db, customer_user, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    conversation, message = _conversation_message(db, customer_user.id, "黄昏海边清冷人像")
    request = AIImageGenerationRequest(
        mode="text_to_image",
        aspect_ratio="3:4",
        count=2,
        idempotency_key=uuid4(),
    )
    job = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=message.id,
        prompt=message.content,
        attachments=[],
        request=request,
        source="explicit_button",
    )
    duplicate = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=message.id,
        prompt=message.content,
        attachments=[],
        request=request,
        source="explicit_button",
    )

    assert duplicate.id == job.id
    assert await process_next_image_generation_job(db, provider=MockImageGenerationProvider()) == "completed"
    payload = get_image_generation_job(db, owner_id=customer_user.id, job_id=job.id)
    assert payload["status"] == "completed"
    assert payload["progress"] == {"completed": 2, "total": 2}
    assert all(item["url"].startswith(f"/static/ai-generated/{customer_user.id}/{job.id}/") for item in payload["result_images"])


@pytest.mark.asyncio
async def test_mock_image_to_image_requires_owned_reference(db, customer_user, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    reference_dir = tmp_path / "ai" / str(customer_user.id)
    reference_dir.mkdir(parents=True)
    reference_path = reference_dir / "reference.png"
    reference_path.write_bytes(_png_bytes())
    conversation, message = _conversation_message(db, customer_user.id, "保留人物姿势，改成黄昏逆光")
    request = AIImageGenerationRequest(mode="image_to_image", strength=0.65)

    with pytest.raises(HTTPException) as forbidden:
        create_image_generation_job(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            source_message_id=message.id,
            prompt=message.content,
            attachments=[{"type": "image", "url": "/static/ai/999/reference.png", "mime_type": "image/png"}],
            request=request,
            source="explicit_button",
        )
    assert forbidden.value.status_code == 403

    job = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=message.id,
        prompt=message.content,
        attachments=[{"type": "image", "url": f"/static/ai/{customer_user.id}/reference.png", "mime_type": "image/png"}],
        request=request,
        source="explicit_button",
    )
    assert await process_next_image_generation_job(db, provider=MockImageGenerationProvider()) == "completed"
    payload = get_image_generation_job(db, owner_id=customer_user.id, job_id=job.id)
    assert len(payload["source_images"]) == 1
    assert len(payload["result_images"]) == 1


def test_cancel_retry_and_owner_isolation(db, customer_user, photographer_user):
    conversation, message = _conversation_message(db, customer_user.id, "夜景霓虹街拍")
    job = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=message.id,
        prompt=message.content,
        attachments=[],
        request=AIImageGenerationRequest(mode="text_to_image"),
        source="explicit_button",
    )

    with pytest.raises(HTTPException) as missing:
        get_image_generation_job(db, owner_id=photographer_user.id, job_id=job.id)
    assert missing.value.status_code == 404

    cancelled = cancel_image_generation_job(db, owner_id=customer_user.id, job_id=job.id)
    assert cancelled["status"] == "cancelled"

    persisted = db.query(ImageGenerationJob).filter(ImageGenerationJob.id == job.id).one()
    persisted.status = "failed"
    persisted.stage = "failed"
    persisted.last_error_code = "provider_timeout"
    db.commit()
    retried = retry_image_generation_job(db, owner_id=customer_user.id, job_id=job.id)
    assert retried["status"] == "queued"
    assert retried["error"] is None


def test_generation_request_validation_rejects_conflicting_inputs(db, customer_user):
    conversation, message = _conversation_message(db, customer_user.id, "生成一张人像")
    with pytest.raises(HTTPException) as image_not_allowed:
        create_image_generation_job(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            source_message_id=message.id,
            prompt=message.content,
            attachments=[{"type": "image", "url": f"/static/ai/{customer_user.id}/reference.png"}],
            request=AIImageGenerationRequest(mode="text_to_image"),
            source="explicit_button",
        )
    assert image_not_allowed.value.detail["code"] == "reference_image_not_allowed"

    with pytest.raises(HTTPException) as reference_required:
        create_image_generation_job(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            source_message_id=message.id,
            prompt="改成黄昏",
            attachments=[],
            request=AIImageGenerationRequest(mode="image_to_image"),
            source="explicit_button",
        )
    assert reference_required.value.detail["code"] == "reference_image_required"


@pytest.mark.asyncio
async def test_explicit_request_bypasses_classifier(db, customer_user, monkeypatch):
    conversation = AIConversation(user_id=customer_user.id, title="explicit image generation")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    async def fail_if_classified(*args, **kwargs):
        raise AssertionError("explicit generation request must bypass the classifier")

    monkeypatch.setattr(ai_service, "classify_intent", fail_if_classified)
    _, assistant = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "黄昏海边的清冷人像，胶片质感",
        generation_request=AIImageGenerationRequest(mode="text_to_image", aspect_ratio="3:4"),
    )

    generation = assistant.message_metadata["image_generation"]
    assert generation["mode"] == "text_to_image"
    assert generation["status"] == "queued"
    assert assistant.message_metadata["intent"]["intent"] == "image_generation_flow"
