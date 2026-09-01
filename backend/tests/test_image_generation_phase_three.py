"""Phase-three OpenAI-compatible provider, download safety and audit tests."""

import base64
import json
from io import BytesIO

import httpx
import pytest
from fastapi import HTTPException
from PIL import Image

from backend.app.core.config import settings
from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.schemas.ai import AIImageGenerationRequest
from backend.app.services import image_generation_job_service
from backend.app.services.image_generation_job_service import (
    _validate_public_https_url,
    get_image_generation_job,
    process_next_image_generation_job,
)
from backend.app.services.image_generation_provider import (
    GeneratedImagePayload,
    ImageGenerationProviderError,
    ImageGenerationProviderResult,
    ImageToImageRequest,
    OpenAICompatibleImageGenerationProvider,
    TextToImageRequest,
)
from backend.app.services.image_generation_workflow_service import create_image_generation_job


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (48, 64), (70, 110, 140)).save(output, "PNG")
    return output.getvalue()


def _provider(handler, **kwargs) -> OpenAICompatibleImageGenerationProvider:
    return OpenAICompatibleImageGenerationProvider(
        api_key="test-key",
        base_url="https://images.example.test/v1",
        model="image-model-v1",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_openai_compatible_generate_sends_json_and_parses_base64():
    encoded = base64.b64encode(_png_bytes()).decode("ascii")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://images.example.test/v1/images/generations"
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload == {
            "model": "image-model-v1",
            "prompt": "黄昏海边人像",
            "n": 2,
            "size": "1024x1536",
            "quality": "high",
            "response_format": "b64_json",
        }
        return httpx.Response(
            200,
            headers={"x-request-id": "request-123"},
            json={"data": [{"b64_json": encoded}, {"b64_json": encoded}], "usage": {"images": 2}},
        )

    result = await _provider(handler).generate(TextToImageRequest(
        prompt="黄昏海边人像", aspect_ratio="3:4", count=2, quality="high"
    ))

    assert result.request_id == "request-123"
    assert result.usage == {"images": 2}
    assert [image.content for image in result.images] == [_png_bytes(), _png_bytes()]


@pytest.mark.asyncio
async def test_openai_compatible_edit_sends_multipart_with_photography_guidance():
    encoded = base64.b64encode(_png_bytes()).decode("ascii")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://images.example.test/v1/images/edits"
        assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
        body = request.content.decode("utf-8", errors="ignore")
        assert 'name="image"; filename="reference.png"' in body
        assert 'name="strength"' in body
        assert "0.7" in body
        assert "天气" in body
        assert "主体姿势" in body
        assert "保留人物姿势，换成海边背景" in body
        return httpx.Response(200, json={"id": "edit-456", "data": [{"b64_json": encoded}]})

    result = await _provider(handler).edit(ImageToImageRequest(
        prompt="保留人物姿势，换成海边背景",
        source_image=_png_bytes(),
        source_mime_type="image/png",
        aspect_ratio="4:3",
        strength=0.7,
    ))

    assert result.request_id == "edit-456"
    assert result.images[0].content == _png_bytes()


@pytest.mark.asyncio
async def test_openai_compatible_parses_url_and_normalizes_rate_limit():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"data": [{"url": "https://cdn.example.test/result.png"}]})
        return httpx.Response(429, json={"error": {"message": "busy"}})

    provider = _provider(handler, response_format="url")
    result = await provider.generate(TextToImageRequest(prompt="夜景街拍"))
    assert result.images[0].temporary_url == "https://cdn.example.test/result.png"

    with pytest.raises(ImageGenerationProviderError) as error:
        await provider.generate(TextToImageRequest(prompt="夜景街拍"))
    assert error.value.code == "provider_rate_limited"
    assert error.value.retryable is True
    assert str(error.value) == "busy"


def test_provider_image_url_rejects_private_and_non_https_targets():
    for url in ("http://example.com/image.png", "https://127.0.0.1/image.png", "https://169.254.169.254/latest/meta-data"):
        with pytest.raises(ImageGenerationProviderError) as error:
            _validate_public_https_url(url)
        assert error.value.code == "invalid_provider_image_url"


def test_generation_enforces_active_and_daily_limits(db, customer_user, monkeypatch):
    conversation = AIConversation(user_id=customer_user.id, title="limits")
    db.add(conversation)
    db.flush()
    first_message = AIMessage(conversation_id=conversation.id, role="user", content="第一张")
    db.add(first_message)
    db.commit()
    db.refresh(conversation)
    db.refresh(first_message)

    monkeypatch.setattr(settings, "IMAGE_MAX_ACTIVE_JOBS_PER_USER", 1)
    first = create_image_generation_job(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        source_message_id=first_message.id,
        prompt=first_message.content,
        attachments=[],
        request=AIImageGenerationRequest(mode="text_to_image"),
        source="explicit_button",
    )
    with pytest.raises(HTTPException) as concurrency_error:
        create_image_generation_job(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            source_message_id=first_message.id,
            prompt="第二张",
            attachments=[],
            request=AIImageGenerationRequest(mode="text_to_image"),
            source="explicit_button",
        )
    assert concurrency_error.value.detail["code"] == "generation_concurrency_exceeded"

    first.status = "completed"
    first.stage = "completed"
    db.commit()
    monkeypatch.setattr(settings, "IMAGE_MAX_ACTIVE_JOBS_PER_USER", 2)
    monkeypatch.setattr(settings, "IMAGE_DAILY_LIMIT_PER_USER", 1)
    with pytest.raises(HTTPException) as quota_error:
        create_image_generation_job(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            source_message_id=first_message.id,
            prompt="第二张",
            attachments=[],
            request=AIImageGenerationRequest(mode="text_to_image"),
            source="explicit_button",
        )
    assert quota_error.value.detail["code"] == "generation_quota_exceeded"


@pytest.mark.asyncio
async def test_job_persists_provider_result_and_call_audit(db, customer_user, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    async def download_result(url: str):
        assert url == "https://cdn.example.test/generated.png"
        return _png_bytes(), "image/png"

    monkeypatch.setattr(image_generation_job_service, "_download_provider_image", download_result)
    conversation = AIConversation(user_id=customer_user.id, title="phase three")
    db.add(conversation)
    db.flush()
    message = AIMessage(conversation_id=conversation.id, role="user", content="清冷棚拍人像")
    db.add(message)
    db.commit()
    db.refresh(conversation)
    db.refresh(message)
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

    class AuditProvider:
        provider_name = "test_provider"
        model_name = "test-image-model"

        async def generate(self, request):
            return ImageGenerationProviderResult(
                images=[GeneratedImagePayload(temporary_url="https://cdn.example.test/generated.png")],
                provider=self.provider_name,
                model=self.model_name,
                request_id="audit-request-id",
                usage={"images": 1},
            )

        async def edit(self, request):
            raise AssertionError("not used")

    assert await process_next_image_generation_job(db, provider=AuditProvider()) == "completed"
    payload = get_image_generation_job(db, owner_id=customer_user.id, job_id=job.id)
    db.refresh(job)

    assert payload["provider"] == "test_provider"
    assert payload["model"] == "test-image-model"
    assert payload["result_images"][0]["url"].startswith("/static/ai-generated/")
    assert job.provider_request_id == "audit-request-id"
    assert job.usage_metadata["images"] == 1
    assert job.usage_metadata["audit"]["source"] == "explicit_button"
    assert job.usage_metadata["audit"]["requested_count"] == 1
    assert job.usage_metadata["audit"]["saved_count"] == 1
    assert job.usage_metadata["audit"]["provider_latency_ms"] >= 0
    assert job.usage_metadata["audit"]["asset_save_latency_ms"] >= 0
