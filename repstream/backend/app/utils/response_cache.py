"""Day-long GET response cache — no Redis required.

Registered once in main.py as ASGI middleware. The first time a caller hits a
GET endpoint, the response is stored for 24 hours keyed by (method, path,
query params, caller). If the same caller hits the same endpoint again within
that window, the stored response is returned instantly instead of
recomputing. Entries expire automatically after 24h (checked lazily on read);
`clear_expired()` can be called to sweep them out proactively.

Independent of app/utils/cache.py (which needs Redis and is currently a
no-op in this environment) — this one is in-memory + a local JSON file, same
durable pattern as the AI insight/warm-approach caches, so it survives
`--reload` restarts.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)

TTL_SECONDS = settings.RESPONSE_CACHE_TTL_MINUTES * 60

_CACHE_FILE = Path(__file__).resolve().parents[2] / ".endpoint_response_cache.json"

_cache: Dict[str, dict] = {}
_io_lock = threading.Lock()


def _load() -> None:
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _cache.update(json.load(f))
        logger.info("Loaded %d cached responses from %s", len(_cache), _CACHE_FILE.name)
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load response cache (%s).", exc)


def _save() -> None:
    try:
        with _io_lock:
            tmp = _CACHE_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_cache, f)
            os.replace(tmp, _CACHE_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save response cache (%s).", exc)


_load()


def _cache_key(request: Request) -> str:
    """Same user + same endpoint + same query = same cache entry.
    "User" = the caller's Bearer token if present, else their IP."""
    caller = request.headers.get("authorization")
    if not caller:
        caller = request.client.host if request.client else "anonymous"
    query = str(sorted(request.query_params.multi_items()))
    return f"{request.method}:{request.url.path}:{query}:{caller}"


def clear_expired() -> int:
    """Remove expired entries. Returns how many were dropped."""
    now = time.time()
    expired = [k for k, v in _cache.items() if v["expires_at"] <= now]
    for k in expired:
        del _cache[k]
    if expired:
        _save()
    return len(expired)


def clear_all() -> int:
    n = len(_cache)
    _cache.clear()
    _save()
    return n


class DailyResponseCacheMiddleware(BaseHTTPMiddleware):
    """Cache GET responses for 24h, keyed by endpoint + query + caller."""

    async def dispatch(self, request: Request, call_next):
        if request.method != "GET":
            return await call_next(request)

        key = _cache_key(request)
        now = time.time()
        entry = _cache.get(key)

        if entry and entry["expires_at"] > now:
            logger.info("Response cache HIT: %s", request.url.path)
            body = base64.b64decode(entry["body"])
            headers = {"content-type": entry["content_type"]} if entry.get("content_type") else None
            return Response(content=body, status_code=entry["status_code"], headers=headers)

        if entry:
            del _cache[key]  # expired — fall through and regenerate

        response = await call_next(request)

        if 200 <= response.status_code < 300:
            body = b"".join([chunk async for chunk in response.body_iterator])
            # response.media_type is unreliable through BaseHTTPMiddleware's
            # call_next() wrapper (often None even for real files) — the real
            # Content-Type survives in .headers, so read it from there instead.
            content_type = response.headers.get("content-type")

            _cache[key] = {
                "body": base64.b64encode(body).decode("ascii"),
                "status_code": response.status_code,
                "content_type": content_type,
                "expires_at": now + TTL_SECONDS,
            }
            _save()
            logger.info("Response cache SET: %s (expires in 24h)", request.url.path)

            headers = {"content-type": content_type} if content_type else None
            return Response(content=body, status_code=response.status_code, headers=headers)

        return response
