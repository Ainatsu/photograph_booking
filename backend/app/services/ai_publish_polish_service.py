"""Text-only agent workflow for polishing publishing forms."""

import json
import re
from typing import Any

from fastapi import HTTPException, status

from backend.app.services.ai_provider import get_text_provider


FIELD_RULES: dict[str, dict[str, tuple[str, int]]] = {
    "project": {
        "title": ("text", 120),
        "description": ("text", 2000),
        "deliverables": ("text", 1000),
        "city": ("text", 80),
        "location_text": ("text", 255),
        "style_tags": ("list", 12),
    },
    "package": {
        "name": ("text", 120),
        "city": ("text", 80),
        "service_location": ("text", 160),
        "description": ("text", 1600),
        "styles": ("list", 12),
        "includes": ("list", 20),
        "delivery_formats": ("list", 8),
        "terms_rules": ("text", 2400),
    },
    "work": {
        "title": ("text", 120),
        "description": ("text", 1200),
        "tags": ("list", 12),
    },
}


def _clean_text(value: Any, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _clean_list(value: Any, max_items: int) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()[:40]
        key = text.casefold()
        if not text or key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _normalize_fields(content_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    rules = FIELD_RULES[content_type]
    normalized: dict[str, Any] = {}
    for key, (field_type, limit) in rules.items():
        if key not in fields:
            continue
        normalized[key] = (
            _clean_list(fields[key], limit)
            if field_type == "list"
            else _clean_text(fields[key], limit)
        )
    return normalized


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent 未返回可用的润色结果，请稍后重试",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent 未返回可用的润色结果，请稍后重试",
        )
    nested = parsed.get("fields")
    return nested if isinstance(nested, dict) else parsed


async def polish_publish_fields(content_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Polish allow-listed text fields without receiving or altering media."""
    source = _normalize_fields(content_type, fields)
    has_content = any(
        value.strip() if isinstance(value, str) else bool(value)
        for value in source.values()
    )
    if not has_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先填写至少一个标题、说明或标签，再使用 Agent 润色",
        )

    provider = get_text_provider()
    response = await provider.chat(
        [
            {
                "role": "system",
                "content": (
                    "你是摄影服务平台的发布文案编辑。只润色用户提供的文字，不分析图片，"
                    "不虚构地点、价格、数量、承诺、版权或交付事实。保留原意和语言，提升清晰度、"
                    "专业度与可读性。可以适当扩充形容词与语义词。可以将用户含义用意不同的文字分为单独的几段，段间不空行。空字段保持为空；标签应简短、去重。只返回 JSON 对象，"
                    "键必须与输入完全一致，值只能是字符串或字符串数组。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"content_type": content_type, "fields": source},
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.5,
        response_format={"type": "json_object"},
    )
    metadata = response.get("metadata") or {}
    if metadata.get("degraded"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent 润色服务暂时不可用，请稍后重试",
        )

    proposed = _parse_json_object(response.get("content") or "")
    polished = _normalize_fields(content_type, proposed)
    result = {
        key: (
            value
            if value == "" or value == []
            else polished.get(key, value)
        )
        for key, value in source.items()
    }
    return {
        "fields": result,
        "polished_field_count": sum(result[key] != source[key] for key in result),
    }
