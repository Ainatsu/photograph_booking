"""Execution, recovery, retry and serialization for image generation jobs."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageOps
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.agent_task import AgentTaskDraft
from backend.app.models.image_generation import ImageGenerationAsset, ImageGenerationJob
from backend.app.services.image_generation_provider import (
    ImageGenerationProvider,
    ImageToImageRequest,
    TextToImageRequest,
    get_image_generation_provider,
)

MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (5, 20)
STALE_RUNNING_SECONDS = 240


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owned_job(db: Session, owner_id: int, job_id: int) -> ImageGenerationJob:
    job = db.query(ImageGenerationJob).filter(ImageGenerationJob.id == job_id, ImageGenerationJob.owner_id == owner_id).first()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "image_generation_not_found"})
    return job


def _assets(db: Session, job_id: int, role: str) -> list[ImageGenerationAsset]:
    return (
        db.query(ImageGenerationAsset)
        .filter(ImageGenerationAsset.job_id == job_id, ImageGenerationAsset.role == role)
        .order_by(ImageGenerationAsset.position.asc())
        .all()
    )


def _asset_dict(asset: ImageGenerationAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "url": asset.storage_url,
        "thumbnail_url": asset.thumbnail_url,
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "size_bytes": asset.size_bytes,
        "position": asset.position,
    }


def serialize_image_generation_job(db: Session, job: ImageGenerationJob) -> dict[str, Any]:
    sources = _assets(db, job.id, "source")
    results = _assets(db, job.id, "result")
    requested = int((job.parameters or {}).get("count", 1))
    active = job.status in {"queued", "generating", "retry_wait"}
    return {
        "job_id": job.id,
        "task_id": job.agent_task_id,
        "mode": job.mode,
        "status": job.status,
        "stage": job.stage,
        "progress": {"completed": len(results), "total": requested},
        "source_images": [_asset_dict(item) for item in sources],
        "result_images": [_asset_dict(item) for item in results],
        "parameters": job.parameters or {},
        "provider": job.provider,
        "model": job.model,
        "can_retry": job.status in {"failed", "partial"},
        "can_cancel": active,
        "error": ({"code": job.last_error_code, "message": job.last_error} if job.last_error_code else None),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def get_image_generation_job(db: Session, *, owner_id: int, job_id: int) -> dict[str, Any]:
    return serialize_image_generation_job(db, _owned_job(db, owner_id, job_id))


def cancel_image_generation_job(db: Session, *, owner_id: int, job_id: int) -> dict[str, Any]:
    job = _owned_job(db, owner_id, job_id)
    if job.status in {"queued", "retry_wait"} or (job.status == "generating" and job.stage in {"validating_input", "preparing_request"}):
        job.status = "cancelled"
        job.stage = "cancelled"
        job.completed_at = _now()
        task = db.query(AgentTaskDraft).filter(AgentTaskDraft.id == job.agent_task_id).first()
        if task:
            task.status = "cancelled"
            task.completed_at = _now()
        db.commit()
        db.refresh(job)
    return serialize_image_generation_job(db, job)


def retry_image_generation_job(db: Session, *, owner_id: int, job_id: int) -> dict[str, Any]:
    job = _owned_job(db, owner_id, job_id)
    if job.status not in {"failed", "partial"}:
        raise HTTPException(status_code=409, detail={"code": "image_generation_not_retryable"})
    job.status = "queued"
    job.stage = "queued"
    job.attempts = 0
    job.available_at = _now()
    job.started_at = None
    job.completed_at = None
    job.last_error_code = None
    job.last_error = None
    task = db.query(AgentTaskDraft).filter(AgentTaskDraft.id == job.agent_task_id).first()
    if task:
        task.status = "generating"
        task.completed_at = None
    db.commit()
    db.refresh(job)
    return serialize_image_generation_job(db, job)


def recover_stale_image_generation_jobs(db: Session, *, stale_seconds: int = STALE_RUNNING_SECONDS) -> int:
    cutoff = _now() - timedelta(seconds=stale_seconds)
    jobs = (
        db.query(ImageGenerationJob)
        .filter(
            ImageGenerationJob.status == "generating",
            or_(ImageGenerationJob.started_at < cutoff, ImageGenerationJob.started_at.is_(None)),
        )
        .all()
    )
    for job in jobs:
        job.status = "queued"
        job.stage = "queued"
        job.available_at = _now()
        job.last_error_code = "stale_running_recovered"
        job.started_at = None
    if jobs:
        db.commit()
    return len(jobs)


def claim_next_image_generation_job(db: Session) -> ImageGenerationJob | None:
    now = _now()
    job = (
        db.query(ImageGenerationJob)
        .filter(ImageGenerationJob.status.in_(["queued", "retry_wait"]), ImageGenerationJob.available_at <= now)
        .order_by(ImageGenerationJob.created_at.asc(), ImageGenerationJob.id.asc())
        .first()
    )
    if not job:
        return None
    job.status = "generating"
    job.stage = "validating_input"
    job.attempts = (job.attempts or 0) + 1
    job.started_at = now
    db.commit()
    db.refresh(job)
    return job


def _local_path_from_url(url: str) -> str:
    if not url.startswith("/static/"):
        raise ValueError("reference_image_not_local")
    relative = url.removeprefix("/static/").replace("/", os.sep)
    root = os.path.abspath(settings.UPLOAD_DIR)
    path = os.path.abspath(os.path.join(root, relative))
    if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
        raise ValueError("reference_image_not_found")
    return path


def _save_result_asset(db: Session, job: ImageGenerationJob, payload: bytes, position: int, metadata: dict[str, Any]) -> ImageGenerationAsset:
    max_bytes = int(settings.IMAGE_MAX_DOWNLOAD_BYTES)
    if not payload or len(payload) > max_bytes:
        raise ValueError("invalid_provider_image")
    with Image.open(BytesIO(payload)) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        if image.width <= 0 or image.height <= 0:
            raise ValueError("invalid_provider_image")
        image = image.convert("RGB")
        width, height = image.size
        folder = os.path.join(settings.UPLOAD_DIR, "ai-generated", str(job.owner_id), str(job.id))
        os.makedirs(folder, exist_ok=True)
        filename = f"result-{position}.jpg"
        path = os.path.join(folder, filename)
        image.save(path, "JPEG", quality=92, optimize=True)
        thumb = image.copy()
        thumb.thumbnail((640, 640), Image.Resampling.LANCZOS)
        thumb_dir = os.path.join(folder, "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"result-{position}-thumb.jpg")
        thumb.save(thumb_path, "JPEG", quality=78, optimize=True)
    with open(path, "rb") as saved:
        digest = hashlib.sha256(saved.read()).hexdigest()
    relative_folder = f"ai-generated/{job.owner_id}/{job.id}"
    asset = ImageGenerationAsset(
        job_id=job.id,
        role="result",
        position=position,
        storage_url=f"/static/{relative_folder}/{filename}",
        thumbnail_url=f"/static/{relative_folder}/thumbnails/result-{position}-thumb.jpg",
        mime_type="image/jpeg",
        width=width,
        height=height,
        size_bytes=os.path.getsize(path),
        sha256=digest,
        provider_metadata=metadata,
    )
    db.add(asset)
    db.flush()
    return asset


def _classify_error(exc: Exception) -> tuple[str, bool]:
    stable_codes = {
        "invalid_provider_image",
        "reference_image_not_found",
        "reference_image_not_local",
        "reference_image_too_large",
    }
    code = str(exc) if str(exc) in stable_codes else "provider_unavailable"
    return code, code in {"provider_unavailable", "invalid_provider_image"}


async def process_image_generation_job(db: Session, job: ImageGenerationJob, *, provider: ImageGenerationProvider | None = None) -> str:
    provider = provider or get_image_generation_provider()
    parameters = job.parameters or {}
    try:
        job.stage = "preparing_request"
        db.commit()
        common = {
            "prompt": job.prompt,
            "aspect_ratio": parameters.get("aspect_ratio", "1:1"),
            "count": int(parameters.get("count", 1)),
            "quality": parameters.get("quality", "standard"),
        }
        job.stage = "calling_provider"
        db.commit()
        if job.mode == "image_to_image":
            source = _assets(db, job.id, "source")[0]
            path = _local_path_from_url(source.storage_url)
            with open(path, "rb") as source_file:
                source_bytes = source_file.read()
            if len(source_bytes) > int(settings.IMAGE_MAX_UPLOAD_BYTES):
                raise ValueError("reference_image_too_large")
            with Image.open(BytesIO(source_bytes)) as source_image:
                source_image.verify()
            result = await provider.edit(ImageToImageRequest(
                **common,
                source_image=source_bytes,
                source_mime_type=source.mime_type,
                strength=float(parameters.get("strength", 0.65)),
            ))
        else:
            result = await provider.generate(TextToImageRequest(**common))
        job.provider = result.provider
        job.model = result.model
        job.provider_request_id = result.request_id
        job.usage_metadata = result.usage
        job.stage = "saving_assets"
        db.commit()
        existing_positions = {asset.position for asset in _assets(db, job.id, "result")}
        failures = 0
        for position, image in enumerate(result.images):
            if position in existing_positions:
                continue
            if image.content is None:
                failures += 1
                continue
            try:
                _save_result_asset(db, job, image.content, position, image.provider_metadata)
            except Exception:
                failures += 1
        db.flush()
        saved_count = len(_assets(db, job.id, "result"))
        requested = int(parameters.get("count", 1))
        if saved_count >= requested:
            job.status = "completed"
        elif saved_count > 0:
            job.status = "partial"
            job.last_error_code = "asset_save_failed"
            job.last_error = f"{failures or requested - saved_count} result asset(s) failed"
        else:
            raise ValueError("invalid_provider_image")
        job.stage = job.status
        job.completed_at = _now()
        job.started_at = None
        task = db.query(AgentTaskDraft).filter(AgentTaskDraft.id == job.agent_task_id).first()
        if task:
            task.status = "completed" if saved_count else "failed"
            task.completed_at = _now()
            task.result = {"job_id": job.id, "status": job.status, "result_count": saved_count}
        db.commit()
        return job.status
    except Exception as exc:
        code, retryable = _classify_error(exc)
        job.last_error_code = code
        job.last_error = str(exc)[:500]
        job.started_at = None
        if retryable and (job.attempts or 0) < MAX_ATTEMPTS:
            delay_index = min(max((job.attempts or 1) - 1, 0), len(RETRY_DELAYS_SECONDS) - 1)
            job.status = "retry_wait"
            job.stage = "retry_wait"
            job.available_at = _now() + timedelta(seconds=RETRY_DELAYS_SECONDS[delay_index])
        else:
            job.status = "failed"
            job.stage = "failed"
            job.completed_at = _now()
            task = db.query(AgentTaskDraft).filter(AgentTaskDraft.id == job.agent_task_id).first()
            if task:
                task.status = "failed"
                task.result = {"job_id": job.id, "status": "failed", "error_code": code}
        db.commit()
        return job.status


async def process_next_image_generation_job(db: Session, *, provider: ImageGenerationProvider | None = None) -> str | None:
    job = claim_next_image_generation_job(db)
    if not job:
        return None
    return await process_image_generation_job(db, job, provider=provider)


async def run_image_generation_worker(*, poll_interval_seconds: float = 2.0) -> None:
    from asyncio import sleep

    while True:
        db = SessionLocal()
        try:
            recover_stale_image_generation_jobs(db)
            processed = await process_next_image_generation_job(db)
        except Exception:
            db.rollback()
            processed = None
        finally:
            db.close()
        if processed is None:
            await sleep(max(0.2, poll_interval_seconds))
