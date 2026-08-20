"""
Application-level logging — writes to the single `application_logs` table
in the existing PostgreSQL chatbot_db.

All log types are stored in one table, distinguished by `log_type`:
  'application'  — chat processing success / app events
  'user_feedback'— user votes / comments
  'auth'         — login / authentication events
  'error'        — exception stack traces
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from utils.logging_util import setup_logging

logger = setup_logging("application_logs")

# ── Action constants ──────────────────────────────────────────────────────────
ACTION_USER_CHAT     = "user_chat"
ACTION_GOOD_RESPONSE = "good_response"
ACTION_BAD_RESPONSE  = "bad_response"
ACTION_REMARK        = "remark"

# ── Status codes ──────────────────────────────────────────────────────────────
STATUS_CODE_SUCCESS = "SUCCESS"
STATUS_CODE_FAILED  = "FAILED"

# ── Status levels ─────────────────────────────────────────────────────────────
STATUS_LEVEL_INFO     = "INFO"
STATUS_LEVEL_WARNING  = "WARNING"
STATUS_LEVEL_ERROR    = "ERROR"
STATUS_LEVEL_CRITICAL = "CRITICAL"

# ── App-status sentinels ──────────────────────────────────────────────────────
APP_STATUS_SUCCESS = {
    "status_code": STATUS_CODE_SUCCESS,
    "status_level": STATUS_LEVEL_INFO,
    "status_message": "Response generated successfully",
}
APP_STATUS_ERROR = {
    "status_code": STATUS_CODE_FAILED,
    "status_level": STATUS_LEVEL_ERROR,
    "status_message": "Request processing failed",
}

# ── Auth event constants ──────────────────────────────────────────────────────
AUTH_EVENT_SUCCESS             = "SUCCESS"
AUTH_EVENT_INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
AUTH_EVENT_USER_NOT_FOUND      = "USER_NOT_FOUND"

AUTH_EVENT_CATALOG: dict[str, tuple[str, str]] = {
    "SUCCESS":               ("Login successful",                       STATUS_LEVEL_INFO),
    "INVALID_CREDENTIALS":   ("Invalid password provided",              STATUS_LEVEL_WARNING),
    "USER_NOT_FOUND":        ("Username not found",                     STATUS_LEVEL_WARNING),
    "ACCOUNT_LOCKED":        ("Account is locked",                      STATUS_LEVEL_WARNING),
    "ACCOUNT_DISABLED":      ("Account is disabled",                    STATUS_LEVEL_WARNING),
    "PASSWORD_EXPIRED":      ("Password has expired",                   STATUS_LEVEL_WARNING),
    "MFA_REQUIRED":          ("Multi-factor authentication required",   STATUS_LEVEL_INFO),
    "MFA_FAILED":            ("Multi-factor authentication failed",     STATUS_LEVEL_WARNING),
    "SESSION_EXPIRED":       ("Session has expired",                    STATUS_LEVEL_INFO),
    "TOKEN_EXPIRED":         ("Token has expired",                      STATUS_LEVEL_INFO),
    "UNAUTHORIZED":          ("Unauthorized access attempt",            STATUS_LEVEL_WARNING),
    "FORBIDDEN":             ("Forbidden — insufficient permissions",   STATUS_LEVEL_WARNING),
    "NETWORK_ERROR":         ("Network error during authentication",    STATUS_LEVEL_ERROR),
    "DATABASE_ERROR":        ("Database error during authentication",   STATUS_LEVEL_ERROR),
    "INTERNAL_SERVER_ERROR": ("Internal server error",                  STATUS_LEVEL_ERROR),
}


class ApplicationLogger:
    """
    Writes all log types into the single `application_logs` table
    in PostgreSQL chatbot_db.
    """

    def __init__(self, db_url: str):
        import psycopg2
        from psycopg2 import pool
        from urllib.parse import urlparse, unquote
        parsed = urlparse(db_url)
        self._pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=unquote(parsed.password or ""),
            dbname=parsed.path.lstrip("/"),
        )
        self._ensure_table()

    @contextmanager
    def _conn(self):
        con = self._pool.getconn()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            self._pool.putconn(con)

    def _ensure_table(self):
        """
        Creates application_logs table if it doesn't exist.
        If the table already exists, checks that required columns are present
        and adds any that are missing (safe for existing DBs).
        """
        with self._conn() as con:
            with con.cursor() as cur:

                # Step 1 — create table only if it does not exist at all
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS application_logs (
                        id             SERIAL PRIMARY KEY,
                        log_type       TEXT NOT NULL DEFAULT 'application',
                        status_type    TEXT NOT NULL DEFAULT 'application',
                        status_code    TEXT NOT NULL DEFAULT 'SUCCESS',
                        status_level   TEXT NOT NULL DEFAULT 'INFO',
                        status_message TEXT,
                        user_id        TEXT DEFAULT '',
                        session_id     TEXT DEFAULT '',
                        tenant_id      TEXT DEFAULT '',
                        project_id     TEXT DEFAULT '',
                        request_source TEXT DEFAULT 'web',
                        message_id     TEXT DEFAULT '',
                        input_query    TEXT DEFAULT '',
                        output_query   TEXT DEFAULT '',
                        error_type     TEXT DEFAULT '',
                        error_message  TEXT DEFAULT '',
                        stack_trace    TEXT DEFAULT '',
                        scenario       INTEGER DEFAULT 0,
                        metadata       JSONB,
                        created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)

                # Step 2 — add any columns that may be missing in an older table
                _required_columns = {
                    "log_type":       "TEXT NOT NULL DEFAULT 'application'",
                    "status_type":    "TEXT NOT NULL DEFAULT 'application'",
                    "status_code":    "TEXT NOT NULL DEFAULT 'SUCCESS'",
                    "status_level":   "TEXT NOT NULL DEFAULT 'INFO'",
                    "status_message": "TEXT",
                    "user_id":        "TEXT DEFAULT ''",
                    "session_id":     "TEXT DEFAULT ''",
                    "tenant_id":      "TEXT DEFAULT ''",
                    "project_id":     "TEXT DEFAULT ''",
                    "request_source": "TEXT DEFAULT 'web'",
                    "message_id":     "TEXT DEFAULT ''",
                    "input_query":    "TEXT DEFAULT ''",
                    "output_query":   "TEXT DEFAULT ''",
                    "error_type":     "TEXT DEFAULT ''",
                    "error_message":  "TEXT DEFAULT ''",
                    "stack_trace":    "TEXT DEFAULT ''",
                    "scenario":       "INTEGER DEFAULT 0",
                    "metadata":       "JSONB",
                    "created_at":     "TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
                    "updated_at":     "TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
                }
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'application_logs'
                """)
                existing_cols = {row[0] for row in cur.fetchall()}
                for col, col_def in _required_columns.items():
                    if col not in existing_cols:
                        cur.execute(
                            f"ALTER TABLE application_logs ADD COLUMN IF NOT EXISTS {col} {col_def}"
                        )
                        logger.info({"event": "column_added", "column": col})

                # Step 3 — create indexes (each separately so one failure doesn't block others)
                _indexes = [
                    ("idx_al_user",       "application_logs(user_id, created_at DESC)"),
                    ("idx_al_session",    "application_logs(session_id, created_at DESC)"),
                    ("idx_al_status",     "application_logs(status_type, status_code)"),
                    ("idx_al_log_type",   "application_logs(log_type, created_at DESC)"),
                    ("idx_al_tenant",     "application_logs(tenant_id, project_id)"),
                    ("idx_al_message_id", "application_logs(message_id)"),
                ]
                for idx_name, idx_cols in _indexes:
                    try:
                        cur.execute(
                            f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_cols}"
                        )
                    except Exception as idx_exc:
                        logger.warning({"event": "index_skip", "index": idx_name, "reason": str(idx_exc)})

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _insert(self, cur, **fields) -> int:
        """Generic INSERT into application_logs. Returns the new row id."""
        from psycopg2.extras import Json
        cols = list(fields.keys())
        vals = []
        for v in fields.values():
            vals.append(Json(v) if isinstance(v, (dict, list)) else v)
        placeholders = ", ".join(["%s"] * len(cols))
        col_list     = ", ".join(cols)
        cur.execute(
            f"INSERT INTO application_logs ({col_list}) VALUES ({placeholders}) RETURNING id",
            vals,
        )
        return cur.fetchone()[0]

    # ── Called from chat.py on every request ─────────────────────────────────

    def log_interaction(
        self,
        user_id: str,
        session_id: str,
        message: str,
        response: str,
        status: str = "success",
        response_time_ms: float = 0.0,
        scenario: int = 2,
        provider: str = "",
        model: str = "",
        rule_matched: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        is_error = status == "error"
        try:
            with self._conn() as con:
                with con.cursor() as cur:
                    self._insert(cur,
                        log_type      = "error" if is_error else "application",
                        status_type   = "application",
                        status_code   = STATUS_CODE_FAILED if is_error else STATUS_CODE_SUCCESS,
                        status_level  = STATUS_LEVEL_ERROR if is_error else STATUS_LEVEL_INFO,
                        status_message= error_message or "Response generated successfully",
                        user_id       = user_id,
                        session_id    = session_id,
                        input_query   = message,
                        output_query  = response,
                        scenario      = scenario,
                        error_message = error_message or "",
                        metadata      = {"provider": provider, "model": model,
                                         "rule_matched": rule_matched,
                                         "response_time_ms": round(response_time_ms, 2)},
                        created_at    = self._now(),
                        updated_at    = self._now(),
                    )
        except Exception as exc:
            logger.error({"event": "log_interaction_failed", "error": str(exc)})

    def log_error(
        self,
        user_id: str,
        session_id: str,
        error_type: str,
        error_message: str,
        stack_trace: str = "",
        scenario: int = 0,
    ) -> None:
        try:
            with self._conn() as con:
                with con.cursor() as cur:
                    self._insert(cur,
                        log_type      = "error",
                        status_type   = "application",
                        status_code   = STATUS_CODE_FAILED,
                        status_level  = STATUS_LEVEL_ERROR,
                        status_message= error_message,
                        user_id       = user_id,
                        session_id    = session_id,
                        error_type    = error_type,
                        error_message = error_message,
                        stack_trace   = stack_trace,
                        scenario      = scenario,
                        created_at    = self._now(),
                        updated_at    = self._now(),
                    )
        except Exception as exc:
            logger.error({"event": "log_error_failed", "error": str(exc)})

    # ── Called from auth.py on every login ───────────────────────────────────

    def log_auth_login_event(
        self,
        status_code: str,
        user_id: str = "",
        session_id: str = "",
        request_source: str = "web",
        tenant_id: str = "",
        project_id: str = "",
    ) -> Optional[int]:
        msg, level = AUTH_EVENT_CATALOG.get(
            status_code, ("Unknown auth event", STATUS_LEVEL_WARNING)
        )
        try:
            with self._conn() as con:
                with con.cursor() as cur:
                    row_id = self._insert(cur,
                        log_type      = "auth",
                        status_type   = "application",
                        status_code   = status_code,
                        status_level  = level,
                        status_message= msg,
                        user_id       = user_id,
                        session_id    = session_id,
                        tenant_id     = tenant_id,
                        project_id    = project_id,
                        request_source= request_source,
                        created_at    = self._now(),
                        updated_at    = self._now(),
                    )
            return row_id
        except Exception as exc:
            logger.error({"event": "log_auth_event_failed", "error": str(exc)})
            return None

    # ── 3-step lifecycle for /logs endpoints ─────────────────────────────────

    def log_chat_message(
        self,
        tenant_id: str,
        project_id: str,
        user_id: str,
        app_session_id: str,
        user_query: str,
        request_source: str = "web",
        user_action_status: str = ACTION_USER_CHAT,
        chat_session_id: Optional[str] = None,
    ) -> Optional[dict]:
        now        = self._now()
        message_id = str(uuid.uuid4())
        chat_sid   = chat_session_id or str(uuid.uuid4())
        try:
            with self._conn() as con:
                with con.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM application_logs WHERE session_id=%s AND log_type='application'",
                        (chat_sid,),
                    )
                    message_index = cur.fetchone()[0]
                    row_id = self._insert(cur,
                        log_type      = "application",
                        status_type   = "application",
                        status_code   = STATUS_CODE_SUCCESS,
                        status_level  = STATUS_LEVEL_INFO,
                        status_message= "User query received",
                        user_id       = user_id,
                        session_id    = chat_sid,
                        tenant_id     = tenant_id,
                        project_id    = project_id,
                        request_source= request_source,
                        message_id    = message_id,
                        input_query   = user_query,
                        metadata      = {
                            "app_session_id":     app_session_id,
                            "message_index":      message_index,
                            "user_action_status": user_action_status,
                        },
                        created_at    = now,
                        updated_at    = now,
                    )
        except Exception as exc:
            logger.error({"event": "log_chat_message_failed", "error": str(exc)})
            return None
        return {"message_id": message_id, "chat_session_id": chat_sid, "message_index": message_index}

    def update_bot_response(
        self,
        message_id: str,
        output_query: str,
        app_status: Optional[dict] = None,
        processing_details: Optional[dict] = None,
        chat_session_id: Optional[str] = None,
    ) -> bool:
        from psycopg2.extras import Json
        extra = {}
        if app_status:
            extra["app_status"] = app_status
        if processing_details:
            extra["processing_details"] = processing_details
        try:
            with self._conn() as con:
                with con.cursor() as cur:
                    cur.execute(
                        """UPDATE application_logs
                           SET output_query = %s,
                               status_message = %s,
                               metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                               updated_at = %s
                           WHERE message_id = %s""",
                        (
                            output_query,
                            (app_status or {}).get("status_message", "Response generated"),
                            json.dumps(extra),
                            self._now(),
                            message_id,
                        ),
                    )
                    return cur.rowcount > 0
        except Exception as exc:
            logger.error({"event": "update_bot_response_failed", "error": str(exc)})
            return False

    def log_user_feedback(
        self,
        related_message_id: str,
        related_session_id: str,
        user_action_status: str,
        rating: Optional[float] = None,
        comments: str = "",
    ) -> bool:
        _map = {
            ACTION_GOOD_RESPONSE: (STATUS_CODE_SUCCESS, STATUS_LEVEL_INFO,    "User marked as good response"),
            ACTION_BAD_RESPONSE:  (STATUS_CODE_FAILED,  STATUS_LEVEL_WARNING, "User marked as bad response"),
            ACTION_REMARK:        (STATUS_CODE_SUCCESS, STATUS_LEVEL_INFO,    "User submitted a remark"),
        }
        sc, sl, sm = _map.get(
            user_action_status,
            (STATUS_CODE_SUCCESS, STATUS_LEVEL_INFO, "User feedback received"),
        )
        feedback_data = {
            "rating": rating,
            "comments": comments,
            "related_message_id": related_message_id,
            "related_session_id": related_session_id,
        }
        try:
            with self._conn() as con:
                with con.cursor() as cur:
                    cur.execute(
                        """UPDATE application_logs
                           SET status_type    = 'user_feedback',
                               status_code    = %s,
                               status_level   = %s,
                               status_message = %s,
                               metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                               updated_at = %s
                           WHERE message_id = %s""",
                        (sc, sl, sm, json.dumps({"feedback": feedback_data,
                                                  "user_action_status": user_action_status}),
                         self._now(), related_message_id),
                    )
                    return cur.rowcount > 0
        except Exception as exc:
            logger.error({"event": "log_user_feedback_failed", "error": str(exc)})
            return False

    # ── Read-back methods ─────────────────────────────────────────────────────

    def get_message_log(self, message_id: str) -> Optional[dict]:
        try:
            from psycopg2.extras import DictCursor
            with self._conn() as con:
                with con.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM application_logs WHERE message_id=%s", (message_id,)
                    )
                    row = cur.fetchone()
            return _to_full_log(dict(row)) if row else None
        except Exception as exc:
            logger.error({"event": "get_message_log_failed", "error": str(exc)})
            return None

    def get_session_logs(self, chat_session_id: str, limit: int = 100) -> list[dict]:
        try:
            from psycopg2.extras import DictCursor
            with self._conn() as con:
                with con.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        """SELECT * FROM application_logs
                           WHERE session_id=%s AND log_type='application'
                           ORDER BY created_at ASC LIMIT %s""",
                        (chat_session_id, limit),
                    )
                    rows = cur.fetchall()
            return [_to_full_log(dict(r)) for r in rows]
        except Exception as exc:
            logger.error({"event": "get_session_logs_failed", "error": str(exc)})
            return []

    def get_tenant_logs(self, tenant_id: str, project_id: Optional[str] = None,
                        limit: int = 100) -> list[dict]:
        try:
            from psycopg2.extras import DictCursor
            with self._conn() as con:
                with con.cursor(cursor_factory=DictCursor) as cur:
                    if project_id:
                        cur.execute(
                            "SELECT * FROM application_logs WHERE tenant_id=%s AND project_id=%s ORDER BY created_at DESC LIMIT %s",
                            (tenant_id, project_id, limit),
                        )
                    else:
                        cur.execute(
                            "SELECT * FROM application_logs WHERE tenant_id=%s ORDER BY created_at DESC LIMIT %s",
                            (tenant_id, limit),
                        )
                    rows = cur.fetchall()
            return [_to_full_log(dict(r)) for r in rows]
        except Exception as exc:
            logger.error({"event": "get_tenant_logs_failed", "error": str(exc)})
            return []

    def log_app_event(self, tenant_id="", project_id="", user_id="",
                      session_id="", request_source="web",
                      status_code=STATUS_CODE_SUCCESS,
                      status_level=STATUS_LEVEL_INFO,
                      status_message="") -> Optional[int]:
        try:
            with self._conn() as con:
                with con.cursor() as cur:
                    return self._insert(cur,
                        log_type      = "application",
                        status_type   = "application",
                        status_code   = status_code,
                        status_level  = status_level,
                        status_message= status_message,
                        user_id       = user_id,
                        session_id    = session_id,
                        tenant_id     = tenant_id,
                        project_id    = project_id,
                        request_source= request_source,
                        created_at    = self._now(),
                        updated_at    = self._now(),
                    )
        except Exception as exc:
            logger.error({"event": "log_app_event_failed", "error": str(exc)})
            return None

    def get_app_events(self, tenant_id=None, project_id=None, user_id=None,
                       session_id=None, status_level=None, limit=100) -> list[dict]:
        clauses = ["log_type = 'application'"]
        params  = []
        if tenant_id:    clauses.append("tenant_id=%s");    params.append(tenant_id)
        if project_id:   clauses.append("project_id=%s");   params.append(project_id)
        if user_id:      clauses.append("user_id=%s");      params.append(user_id)
        if session_id:   clauses.append("session_id=%s");   params.append(session_id)
        if status_level: clauses.append("status_level=%s"); params.append(status_level)
        params.append(limit)
        try:
            from psycopg2.extras import DictCursor
            with self._conn() as con:
                with con.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        f"SELECT * FROM application_logs WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT %s",
                        params,
                    )
                    rows = cur.fetchall()
            return [_to_event(dict(r)) for r in rows]
        except Exception as exc:
            logger.error({"event": "get_app_events_failed", "error": str(exc)})
            return []

    def get_auth_login_event_by_id(self, row_id: int) -> Optional[dict]:
        try:
            from psycopg2.extras import DictCursor
            with self._conn() as con:
                with con.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM application_logs WHERE id=%s AND log_type='auth'", (row_id,)
                    )
                    row = cur.fetchone()
            return _to_auth_event(dict(row)) if row else None
        except Exception as exc:
            logger.error({"event": "get_auth_event_by_id_failed", "error": str(exc)})
            return None

    def get_auth_login_events(self, tenant_id=None, project_id=None, user_id=None,
                              status_code=None, status_level=None, limit=100) -> list[dict]:
        clauses = ["log_type = 'auth'"]
        params  = []
        if tenant_id:    clauses.append("tenant_id=%s");    params.append(tenant_id)
        if project_id:   clauses.append("project_id=%s");   params.append(project_id)
        if user_id:      clauses.append("user_id=%s");      params.append(user_id)
        if status_code:  clauses.append("status_code=%s");  params.append(status_code)
        if status_level: clauses.append("status_level=%s"); params.append(status_level)
        params.append(limit)
        try:
            from psycopg2.extras import DictCursor
            with self._conn() as con:
                with con.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        f"SELECT * FROM application_logs WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT %s",
                        params,
                    )
                    rows = cur.fetchall()
            return [_to_auth_event(dict(r)) for r in rows]
        except Exception as exc:
            logger.error({"event": "get_auth_events_failed", "error": str(exc)})
            return []


# ── Row mappers ───────────────────────────────────────────────────────────────

def _meta(row: dict, key: str, default=None):
    m = row.get("metadata") or {}
    return m.get(key, default)


def _to_full_log(row: dict) -> dict:
    meta = row.get("metadata") or {}
    return {
        "id":                 row.get("id"),
        "message_id":         row.get("message_id", ""),
        "message_index":      meta.get("message_index", 0),
        "chat_session_id":    row.get("session_id"),
        "app_session_id":     meta.get("app_session_id"),
        "tenant_id":          row.get("tenant_id"),
        "project_id":         row.get("project_id"),
        "user_id":            row.get("user_id"),
        "input_query":        row.get("input_query"),
        "output_query":       row.get("output_query"),
        "bot_status":         json.dumps([{
                                  "status_type":    row.get("status_type"),
                                  "status_code":    row.get("status_code"),
                                  "status_level":   row.get("status_level"),
                                  "status_message": row.get("status_message"),
                              }]),
        "app_status":         meta.get("app_status"),
        "user_action_status": meta.get("user_action_status", row.get("status_type")),
        "request_source":     row.get("request_source"),
        "processing_details": meta.get("processing_details"),
        "feedback":           meta.get("feedback"),
        "created_at":         str(row.get("created_at") or ""),
        "updated_at":         str(row.get("updated_at") or ""),
    }


def _to_event(row: dict) -> dict:
    return {
        "id":             row.get("id"),
        "tenant_id":      row.get("tenant_id"),
        "project_id":     row.get("project_id"),
        "user_id":        row.get("user_id"),
        "session_id":     row.get("session_id"),
        "request_source": row.get("request_source"),
        "status_code":    row.get("status_code"),
        "status_level":   row.get("status_level"),
        "status_message": row.get("status_message"),
        "timestamp":      str(row.get("created_at") or ""),
    }


def _to_auth_event(row: dict) -> dict:
    return _to_event(row)


# ── Singleton factory ─────────────────────────────────────────────────────────

_instance: Optional[ApplicationLogger] = None


def get_application_logger() -> ApplicationLogger:
    """
    Returns the singleton ApplicationLogger connected to PostgreSQL chatbot_db.
    Falls back gracefully and logs a warning if the connection fails.
    """
    global _instance
    if _instance is None:
        try:
            from config.settings import get_config
            cfg     = get_config()
            pg_url  = getattr(cfg, "postgres_url", "")
            if not pg_url:
                raise ValueError("POSTGRES_URL not set in .env")
            _instance = ApplicationLogger(pg_url)
            logger.info({"event": "app_logger_ready", "backend": "postgresql", "db": "chatbot_db"})
        except Exception as exc:
            logger.error({"event": "app_logger_init_failed", "error": str(exc)})
            raise
    return _instance
