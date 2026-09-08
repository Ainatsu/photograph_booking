"""Internal multimodal agent that creates validated inspiration content."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.inspiration import InspirationBatchResult, InspirationSummaryResult
from backend.app.services.ai_provider import AIProvider, get_ai_provider


INSPIRATION_AGENT_BATCH_PROMPT_VERSION = "inspiration_agent_batch_v3"
INSPIRATION_SUMMARY_PROMPT_VERSION = "inspiration_summary_v1"


class InspirationProviderUnavailableError(RuntimeError):
    """Raised when the configured provider returned a degraded fallback."""


class InspirationAgentImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment_index: int = Field(ge=0)
    provider_image_url: str = Field(min_length=1)
    mime_type: str = Field(min_length=1, max_length=100)


class InspirationAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=36)
    reference_text: str = Field(default="", max_length=8000)
    images: list[InspirationAgentImage] = Field(min_length=1, max_length=12)
    language: str = Field(default="zh-CN", max_length=20)


class InspirationBatchInput(InspirationAgentInput):
    """Input contract for a single batch. A batch contains at most two images."""

    images: list[InspirationAgentImage] = Field(min_length=1, max_length=2)


def validate_batch_result(payload: Any, expected_indices: list[int]) -> InspirationBatchResult:
    result = InspirationBatchResult.model_validate(payload)
    actual = [item.attachment_index for item in result.items]
    if len(actual) != len(expected_indices):
        raise ValueError("inspiration_item_count_mismatch")
    if len(set(actual)) != len(actual):
        raise ValueError("inspiration_attachment_index_duplicate")
    if set(actual) != set(expected_indices):
        raise ValueError("inspiration_attachment_index_mismatch")
    result.items.sort(key=lambda item: expected_indices.index(item.attachment_index))
    return result


def fallback_inspiration_summary(reference_text: str, batches: list[Any]) -> InspirationSummaryResult:
    """Build a stable summary when the text-only provider call is unavailable."""
    themes: list[str] = []
    tags: list[str] = []
    for batch in batches:
        value = batch.model_dump() if isinstance(batch, InspirationBatchResult) else batch
        if value.get("batch_theme") and not themes:
            themes.append(str(value["batch_theme"]))
        for tag in value.get("tags") or []:
            cleaned = str(tag).strip()
            if cleaned and cleaned not in tags:
                tags.append(cleaned)
    title = themes[0] if themes else "拍摄灵感"
    summary = reference_text.strip()[:300] if reference_text.strip() else "参考图片分批生成的拍摄灵感建议。"
    return InspirationSummaryResult(title=title, summary=summary, tags=tags[:10] or ["拍摄灵感"])


def build_inspiration_content(result: InspirationBatchResult, trusted_images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    image_by_index = {int(item["attachment_index"]): item for item in trusted_images}
    result_title = getattr(result, "title", None) or getattr(result, "batch_theme", "拍摄灵感")
    blocks: list[dict[str, Any]] = []
    for advice in result.items:
        image = image_by_index[advice.attachment_index]
        blocks.extend([
            {
                "type": "image",
                "url": image["url"],
                "thumb_url": image.get("thumb_url"),
                "alt": f"{result_title}参考图 {advice.attachment_index + 1}",
            },
            {"type": "heading", "text": advice.title},
            {"type": "paragraph", "text": advice.description},
            {"type": "paragraph", "text": f"创作延伸：{advice.extension}"},
        ])
    return blocks


async def generate_inspiration_batch(
    data: InspirationBatchInput,
    *,
    provider: AIProvider | None = None,
    max_repairs: int = 2,
) -> tuple[InspirationBatchResult, dict[str, Any]]:
    """Analyze one to two images and return only batch-scoped suggestions."""
    provider = provider or get_ai_provider()
    expected_indices = [image.attachment_index for image in data.images]
    request_text = json.dumps({
        "task_id": data.task_id,
        "reference_text": data.reference_text,
        "language": data.language,
        "attachment_indices": expected_indices,
        "output_limits": {
            "max_total_characters": 1000,
            "batch_theme": 24,
            "tags": 4,
            "tag": 8,
            "title": 24,
            "description": 160,
            "extension": 120,
        },
    }, ensure_ascii=False)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": request_text}]
    user_content.extend({"type": "image_url", "image_url": {"url": image.provider_image_url}} for image in data.images)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": (
            "你是摄影灵感 Agent，为每张参考图写一条自然的摄影灵感笔记。"
            "只返回一个 JSON 对象，包含 batch_theme、tags，以及与每个传入 "
            "attachment_index 恰好对应的 item；每个 item 只含字段 "
            "attachment_index、title（灵感标题）、description（灵感描述）、"
            "extension（创作延伸）。写作要求：不要机械罗列构图、色彩、打光、"
            "道具等参数；重点描述照片带来的情绪、氛围、视觉语言和创作意图，"
            "思考「这张照片为什么有感觉」，而不只是「画面里有什么」；"
            "创作延伸要给出沿着这种感觉可以继续拍摄的方向；语言可以有画面感"
            "和适度文学性，但不要堆砌华丽辞藻，避免空泛的诗意；所有内容必须"
            "基于图片本身，不要臆造拍摄地点、参数、故事等未知信息；让输出像"
            "摄影师自己的灵感笔记，而不是一份照片体检报告。"
            "不要返回 summary、URL、地点、markdown 或解释。JSON 总长不超过 1000 字符；"
            "batch_theme 不超过 24 个汉字，最多 4 个 tag 且每个不超过 8 字，"
            "title 不超过 24 字，description 不超过 160 字，extension 不超过 120 字。"
        )},
        {"role": "user", "content": user_content},
    ]
    last_error: Exception | None = None
    for attempt in range(max_repairs + 1):
        response = await provider.chat(messages, temperature=0.2, response_format={"type": "json_object"})
        metadata = response.get("metadata") or {}
        if metadata.get("degraded"):
            fallback = metadata.get("fallback") or {}
            primary_error = fallback.get("primary_error") or "provider_unavailable"
            raise InspirationProviderUnavailableError(f"inspiration_provider_unavailable:{primary_error}")
        raw = (response.get("content") or "").strip()
        try:
            result = validate_batch_result(_parse_json_object(raw), expected_indices)
            return result, {
                "prompt_version": INSPIRATION_AGENT_BATCH_PROMPT_VERSION,
                "attempts": attempt + 1,
                "model": metadata.get("model") or {},
            }
        except Exception as exc:
            last_error = exc
            if attempt >= max_repairs:
                break
            messages.extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "Return a corrected JSON object only. Required attachment_indices: "
                    f"{expected_indices}. Error: {type(exc).__name__}: {exc}"
                )},
            ])
    raise ValueError(f"inspiration_generation_invalid:{last_error}")


async def summarize_inspiration_batches(
    reference_text: str,
    batches: list[Any],
    *,
    provider: AIProvider | None = None,
    max_repairs: int = 1,
) -> tuple[InspirationSummaryResult, dict[str, Any]]:
    """Summarize batch text without sending any original images to the provider."""
    provider = provider or get_ai_provider()
    normalized = [batch.model_dump() if isinstance(batch, InspirationBatchResult) else batch for batch in batches]
    request_text = json.dumps({"reference_text": reference_text, "batches": normalized}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": (
            "Return one JSON object only with title, summary, and tags. Use only the supplied text; "
            "do not invent locations, URLs, identifiers, markdown, or explanations. Keep JSON under 500 characters."
        )},
        {"role": "user", "content": request_text},
    ]
    last_error: Exception | None = None
    for attempt in range(max_repairs + 1):
        response = await provider.chat(messages, temperature=0.2, response_format={"type": "json_object"})
        metadata = response.get("metadata") or {}
        if metadata.get("degraded"):
            fallback = fallback_inspiration_summary(reference_text, batches)
            return fallback, {
                "prompt_version": INSPIRATION_SUMMARY_PROMPT_VERSION,
                "attempts": attempt + 1,
                "summary_degraded": True,
                "primary_error": (metadata.get("fallback") or {}).get("primary_error") or "provider_unavailable",
            }
        raw = (response.get("content") or "").strip()
        try:
            result = InspirationSummaryResult.model_validate(_parse_json_object(raw))
            return result, {
                "prompt_version": INSPIRATION_SUMMARY_PROMPT_VERSION,
                "attempts": attempt + 1,
                "model": metadata.get("model") or {},
            }
        except Exception as exc:
            last_error = exc
            if attempt >= max_repairs:
                break
            messages.extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"Return corrected JSON only. Error: {type(exc).__name__}: {exc}"},
            ])
    fallback = fallback_inspiration_summary(reference_text, batches)
    return fallback, {
        "prompt_version": INSPIRATION_SUMMARY_PROMPT_VERSION,
        "attempts": max_repairs + 1,
        "summary_degraded": True,
        "primary_error": str(last_error)[:300] if last_error else "invalid_summary",
    }


# Descriptive alias used by callers migrating from the all-images contract.
validate_generation_batch_result = validate_batch_result


def _parse_json_object(raw: str) -> dict[str, Any]:
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        if start < 0:
            raise
        payload, _ = decoder.raw_decode(raw[start:])
    if not isinstance(payload, dict):
        raise ValueError("inspiration_generation_not_object")
    return payload
