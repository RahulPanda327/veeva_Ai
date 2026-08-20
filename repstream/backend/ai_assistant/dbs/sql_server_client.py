"""
SQL Server / Azure Synapse client via pyodbc.

Connection is built from individual env vars (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)
plus Azure-Synapse-appropriate options (Encrypt=yes, TrustServerCertificate=no).

All queries are validated read-only — any DDL/DML statement (INSERT/UPDATE/DELETE/
DROP/TRUNCATE/ALTER/CREATE/EXEC/GRANT) raises before contacting the database.

Row counts are capped at db_max_rows to protect the API from a single accidentally
unbounded result set.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Optional

from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("sql_client")

# Statement-boundary regex — matches the keyword as the first token of a statement
# (start-of-string OR after `;` / whitespace) so it doesn't trip on column names.
_WRITE_STMT_RE = re.compile(
    r"(^|[\s;])(insert|update|delete|drop|truncate|alter|create|exec|execute|merge|grant|revoke|backup|restore)\s+",
    re.IGNORECASE,
)


class ReadOnlyViolation(ValueError):
    """Raised when a query would modify the database."""


class SQLServerClient:
    """Lazy-connect wrapper around pyodbc. One connection per query (Synapse-friendly)."""

    def __init__(self):
        self.cfg = get_config()

    # ── Connection ─────────────────────────────────────────────────────────────

    def _connection_string(self) -> str:
        cfg = self.cfg
        if not (cfg.db_host and cfg.db_name and cfg.db_user and cfg.db_password):
            raise RuntimeError(
                "Database is not fully configured. "
                "Set DB_HOST, DB_NAME, DB_USER, DB_PASSWORD in .env."
            )
        return ";".join([
            f"DRIVER={cfg.db_driver}",
            f"SERVER={cfg.db_host}",
            f"DATABASE={cfg.db_name}",
            f"UID={cfg.db_user}",
            f"PWD={cfg.db_password}",
            "Encrypt=yes",
            "TrustServerCertificate=no",
            f"Connection Timeout={cfg.db_query_timeout_seconds}",
        ])

    @contextmanager
    def _conn(self):
        import pyodbc
        con = pyodbc.connect(self._connection_string(), readonly=True)
        try:
            yield con
        finally:
            con.close()

    # ── Validation ─────────────────────────────────────────────────────────────

    @staticmethod
    def assert_readonly(sql: str):
        if _WRITE_STMT_RE.search(sql):
            raise ReadOnlyViolation("Write statements are not allowed in this scenario")

    # ── Query API ──────────────────────────────────────────────────────────────

    def execute(self, sql: str, params: Optional[list] = None) -> tuple[list[str], list[dict]]:
        """
        Execute a SELECT and return (columns, rows). Rows capped at db_max_rows.
        Raises ReadOnlyViolation for any non-SELECT statement.
        """
        self.assert_readonly(sql)

        with self._conn() as con:
            cur = con.cursor()
            cur.execute(sql, params or [])
            cols: list[str] = [d[0] for d in cur.description] if cur.description else []
            rows: list[dict] = []
            for i, raw in enumerate(cur.fetchall()):
                if i >= self.cfg.db_max_rows:
                    logger.warning({
                        "event": "row_cap_hit",
                        "cap": self.cfg.db_max_rows,
                    })
                    break
                rows.append({c: _coerce(v) for c, v in zip(cols, raw)})

        logger.info({
            "event": "query_executed",
            "row_count": len(rows),
            "columns": cols,
        })
        return cols, rows

    # ── Connectivity diagnostics ───────────────────────────────────────────────

    def ping(self) -> dict:
        """Quick connectivity check — returns server version on success."""
        try:
            cols, rows = self.execute("SELECT @@VERSION AS version")
            return {"ok": True, "version": rows[0]["version"] if rows else "?"}
        except Exception as exc:
            logger.error({"event": "ping_failed", "error": str(exc)})
            return {"ok": False, "error": str(exc)}


def _coerce(value: Any) -> Any:
    """Make pyodbc row values JSON-serializable."""
    # datetime/date pass through — FastAPI's encoder handles them
    # Decimal → float to be JSON-safe
    import decimal
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value
