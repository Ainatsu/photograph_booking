"""Bounded, SSRF-aware public page fetcher for web-search Phase 2."""

from __future__ import annotations

import asyncio
import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

from backend.app.core.config import settings


class _TextExtractor(HTMLParser):
    DROP = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"}
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.title: list[str] = []
        self._drop = 0
        self._in_title = False
        self.images: list[dict[str, str]] = []
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.DROP: self._drop += 1
        if tag == "title": self._in_title = True
        if tag == "img" and len(self.images) < 8:
            values = {str(key).lower(): str(value or "") for key, value in attrs}
            src = values.get("src") or values.get("data-src") or values.get("data-original")
            if src:
                self.images.append({"url": src, "alt": values.get("alt", "")})
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.DROP: self._drop = max(0, self._drop - 1)
        if tag == "title": self._in_title = False
    def handle_data(self, data):
        if self._drop: return
        text = " ".join(data.split())
        if not text: return
        if self._in_title: self.title.append(text)
        self.parts.append(text)


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url_not_public_http")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "metadata.google.internal", "metadata.google.internal."}:
        raise ValueError("private_host")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("dns_resolution_failed") from exc
    for entry in addresses:
        address = ipaddress.ip_address(entry[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified:
            raise ValueError("private_address")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(url: str) -> dict:
    current = url
    opener = build_opener(_NoRedirect())
    for _ in range(settings.WEB_SEARCH_MAX_REDIRECTS + 1):
        _validate_public_url(current)
        request = Request(current, headers={"User-Agent": "photographer-booking/1.0", "Accept": "text/html,text/plain"})
        try:
            response = opener.open(request, timeout=settings.WEB_SEARCH_TIMEOUT_SECONDS)
        except Exception as exc:
            # urllib exposes redirects as HTTPError when redirects are disabled.
            headers = getattr(exc, "headers", None)
            location = headers.get("Location") if headers else None
            if location:
                current = urljoin(current, location)
                continue
            raise
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" not in content_type and "text/plain" not in content_type:
            return {"fetch_status": "unsupported_content_type", "clean_text": "", "title": ""}
        body = response.read(settings.WEB_SEARCH_MAX_PAGE_BYTES + 1)
        if len(body) > settings.WEB_SEARCH_MAX_PAGE_BYTES:
            body = body[:settings.WEB_SEARCH_MAX_PAGE_BYTES]
            truncated = True
        else:
            truncated = False
        charset = "utf-8"
        match = re.search(r"charset=([\w-]+)", content_type)
        if match: charset = match.group(1)
        text = body.decode(charset, errors="replace")
        parser = _TextExtractor()
        parser.feed(text)
        clean = re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()
        images = []
        for image in parser.images:
            image_url = urljoin(current, image["url"])
            try:
                _validate_public_url(image_url)
            except ValueError:
                continue
            if image_url not in {item["url"] for item in images}:
                images.append({"image_url": image_url, "alt": image.get("alt", ""), "source_url": current})
            if len(images) >= 3:
                break
        return {"fetch_status": "success", "clean_text": clean[:settings.WEB_SEARCH_MAX_CONTENT_CHARS],
                "title": " ".join(parser.title)[:500], "truncated": truncated, "images": images}
    raise ValueError("too_many_redirects")


async def fetch_public_page(url: str) -> dict:
    try:
        return await asyncio.to_thread(_fetch, url)
    except TimeoutError:
        return {"fetch_status": "timeout", "clean_text": "", "title": ""}
    except ValueError as exc:
        return {"fetch_status": str(exc), "clean_text": "", "title": ""}
    except Exception:
        return {"fetch_status": "error", "clean_text": "", "title": ""}
