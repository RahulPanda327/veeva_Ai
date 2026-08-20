"""
PostgreSQL-backed unified chat interaction store.
Single chat_interactions table stores every message + feedback.
Used when USE_REDIS_PG=True in .env.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from urllib.parse import urlparse, unquote

import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor, Json

from config.settings import get_config


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


@dataclass
class SessionSummaryPG:
    id: str
    title: Optional[str]
    message_count: int
    created_at: str
    updated_at: str
    # compat shims so sessions.py can use getattr(s, 'scenario', 1) safely
    scenario: int = 1
    provider: str = "groq"
    model: str = ""
    client_id: str = "api"
    user_id: str = ""


class _MockMessage:
    def __init__(self, id, session_id, role, content, created_at):
        self.id = id
        self.session_id = session_id
        self.role = role
        self.content = content
        self.created_at = created_at


class _MockSession:
    scenario = 1
    provider = "groq"
    model = ""
    client_id = "api"

    def __init__(self, row):
        self.id = row["id"]
        self.title = row["title"]
        self.message_count = row["message_count"]
        self.created_at = str(row["created_at"]) if row["created_at"] else ""
        self.updated_at = str(row["updated_at"]) if row["updated_at"] else ""
        self.user_id = row["user_id"]


class SessionStorePG:
    def __init__(self, db_url: Optional[str] = None):
        cfg = get_config()
        self.db_url = db_url or getattr(cfg, "postgres_url", "postgresql://postgres:postgres@localhost:5432/chatbot")
        parsed = urlparse(self.db_url)
        self.pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=unquote(parsed.password or ""),
            dbname=parsed.path.lstrip("/"),
        )
        self._init_db()

    @contextmanager
    def _conn(self):
        con = self.pool.getconn()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            self.pool.putconn(con)

    def _init_db(self):
        with self._conn() as con:
            with con.cursor() as cur:
                cur.execute("""
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
                        output_query       JSONB,
                        bot_status         JSONB,
                        processing_details JSONB,
                        feedback           JSONB,
                        created_at         TIMESTAMP WITH TIME ZONE,
                        updated_at         TIMESTAMP WITH TIME ZONE
                    );
                    CREATE INDEX IF NOT EXISTS idx_ci_session
                        ON chat_interactions(chat_session_id, message_index);
                    CREATE INDEX IF NOT EXISTS idx_ci_user
                        ON chat_interactions(user_id, updated_at DESC);
                """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Interaction CRUD ────────────────────────────────────────────────────────

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
        message_index: int = 0,
    ) -> None:
        now = self._now()
        with self._conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_interactions
                    (message_id, chat_session_id, message_index, tenant_id, project_id,
                     user_id, app_session_id, request_source, user_action_status,
                     input_query, output_query, bot_status, processing_details,
                     feedback, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (message_id) DO UPDATE SET
                        output_query       = EXCLUDED.output_query,
                        bot_status         = EXCLUDED.bot_status,
                        processing_details = EXCLUDED.processing_details,
                        feedback           = EXCLUDED.feedback,
                        user_action_status = EXCLUDED.user_action_status,
                        updated_at         = EXCLUDED.updated_at
                    """,
                    (
                        message_id, chat_session_id, message_index, tenant_id, project_id,
                        user_id, app_session_id, request_source, user_action_status,
                        input_query,
                        Json(output_query) if output_query is not None else None,
                        Json(bot_status) if bot_status is not None else None,
                        Json(processing_details) if processing_details is not None else None,
                        Json(feedback) if feedback is not None else None,
                        now, now,
                    ),
                )

    def get_interaction(self, message_id: str) -> Optional[InteractionRecord]:
        with self._conn() as con:
            with con.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM chat_interactions WHERE message_id = %s", (message_id,))
                row = cur.fetchone()
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
            with con.cursor() as cur:
                if bot_status is not None:
                    cur.execute(
                        "UPDATE chat_interactions SET feedback=%s, user_action_status=%s, bot_status=%s, updated_at=%s WHERE message_id=%s",
                        (Json(feedback), user_action_status, Json(bot_status), now, message_id),
                    )
                else:
                    cur.execute(
                        "UPDATE chat_interactions SET feedback=%s, user_action_status=%s, updated_at=%s WHERE message_id=%s",
                        (Json(feedback), user_action_status, now, message_id),
                    )
                return cur.rowcount > 0

    def get_session_interactions(self, chat_session_id: str) -> list[InteractionRecord]:
        with self._conn() as con:
            with con.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    "SELECT * FROM chat_interactions WHERE chat_session_id=%s ORDER BY message_index ASC",
                    (chat_session_id,),
                )
                rows = cur.fetchall()
        return [_to_interaction(r) for r in rows]

    def get_recent_interactions(self, limit: int = 50) -> list[InteractionRecord]:
        """Fetch the most recent interactions globally across all sessions."""
        with self._conn() as con:
            with con.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    "SELECT * FROM chat_interactions ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cur.fetchall()
        return [_to_interaction(r) for r in rows]

    def get_user_recent_interactions(self, user_id: str, limit: int = 50) -> list[InteractionRecord]:
        """Fetch the most recent interactions for a specific user, grouped by session."""
        with self._conn() as con:
            with con.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM chat_interactions
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cur.fetchall()
        return [_to_interaction(r) for r in rows]

    # ── Session-level helpers (compat with SessionStore interface) ──────────────

    def create_session(self, user_id: str, **kwargs) -> str:
        return kwargs.get("session_id") or str(uuid.uuid4())

    def get_session(self, session_id: str) -> Optional[_MockSession]:
        with self._conn() as con:
            with con.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    """
                    SELECT chat_session_id AS id,
                           COUNT(message_id) AS message_count,
                           MAX(updated_at)   AS updated_at,
                           MIN(created_at)   AS created_at,
                           MAX(user_id)      AS user_id,
                           (SELECT input_query FROM chat_interactions c2
                            WHERE c2.chat_session_id = ci.chat_session_id
                            ORDER BY message_index ASC LIMIT 1) AS title
                    FROM chat_interactions ci
                    WHERE chat_session_id = %s OR app_session_id = %s
                    GROUP BY chat_session_id
                    ORDER BY MIN(created_at) DESC
                    LIMIT 1
                    """,
                    (session_id, session_id),
                )
                row = cur.fetchone()
        return _MockSession(row) if row else None

    def list_sessions(self, user_id: str, limit: int = 50) -> list[SessionSummaryPG]:
        with self._conn() as con:
            with con.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    """
                    SELECT chat_session_id AS id,
                           COUNT(message_id) AS message_count,
                           MAX(updated_at)   AS updated_at,
                           MIN(created_at)   AS created_at,
                           (SELECT input_query FROM chat_interactions c2
                            WHERE c2.chat_session_id = ci.chat_session_id
                            ORDER BY message_index ASC LIMIT 1) AS title
                    FROM chat_interactions ci
                    WHERE user_id = %s
                    GROUP BY chat_session_id
                    ORDER BY MAX(updated_at) DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cur.fetchall()
        return [
            SessionSummaryPG(
                id=r["id"],
                title=r["title"],
                message_count=r["message_count"],
                created_at=str(r["created_at"]) if r["created_at"] else "",
                updated_at=str(r["updated_at"]) if r["updated_at"] else "",
            )
            for r in rows
        ]

    def delete_session(self, session_id: str, user_id: str) -> bool:
        with self._conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    "DELETE FROM chat_interactions WHERE chat_session_id=%s AND user_id=%s",
                    (session_id, user_id),
                )
                return cur.rowcount > 0

    def get_messages(self, session_id: str) -> list[_MockMessage]:
        messages: list[_MockMessage] = []
        for ix in self.get_session_interactions(session_id):
            messages.append(_MockMessage(ix.message_index, ix.chat_session_id, "user", ix.input_query, ix.created_at))
            if ix.output_query:
                answer = ix.output_query.get("answer") or ix.output_query.get("response", "")
                if answer:
                    messages.append(_MockMessage(ix.message_index * 1000, ix.chat_session_id, "assistant", str(answer), ix.updated_at))
        return messages

    def save_message(self, session_id: str, role: str, content: str):
        """Fallback called by ConversationMemoryRedis.add_message()."""
        now = self._now()
        with self._conn() as con:
            with con.cursor(cursor_factory=DictCursor) as cur:
                if role == "user":
                    cur.execute(
                        "SELECT MAX(message_index) AS max_idx FROM chat_interactions WHERE chat_session_id=%s",
                        (session_id,),
                    )
                    row = cur.fetchone()
                    next_idx = 0 if row["max_idx"] is None else row["max_idx"] + 1
                    mid = str(uuid.uuid4())
                    cur.execute(
                        """INSERT INTO chat_interactions
                           (message_id,chat_session_id,message_index,tenant_id,project_id,
                            user_id,app_session_id,request_source,user_action_status,
                            input_query,output_query,bot_status,processing_details,
                            feedback,created_at,updated_at)
                           VALUES(%s,%s,%s,'','','api_user','','api','user_chat',%s,NULL,NULL,NULL,NULL,%s,%s)""",
                        (mid, session_id, next_idx, content, now, now),
                    )
                else:
                    cur.execute(
                        "SELECT message_id FROM chat_interactions WHERE chat_session_id=%s ORDER BY message_index DESC LIMIT 1",
                        (session_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        cur.execute(
                            "UPDATE chat_interactions SET output_query=%s, updated_at=%s WHERE message_id=%s",
                            (Json({"response_type": "text", "answer": content}), now, row["message_id"]),
                        )

    def set_title(self, session_id: str, title: str):
        pass  # title is derived from first input_query dynamically

    def update_title(self, session_id: str, title: str, user_id: str) -> bool:
        with self._conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    "UPDATE chat_interactions SET input_query=%s WHERE chat_session_id=%s AND user_id=%s AND message_index=0",
                    (title, session_id, user_id),
                )
                return cur.rowcount > 0


def _to_interaction(row) -> InteractionRecord:
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
        output_query=row["output_query"] if row["output_query"] else None,
        bot_status=row["bot_status"] if row["bot_status"] else None,
        processing_details=row["processing_details"] if row["processing_details"] else None,
        feedback=row["feedback"] if row["feedback"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else "",
        updated_at=str(row["updated_at"]) if row["updated_at"] else "",
    )
