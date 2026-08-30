"""Batch generation state machine for inspiration jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session, aliased

from backend.app.core.database import SessionLocal
from backend.app.models.agent_task import AgentTaskDraft
from backend.app.models.inspiration import Inspiration
from backend.app.models.inspiration_generation import InspirationGenerationBatch, InspirationGenerationJob
from backend.app.services.ai_provider import AIProvider
from backend.app.services.inspiration_agent_service import (
    InspirationAgentImage,
    InspirationBatchInput,
    build_inspiration_content,
    generate_inspiration_batch,
    summarize_inspiration_batches,
)
from backend.app.schemas.inspiration import InspirationBatchResult

MAX_BATCH_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (5, 20)
STALE_RUNNING_SECONDS = 120


def _now() -> datetime:
    return datetime.now(timezone.utc)


def recover_stale_running_batches(db: Session, *, stale_seconds: int = STALE_RUNNING_SECONDS) -> int:
    """Return abandoned running batches to the queue without touching other results."""
    cutoff = _now() - timedelta(seconds=stale_seconds)
    batches = (
        db.query(InspirationGenerationBatch)
        .filter(
            InspirationGenerationBatch.status == "running",
            or_(
                InspirationGenerationBatch.started_at < cutoff,
                and_(InspirationGenerationBatch.started_at.is_(None), InspirationGenerationBatch.updated_at < cutoff),
            ),
        )
        .all()
    )
    for batch in batches:
        batch.status = "queued"
        batch.available_at = _now()
        batch.last_error = "stale_running_recovered"
        batch.updated_at = _now()
    if batches:
        db.commit()
    return len(batches)


def get_generation_status(db: Session, *, owner_id: int, inspiration_id: int) -> dict[str, Any] | None:
    job = (
        db.query(InspirationGenerationJob)
        .filter(
            InspirationGenerationJob.inspiration_id == inspiration_id,
            InspirationGenerationJob.owner_id == owner_id,
        )
        .first()
    )
    if not job:
        return None
    return {
        "status": job.status,
        "total_images": job.total_images,
        "completed_images": job.completed_images,
        "failed_images": job.failed_images,
        "can_retry": job.status in {"partial", "failed"} and job.failed_images > 0,
        "updated_at": job.updated_at,
    }


def retry_failed_batches(db: Session, *, owner_id: int, inspiration_id: int) -> dict[str, Any] | None:
    job = (
        db.query(InspirationGenerationJob)
        .filter(
            InspirationGenerationJob.inspiration_id == inspiration_id,
            InspirationGenerationJob.owner_id == owner_id,
        )
        .first()
    )
    if not job:
        return None
    failed = (
        db.query(InspirationGenerationBatch)
        .filter(
            InspirationGenerationBatch.job_id == job.id,
            InspirationGenerationBatch.status == "failed",
        )
        .all()
    )
    now = _now()
    for batch in failed:
        batch.status = "queued"
        batch.attempts = 0
        batch.available_at = now
        batch.last_error = None
        batch.started_at = None
        batch.completed_at = None
        batch.updated_at = now
    if failed:
        job.status = "queued"
        job.completed_at = None
        job.last_error = None
        job.updated_at = now
        db.commit()
    return get_generation_status(db, owner_id=owner_id, inspiration_id=inspiration_id)


def claim_next_batch(db: Session) -> InspirationGenerationBatch | None:
    """Claim one available batch while ensuring its job has no other running batch."""
    now = _now()
    running_batch = aliased(InspirationGenerationBatch)
    running_for_job = exists().where(
        and_(
            running_batch.job_id == InspirationGenerationJob.id,
            running_batch.status == "running",
        )
    )
    batch = (
        db.query(InspirationGenerationBatch)
        .join(InspirationGenerationJob, InspirationGenerationJob.id == InspirationGenerationBatch.job_id)
        .filter(
            InspirationGenerationBatch.status == "queued",
            InspirationGenerationBatch.available_at <= now,
            InspirationGenerationJob.status.in_(["queued", "generating"]),
            ~running_for_job,
        )
        .order_by(InspirationGenerationJob.created_at.asc(), InspirationGenerationBatch.batch_index.asc())
        .first()
    )
    if not batch:
        return None
    batch.status = "running"
    batch.attempts = (batch.attempts or 0) + 1
    batch.started_at = now
    batch.updated_at = now
    job = db.query(InspirationGenerationJob).filter(InspirationGenerationJob.id == batch.job_id).one()
    job.status = "generating"
    job.updated_at = now
    db.commit()
    db.refresh(batch)
    return batch


def _rebuild_inspiration_content(db: Session, job: InspirationGenerationJob) -> None:
    inspiration = db.query(Inspiration).filter(Inspiration.id == job.inspiration_id).one()
    blocks: list[dict[str, Any]] = []
    completed = (
        db.query(InspirationGenerationBatch)
        .filter(
            InspirationGenerationBatch.job_id == job.id,
            InspirationGenerationBatch.status == "completed",
        )
        .order_by(InspirationGenerationBatch.batch_index.asc())
        .all()
    )
    for batch in completed:
        result = batch.result or {}
        items = sorted(result.get("items") or [], key=lambda item: int(item.get("attachment_index", 0)))
        trusted_images = batch.image_refs or []
        if not items or not trusted_images:
            continue
        # The batch contract has already validated these items before persistence.
        blocks.extend(build_inspiration_content(InspirationBatchResult.model_validate(result), trusted_images))
    inspiration.content = blocks
    inspiration.updated_at = _now()


def _update_progress(db: Session, job: InspirationGenerationJob) -> list[InspirationGenerationBatch]:
    batches = db.query(InspirationGenerationBatch).filter(InspirationGenerationBatch.job_id == job.id).all()
    job.total_images = sum(len(batch.attachment_indices or []) for batch in batches)
    job.completed_images = sum(len(batch.attachment_indices or []) for batch in batches if batch.status == "completed")
    job.failed_images = sum(len(batch.attachment_indices or []) for batch in batches if batch.status == "failed")
    return batches


async def _finalize_job(
    db: Session,
    job: InspirationGenerationJob,
    batches: list[InspirationGenerationBatch],
    *,
    provider: AIProvider | None = None,
) -> None:
    if not batches or not all(batch.status in {"completed", "failed"} for batch in batches):
        return
    completed = [batch for batch in batches if batch.status == "completed"]
    inspiration = db.query(Inspiration).filter(Inspiration.id == job.inspiration_id).one()
    summary_meta: dict[str, Any] = {}
    if completed:
        summary, summary_meta = await summarize_inspiration_batches(
            job.reference_text or "",
            [batch.result or {} for batch in completed],
            provider=provider,
        )
        inspiration.title = summary.title
        inspiration.summary = summary.summary
        inspiration.tags = summary.tags
        job.status = "partial" if len(completed) < len(batches) else "completed"
    else:
        job.status = "failed"
        job.last_error = next((batch.last_error for batch in batches if batch.last_error), "all_batches_failed")
    job.summary_result = {"result": summary.model_dump(mode="json"), "metadata": summary_meta} if completed else None
    job.completed_at = _now()
    job.updated_at = _now()
    task = db.query(AgentTaskDraft).filter(AgentTaskDraft.id == job.agent_task_id).first()
    if task:
        task.status = "completed" if completed else "failed"
        task.completed_at = _now()
        task.updated_at = _now()
        task.result = {
            "inspiration_id": job.inspiration_id,
            "title": inspiration.title,
            "summary": inspiration.summary,
            "tags": inspiration.tags or [],
            "cover_url": inspiration.cover_url,
            "status": inspiration.status.value if hasattr(inspiration.status, "value") else str(inspiration.status),
            "generation_status": job.status,
            "total_images": job.total_images,
            "completed_images": job.completed_images,
            "failed_images": job.failed_images,
        }
        task.fields = {**(task.fields or {}), **task.result, "generation_status": job.status}


async def process_batch(db: Session, batch: InspirationGenerationBatch, *, provider: AIProvider | None = None) -> str:
    """Execute a claimed batch and persist its result or retry state."""
    job = db.query(InspirationGenerationJob).filter(InspirationGenerationJob.id == batch.job_id).one()
    try:
        result, metadata = await generate_inspiration_batch(
            InspirationBatchInput(
                task_id=job.agent_task_id,
                reference_text=job.reference_text or "",
                images=[InspirationAgentImage(**{
                    "attachment_index": int(image["attachment_index"]),
                    "provider_image_url": image["provider_image_url"],
                    "mime_type": image.get("mime_type") or "image/jpeg",
                }) for image in (batch.image_refs or [])],
            ),
            provider=provider,
        )
    except Exception as exc:
        batch.last_error = str(exc)[:500]
        batch.started_at = None
        batch.updated_at = _now()
        if (batch.attempts or 0) >= MAX_BATCH_ATTEMPTS:
            batch.status = "failed"
            batch.completed_at = _now()
        else:
            batch.status = "queued"
            delay_index = min(batch.attempts - 1, len(RETRY_DELAYS_SECONDS) - 1)
            batch.available_at = _now() + timedelta(seconds=RETRY_DELAYS_SECONDS[max(delay_index, 0)])
        db.flush()
        batches = _update_progress(db, job)
        await _finalize_job(db, job, batches, provider=provider)
        db.commit()
        return batch.status

    batch.result = result.model_dump(mode="json")
    batch.provider_metadata = metadata
    batch.status = "completed"
    batch.last_error = None
    batch.completed_at = _now()
    batch.started_at = None
    batch.updated_at = _now()
    db.flush()
    _rebuild_inspiration_content(db, job)
    batches = _update_progress(db, job)
    await _finalize_job(db, job, batches, provider=provider)
    db.commit()
    return batch.status


async def process_next_batch(db: Session, *, provider: AIProvider | None = None) -> str | None:
    batch = claim_next_batch(db)
    if not batch:
        return None
    return await process_batch(db, batch, provider=provider)


async def run_inspiration_generation_worker(*, poll_interval_seconds: float = 2.0) -> None:
    """Long-lived worker loop; one batch per iteration keeps provider pressure bounded."""
    from asyncio import sleep

    while True:
        db = SessionLocal()
        try:
            recover_stale_running_batches(db)
            processed = await process_next_batch(db)
        except Exception:
            db.rollback()
            processed = None
        finally:
            db.close()
        if processed is None:
            await sleep(max(0.2, poll_interval_seconds))
