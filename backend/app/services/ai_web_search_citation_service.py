"""Enforce Phase 1 web citations against URLs returned by the provider."""

from __future__ import annotations

import re

URL_RE = re.compile(r"https?://[^\s)\]>]+")
WEB_CITATION_RE = re.compile(r"\[WEB-(\d+)\]\((https?://[^)]+)\)")


def enforce_web_citations(content: str, items: list[dict]) -> tuple[str, list[str]]:
    allowed = [str(item.get("url") or "") for item in items if item.get("url")]
    warnings: list[str] = []
    text = content or ""
    # A successful web search must not silently retain a stale platform answer.
    stale_markers = ("摄影师推荐", "为你筛选了以下", "需要我帮你预约吗", "平台上的摄影师")
    if allowed and any(marker in text for marker in stale_markers):
        warnings.append("stale_platform_answer_detected")
        text = "我根据公开网页资料整理了以下信息：\n" + "\n".join(
            f"- [WEB-{item.get('rank')}]({item['url']})：{item.get('snippet') or item.get('title') or ''}"
            for item in items if item.get("url")
        )
    rank_urls = {str(item.get("rank")): str(item.get("url")) for item in items if item.get("rank") and item.get("url")}
    for rank, url in WEB_CITATION_RE.findall(text):
        if rank_urls.get(rank) != url:
            text = text.replace(f"[WEB-{rank}]({url})", "[invalid web citation removed]")
            warnings.append("invalid_web_citation_removed")
    for url in URL_RE.findall(text):
        clean = url.rstrip(".,;:!?，。；：！？")
        if clean not in allowed:
            text = text.replace(url, "[invalid external URL removed]")
            warnings.append("unapproved_url_removed")
    if allowed and not any(url in text for url in allowed):
        warnings.append("source_list_appended")
        sources = "\n\nSources:\n" + "\n".join(
            f"- [WEB-{item.get('rank')}]({item['url']}) — {item.get('title') or item['url']}" for item in items if item.get("url")
        )
        text += sources
    return text, warnings
