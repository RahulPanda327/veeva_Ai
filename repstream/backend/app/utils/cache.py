"""Redis cache helpers for RepStream.

Caching is entirely optional — every function here degrades to a silent
no-op (cache miss) if Redis isn't reachable. The app works identically
either way, just without response caching. Once Redis is found to be down,
no further connection attempts or log messages happen for the rest of the
process — set REDIS_URL and restart if you want caching enabled later.
"""
import json
import logging
from typing import Any, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None
_disabled = False


def _get_redis() -> Optional[redis.Redis]:
    global _redis_client, _disabled

    if _disabled:
        return None

    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        _redis_client.ping()
        return _redis_client
    except Exception:
        _disabled = True
        logger.info("Redis not reachable — caching disabled for this process.")
        return None


def cache_get(key: str) -> Optional[Any]:
    r = _get_redis()
    if r is None:
        return None
    try:
        value = r.get(key)
        return json.loads(value) if value is not None else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL_DEFAULT) -> bool:
    r = _get_redis()
    if r is None:
        return False
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception:
        return False


def cache_delete(key: str) -> bool:
    r = _get_redis()
    if r is None:
        return False
    try:
        r.delete(key)
        return True
    except Exception:
        return False


def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern. Returns count deleted."""
    r = _get_redis()
    if r is None:
        return 0
    try:
        keys = list(r.scan_iter(pattern))
        return r.delete(*keys) if keys else 0
    except Exception:
        return 0


def territory_cache_key(prefix: str, territory_id: str) -> str:
    return f"{prefix}:{territory_id}"
