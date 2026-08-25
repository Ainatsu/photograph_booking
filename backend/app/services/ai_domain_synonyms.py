"""摄影领域同义词归一化。

同一个概念在用户表达、数据库标签和索引文档里往往写法不同：
用户说“婚庆”，摄影师标签写“婚礼跟拍”，套餐标题写“婚宴”。
只做精确子串匹配时，资源类型识别正确也会在风格过滤或相关性阈值处被排除。

本模块只提供纯函数：把变体归一化到规范词，并按“同组任一变体命中即算命中”的方式匹配文档。
检索条件的实际应用在 ai_retrieval_service，多轮状态在 ai_search_context_service。
"""

from __future__ import annotations

from typing import Any


# 每组第一个词是规范词，其余为可互换变体。
WEDDING_TERMS = ("婚礼", "婚庆", "婚宴", "婚礼跟拍", "婚礼摄影", "婚礼拍摄", "结婚")
BRIDAL_TERMS = ("婚纱", "婚纱照", "婚纱摄影")
PORTRAIT_TERMS = ("写真", "人像", "肖像", "个人写真")
MAKEUP_TERMS = ("妆造", "化妆", "含妆", "带妆", "造型")
PACKAGE_TERMS = ("套餐", "方案", "报价", "服务包", "拍摄方案")

# 可以作为“风格 / 拍摄题材”条件参与过滤的同义词组。
# 妆造属于服务内容（由 requires_makeup 处理），套餐属于资源类型，都不算风格。
STYLE_SYNONYM_GROUPS = (WEDDING_TERMS, BRIDAL_TERMS, PORTRAIT_TERMS)

SYNONYM_GROUPS = (*STYLE_SYNONYM_GROUPS, MAKEUP_TERMS, PACKAGE_TERMS)

_VARIANT_TO_CANONICAL: dict[str, str] = {
    variant: group[0] for group in SYNONYM_GROUPS for variant in group
}
_CANONICAL_TO_VARIANTS: dict[str, tuple[str, ...]] = {
    group[0]: group for group in SYNONYM_GROUPS
}


def canonical_term(term: Any) -> str:
    """把任意变体映射到规范词；不在词表里的原样返回。"""
    text = str(term or "").strip()
    return _VARIANT_TO_CANONICAL.get(text, text)


def term_variants(term: Any) -> tuple[str, ...]:
    """返回该词在匹配时可接受的所有写法。"""
    text = str(term or "").strip()
    if not text:
        return ()
    canonical = _VARIANT_TO_CANONICAL.get(text)
    if canonical is None:
        return (text,)
    return _CANONICAL_TO_VARIANTS[canonical]


def matches_term(haystack: str, term: Any) -> bool:
    """同义词感知的匹配：同组任一写法出现在文档文本里就算命中。"""
    variants = term_variants(term)
    if not variants:
        return False
    return any(variant in haystack for variant in variants)


def normalize_terms(terms: list[Any] | tuple[Any, ...] | None) -> list[str]:
    """归一化并去重，保持原有顺序（同组只保留一个规范词）。"""
    result: list[str] = []
    seen: set[str] = set()
    for term in terms or []:
        normalized = canonical_term(term)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def detect_style_terms(content: str | None) -> list[str]:
    """从用户原文里识别风格条件的规范词，例如“婚庆拍摄方案”→ ["婚礼"]。"""
    text = content or ""
    if not text:
        return []
    return [
        group[0]
        for group in STYLE_SYNONYM_GROUPS
        if any(variant in text for variant in group)
    ]
