"""Execution, recovery, retry and serialization for image generation jobs."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
from asyncio import Semaphore
from datetime import datetime, timedelta, timezone
from io import BytesIO
from time import perf_counter
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException
from PIL import Image, ImageOps
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.agent_task import AgentTaskDraft
from backend.app.models.ai_conversation import AIMessage
from backend.app.models.image_generation import ImageGenerationAsset, ImageGenerationJob
from backend.app.schemas.ai import AIImageGenerationRequest
from backend.app.services.image_generation_provider import (
    ImageGenerationProvider,
    ImageGenerationProviderError,
    ImageToImageRequest,
    TextToImageRequest,
    get_image_generation_provider,
)
from backend.app.utils.file_upload import _normalize_ai_image, create_thumbnail_for_url

MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (5, 20)
STALE_RUNNING_SECONDS = 240
_provider_semaphore: Semaphore | None = None
_provider_semaphore_limit: int | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _get_provider_semaphore() -> Semaphore:
    global _provider_semaphore, _provider_semaphore_limit
    limit = max(1, int(settings.IMAGE_MAX_CONCURRENCY))
    if _provider_semaphore is None or _provider_semaphore_limit != limit:
        _provider_semaphore = Semaphore(limit)
        _provider_semaphore_limit = limit
    return _provider_semaphore


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
        "storage_url": asset.storage_url,
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


def regenerate_image_generation_job(db: Session, *, owner_id: int, job_id: int) -> dict[str, Any]:
    """Create a fresh job while inheriting the original prompt, media and parameters."""
    original = _owned_job(db, owner_id, job_id)
    if original.status in {"queued", "generating", "retry_wait"}:
        raise HTTPException(status_code=409, detail={"code": "image_generation_still_active"})

    from backend.app.services.image_generation_workflow_service import create_image_generation_job

    inherited = dict(original.parameters or {})
    request = AIImageGenerationRequest(
        mode=original.mode,
        aspect_ratio=inherited.get("aspect_ratio", "1:1"),
        count=int(inherited.get("count", 1)),
        quality=inherited.get("quality", "standard"),
        strength=inherited.get("strength") if original.mode == "image_to_image" else None,
    )
    attachments = [
        {
            "type": "image",
            "url": asset.storage_url,
            "mime_type": asset.mime_type,
            "thumb_url": asset.thumbnail_url,
        }
        for asset in _assets(db, original.id, "source")
    ]
    regenerated = create_image_generation_job(
        db,
        user_id=owner_id,
        conversation_id=original.conversation_id,
        source_message_id=original.source_message_id,
        prompt=original.prompt,
        attachments=attachments,
        request=request,
        source="regenerate",
    )
    parameters = dict(regenerated.parameters or {})
    parameters["regenerated_from_job_id"] = original.id
    regenerated.parameters = parameters

    assistant_messages = (
        db.query(AIMessage)
        .filter(
            AIMessage.conversation_id == original.conversation_id,
            AIMessage.role == "assistant",
        )
        .order_by(AIMessage.id.desc())
        .all()
    )
    for message in assistant_messages:
        metadata = dict(message.message_metadata or {})
        reference = metadata.get("image_generation")
        if isinstance(reference, dict) and reference.get("job_id") == original.id:
            metadata["image_generation"] = {
                **reference,
                "job_id": regenerated.id,
                "task_id": regenerated.agent_task_id,
                "status": regenerated.status,
                "mode": regenerated.mode,
                "regenerated_from_job_id": original.id,
            }
            message.message_metadata = metadata
            break

    db.commit()
    db.refresh(regenerated)
    return serialize_image_generation_job(db, regenerated)


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


def _validate_public_https_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ImageGenerationProviderError("invalid_provider_image_url", "Provider image URL must be public HTTPS", retryable=False)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ImageGenerationProviderError("provider_download_failed", "Provider image host could not be resolved", retryable=True) from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ImageGenerationProviderError("invalid_provider_image_url", "Provider image URL resolves to a non-public address", retryable=False)


async def _download_provider_image(url: str) -> tuple[bytes, str | None]:
    current_url = url
    max_redirects = max(0, int(settings.IMAGE_MAX_DOWNLOAD_REDIRECTS))
    max_bytes = int(settings.IMAGE_MAX_DOWNLOAD_BYTES)
    timeout = httpx.Timeout(settings.IMAGE_REQUEST_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for redirect_count in range(max_redirects + 1):
            _validate_public_https_url(current_url)
            try:
                async with client.stream("GET", current_url, headers={"Accept": "image/*"}) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location or redirect_count >= max_redirects:
                            raise ImageGenerationProviderError("provider_download_failed", "Provider image redirect limit exceeded", retryable=True)
                        current_url = urljoin(current_url, location)
                        continue
                    response.raise_for_status()
                    content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                    if not content_type.startswith("image/"):
                        raise ImageGenerationProviderError("invalid_provider_image", "Provider image response has an invalid content type", retryable=True)
                    content_length = response.headers.get("content-length")
                    if content_length:
                        try:
                            declared_size = int(content_length)
                        except ValueError:
                            declared_size = 0
                        if declared_size > max_bytes:
                            raise ImageGenerationProviderError("invalid_provider_image", "Provider image response is too large", retryable=True)
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > max_bytes:
                            raise ImageGenerationProviderError("invalid_provider_image", "Provider image response is too large", retryable=True)
                    return bytes(chunks), content_type
            except ImageGenerationProviderError:
                raise
            except httpx.TimeoutException as exc:
                raise ImageGenerationProviderError("provider_timeout", "Provider image download timed out", retryable=True) from exc
            except httpx.HTTPStatusError as exc:
                retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
                code = "provider_rate_limited" if exc.response.status_code == 429 else "provider_download_failed"
                raise ImageGenerationProviderError(code, "Provider image download failed", retryable=retryable) from exc
            except httpx.RequestError as exc:
                raise ImageGenerationProviderError("provider_download_failed", "Provider image download failed", retryable=True) from exc
    raise ImageGenerationProviderError("provider_download_failed", "Provider image download failed", retryable=True)


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
    if isinstance(exc, ImageGenerationProviderError):
        return exc.code, exc.retryable
    stable_codes = {
        "invalid_provider_image",
        "reference_image_required",
        "reference_image_not_found",
        "reference_image_not_local",
        "reference_image_too_large",
        "reference_image_source_too_large",
        "reference_image_dimensions_too_large",
    }
    code = str(exc) if str(exc) in stable_codes else "provider_unavailable"
    return code, code in {"provider_unavailable", "invalid_provider_image"}


def _normalize_legacy_source_asset(
    db: Session,
    source: ImageGenerationAsset,
    path: str,
    source_bytes: bytes,
) -> bytes:
    try:
        normalized, metadata = _normalize_ai_image(source_bytes)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        raise ValueError(detail.get("code") or "reference_image_too_large") from exc

    normalized_path = f"{os.path.splitext(path)[0]}_normalized{metadata['extension']}"
    with open(normalized_path, "wb") as normalized_file:
        normalized_file.write(normalized)
    relative_path = os.path.relpath(normalized_path, settings.UPLOAD_DIR).replace(os.sep, "/")
    source.storage_url = f"/static/{relative_path}"
    source.thumbnail_url = create_thumbnail_for_url(source.storage_url)
    source.mime_type = metadata["mime_type"]
    source.width = metadata["width"]
    source.height = metadata["height"]
    source.size_bytes = metadata["size_bytes"]
    source.sha256 = metadata["sha256"]
    source.provider_metadata = {
        **(source.provider_metadata or {}),
        "upload": {
            "original_width": metadata["original_width"],
            "original_height": metadata["original_height"],
            "original_size_bytes": metadata["original_size_bytes"],
            "normalized": True,
            "normalized_by": "worker_retry",
        },
    }
    db.commit()
    return normalized


async def process_image_generation_job(db: Session, job: ImageGenerationJob, *, provider: ImageGenerationProvider | None = None) -> str:
    parameters = job.parameters or {}
    total_started = perf_counter()
    provider_started: float | None = None
    concurrency_wait_ms = 0
    queue_wait_ms = 0
    created_at = _aware(job.created_at)
    if created_at:
        queue_wait_ms = max(0, round((_now() - created_at).total_seconds() * 1000))
    try:
        if provider is None:
            job.provider = settings.IMAGE_PROVIDER
            job.model = settings.IMAGE_MODEL
            provider = get_image_generation_provider()
        job.provider = getattr(provider, "provider_name", None)
        job.model = getattr(provider, "model_name", None)
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
        concurrency_started = perf_counter()
        async with _get_provider_semaphore():
            concurrency_wait_ms = _elapsed_ms(concurrency_started)
            provider_started = perf_counter()
            if job.mode == "image_to_image":
                source_assets = _assets(db, job.id, "source")
                if not source_assets:
                    raise ValueError("reference_image_required")
                source = source_assets[0]
                path = _local_path_from_url(source.storage_url)
                with open(path, "rb") as source_file:
                    source_bytes = source_file.read()
                if len(source_bytes) > int(settings.IMAGE_MAX_UPLOAD_BYTES):
                    source_bytes = _normalize_legacy_source_asset(db, source, path, source_bytes)
                with Image.open(BytesIO(source_bytes)) as source_image:
                    source_image.verify()
                result = await provider.edit(ImageToImageRequest(
                    **common,
                    source_image=source_bytes,
                    source_mime_type=source.mime_type,
                    strength=float(parameters["strength"]) if "strength" in parameters else None,
                ))
            else:
                result = await provider.generate(TextToImageRequest(**common))
        provider_latency_ms = _elapsed_ms(provider_started)
        job.provider = result.provider
        job.model = result.model
        job.provider_request_id = result.request_id
        job.stage = "saving_assets"
        db.commit()
        save_started = perf_counter()
        requested = int(parameters.get("count", 1))
        existing_positions = {asset.position for asset in _assets(db, job.id, "result")}
        failures = 0
        last_asset_error: Exception | None = None
        for position, image in enumerate(result.images[:requested]):
            if position in existing_positions:
                continue
            try:
                payload = image.content
                mime_type = image.mime_type
                if payload is None and image.temporary_url:
                    payload, mime_type = await _download_provider_image(image.temporary_url)
                if payload is None:
                    raise ImageGenerationProviderError("invalid_provider_image", "Provider returned an empty image", retryable=True)
                metadata = dict(image.provider_metadata)
                if image.revised_prompt:
                    metadata["revised_prompt"] = image.revised_prompt
                if mime_type:
                    metadata["source_mime_type"] = mime_type
                _save_result_asset(db, job, payload, position, metadata)
            except Exception as exc:
                failures += 1
                last_asset_error = exc
        db.flush()
        asset_save_latency_ms = _elapsed_ms(save_started)
        saved_count = len(_assets(db, job.id, "result"))
        job.usage_metadata = {
            **(result.usage or {}),
            "audit": {
                "source": parameters.get("source"),
                "queue_wait_ms": queue_wait_ms,
                "concurrency_wait_ms": concurrency_wait_ms,
                "provider_latency_ms": provider_latency_ms,
                "asset_save_latency_ms": asset_save_latency_ms,
                "total_latency_ms": _elapsed_ms(total_started),
                "requested_count": requested,
                "saved_count": saved_count,
            },
        }
        if saved_count >= requested:
            job.status = "completed"
        elif saved_count > 0:
            job.status = "partial"
            job.last_error_code = "asset_save_failed"
            job.last_error = f"{failures or requested - saved_count} result asset(s) failed"
        else:
            raise last_asset_error or ValueError("invalid_provider_image")
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
        audit = dict(job.usage_metadata or {})
        audit["audit"] = {
            **(audit.get("audit") or {}),
            "source": parameters.get("source"),
            "queue_wait_ms": queue_wait_ms,
            "concurrency_wait_ms": concurrency_wait_ms,
            "total_latency_ms": _elapsed_ms(total_started),
            "requested_count": int(parameters.get("count", 1)),
            "error_code": code,
        }
        if provider_started is not None:
            audit["audit"]["provider_latency_ms"] = _elapsed_ms(provider_started)
        job.usage_metadata = audit
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
