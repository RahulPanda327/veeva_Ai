"""Redis cache helpers for RepStream."""
import json
import logging
from typing import Any, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    try:
        r = _get_redis()
        value = r.get(key)
        if value is None:
            return None
        return json.loads(value)
    except Exception as exc:
        logger.warning("Cache GET failed for key %s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL_DEFAULT) -> bool:
    try:
        r = _get_redis()
        serialized = json.dumps(value, default=str)
        r.setex(key, ttl, serialized)
        return True
    except Exception as exc:
        logger.warning("Cache SET failed for key %s: %s", key, exc)
        return False


def cache_delete(key: str) -> bool:
    try:
        _get_redis().delete(key)
        return True
    except Exception as exc:
        logger.warning("Cache DELETE failed for key %s: %s", key, exc)
        return False


def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern. Returns count deleted."""
    try:
        r = _get_redis()
        keys = list(r.scan_iter(pattern))
        if keys:
            return r.delete(*keys)
        return 0
    except Exception as exc:
        logger.warning("Cache DELETE PATTERN failed for %s: %s", pattern, exc)
        return 0


def territory_cache_key(prefix: str, territory_id: str) -> str:
    return f"{prefix}:{territory_id}"
