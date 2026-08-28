"""Every chat exchange, persisted in the Datastream `chat_interactions` format.

WHY THIS SHAPE
    It is the format the previous chatbot already writes and that downstream
    tooling already reads, and it happens to be exactly the response envelope
    this endpoint returns - message_id, chat_session_id, message_index, the
    tenant/project/user triple, input_query, and the output_query /  bot_status /
    processing_details / feedback JSONB blocks. So a row is the response, stored
    verbatim: no second mapping to keep in step with the API.

ONE ROW PER MESSAGE, NOT PER SESSION
    The earlier assistant_sessions table kept a whole conversation in one JSONB
    column, which suited the memory window and nothing else. This table answers
    the questions that actually get asked of chat history - what did user X ask,
    which answers came from cache, what was slow, what did the model say on the
    18th - none of which a per-session blob supports without unpacking it first.

    Conversation memory now reads from here too, so there is ONE record of what
    was said rather than two that can disagree.

FAILURES ARE SWALLOWED
    Logging an exchange must never break the exchange. Every method degrades to
    "no history" rather than raising: the answer has already been produced and
    the user should get it.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.config import settings

log = logging.getLogger(__name__)

_ready: Optional[bool] = None

# Matches the previous chatbot's table exactly, so an existing database needs no
# migration and the two applications can share one history.
_DDL = """
    CREATE TABLE IF NOT EXISTS chat_interactions (
        message_id          TEXT PRIMARY KEY,
        chat_session_id     TEXT NOT NULL,
        message_index       INTEGER NOT NULL,
        tenant_id           TEXT,
        project_id          TEXT,
        user_id             TEXT NOT NULL,
        app_session_id      TEXT,
        request_source      TEXT,
        user_action_status  TEXT,
        input_query         TEXT NOT NULL,
        output_query        JSONB,
        bot_status          JSONB,
        processing_details  JSONB,
        feedback            JSONB,
        created_at          TIMESTAMPTZ,
        updated_at          TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS chat_interactions_session_idx
        ON chat_interactions (chat_session_id, message_index);
"""


def enabled() -> bool:
    return (settings.ASSISTANT_SESSION_STORE or "file").strip().lower() in (
        "postgres", "postgresql", "pg")


def _connect():
    import psycopg2   # noqa: PLC0415

    return psycopg2.connect(settings.POSTGRES_URL, connect_timeout=5)


def _ensure() -> bool:
    global _ready
    if _ready is not None:
        return _ready
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(_DDL)
        _ready = True
        log.info("Chat history: PostgreSQL table chat_interactions ready.")
    except Exception as exc:  # noqa: BLE001
        _ready = False
        log.warning("Could not prepare chat_interactions (%s); "
                    "chat history will not be stored.", exc)
    return _ready


def next_message_index(chat_session_id: str) -> int:
    """The next index in this thread.

    Derived from the table rather than counted in memory: several processes may
    serve the same session, and an in-memory counter would restart at 0 on each
    one and collide.
    """
    if not (enabled() and _ensure()):
        return 0
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(message_index), -1) + 1 "
                        "FROM chat_interactions WHERE chat_session_id = %s",
                        (chat_session_id,))
            return int(cur.fetchone()[0])
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read message index (%s); using 0.", exc)
        return 0


def record(envelope: Dict[str, Any]) -> None:
    """Store one exchange. `envelope` is the response body this endpoint returns."""
    if not (enabled() and _ensure()):
        return
    try:
        r = envelope
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_interactions
                    (message_id, chat_session_id, message_index, tenant_id,
                     project_id, user_id, app_session_id, request_source,
                     user_action_status, input_query, output_query, bot_status,
                     processing_details, feedback, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)
                ON CONFLICT (message_id) DO NOTHING
                """,
                (r.get("message_id"), r.get("chat_session_id"),
                 int(r.get("message_index") or 0), r.get("tenant_id") or "",
                 r.get("project_id") or "", r.get("user_id") or "",
                 r.get("app_session_id"), r.get("request_source") or "web",
                 r.get("user_action_status") or "user_chat",
                 r.get("input_query") or "",
                 json.dumps(r.get("output_query") or {}),
                 json.dumps(r.get("bot_status") or []),
                 json.dumps(r.get("processing_details") or {}),
                 json.dumps(r.get("feedback") or {}),
                 r.get("created_at"), r.get("updated_at")),
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not store chat interaction (%s).", exc)


def history_for_llm(chat_session_id: str, window_turns: int) -> List[Dict[str, str]]:
    """The last `window_turns` exchanges, as chat messages, oldest first.

    Only rows that carry a real answer are returned. Greetings, validation
    failures and errors are stored - the audit trail should show them - but they
    are not part of the conversation the model needs, and including them would
    push real turns out of the window.
    """
    if not (enabled() and _ensure()):
        return []
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT input_query, output_query->>'answer'
                FROM chat_interactions
                WHERE chat_session_id = %s
                  AND processing_details->>'answer_type' NOT IN
                      ('greeting', 'validation', 'error', 'no_match', 'rate_limited')
                ORDER BY message_index DESC
                LIMIT %s
                """,
                (chat_session_id, max(1, int(window_turns))),
            )
            rows = cur.fetchall()
        out: List[Dict[str, str]] = []
        for question, answer in reversed(rows):      # oldest first
            if question and answer:
                out.append({"role": "user", "content": question})
                out.append({"role": "assistant", "content": answer})
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read chat history (%s); answering without it.", exc)
        return []


def stats() -> Dict[str, Any]:
    if not (enabled() and _ensure()):
        return {"backend": "disabled"}
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), COUNT(DISTINCT chat_session_id) "
                        "FROM chat_interactions")
            messages, sessions = cur.fetchone()
        return {"backend": "postgres", "table": "chat_interactions",
                "messages": int(messages), "sessions": int(sessions)}
    except Exception as exc:  # noqa: BLE001
        return {"backend": "postgres", "error": str(exc)[:120]}
