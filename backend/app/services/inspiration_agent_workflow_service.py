"""Main-Agent orchestration for creating and finalizing inspiration tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.services.agent_task_service import ensure_task, serialize_task
from backend.app.services.ai_agent_tool_service import create_inspiration_draft
from backend.app.services.ai_provider import AIProvider
from backend.app.models.inspiration_generation import InspirationGenerationBatch, InspirationGenerationJob


async def create_inspiration_workflow(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int,
    reference_text: str,
    images: list[dict[str, Any]],
    provider: AIProvider | None = None,
) -> dict[str, Any]:
    if not images:
        return {
            "content": "请先上传至少一张参考图片，我再帮你创建拍摄灵感。",
            "metadata": {"inspiration_flow": {"status": "awaiting_reference_images"}},
        }

    task = ensure_task(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        task_type="create_inspiration",
    )
    task.status = "generating"
    task.media_assets = [image["url"] for image in images]
    task.fields = {**(task.fields or {}), "reference_text": reference_text}
    task.revision += 1
    db.commit()
    db.refresh(task)

    try:
        # Create only a placeholder here. Provider calls are owned by the phase-D worker.
        payload = {
            "title": "正在生成灵感",
            "summary": "参考图片正在分批分析中",
            "tags": [],
            "content": [],
            "cover_url": images[0]["url"],
            "status": "draft",
        }
        draft_call = create_inspiration_draft(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            inspiration_payload=payload,
            idempotency_key=f"inspiration-draft:{task.id}",
            commit=False,
        )
        if draft_call.get("status") != "success":
            raise ValueError((draft_call.get("result") or {}).get("error") or "inspiration_draft_failed")
        draft = draft_call["result"]
        inspiration_id = draft["inspiration_id"]
        job = InspirationGenerationJob(
            inspiration_id=inspiration_id,
            agent_task_id=task.id,
            owner_id=user_id,
            conversation_id=conversation_id,
            reference_text=reference_text,
            status="queued",
            total_images=len(images),
            completed_images=0,
            failed_images=0,
        )
        db.add(job)
        db.flush()
        for batch_index in range(0, len(images), 2):
            batch_images = images[batch_index:batch_index + 2]
            db.add(InspirationGenerationBatch(
                job_id=job.id,
                batch_index=batch_index // 2,
                attachment_indices=[int(image["attachment_index"]) for image in batch_images],
                image_refs=[{
                    "attachment_index": int(image["attachment_index"]),
                    "url": image["url"],
                    "thumb_url": image.get("thumb_url"),
                    "provider_image_url": image["provider_image_url"],
                    "mime_type": image.get("mime_type") or "image/jpeg",
                } for image in batch_images],
                status="queued",
                attempts=0,
            ))
        entry = {
            "inspiration_id": inspiration_id,
            "title": payload["title"],
            "summary": payload["summary"],
            "cover_url": images[0]["url"],
            "status": "draft",
            "generation_status": "generating",
            "total_images": len(images),
            "completed_images": 0,
            "failed_images": 0,
        }
        task.status = "generating"
        task.fields = {
            "inspiration_id": inspiration_id,
            "reference_text": reference_text,
            "title": payload["title"],
            "summary": payload["summary"],
            "tags": [],
            "cover_url": images[0]["url"],
            "generation_status": "generating",
        }
        task.result = entry
        task.revision += 1
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        task = ensure_task(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            task_type="create_inspiration",
        )
        task.status = "failed"
        task.result = {"error": str(exc)[:500]}
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
        return {
            "content": "灵感内容生成失败了。参考图片和任务已保留，你可以稍后重新发送创建请求。",
            "metadata": {
                "inspiration_flow": {"status": "failed", "error": str(exc)[:300]},
                "active_task": serialize_task(task),
            },
        }

    return {
        "content": "灵感草稿已经创建，参考图片会分批生成，你可以通过下方卡片查看进度。",
        "metadata": {
            "inspiration_flow": {
                "status": "generating",
                "inspiration_id": task.fields["inspiration_id"],
                "entry": task.result,
            },
            "active_task": None,
            "tool_call": draft_call,
        },
    }
