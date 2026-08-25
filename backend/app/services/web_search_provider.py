"""Replaceable public web-search providers for Agent Phase 1."""

from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError, URLError
from dataclasses import asdict, dataclass
from typing import Protocol
from urllib.request import Request, urlopen

from backend.app.core.config import settings


class WebSearchProviderError(RuntimeError):
    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class WebSearchResult:
    rank: int
    title: str
    url: str
    snippet: str
    published_at: str | None = None
    source_domain: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class WebSearchProvider(Protocol):
    async def search(self, query: str, *, limit: int = 5, language: str | None = None,
                     freshness: str | None = None, include_domains: list[str] | None = None,
                     exclude_domains: list[str] | None = None) -> list[WebSearchResult]: ...


class TavilyWebSearchProvider:
    endpoint = "https://api.tavily.com/search"

    async def search(self, query: str, *, limit: int = 5, language: str | None = None,
                     freshness: str | None = None, include_domains: list[str] | None = None,
                     exclude_domains: list[str] | None = None) -> list[WebSearchResult]:
        if not settings.WEB_SEARCH_API_KEY:
            raise RuntimeError("provider_not_configured")
        payload = {
            "api_key": settings.WEB_SEARCH_API_KEY,
            "query": query,
            "max_results": min(limit, settings.WEB_SEARCH_MAX_RESULTS, 5),
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "include_domains": include_domains or [],
            "exclude_domains": exclude_domains or [],
        }
        if freshness:
            payload["time_range"] = freshness
        raw = await asyncio.to_thread(self._post, payload)
        results = []
        for rank, item in enumerate(raw.get("results") or [], start=1):
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            results.append(WebSearchResult(rank, str(item.get("title") or url), url,
                                           str(item.get("content") or "")[:2000],
                                           item.get("published_date"), None))
        return results[:limit]

    def _post(self, payload: dict) -> dict:
        request = Request(self.endpoint, data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json", "User-Agent": "photographer-booking/1.0"},
                          method="POST")
        try:
            with urlopen(request, timeout=settings.WEB_SEARCH_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise WebSearchProviderError("provider_auth_failed", exc.code) from exc
            if exc.code == 429:
                raise WebSearchProviderError("provider_rate_limited", exc.code) from exc
            raise WebSearchProviderError("provider_http_error", exc.code) from exc
        except URLError as exc:
            raise WebSearchProviderError("provider_network_error") from exc


def get_web_search_provider() -> WebSearchProvider:
    if settings.WEB_SEARCH_PROVIDER.lower() == "tavily":
        return TavilyWebSearchProvider()
    raise RuntimeError("unsupported_provider")


def get_web_search_providers() -> list[tuple[str, WebSearchProvider]]:
    names = [settings.WEB_SEARCH_PROVIDER, *settings.WEB_SEARCH_FALLBACK_PROVIDERS.split(",")]
    providers = []
    for raw_name in names:
        name = raw_name.strip().lower()
        if not name:
            continue
        if name == "tavily":
            providers.append((name, TavilyWebSearchProvider()))
    if not providers:
        raise RuntimeError("unsupported_provider")
    return providers
