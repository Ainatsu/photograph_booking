"""AI 视觉服务：解析参考图分析结果并生成检索词与回复。"""

import json
import re
from typing import Any


VISION_SCHEMA_VERSION = "vision_analysis_v1"

VISION_SYSTEM_PROMPT = (
    "你是摄影平台的 Vision Agent。请分析用户上传的参考图片，输出两部分："
    "第一部分用中文简洁说明图片的摄影风格、场景、光线、色彩、情绪、构图和妆造；"
    "第二部分必须给出一个 JSON 对象，字段固定为 "
    "summary, style, scene, mood, makeup, lighting, color, composition, search_terms。"
    "这些字段里的数组值要使用短标签，便于后续检索真实摄影师、作品或套餐。"
)

STYLE_TERMS = (
    "胶片质感",
    "自然光",
    "毕业照",
    "复古港风",
    "日系",
    "复古",
    "胶片",
    "清新",
    "婚纱",
    "人像",
    "校园",
    "写真",
    "室内",
    "教室",
    "外景",
    "棚拍",
    "街拍",
    "纪实",
    "港风",
    "法式",
    "韩系",
    "森系",
    "甜酷",
    "高级感",
    "黑白",
)

SCENE_TERMS = (
    "窗边",
    "教室",
    "校园",
    "室内",
    "外景",
    "棚拍",
    "街道",
    "海边",
    "咖啡馆",
    "天台",
    "花园",
    "公园",
    "民宿",
    "工作室",
)

MOOD_TERMS = (
    "清透",
    "清新",
    "自然",
    "温柔",
    "安静",
    "松弛",
    "复古",
    "高级",
    "甜美",
    "明亮",
    "通透",
    "氛围感",
    "治愈",
)

MAKEUP_TERMS = (
    "清透妆",
    "自然妆",
    "复古妆",
    "淡妆",
    "裸妆",
    "妆造",
    "化妆",
    "造型",
)

LIGHTING_TERMS = (
    "自然光",
    "窗光",
    "逆光",
    "侧光",
    "柔光",
    "高调",
    "低调",
)

COLOR_TERMS = (
    "低饱和",
    "暖色",
    "冷色",
    "黑白",
    "奶油色",
    "绿色",
    "蓝调",
)

COMPOSITION_TERMS = (
    "半身",
    "全身",
    "特写",
    "近景",
    "留白",
    "对称",
    "抓拍",
)


def normalize_vision_analysis(
    provider_result: dict[str, Any],
    *,
    content: str | None = None,
    attachments: list[dict] | None = None,
) -> dict[str, Any]:
    """规范化模型返回的图片分析结果，提取各维度标签。"""
    raw_text = (provider_result.get("content") or "").strip()
    payload = _extract_json_object(raw_text)
    combined_text = " ".join(part for part in (content or "", raw_text) if part)

    style = _normalize_terms(_field(payload, "style", "styles") or _match_terms(combined_text, STYLE_TERMS))
    scene = _normalize_terms(_field(payload, "scene", "scenes") or _match_terms(combined_text, SCENE_TERMS))
    mood = _normalize_terms(_field(payload, "mood", "moods") or _match_terms(combined_text, MOOD_TERMS))
    makeup = _normalize_terms(_field(payload, "makeup", "makeup_style") or _match_terms(combined_text, MAKEUP_TERMS))
    lighting = _normalize_terms(_field(payload, "lighting", "light") or _match_terms(combined_text, LIGHTING_TERMS))
    color = _normalize_terms(_field(payload, "color", "colors") or _match_terms(combined_text, COLOR_TERMS))
    composition = _normalize_terms(
        _field(payload, "composition", "compositions") or _match_terms(combined_text, COMPOSITION_TERMS)
    )
    search_terms = _normalize_terms(
        [
            *_clean_list(payload.get("search_terms")),
            *style,
            *scene,
            *mood,
            *makeup,
            *lighting,
            *color,
        ]
    )
    search_terms = _expand_search_terms(search_terms)

    return {
        "schema_version": VISION_SCHEMA_VERSION,
        "summary": _summary_text(payload, raw_text),
        "style": style,
        "scene": scene,
        "mood": mood,
        "makeup": makeup,
        "lighting": lighting,
        "color": color,
        "composition": composition,
        "search_terms": search_terms,
        "attachments": [
            {
                "type": item.get("type"),
                "url": item.get("url"),
                "mime_type": item.get("mime_type"),
            }
            for item in attachments or []
            if item.get("type") == "image" and item.get("url")
        ],
        "provider": (provider_result.get("metadata") or {}).get("model") or {},
    }


def build_vision_search_text(content: str | None, analysis: dict[str, Any]) -> str:
    """结合用户文本与视觉标签生成检索文本。"""
    base = _strip_visual_reference_text((content or "").strip()) or "找类似风格的摄影师"
    terms = vision_search_terms(analysis)
    if not terms:
        return base
    return " ".join([base, *terms])


def vision_search_terms(analysis: dict[str, Any]) -> list[str]:
    """汇总分析结果中的全部可检索标签。"""
    return _normalize_terms(
        [
            *(analysis.get("search_terms") or []),
            *(analysis.get("style") or []),
            *(analysis.get("scene") or []),
            *(analysis.get("mood") or []),
            *(analysis.get("makeup") or []),
            *(analysis.get("lighting") or []),
        ]
    )


def vision_slots_from_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    """从视觉分析结果提取检索槽位（风格、妆造要求）。"""
    slots: dict[str, Any] = {}
    styles = [
        term
        for term in _normalize_terms([*(analysis.get("style") or []), *(analysis.get("search_terms") or [])])
        if term not in {"写真", "化妆", "妆造", "造型"}
    ][:5]
    if styles:
        slots["style"] = styles[0] if len(styles) == 1 else styles

    makeup_terms = analysis.get("makeup") or []
    if makeup_terms:
        slots["requires_makeup"] = True
        slots["package_includes"] = ["妆造"]
    return slots


def build_vision_reply(analysis: dict[str, Any]) -> str:
    """基于分析摘要构建面向用户的回复文本。"""
    return analysis.get("summary") or "我已经看完这张参考图，并整理出了后续可用于检索的风格信息。"


def build_vision_retrieval_reply(
    analysis: dict[str, Any],
    retrieval: dict[str, Any] | None,
    *,
    reused_context: bool = False,
) -> str:
    """根据检索结果生成匹配资源的回复文案。"""
    references = (retrieval or {}).get("references") or {}
    criteria = (retrieval or {}).get("criteria") or {}
    resource_types = criteria.get("resource_types") or []
    resource_type = resource_types[0] if resource_types else "photographers"
    matches = references.get(resource_type) or []

    label = {
        "photographers": "摄影师",
        "portfolio_items": "作品",
        "packages": "套餐",
    }.get(resource_type, "资源")

    source_text = "刚才图片的整体风格" if reused_context else "这张图的整体风格"
    if not matches:
        return (
            f"我按{source_text}查了一下，暂时没找到完全匹配的{label}。"
            "可以再告诉我城市或预算，我继续帮你缩小范围。"
        )

    return (
        f"我按{source_text}找到了 {len(matches)} 个匹配的{label}，可以先看下面这些结果。"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    """从文本中提取并解析第一个 JSON 对象。"""
    if not text:
        return {}

    candidates = []
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        candidates.append(fence_match.group(1))
    candidates.append(text)

    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        candidates.append(text[first:last + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def _field(payload: dict[str, Any], *names: str) -> list[str]:
    """按候选字段名依次取值，返回首个非空列表。"""
    for name in names:
        values = _clean_list(payload.get(name))
        if values:
            return values
    return []


def _clean_list(value: Any) -> list[str]:
    """将任意值规范化为去空字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [
            item.strip()
            for item in re.split(r"[,，、;；\n]+", value)
            if item.strip()
        ]
    return [str(value).strip()] if str(value).strip() else []


def _match_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    """返回文本中命中的词条。"""
    return [term for term in terms if term and term in text]


def _normalize_terms(values: list[Any]) -> list[str]:
    """对词条去空白并去重。"""
    result = []
    seen = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        result.append(normalized)
        seen.add(normalized)
    return result


def _expand_search_terms(values: list[str]) -> list[str]:
    """按词库扩充检索词，补全命中的相关标签。"""
    expanded = list(values)
    haystack = " ".join(values)
    for term in (*STYLE_TERMS, *SCENE_TERMS, *MOOD_TERMS, *MAKEUP_TERMS, *LIGHTING_TERMS):
        if term in haystack:
            expanded.append(term)
    return _normalize_terms(expanded)


def _strip_visual_reference_text(text: str) -> str:
    """去除用户文本中的图片指代短语，保留检索意图。"""
    if not text:
        return ""
    normalized = text
    for phrase in (
        "刚才那张照片",
        "刚才这张照片",
        "刚才那张图片",
        "刚才这张图片",
        "刚才那张图",
        "刚才这张图",
        "这张照片",
        "这张图片",
        "这张图",
        "参考图",
    ):
        normalized = normalized.replace(phrase, "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = normalized.replace("类似的", "类似风格的")
    normalized = normalized.replace("类似风格风格", "类似风格")
    return normalized


def _summary_text(payload: dict[str, Any], raw_text: str) -> str:
    """提取分析摘要文本，缺失时回退到原始文本。"""
    for key in ("summary", "analysis", "analysis_text", "caption", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    without_fence = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", raw_text, flags=re.DOTALL | re.IGNORECASE).strip()
    first = without_fence.find("{")
    if first >= 0:
        without_fence = without_fence[:first].strip()
    return without_fence or "我已经看完这张参考图，并整理出了可用于检索的视觉标签。"
