"""Permanent GET response cache — no Redis required, no expiry.

Registered once in main.py as ASGI middleware. The first time a caller hits a
GET endpoint, the response is stored, keyed by (method, path, query params,
caller). Every later hit on that same key is served from cache — forever,
until explicitly cleared (scripts/clear_cache.py, POST /admin/cache/clear,
or the app's own startup refresh in main.py). There is no time-based expiry;
staleness is handled entirely by explicit clears, not a TTL.

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
from pathlib import Path
from typing import Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.cache_paths import cache_file
from app.services.filters_service import FilterSelection, remember_filter

logger = logging.getLogger(__name__)

_CACHE_FILE = cache_file("endpoint_response_cache.json")

# Modules whose KPI tiles must mirror their (filterable) list. Each list call
# records the caller's filter under the module's scope; the matching summary is
# never cached so it always recomputes against the latest remembered filter.
#   list path suffix → filter-memory scope
_LIST_PATHS = {
    "/action-center/alerts": "alerts",
    "/territory/hcp-list":   "territory",
}
#   summary path suffixes never cached (they reflect the remembered filter)
_SUMMARY_SUFFIXES = (
    "/action-center/alerts/summary",
    "/territory/summary",
)

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


def caller_key(request: Request) -> str:
    """Identify the caller for the response-cache key and the per-caller Active
    Alerts filter memory, so both scope to the same 'user'.

    Authentication is disabled (see app/utils/auth.py), so every request already
    resolves to the SAME identity and sees the same data. Everyone therefore
    shares one namespace.

    This is not just a simplification - it is required for the warm-up to be
    worth anything. Keying on the Authorization header would file the warmed
    entries under the warm-up's own key, and every later caller would miss on
    every endpoint. Restoring real auth means restoring the per-caller branch
    here at the same time.
    """
    return "shared"


def _cache_key(request: Request) -> str:
    """Same user + same endpoint + same query = same cache entry."""
    query = str(sorted(request.query_params.multi_items()))
    return f"{request.method}:{request.url.path}:{query}:{caller_key(request)}"


def clear_all() -> int:
    n = len(_cache)
    _cache.clear()
    _save()
    return n


class DailyResponseCacheMiddleware(BaseHTTPMiddleware):
    """Cache GET responses permanently, keyed by endpoint + query + caller.
    No expiry — only cleared explicitly (clear_all(), the admin endpoint,
    or the app's own startup refresh)."""

    async def dispatch(self, request: Request, call_next):
        if request.method != "GET":
            return await call_next(request)

        path = request.url.path

        # Remember the module's filter on EVERY list call — even a cache hit, where
        # the route handler never runs — so its summary always mirrors the most
        # recent selection. (endswith excludes the '/summary' sub-paths.)
        for suffix, scope in _LIST_PATHS.items():
            if path.endswith(suffix):
                qp = request.query_params
                remember_filter(caller_key(request), FilterSelection(
                    manager_id=qp.get("manager_id"),
                    employee_id=qp.get("employee_id"),
                    territory_id=qp.get("territory_id"),
                ), scope=scope)
                break

        # Never cache a summary: it must recompute so its tiles reflect the latest
        # remembered filter (and the live data).
        if path.endswith(_SUMMARY_SUFFIXES):
            return await call_next(request)

        key = _cache_key(request)
        entry = _cache.get(key)

        if entry:
            logger.info("Response cache HIT: %s", request.url.path)
            body = base64.b64decode(entry["body"])
            headers = {"content-type": entry["content_type"]} if entry.get("content_type") else None
            return Response(content=body, status_code=entry["status_code"], headers=headers)

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
            }
            _save()
            logger.info("Response cache SET (permanent): %s", request.url.path)

            headers = {"content-type": content_type} if content_type else None
            return Response(content=body, status_code=response.status_code, headers=headers)

        return response
