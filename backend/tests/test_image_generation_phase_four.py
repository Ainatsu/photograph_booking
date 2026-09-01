"""Phase-four regeneration and administration overview tests."""

import pytest

from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.schemas.ai import AIImageGenerationRequest
from backend.app.services.admin_service import get_image_generation_overview
from backend.app.services.image_generation_job_service import (
    process_next_image_generation_job,
    regenerate_image_generation_job,
)
from backend.app.services.image_generation_provider import MockImageGenerationProvider
from backend.app.services.image_generation_workflow_service import create_image_generation_job


def _conversation_message(db, user_id: int) -> tuple[AIConversation, AIMessage]:
    conversation = AIConversation(user_id=user_id, title="phase four")
    db.add(conversation)
    db.flush()
    message = AIMessage(conversation_id=conversation.id, role="user", content="黄昏海边胶片人像")
    db.add(message)
    db.commit()
    db.refresh(conversation)
    db.refresh(message)
    return conversation, message


@pytest.mark.asyncio
async def test_regenerate_creates_auditable_job_with_inherited_parameters(db, customer_user):
    conversation, source_message = _conversation_message(db, customer_user.id)
    original = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=source_message.id,
        prompt=source_message.content,
        attachments=None,
        request=AIImageGenerationRequest(
            mode="text_to_image",
            aspect_ratio="3:4",
            count=2,
            quality="high",
        ),
        source="explicit_button",
    )
    assistant = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="图片生成任务已创建。",
        message_metadata={"image_generation": {"job_id": original.id, "task_id": original.agent_task_id, "mode": original.mode, "status": original.status}},
    )
    db.add(assistant)
    db.commit()

    assert await process_next_image_generation_job(db, provider=MockImageGenerationProvider()) == "completed"
    regenerated = regenerate_image_generation_job(db, owner_id=customer_user.id, job_id=original.id)

    assert regenerated["job_id"] != original.id
    assert regenerated["status"] == "queued"
    assert regenerated["parameters"]["aspect_ratio"] == "3:4"
    assert regenerated["parameters"]["count"] == 2
    assert regenerated["parameters"]["quality"] == "high"
    assert regenerated["parameters"]["source"] == "regenerate"
    assert regenerated["parameters"]["regenerated_from_job_id"] == original.id

    db.refresh(assistant)
    reference = assistant.message_metadata["image_generation"]
    assert reference["job_id"] == regenerated["job_id"]
    assert reference["regenerated_from_job_id"] == original.id


@pytest.mark.asyncio
async def test_admin_overview_summarizes_generation_operations(db, customer_user):
    conversation, source_message = _conversation_message(db, customer_user.id)
    original = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=source_message.id,
        prompt=source_message.content,
        attachments=None,
        request=AIImageGenerationRequest(mode="text_to_image", count=1),
        source="explicit_button",
    )
    assert await process_next_image_generation_job(db, provider=MockImageGenerationProvider()) == "completed"
    regenerated = regenerate_image_generation_job(db, owner_id=customer_user.id, job_id=original.id)

    overview = get_image_generation_overview(db, days=7)

    assert overview["total_jobs"] == 2
    assert overview["successful_jobs"] == 1
    assert overview["generated_assets"] == 1
    assert overview["regenerated_jobs"] == 1
    assert overview["status_counts"] == {"completed": 1, "queued": 1}
    assert overview["mode_counts"] == {"text_to_image": 2}
    assert overview["recent_jobs"][0]["job_id"] == regenerated["job_id"]
    assert "prompt" not in overview["recent_jobs"][0]
