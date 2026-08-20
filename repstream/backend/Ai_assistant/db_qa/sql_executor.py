"""
SQL Executor
============

Responsibility: Execute a SQL query against the configured database and return
(columns, rows).  Raises an exception containing the raw database error message
so sql_validator.py can pass it to the LLM correction prompt.

This is an intentionally thin wrapper — all retry / correction logic lives in
sql_validator.py, not here.
"""
from __future__ import annotations

from utils.logging_util import setup_logging

logger = setup_logging("sql_executor")


class SQLExecutor:
    """
    Thin wrapper around the existing database client.

    Usage
    -----
    executor = SQLExecutor(db_client)

    # Pass executor.execute as executor_fn to sql_validator.validate_and_correct:
    final_sql, cols, rows = validate_and_correct(question, sql, executor.execute)
    """

    def __init__(self, db_client) -> None:
        """
        Parameters
        ----------
        db_client
            Any object that exposes .execute(sql: str, binds: list) -> (cols, rows).
            In this project that is dbs.sql_server_client.SQLServerClient.
        """
        if db_client is None:
            raise ValueError("SQLExecutor requires a database client — got None")
        self._db = db_client

    def execute(self, sql: str) -> tuple[list, list]:
        """
        Execute *sql* and return (columns, rows).

        Parameters
        ----------
        sql     Bare SQL string — no trailing semicolon needed.

        Returns
        -------
        (columns, rows)
            columns — list[str] of column names.
            rows    — list of row objects (dict or tuple, depends on driver).

        Raises
        ------
        Exception
            Re-raises whatever the database driver raises so the caller
            (sql_validator) can capture the error message and pass it to the
            LLM correction prompt.
        """
        logger.info({"event": "sql_executor_run", "sql_preview": sql[:120]})
        try:
            cols, rows = self._db.execute(sql, [])
            logger.info({"event": "sql_executor_done", "rows": len(rows)})
            return cols, rows
        except Exception as exc:
            logger.error({"event": "sql_executor_error", "error": str(exc)[:300]})
            raise
