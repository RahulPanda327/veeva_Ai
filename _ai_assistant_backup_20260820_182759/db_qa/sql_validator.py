# """
# SQL Validator
# =============

# Responsibility: Execute a generated SQL query and, if it fails, use LangChain
# to correct it and retry — up to MAX_TRY times.

# Loop per attempt:
#   1. Execute SQL via executor_fn(sql) → (columns, rows)
#   2. Success  → return (corrected_sql, columns, rows)
#   3. Failure  → build correction prompt with error message
#               → LLM returns CorrectedSQL (Pydantic)
#               → update sql and go to step 1

# Provider is resolved at call time from AppConfig.
# """
# from __future__ import annotations

# from typing import Callable

# from langchain_core.messages import HumanMessage, SystemMessage
# from pydantic import BaseModel, Field

# from db_qa.sql_query_router import SCHEMA_CONTEXT
# from config.settings import get_config
# from utils.logging_util import setup_logging

# logger = setup_logging("sql_validator")

# MAX_TRY = 5


# # ── Pydantic output schema ────────────────────────────────────────────────────

# class CorrectedSQL(BaseModel):
#     """Structured output that forces the LLM to return only the corrected SQL."""

#     sql_query: str = Field(
#         description=(
#             "The corrected T-SQL SELECT query. "
#             "Raw SQL only — no markdown fences, no explanation."
#         )
#     )


# # ── LLM factory ──────────────────────────────────────────────────────────────

# def _build_llm(with_structured_output: bool = True):
#     """Build a LangChain chat model based on AppConfig active_api_provider."""
#     cfg      = get_config()
#     provider = cfg.active_api_provider
#     model    = cfg.llm_model_name

#     if provider == "openai":
#         from langchain_openai import ChatOpenAI
#         llm = ChatOpenAI(model=model, api_key=cfg.openai_api_key, temperature=0.0)
#     elif provider == "groq":
#         from langchain_groq import ChatGroq
#         llm = ChatGroq(model=model, api_key=cfg.groq_api_key, temperature=0.0)
#     elif provider == "anthropic":
#         from langchain_anthropic import ChatAnthropic
#         llm = ChatAnthropic(model=model, api_key=cfg.anthropic_api_key, temperature=0.0)
#     else:
#         raise ValueError(f"Unsupported provider for sql_validator: {provider!r}")

#     return llm.with_structured_output(CorrectedSQL) if with_structured_output else llm


# # ── Prompt builders ───────────────────────────────────────────────────────────

# def create_query_correction_prompt(
#     question:      str,
#     buggy_sql:     str,
#     error_message: str,
#     schema:        str = SCHEMA_CONTEXT,
# ) -> tuple[str, str]:
#     """
#     Build (system_content, user_content) for a SQL correction call.

#     Parameters
#     ----------
#     question        Original user question (gives the LLM business context).
#     buggy_sql       The SQL that produced an error.
#     error_message   The exact database error string.
#     schema          Database schema for column/table name reference.

#     Returns
#     -------
#     (system_content, user_content)
#     """
#     system_content = (
#         "You are an expert SQL code reviewer specializing in T-SQL / Azure Synapse SQL.\n\n"
#         "Your job is to fix a broken SQL query based on the database error message.\n\n"
#         "FIX RULES:\n"
#         "1. Read the error message carefully — it tells you exactly what is wrong.\n"
#         "2. Fix spelling mistakes, wrong column names, and syntax errors.\n"
#         "3. Use ONLY columns and tables from the schema provided.\n"
#         "4. WITH (NOLOCK) alias order — alias BEFORE hint:\n"
#         "     CORRECT  : FROM hub_md.table_name t WITH (NOLOCK)\n"
#         "     INCORRECT: FROM hub_md.table_name WITH (NOLOCK) t\n"
#         "5. Inside subqueries and CTEs, omit WITH (NOLOCK) entirely.\n"
#         "6. Return ONLY the corrected SQL — no explanation, no markdown fences.\n"
#     )

#     user_content = (
#         f"Original Question:\n{question}\n\n"
#         f"Broken SQL:\n{buggy_sql}\n\n"
#         f"Database Error:\n{error_message}\n\n"
#         f"Database Schema:\n{schema}\n\n"
#         "Return the corrected SQL query:"
#     )

#     return system_content, user_content


# # ── Main entry point ──────────────────────────────────────────────────────────

# def validate_and_correct(
#     question:    str,
#     sql:         str,
#     executor_fn: Callable[[str], tuple[list, list]],
#     max_try:     int = MAX_TRY,
# ) -> tuple[str, list, list]:
#     """
#     Execute *sql* and correct it with the LLM if it fails, up to *max_try* times.

#     Parameters
#     ----------
#     question    Original user question — fed into the correction prompt.
#     sql         Initial SQL to execute and validate.
#     executor_fn Callable(sql) -> (columns, rows).
#                 Must raise an Exception with the DB error message on failure.
#     max_try     Maximum number of correction attempts (default 5).

#     Returns
#     -------
#     (final_sql, columns, rows)
#         final_sql  — the SQL that executed successfully (may differ from input).
#         columns    — list of column name strings.
#         rows       — list of row dicts / tuples.

#     Raises
#     ------
#     RuntimeError
#         If the SQL still fails after *max_try* correction attempts.
#     """
#     current_sql = sql
#     last_error  = ""

#     for attempt in range(1, max_try + 1):
#         # ── Execute ───────────────────────────────────────────────────────────
#         try:
#             logger.info({
#                 "event":       "validate_execute",
#                 "attempt":     attempt,
#                 "sql_preview": current_sql[:120],
#             })
#             cols, rows = executor_fn(current_sql)
#             logger.info({
#                 "event":   "validate_success",
#                 "attempt": attempt,
#                 "rows":    len(rows),
#             })
#             return current_sql, cols, rows

#         except Exception as exc:
#             last_error = str(exc)
#             logger.warning({
#                 "event":   "validate_failed",
#                 "attempt": attempt,
#                 "error":   last_error[:300],
#             })

#             if attempt >= max_try:
#                 break  # no more retries

#         # ── Correct ───────────────────────────────────────────────────────────
#         system_content, user_content = create_query_correction_prompt(
#             question=question,
#             buggy_sql=current_sql,
#             error_message=last_error,
#         )
#         messages = [
#             SystemMessage(content=system_content),
#             HumanMessage(content=user_content),
#         ]

#         try:
#             llm       = _build_llm(with_structured_output=True)
#             corrected = llm.invoke(messages)
#             new_sql   = (corrected.sql_query or "").strip().rstrip(";")

#             if not new_sql:
#                 logger.warning({"event": "correction_empty", "attempt": attempt})
#                 break

#             logger.info({
#                 "event":       "sql_corrected",
#                 "attempt":     attempt,
#                 "new_preview": new_sql[:120],
#             })
#             current_sql = new_sql

#         except Exception as correction_exc:
#             logger.error({
#                 "event":   "correction_llm_failed",
#                 "attempt": attempt,
#                 "error":   str(correction_exc),
#             })
#             break

#     raise RuntimeError(
#         f"SQL validation failed after {max_try} attempt(s). "
#         f"Last error: {last_error[:400]}"
#     )




"""
SQL Validator
=============

Responsibility: Execute a generated SQL query and, if it fails, use LangChain
to correct it and retry — up to MAX_TRY times.

Loop per attempt:
  1. Execute SQL via executor_fn(sql) → (columns, rows)
  2. Success  → return (corrected_sql, columns, rows)
  3. Failure  → build correction prompt with error message
              → LLM returns CorrectedSQL (Pydantic)
              → update sql and go to step 1

Provider is resolved at call time from AppConfig.
"""
from __future__ import annotations

from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from db_qa.sql_query_router import SCHEMA_CONTEXT
from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("sql_validator")

MAX_TRY = 5


# ── Pydantic output schema ────────────────────────────────────────────────────

class CorrectedSQL(BaseModel):
    """Structured output that forces the LLM to return only the corrected SQL."""

    sql_query: str = Field(
        description=(
            "The corrected T-SQL SELECT query. "
            "Raw SQL only — no markdown fences, no explanation."
        )
    )


# ── LLM factory ──────────────────────────────────────────────────────────────

def _build_llm(with_structured_output: bool = True):
    """Build a LangChain chat model based on AppConfig active_api_provider."""
    cfg      = get_config()
    provider = cfg.active_api_provider
    model    = cfg.llm_model_name

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=model, api_key=cfg.openai_api_key, temperature=0.0)
    elif provider == "groq":
        from langchain_groq import ChatGroq
        llm = ChatGroq(model=model, api_key=cfg.groq_api_key, temperature=0.0)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model=model, api_key=cfg.anthropic_api_key, temperature=0.0)
    else:
        raise ValueError(f"Unsupported provider for sql_validator: {provider!r}")

    return llm.with_structured_output(CorrectedSQL) if with_structured_output else llm


# ── Prompt builders ───────────────────────────────────────────────────────────

def create_query_correction_prompt(
    question:      str,
    buggy_sql:     str,
    error_message: str,
    schema:        str = SCHEMA_CONTEXT,
) -> tuple[str, str]:
    """
    Build (system_content, user_content) for a SQL correction call.

    Parameters
    ----------
    question        Original user question (gives the LLM business context).
    buggy_sql       The SQL that produced an error.
    error_message   The exact database error string.
    schema          Database schema for column/table name reference.

    Returns
    -------
    (system_content, user_content)
    """
    system_content = (
        "You are an expert SQL code reviewer specializing in T-SQL / Azure Synapse SQL.\n\n"
        "Your job is to fix a broken SQL query based on the database error message.\n\n"
        "FIX RULES:\n"
        "1. Read the error message carefully — it tells you exactly what is wrong.\n"
        "2. Fix spelling mistakes, wrong column names, and syntax errors.\n"
        "3. Use ONLY columns and tables from the schema provided.\n"
        "4. WITH (NOLOCK) alias order — alias BEFORE hint:\n"
        "     CORRECT  : FROM hub_md.table_name t WITH (NOLOCK)\n"
        "     INCORRECT: FROM hub_md.table_name WITH (NOLOCK) t\n"
        "5. Inside subqueries and CTEs, omit WITH (NOLOCK) entirely.\n"
        "6. Return ONLY the corrected SQL — no explanation, no markdown fences.\n"
        "7. NEVER use named parameters or scalar variables such as @startDate, @endDate, "
        "or ? placeholders — this SQL is executed as-is with no parameter binding. If the "
        "error is 'Must declare the scalar variable ...', replace that variable with a "
        "literal value or a GETDATE()/DATEADD() expression (default to the last 30 days if "
        "no explicit date was given), never redeclare or reintroduce a variable.\n"
    )

    user_content = (
        f"Original Question:\n{question}\n\n"
        f"Broken SQL:\n{buggy_sql}\n\n"
        f"Database Error:\n{error_message}\n\n"
        f"Database Schema:\n{schema}\n\n"
        "Return the corrected SQL query:"
    )

    return system_content, user_content


# ── Main entry point ──────────────────────────────────────────────────────────

def validate_and_correct(
    question:    str,
    sql:         str,
    executor_fn: Callable[[str], tuple[list, list]],
    max_try:     int = MAX_TRY,
) -> tuple[str, list, list]:
    """
    Execute *sql* and correct it with the LLM if it fails, up to *max_try* times.

    Parameters
    ----------
    question    Original user question — fed into the correction prompt.
    sql         Initial SQL to execute and validate.
    executor_fn Callable(sql) -> (columns, rows).
                Must raise an Exception with the DB error message on failure.
    max_try     Maximum number of correction attempts (default 5).

    Returns
    -------
    (final_sql, columns, rows)
        final_sql  — the SQL that executed successfully (may differ from input).
        columns    — list of column name strings.
        rows       — list of row dicts / tuples.

    Raises
    ------
    RuntimeError
        If the SQL still fails after *max_try* correction attempts.
    """
    current_sql = sql
    last_error  = ""

    for attempt in range(1, max_try + 1):
        # ── Execute ───────────────────────────────────────────────────────────
        try:
            logger.info({
                "event":       "validate_execute",
                "attempt":     attempt,
                "sql_preview": current_sql[:120],
            })
            cols, rows = executor_fn(current_sql)
            logger.info({
                "event":   "validate_success",
                "attempt": attempt,
                "rows":    len(rows),
            })
            return current_sql, cols, rows

        except Exception as exc:
            last_error = str(exc)
            logger.warning({
                "event":   "validate_failed",
                "attempt": attempt,
                "error":   last_error[:300],
            })

            if attempt >= max_try:
                break  # no more retries

        # ── Correct ───────────────────────────────────────────────────────────
        system_content, user_content = create_query_correction_prompt(
            question=question,
            buggy_sql=current_sql,
            error_message=last_error,
        )
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=user_content),
        ]

        try:
            llm       = _build_llm(with_structured_output=True)
            corrected = llm.invoke(messages)
            new_sql   = (corrected.sql_query or "").strip().rstrip(";")

            if not new_sql:
                logger.warning({"event": "correction_empty", "attempt": attempt})
                break

            logger.info({
                "event":       "sql_corrected",
                "attempt":     attempt,
                "new_preview": new_sql[:120],
            })
            current_sql = new_sql

        except Exception as correction_exc:
            logger.error({
                "event":   "correction_llm_failed",
                "attempt": attempt,
                "error":   str(correction_exc),
            })
            break

    raise RuntimeError(
        f"SQL validation failed after {max_try} attempt(s). "
        f"Last error: {last_error[:400]}"
    )
 