"""Validation and job creation for the unified image generation workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.agent_task import AgentTaskDraft
from backend.app.models.image_generation import ImageGenerationAsset, ImageGenerationJob
from backend.app.schemas.ai import AIImageGenerationRequest
from backend.app.services.agent_task_service import get_active_task


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _image_attachments(attachments: list[dict] | None) -> list[dict]:
    return [item for item in attachments or [] if isinstance(item, dict) and item.get("type") == "image" and item.get("url")]


def _validate_request(user_id: int, prompt: str, attachments: list[dict] | None, request: AIImageGenerationRequest) -> list[dict]:
    images = _image_attachments(attachments)
    if not prompt:
        code = "generation_instruction_required" if request.mode == "image_to_image" else "invalid_generation_request"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": code})
    if request.mode == "text_to_image":
        if images:
            raise HTTPException(status_code=400, detail={"code": "reference_image_not_allowed"})
        if request.strength is not None:
            raise HTTPException(status_code=400, detail={"code": "invalid_generation_request", "field": "strength"})
        return images
    if len(images) != 1:
        code = "reference_image_required" if not images else "invalid_generation_request"
        raise HTTPException(status_code=400, detail={"code": code, "field": "attachments"})
    trusted_prefix = f"/static/ai/{user_id}/"
    if not str(images[0]["url"]).startswith(trusted_prefix):
        raise HTTPException(status_code=403, detail={"code": "reference_image_forbidden"})
    return images


def create_image_generation_job(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    source_message_id: int,
    prompt: str | None,
    attachments: list[dict] | None,
    request: AIImageGenerationRequest,
    source: str,
) -> ImageGenerationJob:
    normalized_prompt = (prompt or "").strip()
    images = _validate_request(user_id, normalized_prompt, attachments, request)
    existing = (
        db.query(ImageGenerationJob)
        .filter(ImageGenerationJob.owner_id == user_id, ImageGenerationJob.idempotency_key == str(request.idempotency_key))
        .first()
    )
    if existing:
        return existing
    active_job_count = (
        db.query(ImageGenerationJob)
        .filter(
            ImageGenerationJob.owner_id == user_id,
            ImageGenerationJob.status.in_(["queued", "generating", "retry_wait"]),
        )
        .count()
    )
    if active_job_count >= settings.IMAGE_MAX_ACTIVE_JOBS_PER_USER:
        raise HTTPException(status_code=429, detail={"code": "generation_concurrency_exceeded"})
    day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_count = (
        db.query(ImageGenerationJob)
        .filter(ImageGenerationJob.owner_id == user_id, ImageGenerationJob.created_at >= day_start)
        .count()
    )
    if daily_count >= settings.IMAGE_DAILY_LIMIT_PER_USER:
        raise HTTPException(status_code=429, detail={"code": "generation_quota_exceeded"})
    active = get_active_task(db, user_id, conversation_id)
    if active and active.task_type != "generate_image":
        raise HTTPException(status_code=409, detail={"code": "active_agent_task_conflict"})
    if active and active.task_type == "generate_image":
        raise HTTPException(status_code=409, detail={"code": "generation_job_already_active"})

    task_id = str(uuid4())
    parameters = request.model_dump(mode="json", exclude={"idempotency_key"}, exclude_none=True)
    parameters["source"] = source
    task = AgentTaskDraft(
        id=task_id,
        conversation_id=conversation_id,
        user_id=user_id,
        task_type="generate_image",
        status="generating",
        schema_version=2,
        revision=0,
        target={},
        fields={"prompt": normalized_prompt, **parameters},
        field_sources={},
        media_assets=[item["url"] for item in images],
    )
    db.add(task)
    db.flush()
    job = ImageGenerationJob(
        owner_id=user_id,
        conversation_id=conversation_id,
        source_message_id=source_message_id,
        agent_task_id=task_id,
        mode=request.mode,
        status="queued",
        stage="queued",
        prompt=normalized_prompt,
        normalized_prompt=normalized_prompt,
        parameters=parameters,
        idempotency_key=str(request.idempotency_key),
        available_at=_now(),
    )
    db.add(job)
    db.flush()
    for position, image in enumerate(images):
        db.add(ImageGenerationAsset(
            job_id=job.id,
            role="source",
            position=position,
            storage_url=image["url"],
            thumbnail_url=image.get("thumb_url"),
            mime_type=image.get("mime_type") or "image/jpeg",
        ))
    db.commit()
    db.refresh(job)
    return job


def image_generation_agent_result(job: ImageGenerationJob) -> dict:
    return {
        "content": "图片生成任务已创建，正在等待处理。",
        "metadata": {
            "model": {"provider": "platform_job", "model": "image-generation-workflow"},
            "image_generation": {
                "schema_version": "image_generation_v1",
                "job_id": job.id,
                "task_id": job.agent_task_id,
                "mode": job.mode,
                "status": job.status,
            },
        },
    }
