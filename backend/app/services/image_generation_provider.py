"""Provider contract and implementations for image generation."""

from __future__ import annotations

import base64
import binascii
from io import BytesIO
from typing import Any, Protocol
from urllib.parse import urljoin
from uuid import uuid4

import httpx
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from backend.app.core.config import settings


class TextToImageRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "1:1"
    count: int = 1
    quality: str = "standard"


class ImageToImageRequest(TextToImageRequest):
    source_image: bytes
    source_mime_type: str
    strength: float | None = None


class GeneratedImagePayload(BaseModel):
    content: bytes | None = None
    temporary_url: str | None = None
    mime_type: str | None = None
    revised_prompt: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ImageGenerationProviderResult(BaseModel):
    images: list[GeneratedImagePayload]
    provider: str
    model: str
    request_id: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)


class ImageGenerationProviderError(RuntimeError):
    """Stable provider failure consumed by the image generation job runner."""

    def __init__(self, code: str, message: str, *, retryable: bool):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ImageGenerationProvider(Protocol):
    async def generate(self, request: TextToImageRequest) -> ImageGenerationProviderResult: ...

    async def edit(self, request: ImageToImageRequest) -> ImageGenerationProviderResult: ...


_RATIO_SIZES = {
    "1:1": (768, 768),
    "3:4": (720, 960),
    "4:3": (960, 720),
    "9:16": (576, 1024),
    "16:9": (1024, 576),
}

_OPENAI_RATIO_SIZES = {
    "1:1": "1024x1024",
    "3:4": "1024x1536",
    "9:16": "1024x1536",
    "4:3": "1536x1024",
    "16:9": "1536x1024",
}

PHOTOGRAPHY_EDIT_GUIDANCE = """你是摄影拍摄预演与创意沟通助手。
请把参考图片和用户指令理解为摄影视觉创作需求，优先围绕天气、时间、光线、色调、
摄影风格、拍摄环境、服装、妆造、道具、构图、景别、镜头语言、主体姿势和画面叙事进行修改。
保留用户明确要求保留的主体、姿势、位置、构图和身份特征，只修改用户要求改变的部分。
不要添加文字水印，也不要把生成结果描述为真实拍摄作品或真实客片。"""


class MockImageGenerationProvider:
    """Create real, valid PNG files without network access or credentials."""

    provider_name = "mock"
    model_name = "mock-image-v1"

    def _render(self, request: TextToImageRequest, index: int, mode: str) -> bytes:
        width, height = _RATIO_SIZES.get(request.aspect_ratio, _RATIO_SIZES["1:1"])
        colors = ((40, 73, 92), (169, 103, 83)) if index % 2 == 0 else ((55, 92, 71), (194, 154, 89))
        image = Image.new("RGB", (width, height), colors[0])
        draw = ImageDraw.Draw(image)
        for y in range(height):
            progress = y / max(height - 1, 1)
            color = tuple(round(colors[0][channel] * (1 - progress) + colors[1][channel] * progress) for channel in range(3))
            draw.line((0, y, width, y), fill=color)
        margin = max(24, width // 18)
        draw.rectangle((margin, margin, width - margin, height - margin), outline=(245, 242, 232), width=max(3, width // 180))
        draw.text((margin * 2, margin * 2), f"AI MOCK / {mode}\n{request.aspect_ratio} / {index + 1}", fill=(255, 255, 255))
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()

    async def generate(self, request: TextToImageRequest) -> ImageGenerationProviderResult:
        return ImageGenerationProviderResult(
            images=[GeneratedImagePayload(content=self._render(request, index, "TEXT"), mime_type="image/png") for index in range(request.count)],
            provider=self.provider_name,
            model=self.model_name,
            request_id=f"mock-{uuid4()}",
            usage={"images": request.count},
        )

    async def edit(self, request: ImageToImageRequest) -> ImageGenerationProviderResult:
        return ImageGenerationProviderResult(
            images=[GeneratedImagePayload(content=self._render(request, index, "EDIT"), mime_type="image/png") for index in range(request.count)],
            provider=self.provider_name,
            model=self.model_name,
            request_id=f"mock-{uuid4()}",
            usage={"images": request.count},
        )


class OpenAICompatibleImageGenerationProvider:
    """OpenAI-compatible JSON generation and multipart image editing adapter."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        generation_path: str = "/images/generations",
        edit_path: str = "/images/edits",
        response_format: str = "b64_json",
        timeout: int = 180,
        strength_parameter: str | None = "strength",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key:
            raise ImageGenerationProviderError("provider_auth_failed", "IMAGE_API_KEY is not configured", retryable=False)
        if not base_url:
            raise ImageGenerationProviderError("provider_configuration_error", "IMAGE_API_BASE is not configured", retryable=False)
        if response_format not in {"b64_json", "url"}:
            raise ImageGenerationProviderError("provider_configuration_error", "Unsupported IMAGE_RESPONSE_FORMAT", retryable=False)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") + "/"
        self.model = model
        self.model_name = model
        self.generation_url = urljoin(self.base_url, generation_path.lstrip("/"))
        self.edit_url = urljoin(self.base_url, edit_path.lstrip("/"))
        self.response_format = response_format
        self.timeout = timeout
        self.strength_parameter = (strength_parameter or "").strip() or None
        self.transport = transport

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    async def generate(self, request: TextToImageRequest) -> ImageGenerationProviderResult:
        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "n": request.count,
            "size": _OPENAI_RATIO_SIZES.get(request.aspect_ratio, "1024x1024"),
            "quality": request.quality,
            "response_format": self.response_format,
        }
        return self._parse_response(await self._post(json=payload, url=self.generation_url))

    async def edit(self, request: ImageToImageRequest) -> ImageGenerationProviderResult:
        if request.strength is not None and not self.strength_parameter:
            raise ImageGenerationProviderError(
                "provider_parameter_unsupported",
                "The configured image provider does not support edit strength",
                retryable=False,
            )
        prompt = f"{PHOTOGRAPHY_EDIT_GUIDANCE}\n\n用户修改指令：\n{request.prompt}"
        data: dict[str, str] = {
            "model": self.model,
            "prompt": prompt,
            "n": str(request.count),
            "size": _OPENAI_RATIO_SIZES.get(request.aspect_ratio, "1024x1024"),
            "quality": request.quality,
            "response_format": self.response_format,
        }
        if request.strength is not None and self.strength_parameter:
            data[self.strength_parameter] = str(request.strength)
        extension = "png" if request.source_mime_type == "image/png" else "jpg"
        files = {"image": (f"reference.{extension}", request.source_image, request.source_mime_type)}
        return self._parse_response(await self._post(data=data, files=files, url=self.edit_url))

    async def _post(self, *, url: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(url, headers=self._headers, **kwargs)
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            code, retryable = _classify_http_status(exc.response.status_code)
            raise ImageGenerationProviderError(code, _provider_error_message(exc.response), retryable=retryable) from exc
        except httpx.TimeoutException as exc:
            raise ImageGenerationProviderError("provider_timeout", "Image provider request timed out", retryable=True) from exc
        except httpx.RequestError as exc:
            raise ImageGenerationProviderError("provider_unavailable", "Image provider is unavailable", retryable=True) from exc

    def _parse_response(self, response: httpx.Response) -> ImageGenerationProviderResult:
        try:
            body = response.json()
        except ValueError as exc:
            raise ImageGenerationProviderError("invalid_provider_response", "Image provider returned invalid JSON", retryable=True) from exc
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list) or not data:
            raise ImageGenerationProviderError("invalid_provider_response", "Image provider returned no images", retryable=True)
        images: list[GeneratedImagePayload] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            content = None
            encoded = item.get("b64_json")
            if isinstance(encoded, str) and encoded:
                max_encoded_bytes = ((int(settings.IMAGE_MAX_DOWNLOAD_BYTES) + 2) // 3) * 4
                if len(encoded) > max_encoded_bytes:
                    raise ImageGenerationProviderError("invalid_provider_image", "Image provider returned oversized base64", retryable=True)
                try:
                    content = base64.b64decode(encoded, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ImageGenerationProviderError("invalid_provider_image", "Image provider returned invalid base64", retryable=True) from exc
            temporary_url = item.get("url") if isinstance(item.get("url"), str) else None
            if content is None and not temporary_url:
                continue
            metadata = {key: value for key, value in item.items() if key not in {"b64_json", "url", "revised_prompt"}}
            images.append(GeneratedImagePayload(
                content=content,
                temporary_url=temporary_url,
                mime_type="image/png" if content is not None else None,
                revised_prompt=item.get("revised_prompt"),
                provider_metadata=metadata,
            ))
        if not images:
            raise ImageGenerationProviderError("invalid_provider_response", "Image provider returned no usable images", retryable=True)
        request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
        if not request_id and isinstance(body, dict):
            request_id = body.get("id")
        usage = body.get("usage") if isinstance(body, dict) and isinstance(body.get("usage"), dict) else {}
        return ImageGenerationProviderResult(
            images=images,
            provider=self.provider_name,
            model=self.model,
            request_id=request_id,
            usage=usage,
        )


def _classify_http_status(status_code: int) -> tuple[str, bool]:
    if status_code in {401, 403}:
        return "provider_auth_failed", False
    if status_code == 429:
        return "provider_rate_limited", True
    if status_code in {408, 504}:
        return "provider_timeout", True
    if status_code in {400, 404, 409, 415, 422}:
        return "provider_rejected", False
    if status_code >= 500:
        return "provider_unavailable", True
    return "provider_rejected", False


def _provider_error_message(response: httpx.Response) -> str:
    message = f"Image provider request failed with HTTP {response.status_code}"
    try:
        body = response.json()
    except ValueError:
        return message
    if not isinstance(body, dict):
        return message
    error = body.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        message = error["message"]
    elif isinstance(error, str):
        message = error
    elif isinstance(body.get("message"), str):
        message = body["message"]
    return message[:500]


def get_image_generation_provider() -> ImageGenerationProvider:
    provider = settings.IMAGE_PROVIDER.lower()
    if provider == "mock":
        return MockImageGenerationProvider()
    if provider in {"openai", "openai_compatible"}:
        return OpenAICompatibleImageGenerationProvider(
            api_key=settings.IMAGE_API_KEY or "",
            base_url=settings.IMAGE_API_BASE or "",
            model=settings.IMAGE_MODEL,
            generation_path=settings.IMAGE_GENERATION_PATH,
            edit_path=settings.IMAGE_EDIT_PATH,
            response_format=settings.IMAGE_RESPONSE_FORMAT,
            timeout=settings.IMAGE_REQUEST_TIMEOUT,
            strength_parameter=settings.IMAGE_EDIT_STRENGTH_PARAMETER,
        )
    raise RuntimeError(f"Unsupported image generation provider: {provider}")
