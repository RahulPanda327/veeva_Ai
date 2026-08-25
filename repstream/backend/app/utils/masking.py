"""Masks pharma brand/product names out of every API response.

Runs as ASGI middleware over the full JSON response body — catches brand
names wherever they appear, whether from a structured DB field value (e.g.
competitor_brand="CREON") or free-text Ollama-generated content (counter
scripts, descriptions, email bodies, etc.). No product name — the client's
own or a competitor's — reaches the client.

Registered in main.py BEFORE DailyResponseCacheMiddleware (closest to the
routes), so the cache stores the already-masked body.
"""
from __future__ import annotations

import json
import re
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Real brand name -> masked label. Matching is case-insensitive with word
# boundaries so substrings inside unrelated words/names aren't touched.
_BRAND_MAP = {
    "zenpep": "Product",
    "creon": "Competitor A",
    "pancreaze": "Competitor B",
}

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _BRAND_MAP) + r")\b",
    re.IGNORECASE,
)


def _replace(match: "re.Match[str]") -> str:
    return _BRAND_MAP[match.group(0).lower()]


def mask_text(value: str) -> str:
    return _PATTERN.sub(_replace, value)


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(v) for v in value]
    return value


class BrandMaskingMiddleware(BaseHTTPMiddleware):
    """Replaces ZENPEP/CREON/PANCREAZE (any case) with generic labels
    everywhere in every JSON response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if "application/json" not in (response.headers.get("content-type") or ""):
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            data = json.loads(body) if body else None
        except json.JSONDecodeError:
            content_type = response.headers.get("content-type")
            headers = {"content-type": content_type} if content_type else None
            return _carry_headers(
                Response(content=body, status_code=response.status_code, headers=headers),
                response)

        masked = _mask_value(data)
        new_body = json.dumps(masked, default=str).encode("utf-8")

        return _carry_headers(
            Response(content=new_body, status_code=response.status_code,
                     media_type="application/json"),
            response)


def _carry_headers(new: Response, original: Response) -> Response:
    """Copy the original response's headers onto the rebuilt one.

    This middleware replaces the response object in order to rewrite the body,
    and a fresh Response starts with only the headers it was constructed with.
    Everything the route set was therefore dropped on the floor - most visibly
    Set-Cookie, which made cookie-based identification silently impossible: the
    route set the cookie, the browser never received it, and every request
    looked like a brand-new client.

    Content-Length and Content-Type are skipped because the new body has its own
    and the old values would contradict it. raw_headers is used rather than a
    dict so repeated headers (several Set-Cookie lines) all survive.
    """
    skip = (b"content-length", b"content-type")
    for key, value in original.raw_headers:
        if key.lower() not in skip:
            new.raw_headers.append((key, value))
    return new
