"""Phase 1 web search: provider call, short cache, task association, structured result."""

from __future__ import annotations

import hashlib
import asyncio
from time import perf_counter
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

from backend.app.core.cache import cache_get, cache_set
from backend.app.core.config import settings
from backend.app.services.web_search_provider import get_web_search_providers, WebSearchProviderError
from backend.app.services.web_page_fetcher import fetch_public_page
from backend.app.services.ai_web_search_metrics import increment

SCHEMA_VERSION = "web_search_context_v1"


def _circuit_open() -> bool:
    state = cache_get("agent:web_search:circuit") or {}
    return float(state.get("open_until") or 0) > datetime.now(timezone.utc).timestamp()


def _record_circuit_failure() -> None:
    state = cache_get("agent:web_search:circuit") or {}
    failures = int(state.get("failures") or 0) + 1
    payload = {"failures": failures, "open_until": 0}
    if failures >= settings.WEB_SEARCH_CIRCUIT_FAILURE_THRESHOLD:
        payload["open_until"] = datetime.now(timezone.utc).timestamp() + settings.WEB_SEARCH_CIRCUIT_COOLDOWN_SECONDS
        increment("circuit_opened")
    cache_set("agent:web_search:circuit", payload, settings.WEB_SEARCH_CIRCUIT_COOLDOWN_SECONDS)


def _record_circuit_success() -> None:
    cache_set("agent:web_search:circuit", {"failures": 0, "open_until": 0}, settings.WEB_SEARCH_CIRCUIT_COOLDOWN_SECONDS)


async def run_web_search(*, arguments: dict, task_form_id: str, conversation_id: int,
                         message_id: int) -> dict:
    started = perf_counter()
    if not settings.WEB_SEARCH_ENABLED:
        increment("disabled")
        return _failure(arguments, "web_search_disabled")
    if _circuit_open():
        increment("circuit_rejected")
        return _failure(arguments, "provider_circuit_open")
    query = arguments["query"]
    canonical = " ".join(query.lower().split())
    query_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    query_key = f"agent:web_search:query:{query_hash}"
    items = cache_get(query_key)
    cache_hit = items is not None
    increment("cache_hit" if cache_hit else "cache_miss")
    try:
        if items is None:
            results = None
            selected_provider = None
            last_error = "provider_unavailable"
            for provider_name, provider in get_web_search_providers():
                for attempt in range(max(1, settings.WEB_SEARCH_RETRIES + 1)):
                    try:
                        results = await provider.search(**arguments)
                        selected_provider = provider_name
                        break
                    except WebSearchProviderError as exc:
                        last_error = exc.code
                        if exc.code == "provider_auth_failed":
                            break
                        if attempt + 1 < max(1, settings.WEB_SEARCH_RETRIES + 1):
                            await asyncio.sleep(0.1 * (attempt + 1))
                    except Exception as exc:
                        last_error = type(exc).__name__
                        if attempt + 1 < max(1, settings.WEB_SEARCH_RETRIES + 1):
                            await asyncio.sleep(0.1 * (attempt + 1))
                if results is not None:
                    break
            if results is None:
                increment("provider_failure")
                _record_circuit_failure()
                return _failure(arguments, last_error)
            increment("provider_success")
            increment(f"provider_{selected_provider}_success")
            _record_circuit_success()
            items = []
            for result in results[:5]:
                parsed = urlparse(result.url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    continue
                items.append({"rank": len(items) + 1, "title": result.title, "url": result.url,
                              "domain": parsed.hostname.lower(), "snippet": result.snippet,
                              "clean_text": "", "published_at": result.published_at,
                              "fetch_status": "not_fetched"})
            cache_set(query_key, items, settings.WEB_SEARCH_CACHE_TTL_SECONDS)
    except TimeoutError:
        increment("provider_timeout")
        return _failure(arguments, "provider_timeout")
    except Exception as exc:
        code = str(exc) if str(exc) in {"provider_not_configured", "unsupported_provider"} else "provider_unavailable"
        increment("provider_failure")
        _record_circuit_failure()
        return _failure(arguments, code)
    search_id = f"search_{uuid4().hex[:8]}"
    # Phase 2: fetch only the bounded public pages returned by the provider.
    total_chars = 0
    reference_images: list[dict] = []
    for item in items or []:
        page = await fetch_public_page(item["url"])
        item.update(page)
        for image in page.get("images") or []:
            if image.get("image_url") not in {entry.get("image_url") for entry in reference_images}:
                reference_images.append({**image, "title": item.get("title"), "domain": item.get("domain")})
            if len(reference_images) >= 3:
                break
        increment("fetch_success" if page.get("fetch_status") == "success" else "fetch_failure")
        total_chars += len(item.get("clean_text") or "")
        if total_chars >= settings.WEB_SEARCH_MAX_TOTAL_CONTENT_CHARS:
            item["clean_text"] = (item.get("clean_text") or "")[:max(0, settings.WEB_SEARCH_MAX_TOTAL_CONTENT_CHARS - (total_chars - len(item.get("clean_text") or "")))]
            break
    diagnostics = {"cache_hit": cache_hit, "latency_ms": int((perf_counter() - started) * 1000),
                   "fetch_success_count": sum(1 for item in items or [] if item.get("fetch_status") == "success"),
                   "fetch_failure_count": sum(1 for item in items or [] if item.get("fetch_status") != "success")}
    record = {"schema_version": SCHEMA_VERSION, "task_form_id": task_form_id,
              "conversation_id": conversation_id, "message_id": message_id, "search_id": search_id,
              "query": query, "created_at": datetime.now(timezone.utc).isoformat(), "items": items or [],
              "reference_images": reference_images[:3],
              "diagnostics": diagnostics}
    ttl = settings.WEB_SEARCH_CACHE_TTL_SECONDS
    cache_set(f"agent:web_search:{task_form_id}:{search_id}", record, ttl)
    cache_set(f"agent:context:{task_form_id}:web_searches", record, ttl)
    increment("empty" if not items else "success")
    increment("latency_ms_total", int((perf_counter() - started) * 1000))
    return {"tool": "search_web", "status": "success" if items else "empty", "input": arguments,
            "result": {"schema_version": SCHEMA_VERSION, "count": len(items or []), "items": items or [],
                       "task_form_id": task_form_id, "search_id": search_id, "diagnostics": diagnostics}, "record": record,
            "policy": {"risk_level": "read_only", "confirmation_policy": "none"}}


def _failure(arguments: dict, error: str) -> dict:
    return {"tool": "search_web", "status": "failed", "input": arguments,
            "result": {"schema_version": SCHEMA_VERSION, "count": 0, "items": [], "error": error},
            "error_code": error,
            "record": None, "policy": {"risk_level": "read_only", "confirmation_policy": "none"}}
