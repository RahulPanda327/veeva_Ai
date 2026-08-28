"""Where conversation sessions are persisted — one swappable backend.

WHY AN INTERFACE FOR ONE IMPLEMENTATION
    The storage decision is explicitly deferred: local file today, possibly
    Redis or Postgres later. Everything above this module (session management,
    conversation memory, the chat service) talks to SessionStore and never
    touches a file path, so making that decision later means writing one class
    and changing one .env value - not rewriting the memory layer.

    That is the same mistake this project already paid for once: the vector
    store was wired directly to pgvector, and prising it out later touched the
    ingest script, the chat service and the deployment docs.

FILE FORMAT  (cache/assistant_sessions.json)
    {"<session_id>": {"created_at": epoch, "last_seen": epoch,
                      "device_id": "...",
                      "turns": [{"role": "user"|"assistant",
                                 "content": "...", "at": epoch}, ...]}}

    One document for every session rather than a file per session: at this scale
    the whole thing is tens of KB, and a single atomic os.replace cannot leave
    two files disagreeing about the same conversation.

CONCURRENCY
    A process-wide lock guards the dict, and writes go through a temp file +
    os.replace. That is enough for one server process. It is NOT enough for two
    processes sharing one file - the second writer's copy wins wholesale. If the
    app is ever run multi-worker, that is the point to move to Redis, not to add
    file locking.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional, Protocol

from app.config import settings
from app.utils.cache_paths import cache_file


class SessionStore(Protocol):
    """The contract a backend must satisfy. Deliberately tiny: sessions are read
    and written whole, because a turn is only ever appended to the end and the
    window is small enough that partial updates buy nothing."""

    def get(self, session_id: str) -> Optional[Dict[str, Any]]: ...
    def put(self, session_id: str, session: Dict[str, Any]) -> None: ...
    def delete(self, session_id: str) -> None: ...
    def all_sessions(self) -> Dict[str, Dict[str, Any]]: ...
    def flush(self) -> None: ...


class JSONFileSessionStore:
    """Sessions in one JSON file under backend/cache/.

    Chosen over the chatbot's existing Postgres SessionStore because that one
    needs POSTGRES_URL and a running server - the exact dependency this project
    removed when it dropped pgvector. A file matches every other cache here and
    works on a fresh checkout with nothing installed.
    """

    def __init__(self, path=None) -> None:
        self._path = path or cache_file("assistant_sessions.json")
        self._lock = threading.Lock()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            with open(self._path, encoding="utf-8") as f:
                self._sessions = json.load(f) or {}
            _log().info("Loaded %d chat session(s) from %s",
                        len(self._sessions), self._path.name)
        except FileNotFoundError:
            pass
        except Exception as exc:  # noqa: BLE001 — a corrupt file must not stop the app
            _log().warning("Could not load chat sessions (%s); starting empty.", exc)
            self._sessions = {}

    def flush(self) -> None:
        """Write the whole document atomically.

        Nothing here is worth failing a chat answer over: a lost turn degrades
        the next reply, an exception would deny it entirely.
        """
        if not self._dirty:
            return
        try:
            tmp = self._path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._sessions, f, ensure_ascii=False)
            os.replace(tmp, self._path)
            self._dirty = False
        except Exception as exc:  # noqa: BLE001
            _log().warning("Could not save chat sessions (%s).", exc)

    # ── SessionStore ─────────────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            s = self._sessions.get(session_id)
            # Copied out so a caller mutating the result cannot change stored
            # state without going through put() - which is what keeps _dirty
            # honest and the file in step with memory.
            return json.loads(json.dumps(s)) if s is not None else None

    def put(self, session_id: str, session: Dict[str, Any]) -> None:
        with self._lock:
            self._sessions[session_id] = session
            self._dirty = True
        self.flush()

    def delete(self, session_id: str) -> None:
        with self._lock:
            if self._sessions.pop(session_id, None) is not None:
                self._dirty = True
        self.flush()

    def all_sessions(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._sessions)

    def replace_all(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        """Used by pruning, which rewrites the whole set in one pass rather than
        deleting one id at a time (each delete would otherwise flush the file)."""
        with self._lock:
            self._sessions = sessions
            self._dirty = True
        self.flush()


class PostgresSessionStore:
    """Sessions in PostgreSQL — one row per session, the turns as JSONB.

    WHY A ROW PER SESSION RATHER THAN A ROW PER MESSAGE
        A message table is the more obvious schema and the wrong one here. Every
        read wants the whole window at once, so a message table means an ORDER BY
        + LIMIT on each question; and the window is trimmed on write anyway, so
        the rows would be deleted almost as fast as they were inserted. One JSONB
        column is read and written whole, which is exactly how the memory layer
        above uses it.

    WHY IT SURVIVES POSTGRES BEING DOWN
        Chat must keep working when the database does not. Every method swallows
        connection errors and degrades to "no memory": answers stop carrying
        conversation context, but they still arrive. The alternative - a 500 on
        the chat endpoint because a session could not be written - trades a
        feature for the whole service.

    CONNECTIONS
        One short-lived connection per operation rather than a pool. Chat volume
        here is a handful of requests a minute, and a pool that must be closed
        cleanly is a second failure mode for no measurable gain at this rate.
    """

    _DDL = """
        CREATE TABLE IF NOT EXISTS assistant_sessions (
            session_id  TEXT PRIMARY KEY,
            created_at  DOUBLE PRECISION NOT NULL,
            last_seen   DOUBLE PRECISION NOT NULL,
            device_id   TEXT DEFAULT '',
            turns       JSONB NOT NULL DEFAULT '[]'::jsonb
        );
        CREATE INDEX IF NOT EXISTS assistant_sessions_last_seen_idx
            ON assistant_sessions (last_seen);
    """

    def __init__(self) -> None:
        self._dsn = settings.POSTGRES_URL
        self._ready = False
        self._ensure_table()

    def _connect(self):
        import psycopg2   # noqa: PLC0415

        return psycopg2.connect(self._dsn, connect_timeout=5)

    def _ensure_table(self) -> None:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(self._DDL)
            self._ready = True
            _log().info("Assistant session store: PostgreSQL table assistant_sessions ready.")
        except Exception as exc:  # noqa: BLE001
            _log().warning(
                "Could not prepare assistant_sessions in PostgreSQL (%s). "
                "Chat will run WITHOUT conversation memory until it is reachable.", exc)

    # ── SessionStore ─────────────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT created_at, last_seen, device_id, turns "
                    "FROM assistant_sessions WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
            if not row:
                return None
            return {"created_at": row[0], "last_seen": row[1],
                    "device_id": row[2] or "", "turns": row[3] or []}
        except Exception as exc:  # noqa: BLE001
            _log().warning("Session read failed (%s); continuing without memory.", exc)
            return None

    def put(self, session_id: str, session: Dict[str, Any]) -> None:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assistant_sessions
                        (session_id, created_at, last_seen, device_id, turns)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (session_id) DO UPDATE SET
                        last_seen = EXCLUDED.last_seen,
                        device_id = EXCLUDED.device_id,
                        turns     = EXCLUDED.turns
                    """,
                    (session_id, session.get("created_at"), session.get("last_seen"),
                     session.get("device_id") or "",
                     json.dumps(session.get("turns") or [])),
                )
        except Exception as exc:  # noqa: BLE001
            _log().warning("Session write failed (%s); the turn was not stored.", exc)

    def delete(self, session_id: str) -> None:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM assistant_sessions WHERE session_id = %s",
                            (session_id,))
        except Exception as exc:  # noqa: BLE001
            _log().warning("Session delete failed (%s).", exc)

    def all_sessions(self) -> Dict[str, Dict[str, Any]]:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT session_id, created_at, last_seen, device_id, turns "
                            "FROM assistant_sessions")
                rows = cur.fetchall()
            return {r[0]: {"created_at": r[1], "last_seen": r[2],
                           "device_id": r[3] or "", "turns": r[4] or []} for r in rows}
        except Exception as exc:  # noqa: BLE001
            _log().warning("Session listing failed (%s).", exc)
            return {}

    def replace_all(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        """Pruning path: delete what is no longer wanted.

        Expressed as a DELETE of the complement rather than TRUNCATE + reinsert.
        Rewriting every row to drop a few would lose any session written by
        another process between the read and the write - and unlike the file
        store, the whole point of Postgres here is that several processes CAN
        share it.
        """
        try:
            keep = list(sessions.keys())
            with self._connect() as conn, conn.cursor() as cur:
                if keep:
                    cur.execute("DELETE FROM assistant_sessions "
                                "WHERE NOT (session_id = ANY(%s))", (keep,))
                else:
                    cur.execute("DELETE FROM assistant_sessions")
        except Exception as exc:  # noqa: BLE001
            _log().warning("Session prune failed (%s).", exc)

    def flush(self) -> None:
        """Nothing buffered — every write is committed by its own transaction."""
        return


def _log():
    import logging   # noqa: PLC0415

    return logging.getLogger(__name__)


_instance: Optional[Any] = None


def get_session_store():
    """The configured store (a process-level singleton).

    ASSISTANT_SESSION_STORE selects the backend. Only 'file' exists today; the
    branch is here so adding 'redis' later is a new class and one elif, with no
    caller changes.
    """
    global _instance
    if _instance is None:
        backend = (settings.ASSISTANT_SESSION_STORE or "file").strip().lower()
        if backend in ("file", "json", "local"):
            _instance = JSONFileSessionStore()
        elif backend in ("postgres", "postgresql", "pg"):
            _instance = PostgresSessionStore()
        else:
            raise ValueError(
                f"ASSISTANT_SESSION_STORE={backend!r} is not a known backend. "
                f"Use 'file' or 'postgres'."
            )
    return _instance
