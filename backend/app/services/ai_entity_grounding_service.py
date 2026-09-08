"""平台实体接地校验：用确定性代码拦截最终回复里编造的平台实体名。

背景：mimo 等弱模型在无平台检索结果的 chat 轮次里，会被推荐类话术先验带偏，
点名平台中不存在的摄影师/作品/套餐（如「林小夏」「陈一帆」，2026-06 起多次复现）。
提示词层已改为正向场景注入（见 ai_prompts.CHAT_NO_PLATFORM_DATA_PROMPT），
本模块是代码层兜底：提示词失效时仍然拦得住。

只在"本轮无任何平台数据"的轮次启用——有检索结果或工具数据时，实体名合法性
由注入的受约束上下文保证，不经过这里。
"""

import re
import time
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User
from backend.app.services.ai_prompts import CHAT_GROUNDING_FALLBACK_TEXT, CHAT_GROUNDING_RETRY_PROMPT

# 平台实体全量名字集很小（摄影师 + 各自套餐/作品标题），进程内短缓存即可。
_ENTITY_CACHE_TTL_SECONDS = 60.0
_entity_cache: dict[str, Any] = {"ts": 0.0, "names": frozenset()}

# "摄影师：林小夏"、"**摄影师：林小夏**"这类标签引导名。
# 冒号后放行装饰符（引号、加粗星号），名称本身只收中文/字母/数字/间隔号/空格。
_ENTITY_LABEL_PATTERN = re.compile(
    r"(?:摄影师|作品|套餐)[:：]\s*[「『【*“\"'\s]*([\u4e00-\u9fa5A-Za-z0-9 ·・]{2,24})"
)
# 书名号标题（作品/套餐名常见格式）。
_TITLE_PATTERN = re.compile(r"[《〈]([^》〉]{1,30})[》〉]")
# 引号名只收实体锚定的两种写法："摄影师「林小夏」"和"「海边的夏日午后」的作品"，
# 避免"推荐「日系」风格"里的风格词被当成实体名。
_QUOTED_AFTER_LABEL_PATTERN = re.compile(r"(?:摄影师|作品|套餐)[「『]([^」』]{1,20})[」』]")
_QUOTED_BEFORE_TITLE_PATTERN = re.compile(r"[「『]([^」』]{1,20})[」』]的(?:作品|套餐|方案)")

# 含这些常用词的候选不是专有名词（如"摄影师：林小夏 擅长日系"里的后半段），
# 用于把标签引导的候选截断到真正的名称部分。
_GENERIC_CANDIDATE_WORDS = (
    "建议", "可以", "需要", "适合", "推荐", "如果", "比如", "例如", "或者",
    "没有", "不是", "哪个", "什么", "怎么", "如何", "以及", "考虑", "直接",
    "暂时", "一下", "这个", "那个", "自己", "之间", "之后", "擅长", "拍摄",
    "也", "还", "很", "都", "在", "是", "和", "与", "及", "或", "的",
)
_NAME_SUFFIXES = ("的作品", "的套餐", "的方案")


def _trim_candidate(raw: str) -> str:
    """把标签引导的候选截断成名称本身："林小夏 擅长日系" -> "林小夏"。

    整段以常用词开头（如"建议选择基础款"）说明这不是名称，返回空串。
    """
    text = raw.strip().strip("*_'\"“” ")
    for word in _GENERIC_CANDIDATE_WORDS:
        index = text.find(word)
        if index == 0:
            return ""
        if index > 0:
            text = text[:index]
    for suffix in _NAME_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text.strip()


def _collect_platform_entity_names(db: Session) -> frozenset[str]:
    now = time.monotonic()
    if now - _entity_cache["ts"] < _ENTITY_CACHE_TTL_SECONDS and _entity_cache["names"]:
        return _entity_cache["names"]

    names: set[str] = set()
    rows = (
        db.query(
            User.display_name,
            User.username,
            PhotographerProfile.packages,
            PhotographerProfile.portfolio,
        )
        .join(PhotographerProfile, PhotographerProfile.user_id == User.id)
        .all()
    )
    for display_name, username, packages, portfolio in rows:
        for name in (display_name, username):
            if name and name.strip():
                names.add(name.strip())
        for package in packages or []:
            title = str(package.get("name") or package.get("title") or "").strip()
            if title:
                names.add(title)
        for item in portfolio or []:
            title = str(item.get("title") or item.get("name") or "").strip()
            if title:
                names.add(title)

    names = frozenset(names)
    _entity_cache["ts"] = now
    _entity_cache["names"] = names
    return names


def extract_entity_mentions(content: str | None) -> list[str]:
    """提取回复中被当作平台实体点名的候选名称。"""
    mentions: list[str] = []
    for line in (content or "").splitlines():
        for match in _ENTITY_LABEL_PATTERN.finditer(line):
            mentions.append(_trim_candidate(match.group(1)))
        for pattern in (_TITLE_PATTERN, _QUOTED_AFTER_LABEL_PATTERN, _QUOTED_BEFORE_TITLE_PATTERN):
            mentions.extend(m.group(1).strip() for m in pattern.finditer(line))

    unique: list[str] = []
    for name in mentions:
        if name and len(name) >= 2 and name not in unique:
            unique.append(name)
    return unique


def detect_fabricated_entities(
    db: Session,
    content: str | None,
    *,
    dialogue_text: str = "",
) -> list[str]:
    """找出回复中点名、但平台不存在且对话双方都未提过的实体名。"""
    known = _collect_platform_entity_names(db)
    dialogue = dialogue_text or ""
    fabricated: list[str] = []
    for name in extract_entity_mentions(content):
        if name in known:
            continue
        # 用户或历史消息里出现过的名字（比如用户自己问起某摄影师）不算编造。
        if dialogue and name in dialogue:
            continue
        fabricated.append(name)
    return fabricated


def strip_entity_lines(content: str, names: list[str]) -> str:
    """逐行剔除包含编造实体的内容，保留其余部分。"""
    if not names:
        return (content or "").strip()
    kept = [
        line
        for line in (content or "").splitlines()
        if not any(name in line for name in names)
    ]
    return "\n".join(kept).strip()


def dialogue_text_from_provider_messages(provider_messages: list[dict]) -> str:
    """把模型可见的 user/assistant 历史拼成一段文本，用于"历史提过不算编造"的判断。"""
    parts: list[str] = []
    for message in provider_messages or []:
        if message.get("role") not in ("user", "assistant"):
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
    return "\n".join(parts)


async def enforce_chat_entity_grounding(
    db: Session,
    *,
    provider: Any,
    provider_messages: list[dict],
    result: dict,
) -> dict:
    """无平台数据轮次的输出校验：重答一次，仍不合规就剔除编造行，最后退兜底话术。

    所有分支都会在 metadata.grounding_corrections 里留下审计记录，
    供 trace 里统计提示词与代码两层防线的拦截率。
    """
    content = result.get("content") or ""
    if not content.strip():
        return result
    dialogue_text = dialogue_text_from_provider_messages(provider_messages)
    fabricated = detect_fabricated_entities(db, content, dialogue_text=dialogue_text)
    if not fabricated:
        return result

    corrections: list[dict] = [{"fabricated_entities": fabricated, "action": "retry"}]
    retry_result: dict | None = None
    try:
        retry_messages = [
            provider_messages[0],
            {"role": "system", "content": CHAT_GROUNDING_RETRY_PROMPT},
            *provider_messages[1:],
        ]
        retry_result = await provider.chat(retry_messages)
    except Exception:
        retry_result = None
    retry_content = (retry_result or {}).get("content") or ""
    retry_fabricated = (
        detect_fabricated_entities(db, retry_content, dialogue_text=dialogue_text)
        if retry_content.strip()
        else []
    )
    if retry_content.strip() and not retry_fabricated:
        retry_result["metadata"] = {
            **(retry_result.get("metadata") or {}),
            "grounding_corrections": corrections,
        }
        return retry_result

    corrections.append(
        {"fabricated_entities": retry_fabricated or fabricated, "action": "strip_lines"}
    )
    source = retry_content if retry_content.strip() else content
    names = retry_fabricated or fabricated
    stripped = strip_entity_lines(source, names)
    metadata = {
        **(result.get("metadata") or {}),
        "grounding_corrections": corrections,
    }
    if len(stripped) >= 10:
        return {**result, "content": stripped, "metadata": metadata}
    return {**result, "content": CHAT_GROUNDING_FALLBACK_TEXT, "metadata": metadata}
