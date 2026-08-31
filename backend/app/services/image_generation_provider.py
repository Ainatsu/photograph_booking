"""Provider contract and deterministic mock for image generation."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Protocol
from uuid import uuid4

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
    strength: float = 0.65


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


def get_image_generation_provider() -> ImageGenerationProvider:
    provider = settings.IMAGE_PROVIDER.lower()
    if provider == "mock":
        return MockImageGenerationProvider()
    raise RuntimeError(f"Unsupported image generation provider: {provider}")
