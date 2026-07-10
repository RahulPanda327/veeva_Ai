"""Wraps every JSON API response in a standard {success, response} envelope,
pretty-printed (indented, one key per line) instead of FastAPI's default
compact single-line JSON.

Registered in main.py, added BEFORE DailyResponseCacheMiddleware (so the
cache stores the already-wrapped, already-indented body) and BEFORE
CORSMiddleware. Skips the docs/openapi/redoc paths so Swagger UI keeps
working — those need the raw OpenAPI schema, not a wrapped one.
"""
from __future__ import annotations

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_SKIP_PATH_PREFIXES = ("/api/docs", "/api/redoc", "/api/openapi.json")


class EnvelopeMiddleware(BaseHTTPMiddleware):
    """Wrap every JSON response as {"success": bool, "response": <original body>}."""

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in _SKIP_PATH_PREFIXES):
            return await call_next(request)

        response = await call_next(request)

        if "application/json" not in (response.headers.get("content-type") or ""):
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            original = json.loads(body) if body else None
        except json.JSONDecodeError:
            # Not actually JSON despite the content-type header — pass through untouched.
            # (.media_type is unreliable through call_next()'s wrapper — use the real header.)
            content_type = response.headers.get("content-type")
            headers = {"content-type": content_type} if content_type else None
            return Response(content=body, status_code=response.status_code, headers=headers)

        wrapped = {
            "success": 200 <= response.status_code < 300,
            "response": original,
        }
        new_body = json.dumps(wrapped, default=str, indent=2).encode("utf-8")

        return Response(content=new_body, status_code=response.status_code, media_type="application/json")
