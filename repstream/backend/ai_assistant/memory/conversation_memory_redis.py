"""
ConversationMemoryRedis — Redis-backed sliding window + TTL response cache.
Used when USE_REDIS_PG=True in .env.
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional, TYPE_CHECKING

import redis

from config.settings import get_config
from utils.logging_util import setup_logging

if TYPE_CHECKING:
    from dbs.session_store import SessionStore
    from dbs.session_store_pg import SessionStorePG

logger = setup_logging("memory_redis")


class ConversationMemoryRedis:
    def __init__(self, store: Optional["SessionStore | SessionStorePG"] = None):
        self.cfg = get_config()
        self._store = store
        redis_url = getattr(self.cfg, "redis_url", "redis://localhost:6379/0")
        self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

    # ── Session window ──────────────────────────────────────────────────────────

    def _window_key(self, session_id: str) -> str:
        return f"session_window:{session_id}"

    def _ensure_hydrated(self, session_id: str, window_key: str):
        """Load history from DB into Redis if the key doesn't exist yet."""
        if self.redis_client.exists(window_key):
            return
        window = self.cfg.memory_window_size * 2
        if self._store is None:
            return
        persisted = self._store.get_messages(session_id)
        to_cache = persisted[-window:]
        if not to_cache:
            return
        pipe = self.redis_client.pipeline()
        for msg in to_cache:
            pipe.rpush(window_key, json.dumps({"role": msg.role, "content": msg.content}))
        pipe.execute()
        logger.info({
            "event": "session_hydrated",
            "session_id": session_id,
            "loaded": len(to_cache),
            "total_in_db": len(persisted),
            "backend": "redis",
        })

    def add_message(self, session_id: str, role: str, content: str):
        window_key = self._window_key(session_id)
        self._ensure_hydrated(session_id, window_key)
        window_size = self.cfg.memory_window_size * 2
        item = json.dumps({"role": role, "content": content})
        pipe = self.redis_client.pipeline()
        pipe.rpush(window_key, item)
        pipe.ltrim(window_key, -window_size, -1)
        pipe.execute()
        if self._store is not None:
            self._store.save_message(session_id, role, content)

    def get_context(self, session_id: str) -> list[dict]:
        window_key = self._window_key(session_id)
        self._ensure_hydrated(session_id, window_key)
        return [json.loads(item) for item in self.redis_client.lrange(window_key, 0, -1)]

    def get_messages_for_llm(
        self,
        session_id: str,
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(self.get_context(session_id))
        return messages

    def clear_session(self, session_id: str):
        self.redis_client.delete(self._window_key(session_id))
        logger.info({"event": "session_window_cleared", "session_id": session_id})

    def evict_session(self, session_id: str):
        self.clear_session(session_id)

    # ── Response cache ──────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(query: str, scenario: int, provider: str) -> str:
        raw = f"{query.strip().lower()}|{scenario}|{provider}"
        return f"query_cache:{hashlib.md5(raw.encode()).hexdigest()}"

    def get_cached(self, query: str, scenario: int, provider: str) -> Optional[str]:
        if not self.cfg.cache_enabled:
            return None
        key = self._cache_key(query, scenario, provider)
        hit = self.redis_client.get(key)
        if hit:
            logger.info({"event": "cache_hit", "key_suffix": key[-8:]})
        return hit

    def set_cached(self, query: str, scenario: int, provider: str, response: str):
        if not self.cfg.cache_enabled:
            return
        key = self._cache_key(query, scenario, provider)
        self.redis_client.setex(key, self.cfg.cache_ttl_seconds, response)

    # ── Introspection ────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        try:
            info = self.redis_client.info("memory")
            return {
                "redis_connected": True,
                "keys_count": self.redis_client.dbsize(),
                "used_memory_human": info.get("used_memory_human", "?"),
                "cache_enabled": self.cfg.cache_enabled,
                "cache_ttl_seconds": self.cfg.cache_ttl_seconds,
                "memory_window_size": self.cfg.memory_window_size,
            }
        except redis.RedisError:
            return {"redis_connected": False}
