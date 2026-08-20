# """
# SQL Explainer
# =============

# Responsibility: Take raw database query results + the original user question
# and use LangChain to generate a clean, human-friendly natural-language answer.

# System prompt rules:
#   - Answer ONLY the user's question using the data.
#   - Do NOT mention SQL, table names, or column names.
#   - Do NOT say "Based on the data" or "The query returned".
#   - Use plain English with bullet points or bold where it helps.
#   - If 0 rows: say clearly no results were found.
#   - If many rows: summarize key patterns instead of listing all.
# """
# from __future__ import annotations

# import json
# from typing import Optional

# from langchain_core.messages import HumanMessage, SystemMessage

# from config.settings import get_config
# from utils.logging_util import setup_logging

# logger = setup_logging("sql_explainer")

# _MAX_ROWS = 50   # max rows sent to LLM to control token usage


# # ── LLM factory ──────────────────────────────────────────────────────────────

# def _build_llm():
#     cfg      = get_config()
#     provider = cfg.active_api_provider
#     model    = cfg.llm_model_name

#     if provider == "openai":
#         from langchain_openai import ChatOpenAI
#         return ChatOpenAI(model=model, api_key=cfg.openai_api_key, temperature=0.3)
#     elif provider == "groq":
#         from langchain_groq import ChatGroq
#         return ChatGroq(model=model, api_key=cfg.groq_api_key, temperature=0.3)
#     elif provider == "anthropic":
#         from langchain_anthropic import ChatAnthropic
#         return ChatAnthropic(model=model, api_key=cfg.anthropic_api_key, temperature=0.3)
#     else:
#         raise ValueError(f"Unsupported provider for sql_explainer: {provider!r}")


# # ── System prompt ─────────────────────────────────────────────────────────────

# EXPLAINER_SYSTEM_PROMPT = (
#     "You are DataStream Assistant — an intelligent analyst for a data pipeline "
#     "operations platform. You help operations teams understand feed processing "
#     "status, file loads, failures, scheduling, and data quality results.\n\n"
#     "YOUR JOB:\n"
#     "Given a user's question and a database query result, produce a clear, "
#     "accurate, and professional natural-language answer.\n\n"
#     "STRICT RULES — NEVER BREAK THESE:\n"
#     "1. Use ONLY the data provided. Never invent, assume, or estimate numbers "
#     "not present in the result.\n"
#     "2. If 0 rows were returned, respond: 'No data was found for the given "
#     "criteria. The result may mean there were no matching records for "
#     "the selected time period or filter.'\n"
#     "3. Never reveal SQL syntax, column names, table names, schema names, "
#     "or any technical database detail in your answer.\n"
#     "4. Never say 'the query', 'the table', 'the result set', or 'the data'. "
#     "Speak in business terms only (e.g. 'files', 'feeds', 'loads', 'runs').\n"
#     "5. Keep the answer between 2 to 4 sentences. No bullet points. No headers. "
#     "No lists unless the user explicitly asked 'list all...'.\n"
#     "6. When numbers are available, always state them clearly and precisely. "
#     "Example: say '18 out of 21 feeds loaded successfully (85.7%)' "
#     "not 'most feeds loaded successfully'.\n"
#     "7. For status values: 5 = success, anything else = not successful. "
#     "Translate status codes into plain English — never expose the raw number.\n"
#     "8. For time-based answers (today, yesterday, this week), always confirm "
#     "the date or period you are referring to if it appears in the data.\n"
#     "9. If the result has more than 10 rows, summarize the pattern and call out "
#     "any outliers or notable items — do not list every row.\n"
#     "10. If the data is insufficient to fully answer the question, say so clearly "
#     "and state what was found instead.\n"
#     "11. Maintain a professional, calm, and confident tone — like a senior "
#     "operations analyst briefing a manager.\n\n"
#     "RESPONSE FORMAT:\n"
#     "- 2 to 4 sentences maximum.\n"
#     "- Plain prose only — no markdown, no bold, no bullet points.\n"
#     "- Start your answer directly — do not say 'Based on the data...' or "
#     "'According to the results...'. Just answer."
# )


# # ── Main entry point ──────────────────────────────────────────────────────────

# def explain_results(
#     question: str,
#     columns:  list,
#     rows:     list,
# ) -> str:
#     """
#     Generate a human-readable explanation of query results.

#     Parameters
#     ----------
#     question   Original user question.
#     columns    Column name strings from the DB result.
#     rows       Row dicts / tuples from the DB result.

#     Returns
#     -------
#     str — Natural-language answer ready to display to the user.
#           Falls back to a simple count message if the LLM call fails.
#     """
#     row_count = len(rows)

#     if row_count == 0:
#         return f"No results found for: **{question}**"

#     # Convert rows to list of dicts
#     sample = rows[:_MAX_ROWS]
#     if sample and isinstance(sample[0], dict):
#         data_dicts = sample
#     else:
#         data_dicts = [dict(zip(columns, row)) for row in sample]

#     data_str = json.dumps(data_dicts, indent=2, default=str)

#     note = (
#         f"\n\n(Showing first {_MAX_ROWS} of {row_count} total records.)"
#         if row_count > _MAX_ROWS
#         else f"\n\n(Total records: {row_count})"
#     )

#     user_content = (
#         f"User question: {question}\n\n"
#         f"Query results:\n{data_str}"
#         f"{note}\n\n"
#         "Please answer the user's question in a clear, friendly way."
#     )

#     messages = [
#         SystemMessage(content=EXPLAINER_SYSTEM_PROMPT),
#         HumanMessage(content=user_content),
#     ]

#     logger.info({"event": "sql_explainer_start", "question": question[:100], "rows": row_count})

#     try:
#         llm    = _build_llm()
#         result = llm.invoke(messages)
#         answer = result.content.strip() if hasattr(result, "content") else str(result).strip()
#         logger.info({"event": "sql_explainer_done", "preview": answer[:120]})
#         return answer

#     except Exception as exc:
#         logger.warning({"event": "sql_explainer_failed", "error": str(exc)})
#         # Graceful fallback
#         return f"**{row_count}** record{'s' if row_count != 1 else ''} found for your query."




"""
SQL Generator
=============

Responsibility: Generate a SQL query from a natural-language question using
LangChain structured output.  The LLM is forced to return a Pydantic
QueryStructureSingle object so the SQL is always machine-readable.

Provider is resolved at call time from AppConfig (openai / groq / anthropic).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from db_qa.sql_query_router import SCHEMA_CONTEXT
from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("sql_generator")

_FENCED_SQL_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def explain_results(question: str, columns: list[str] | None = None, rows: list[dict[str, Any]] | None = None) -> str:
    """Create a concise natural-language summary for executed query results."""
    if not rows:
        return "I ran the query, but it did not return any rows."

    if columns is None:
        columns = []

    preview_rows = rows[:3]
    if len(preview_rows) == 1:
        preview_text = "the first result"
    else:
        preview_text = f"the first {len(preview_rows)} results"

    if columns:
        column_text = ", ".join(str(col) for col in columns)
        return (
            f"I found {len(rows)} result(s) for your question. "
            f"The returned columns are {column_text}, and {preview_text} are: "
            f"{_format_preview_rows(preview_rows)}"
        )

    return (
        f"I found {len(rows)} result(s) for your question. "
        f"{preview_text} are: {_format_preview_rows(preview_rows)}"
    )


def _format_preview_rows(rows: list[dict[str, Any]] | list[list[Any]]) -> str:
    formatted: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            parts = [f"{key}={value}" for key, value in row.items()]
            formatted.append("{" + ", ".join(parts) + "}")
        else:
            formatted.append("[" + ", ".join(str(value) for value in row) + "]")
    return "; ".join(formatted)


# ── Pydantic output schema ────────────────────────────────────────────────────

class QueryStructureSingle(BaseModel):
    """Structured output that forces the LLM to return only the SQL string."""

    sql_query: str = Field(
        description=(
            "A valid T-SQL SELECT query that answers the user question. "
            "Raw SQL only — no markdown fences, no explanation."
        )
    )


# ── LLM factory ──────────────────────────────────────────────────────────────

def _build_llm(with_structured_output: bool = True):
    """
    Build a LangChain chat model based on AppConfig active_api_provider.
    If with_structured_output=True, wraps the model with .with_structured_output()
    so it always returns a QueryStructureSingle object.
    """
    cfg      = get_config()
    provider = cfg.active_api_provider
    model    = cfg.llm_model_name

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=model,
            api_key=cfg.openai_api_key,
            temperature=0.1,
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model=model,
            api_key=cfg.groq_api_key,
            temperature=0.1,
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(
            model=model,
            api_key=cfg.anthropic_api_key,
            temperature=0.1,
        )
    else:
        raise ValueError(f"Unsupported provider for sql_generator: {provider!r}")

    return llm.with_structured_output(QueryStructureSingle) if with_structured_output else llm


# ── Prompt builder ────────────────────────────────────────────────────────────

def create_query_generator_prompt(
    schema: str       = SCHEMA_CONTEXT,
    db_type: str      = "MsSQL / Azure Synapse",
    today: str        = None,
    spcl_instr: str   = "",
) -> str:
    """
    Build the system message for SQL generation.

    Parameters
    ----------
    schema      Full database schema context string.
    db_type     Target database dialect label shown to the LLM.
    today       ISO date string injected for relative-date queries.
    spcl_instr  Optional scope / restriction instructions.
    """
    today = today or str(date.today())

    system = (
        f"You are an AI-powered SQL assistant specializing in generating SQL queries.\n\n"
        f"Database Type  : {db_type}\n"
        f"Current Date   : {today}\n\n"
        f"DATABASE SCHEMA:\n{schema}\n\n"
        "GENERATION RULES:\n"
        "1. Return ONLY the raw SQL SELECT statement — no markdown fences, no explanation.\n"
        "2. Use ONLY table/view names present in the schema above.\n"
        "3. WITH (NOLOCK) syntax — alias MUST come BEFORE the hint:\n"
        "     CORRECT  : FROM hub_md.table_name t WITH (NOLOCK)\n"
        "     INCORRECT: FROM hub_md.table_name WITH (NOLOCK) t\n"
        "4. Inside subqueries or CTEs, omit WITH (NOLOCK) entirely.\n"
        "5. For whole-day date filters use: CAST(column AS DATE) = CAST(GETDATE() AS DATE)\n"
        "6. Do NOT use backtick quotes — use [square brackets] or no quotes.\n"
        "7. NEVER use named parameters or scalar variables such as @startDate, @endDate, "
        "or ? placeholders — this SQL is executed as-is with no parameter binding, so any "
        "undeclared variable will fail with 'Must declare the scalar variable'. If the "
        "question references a date range without giving explicit dates (e.g. 'the selected "
        "date range', 'this period'), default to the last 30 days using literal expressions, "
        "e.g. CAST(column AS DATE) >= CAST(DATEADD(DAY, -30, GETDATE()) AS DATE).\n"
    )

    if spcl_instr:
        system += f"\nSPECIAL INSTRUCTIONS:\n{spcl_instr}\n"

    return system


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_sql(
    question: str,
    context_str: str  = "",
    spcl_instr: str   = "",
) -> QueryStructureSingle:
    """
    Generate a SQL query for *question* using LangChain structured output.

    Parameters
    ----------
    question    Natural-language question from the user.
    context_str Optional pgvector-retrieved knowledge base context.
    spcl_instr  Optional special scope/restriction instructions.

    Returns
    -------
    QueryStructureSingle
        Pydantic model — access .sql_query for the bare SQL string.

    Raises
    ------
    ValueError  If the LLM returns an empty or non-SQL response.
    """
    system_content = create_query_generator_prompt(spcl_instr=spcl_instr)

    user_content = question
    if context_str:
        user_content = (
            f"Retrieved knowledge base context:\n\n{context_str}\n\n"
            f"User question: {question}\n\n"
            "Generate the SQL query:"
        )

    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=user_content),
    ]

    logger.info({"event": "sql_generation_start", "question": question[:100]})

    # Primary path: structured output (Pydantic)
    try:
        llm    = _build_llm(with_structured_output=True)
        result = llm.invoke(messages)
        sql    = (result.sql_query or "").strip().rstrip(";")
        logger.info({"event": "sql_generation_structured", "sql_preview": sql[:120]})
    except Exception as exc:
        # Fallback: plain text call + regex extraction
        logger.warning({"event": "sql_generation_structured_failed", "error": str(exc)})
        llm  = _build_llm(with_structured_output=False)
        raw  = llm.invoke(messages)
        text = raw.content if hasattr(raw, "content") else str(raw)
        m    = _FENCED_SQL_RE.search(text)
        sql  = (m.group(1) if m else text).strip().rstrip(";")
        logger.info({"event": "sql_generation_fallback", "sql_preview": sql[:120]})
        result = QueryStructureSingle(sql_query=sql)

    if not result.sql_query:
        raise ValueError("sql_generator: LLM returned an empty SQL query")

    return result
 