"""AI 索引任务服务：入队、处理并后台执行资源索引任务。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.ai_production import AIIndexJob


def _now() -> datetime:
    """返回无时区的当前 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enqueue_index_job(
    db: Session,
    *,
    owner_user_id: int | None,
    reason: str,
    force: bool = False,
) -> AIIndexJob:
    """入队索引任务：复用进行中或失败的任务，否则创建新任务。"""
    existing = db.query(AIIndexJob).filter(
        AIIndexJob.owner_user_id == owner_user_id,
        AIIndexJob.status.in_(["pending", "processing", "failed"]),
        AIIndexJob.index_version == settings.AI_INDEX_VERSION,
    ).order_by(AIIndexJob.id.desc()).first()
    if existing:
        if force:
            existing.force = 1
        if existing.status == "failed":
            existing.status = "pending"
            existing.next_attempt_at = _now()
        db.commit()
        db.refresh(existing)
        return existing

    job = AIIndexJob(
        owner_user_id=owner_user_id,
        job_key=f"index:{owner_user_id or 'all'}:{settings.AI_INDEX_VERSION}:{uuid.uuid4().hex}",
        reason=reason[:80],
        status="pending",
        attempts=0,
        force=1 if force else 0,
        index_version=settings.AI_INDEX_VERSION,
        next_attempt_at=_now(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_index_jobs(db: Session, limit: int = 10) -> dict:
    """处理待执行与重试的索引任务，返回处理统计。"""
    now = _now()
    jobs = db.query(AIIndexJob).filter(
        AIIndexJob.status.in_(["pending", "failed"]),
        AIIndexJob.attempts < max(1, settings.AI_INDEX_MAX_ATTEMPTS),
        or_(AIIndexJob.next_attempt_at.is_(None), AIIndexJob.next_attempt_at <= now),
    ).order_by(AIIndexJob.created_at.asc(), AIIndexJob.id.asc()).limit(limit).all()
    completed = 0
    failed = 0
    for job in jobs:
        attempt = int(job.attempts or 0) + 1
        job.status = "processing"
        job.attempts = attempt
        job.started_at = now
        db.commit()
        try:
            from backend.app.services.ai_embedding_service import sync_resource_embeddings
            from backend.app.services.ai_multimodal_embedding_service import sync_resource_image_embeddings
            from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents

            documents = rebuild_ai_resource_documents(
                db,
                owner_user_id=job.owner_user_id,
                sync_embeddings=False,
            )
            text_result = sync_resource_embeddings(
                db,
                owner_user_id=job.owner_user_id,
                force=bool(job.force),
            )
            image_result = sync_resource_image_embeddings(
                db,
                owner_user_id=job.owner_user_id,
                force=bool(job.force),
            )
            job.status = "completed"
            job.result = {
                "documents": documents,
                "text_embeddings": text_result.__dict__,
                "image_embeddings": image_result.__dict__,
            }
            job.last_error = None
            job.next_attempt_at = None
            job.completed_at = _now()
            db.commit()
            completed += 1
        except Exception as exc:
            db.rollback()
            failed_job = db.query(AIIndexJob).filter(AIIndexJob.id == job.id).first()
            if failed_job:
                failed_job.status = "failed"
                failed_job.attempts = attempt
                failed_job.last_error = str(exc)[:2000]
                failed_job.next_attempt_at = _now() + timedelta(seconds=min(3600, 15 * (2 ** (attempt - 1))))
                db.commit()
            failed += 1
    return {"processed": len(jobs), "completed": completed, "failed": failed}


async def run_ai_index_worker(poll_interval_seconds: int | None = None) -> None:
    """后台循环执行索引任务，按间隔轮询。"""
    from backend.app.core.database import SessionLocal

    interval = max(2, poll_interval_seconds or settings.AI_INDEX_WORKER_POLL_SECONDS)
    while True:
        db = SessionLocal()
        try:
            process_index_jobs(db)
        except asyncio.CancelledError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(interval)
