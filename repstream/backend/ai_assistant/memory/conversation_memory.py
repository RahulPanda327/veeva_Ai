"""
ConversationMemory — in-process sliding window + TTL cache.

Persistence integration
───────────────────────
When a SessionStore is injected (always the case in production), every
add_message() call is double-written: once to the in-memory deque and once
to SQLite. On the first access of a session_id that isn't in the in-memory
dict (e.g. after a server restart), _session() hydrates the deque from the
DB so the LLM sees the correct prior context.
"""

from __future__ import annotations

import hashlib
from collections import deque
from typing import Optional, TYPE_CHECKING

from cachetools import TTLCache

from config.settings import get_config
from utils.logging_util import setup_logging

if TYPE_CHECKING:
    from dbs.session_store import SessionStore

logger = setup_logging("memory")


class ConversationMemory:
    def __init__(self, store: Optional["SessionStore"] = None):
        self.cfg = get_config()
        self._store = store
        self._sessions: dict[str, deque] = {}
        self._cache: TTLCache = TTLCache(
            maxsize=self.cfg.max_cache_entries,
            ttl=self.cfg.cache_ttl_seconds,
        )

    # ── Session window ──────────────────────────────────────────────────────────

    def _session(self, session_id: str) -> deque:
        """
        Return the in-memory deque for a session.
        If not present (first access / server restart), hydrate from the DB.
        """
        if session_id not in self._sessions:
            window = self.cfg.memory_window_size * 2   # user + assistant per turn
            d: deque = deque(maxlen=window)
            if self._store is not None:
                persisted = self._store.get_messages(session_id)
                # Load only the most recent window so the deque doesn't overflow
                for msg in persisted[-window:]:
                    d.append({"role": msg.role, "content": msg.content})
                if persisted:
                    logger.info({
                        "event": "session_hydrated",
                        "session_id": session_id,
                        "loaded": min(len(persisted), window),
                        "total_in_db": len(persisted),
                    })
            self._sessions[session_id] = d
        return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str):
        """Append a message to the in-memory window and persist it to the DB."""
        self._session(session_id).append({"role": role, "content": content})
        if self._store is not None:
            self._store.save_message(session_id, role, content)

    def get_context(self, session_id: str) -> list[dict]:
        return list(self._session(session_id))

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
        """Reset the in-memory window (history stays in DB, LLM context resets)."""
        if session_id in self._sessions:
            self._sessions[session_id].clear()
        logger.info({"event": "session_window_cleared", "session_id": session_id})

    def evict_session(self, session_id: str):
        """Remove session from RAM (called after DB deletion to free memory)."""
        self._sessions.pop(session_id, None)

    # ── Response cache ──────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(query: str, scenario: int, provider: str) -> str:
        raw = f"{query.strip().lower()}|{scenario}|{provider}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get_cached(self, query: str, scenario: int, provider: str) -> Optional[str]:
        if not self.cfg.cache_enabled:
            return None
        key = self._cache_key(query, scenario, provider)
        hit = self._cache.get(key)
        if hit:
            logger.info({"event": "cache_hit", "key_prefix": key[:8]})
        return hit

    def set_cached(self, query: str, scenario: int, provider: str, response: str):
        if not self.cfg.cache_enabled:
            return
        self._cache[self._cache_key(query, scenario, provider)] = response

    # ── Introspection ────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "active_sessions": len(self._sessions),
            "cache_enabled": self.cfg.cache_enabled,
            "cache_size": len(self._cache),
            "cache_max": self.cfg.max_cache_entries,
            "cache_ttl_seconds": self.cfg.cache_ttl_seconds,
            "memory_window_size": self.cfg.memory_window_size,
        }
