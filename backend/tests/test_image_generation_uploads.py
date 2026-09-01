"""AI reference image upload normalization and audit metadata tests."""

from io import BytesIO

import pytest
from PIL import Image

from backend.app.core.config import settings
from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.models.image_generation import ImageGenerationAsset
from backend.app.schemas.ai import AIImageGenerationRequest
from backend.app.services.image_generation_job_service import process_next_image_generation_job
from backend.app.services.image_generation_provider import MockImageGenerationProvider
from backend.app.services.image_generation_workflow_service import create_image_generation_job


def _jpeg_bytes(size: tuple[int, int] = (320, 240), quality: int = 95) -> bytes:
    output = BytesIO()
    Image.effect_noise(size, 80).convert("RGB").save(output, "JPEG", quality=quality)
    return output.getvalue()


def test_ai_upload_normalizes_dimensions_and_returns_audit_metadata(
    client,
    customer_headers,
    tmp_path,
    monkeypatch,
):
    source = _jpeg_bytes((640, 480))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "IMAGE_UPLOAD_MAX_DIMENSION", 512)
    monkeypatch.setattr(settings, "IMAGE_UPLOAD_TARGET_BYTES", 100_000)
    monkeypatch.setattr(settings, "IMAGE_MAX_UPLOAD_BYTES", 150_000)
    monkeypatch.setattr(settings, "IMAGE_MAX_SOURCE_UPLOAD_BYTES", 1_000_000)

    response = client.post(
        "/api/v1/ai/uploads",
        headers=customer_headers,
        files={"file": ("reference.jpg", source, "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mime_type"] == "image/jpeg"
    assert payload["width"] == 512
    assert payload["height"] == 384
    assert payload["size_bytes"] <= 100_000
    assert payload["original_width"] == 640
    assert payload["original_height"] == 480
    assert payload["original_size_bytes"] == len(source)
    assert payload["normalized"] is True
    assert len(payload["sha256"]) == 64
    assert payload["url"].startswith(f"/static/ai/")
    assert payload["thumb_url"].startswith("/static/ai/")

    stored = tmp_path / payload["url"].removeprefix("/static/")
    with Image.open(stored) as image:
        assert image.size == (512, 384)


def test_ai_upload_rejects_source_above_preprocessing_limit(
    client,
    customer_headers,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "IMAGE_MAX_UPLOAD_BYTES", 100)
    monkeypatch.setattr(settings, "IMAGE_MAX_SOURCE_UPLOAD_BYTES", 100)

    response = client.post(
        "/api/v1/ai/uploads",
        headers=customer_headers,
        files={"file": ("reference.jpg", b"x" * 101, "image/jpeg")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "reference_image_source_too_large"


def test_ai_upload_rejects_excessive_pixel_dimensions(
    client,
    customer_headers,
    tmp_path,
    monkeypatch,
):
    source = _jpeg_bytes((100, 100))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "IMAGE_MAX_SOURCE_UPLOAD_BYTES", 1_000_000)
    monkeypatch.setattr(settings, "IMAGE_UPLOAD_MAX_PIXELS", 9_999)

    response = client.post(
        "/api/v1/ai/uploads",
        headers=customer_headers,
        files={"file": ("reference.jpg", source, "image/jpeg")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "reference_image_dimensions_too_large"


def test_generation_job_persists_source_upload_metadata(db, customer_user):
    conversation = AIConversation(user_id=customer_user.id, title="upload audit")
    db.add(conversation)
    db.flush()
    message = AIMessage(conversation_id=conversation.id, role="user", content="美化这张照片")
    db.add(message)
    db.commit()

    job = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=message.id,
        prompt=message.content,
        attachments=[{
            "type": "image",
            "url": f"/static/ai/{customer_user.id}/reference.jpg",
            "mime_type": "image/jpeg",
            "thumb_url": f"/static/ai/{customer_user.id}/thumbnails/reference_thumb.jpg",
            "width": 2048,
            "height": 1365,
            "size_bytes": 2_000_000,
            "sha256": "a" * 64,
            "original_width": 6240,
            "original_height": 4160,
            "original_size_bytes": 14_287_115,
            "normalized": True,
        }],
        request=AIImageGenerationRequest(mode="image_to_image", strength=0.65),
        source="explicit_button",
    )

    asset = db.query(ImageGenerationAsset).filter_by(job_id=job.id, role="source").one()
    assert asset.thumbnail_url.endswith("reference_thumb.jpg")
    assert (asset.width, asset.height, asset.size_bytes) == (2048, 1365, 2_000_000)
    assert asset.sha256 == "a" * 64
    assert asset.provider_metadata["upload"] == {
        "original_width": 6240,
        "original_height": 4160,
        "original_size_bytes": 14_287_115,
        "normalized": True,
    }


@pytest.mark.asyncio
async def test_worker_normalizes_oversized_legacy_source_before_retry(
    db,
    customer_user,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "IMAGE_MAX_UPLOAD_BYTES", 100_000)
    monkeypatch.setattr(settings, "IMAGE_UPLOAD_TARGET_BYTES", 80_000)
    monkeypatch.setattr(settings, "IMAGE_UPLOAD_MAX_DIMENSION", 512)
    monkeypatch.setattr(settings, "IMAGE_UPLOAD_MAX_PIXELS", 50_000_000)
    reference_dir = tmp_path / "ai" / str(customer_user.id)
    reference_dir.mkdir(parents=True)
    reference = _jpeg_bytes((1024, 1024), quality=100)
    assert len(reference) > settings.IMAGE_MAX_UPLOAD_BYTES
    (reference_dir / "legacy.jpg").write_bytes(reference)

    conversation = AIConversation(user_id=customer_user.id, title="legacy retry")
    db.add(conversation)
    db.flush()
    message = AIMessage(conversation_id=conversation.id, role="user", content="美化旧参考图")
    db.add(message)
    db.commit()
    job = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=message.id,
        prompt=message.content,
        attachments=[{
            "type": "image",
            "url": f"/static/ai/{customer_user.id}/legacy.jpg",
            "mime_type": "image/jpeg",
        }],
        request=AIImageGenerationRequest(mode="image_to_image", strength=0.65),
        source="explicit_button",
    )

    assert await process_next_image_generation_job(db, provider=MockImageGenerationProvider()) == "completed"
    asset = db.query(ImageGenerationAsset).filter_by(job_id=job.id, role="source").one()
    assert asset.storage_url.endswith("legacy_normalized.jpg")
    assert asset.size_bytes <= settings.IMAGE_UPLOAD_TARGET_BYTES
    assert (asset.provider_metadata or {})["upload"]["normalized_by"] == "worker_retry"
