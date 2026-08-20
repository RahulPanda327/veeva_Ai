"""
SQLite-backed persistent session store.

Schema:
  sessions  — one row per conversation (metadata + ownership)
  messages  — one row per message turn, linked to a session

Hydration contract:
  ConversationMemory calls get_messages(session_id) on first access to
  reload the sliding window from disk after a server restart.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict

# Always resolve to <project-root>/dbs/chatbot.db regardless of CWD
_DB_PATH = Path(__file__).parent / "chatbot.db"


@dataclass
class SessionRecord:
    id: str
    user_id: str
    client_id: str
    scenario: int
    provider: str
    model: str
    title: Optional[str]
    message_count: int
    created_at: str
    updated_at: str


@dataclass
class MessageRecord:
    id: int
    session_id: str
    role: str
    content: str
    created_at: str


@dataclass
class InteractionRecord:
    message_id: str
    chat_session_id: str
    message_index: int
    tenant_id: str
    project_id: str
    user_id: str
    app_session_id: str
    request_source: str
    user_action_status: str
    input_query: str
    output_query: Optional[Dict[str, Any]]
    bot_status: Optional[list]
    processing_details: Optional[Dict[str, Any]]
    feedback: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str


class SessionStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or _DB_PATH)
        self._init_db()

    # ── Internal helpers ────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")  # concurrent read-write safe
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init_db(self):
        with self._conn() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id            TEXT PRIMARY KEY,
                    user_id       TEXT NOT NULL,
                    client_id     TEXT NOT NULL DEFAULT 'api',
                    scenario      INTEGER NOT NULL DEFAULT 1,
                    provider      TEXT NOT NULL DEFAULT 'groq',
                    model         TEXT NOT NULL DEFAULT '',
                    title         TEXT,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at);
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

                CREATE TABLE IF NOT EXISTS chat_interactions (
                    message_id         TEXT PRIMARY KEY,
                    chat_session_id    TEXT NOT NULL,
                    message_index      INTEGER NOT NULL DEFAULT 1,
                    tenant_id          TEXT DEFAULT '',
                    project_id         TEXT DEFAULT '',
                    user_id            TEXT NOT NULL,
                    app_session_id     TEXT DEFAULT '',
                    request_source     TEXT DEFAULT 'web',
                    user_action_status TEXT DEFAULT 'user_chat',
                    input_query        TEXT NOT NULL,
                    output_query       TEXT,
                    bot_status         TEXT,
                    processing_details TEXT,
                    feedback           TEXT,
                    created_at         TEXT NOT NULL,
                    updated_at         TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ci_session ON chat_interactions(chat_session_id, message_index);
                CREATE INDEX IF NOT EXISTS idx_ci_user ON chat_interactions(user_id, updated_at);
            """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Session lifecycle ───────────────────────────────────────────────────────

    def create_session(
        self,
        user_id: str,
        client_id: str = "api",
        scenario: int = 1,
        provider: str = "groq",
        model: str = "",
        session_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        now = self._now()
        with self._conn() as con:
            con.execute(
                """INSERT OR IGNORE INTO sessions
                   (id, user_id, client_id, scenario, provider, model, title,
                    message_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (sid, user_id, client_id, scenario, provider, model, title, now, now),
            )
        return sid

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return _to_session(row) if row else None

    def list_sessions(self, user_id: str, limit: int = 50) -> list[SessionRecord]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [_to_session(r) for r in rows]

    def delete_session(self, session_id: str, user_id: str) -> bool:
        with self._conn() as con:
            cur = con.execute(
                "DELETE FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
        return cur.rowcount > 0

    def set_title(self, session_id: str, title: str):
        """Set title only if one hasn't been assigned yet (first-message auto-title)."""
        with self._conn() as con:
            con.execute(
                "UPDATE sessions SET title = ? WHERE id = ? AND title IS NULL",
                (title[:80], session_id),
            )

    def update_title(self, session_id: str, title: str, user_id: str) -> bool:
        with self._conn() as con:
            cur = con.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (title[:80], self._now(), session_id, user_id),
            )
        return cur.rowcount > 0

    # ── Message persistence ─────────────────────────────────────────────────────
    def save_message(self, session_id: str, role: str, content: str):
        now = self._now()
        with self._conn() as con:
            con.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            con.execute(
                "UPDATE sessions SET message_count = message_count + 1, updated_at = ? WHERE id = ?",
                (now, session_id),
            )

    def get_messages(self, session_id: str) -> list[MessageRecord]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [_to_message(r) for r in rows]

    # ── Interaction persistence (feedback-aware per-message records) ────────────

    def save_interaction(
        self,
        message_id: str,
        chat_session_id: str,
        user_id: str,
        input_query: str,
        output_query: Optional[dict] = None,
        tenant_id: str = "",
        project_id: str = "",
        app_session_id: str = "",
        request_source: str = "web",
        user_action_status: str = "user_chat",
        bot_status: Optional[list] = None,
        processing_details: Optional[dict] = None,
        feedback: Optional[dict] = None,
        message_index: int = 1,
    ) -> None:
        now = self._now()
        with self._conn() as con:
            con.execute(
                """INSERT OR REPLACE INTO chat_interactions
                   (message_id, chat_session_id, message_index, tenant_id, project_id,
                    user_id, app_session_id, request_source, user_action_status,
                    input_query, output_query, bot_status, processing_details,
                    feedback, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    message_id, chat_session_id, message_index, tenant_id, project_id,
                    user_id, app_session_id, request_source, user_action_status,
                    input_query,
                    json.dumps(output_query) if output_query is not None else None,
                    json.dumps(bot_status) if bot_status is not None else None,
                    json.dumps(processing_details) if processing_details is not None else None,
                    json.dumps(feedback) if feedback is not None else None,
                    now, now,
                ),
            )

    def get_interaction(self, message_id: str) -> Optional[InteractionRecord]:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM chat_interactions WHERE message_id = ?", (message_id,)
            ).fetchone()
        return _to_interaction(row) if row else None

    def update_feedback(
        self,
        message_id: str,
        feedback: dict,
        user_action_status: str,
        bot_status: Optional[list] = None,
    ) -> bool:
        now = self._now()
        with self._conn() as con:
            if bot_status is not None:
                cur = con.execute(
                    "UPDATE chat_interactions SET feedback=?, user_action_status=?, bot_status=?, updated_at=? WHERE message_id=?",
                    (json.dumps(feedback), user_action_status, json.dumps(bot_status), now, message_id),
                )
            else:
                cur = con.execute(
                    "UPDATE chat_interactions SET feedback=?, user_action_status=?, updated_at=? WHERE message_id=?",
                    (json.dumps(feedback), user_action_status, now, message_id),
                )
        return cur.rowcount > 0

    def get_session_interactions(self, chat_session_id: str) -> list[InteractionRecord]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM chat_interactions WHERE chat_session_id=? ORDER BY message_index ASC",
                (chat_session_id,),
            ).fetchall()
        return [_to_interaction(r) for r in rows]


# ── Row mappers (module-level to keep the class clean) ──────────────────────────

def _to_session(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        user_id=row["user_id"],
        client_id=row["client_id"],
        scenario=row["scenario"],
        provider=row["provider"],
        model=row["model"],
        title=row["title"],
        message_count=row["message_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_message(row: sqlite3.Row) -> MessageRecord:
    return MessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )


def _to_interaction(row: sqlite3.Row) -> InteractionRecord:
    def _j(val):
        return json.loads(val) if val else None

    return InteractionRecord(
        message_id=row["message_id"],
        chat_session_id=row["chat_session_id"],
        message_index=row["message_index"],
        tenant_id=row["tenant_id"] or "",
        project_id=row["project_id"] or "",
        user_id=row["user_id"],
        app_session_id=row["app_session_id"] or "",
        request_source=row["request_source"] or "web",
        user_action_status=row["user_action_status"] or "user_chat",
        input_query=row["input_query"],
        output_query=_j(row["output_query"]),
        bot_status=_j(row["bot_status"]),
        processing_details=_j(row["processing_details"]),
        feedback=_j(row["feedback"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
