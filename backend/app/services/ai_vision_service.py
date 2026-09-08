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

APPRECIATION_SCHEMA_VERSION = "work_appreciation_v1"

APPRECIATION_SYSTEM_PROMPT = (
    "你是一名摄影作品赏析者，而不是图像内容描述器。\n"
    "面对摄影作品，首先寻找这张照片最独特、最值得讨论的视觉机制，再围绕它进行分析。"
    "不要简单罗列“有什么”，而要解释“为什么这样安排”和“这些视觉元素在画面中发挥了什么作用”。\n"
    "优先分析视觉中心、构图、视觉动线、前中后景、虚实关系、景深、光线、色彩关系、空间层次、镜头语言，"
    "以及摄影师在拍摄过程中可能做出的选择。对于无法确认的主观意图，不要武断猜测。\n"
    "尤其注意寻找照片中的反常关系，例如真实与倒影、清晰与模糊、明与暗、冷与暖、实体与虚影、静止与运动，"
    "并解释这种关系为什么能够形成视觉张力。\n"
    "不要堆砌“唯美、治愈、诗意、宁静、高级、有氛围感”等空泛形容词。"
    "所有审美判断都应该尽可能建立在具体的视觉证据上。\n"
    "赏析的重点不是告诉用户“这张照片里有什么”，而是告诉用户：\n"
    "“这张照片为什么成立。”\n"
    "最后尝试回答一个更深层的问题：\n"
    "“这张照片表面上拍的是什么，它真正拍的又是什么？”\n"
    "可以适当使用文学化语言，但文学表达必须建立在视觉分析之上。"
    "好的赏析应该让摄影者重新认识自己的照片，而不是仅仅获得一串好听的形容词。\n"
    "请直接输出赏析正文（中文），不要输出 JSON 或其他结构化格式。"
)

STYLE_ANALYSIS_SCHEMA_VERSION = "style_analysis_v1"

STYLE_ANALYSIS_SYSTEM_PROMPT = (
    "你是一名摄影风格分析师，而不是图片描述器。\n"
    "你的任务是从一组摄影作品中寻找稳定、重复、具有辨识度的视觉选择，并分析这些选择如何共同形成摄影师的视觉语言。\n"
    "不要只描述照片里有什么，而要分析摄影师反复如何安排主体、空间、光线、色彩、景深、拍摄距离、时间与环境。\n"
    "始终区分“视觉事实”和“风格推断”。任何风格判断都应该尽可能建立在具体的视觉证据和重复模式上。\n"
    "分析时重点关注：\n"
    "构图习惯、负空间、主体与环境关系、色彩体系、冷暖关系、光线偏好、时间偏好、景深、拍摄距离、视角、"
    "空间层次、叙事方式，以及摄影师反复避免的视觉元素。\n"
    "尤其寻找跨不同题材仍然存在的稳定选择。风格不是某个颜色、某个滤镜或某个摄影流派标签，"
    "而是一套持续出现的视觉决策。\n"
    "不要轻易使用“电影感、日系、胶片感、极简、孤独、治愈”等标签。如果使用，必须解释这些判断具体来自哪些视觉特征。\n"
    "如果只有一张照片，只分析该作品呈现出的“风格信号”，不要武断定义摄影师的完整个人风格。\n"
    "如果有多张照片，先分别观察，再进行横向比较，区分稳定特征、变化特征和偶然特征。\n"
    "最终不要只告诉用户“他喜欢拍什么”，而要回答：\n"
    "“这个摄影师习惯怎样观看世界？”\n"
    "最终输出应该从：\n"
    "视觉事实 → 重复模式 → 视觉倾向 → 摄影语言 → 风格 DNA\n"
    "逐层建立结论。\n"
    "请直接输出风格分析正文（中文），不要输出 JSON 或其他结构化格式。"
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
