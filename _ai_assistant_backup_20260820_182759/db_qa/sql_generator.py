# """
# SQL Generator
# =============

# Responsibility: Generate a SQL query from a natural-language question using
# LangChain structured output.  The LLM is forced to return a Pydantic
# QueryStructureSingle object so the SQL is always machine-readable.

# Provider is resolved at call time from AppConfig (openai / groq / anthropic).
# """
# from __future__ import annotations

# import re
# from datetime import date
# from typing import Optional

# from langchain_core.messages import HumanMessage, SystemMessage
# from pydantic import BaseModel, Field

# from db_qa.sql_query_router import SCHEMA_CONTEXT
# from config.settings import get_config
# from utils.logging_util import setup_logging

# logger = setup_logging("sql_generator")

# _FENCED_SQL_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


# # ── Pydantic output schema ────────────────────────────────────────────────────

# class QueryStructureSingle(BaseModel):
#     """Structured output that forces the LLM to return only the SQL string."""

#     sql_query: str = Field(
#         description=(
#             "A valid T-SQL SELECT query that answers the user question. "
#             "Raw SQL only — no markdown fences, no explanation."
#         )
#     )


# # ── LLM factory ──────────────────────────────────────────────────────────────

# def _build_llm(with_structured_output: bool = True):
#     """
#     Build a LangChain chat model based on AppConfig active_api_provider.
#     If with_structured_output=True, wraps the model with .with_structured_output()
#     so it always returns a QueryStructureSingle object.
#     """
#     cfg      = get_config()
#     provider = cfg.active_api_provider
#     model    = cfg.llm_model_name

#     if provider == "openai":
#         from langchain_openai import ChatOpenAI
#         llm = ChatOpenAI(
#             model=model,
#             api_key=cfg.openai_api_key,
#             temperature=0.1,
#         )
#     elif provider == "groq":
#         from langchain_groq import ChatGroq
#         llm = ChatGroq(
#             model=model,
#             api_key=cfg.groq_api_key,
#             temperature=0.1,
#         )
#     elif provider == "anthropic":
#         from langchain_anthropic import ChatAnthropic
#         llm = ChatAnthropic(
#             model=model,
#             api_key=cfg.anthropic_api_key,
#             temperature=0.1,
#         )
#     else:
#         raise ValueError(f"Unsupported provider for sql_generator: {provider!r}")

#     return llm.with_structured_output(QueryStructureSingle) if with_structured_output else llm


# # ── Prompt builder ────────────────────────────────────────────────────────────

# def create_query_generator_prompt(
#     schema: str       = SCHEMA_CONTEXT,
#     db_type: str      = "MsSQL / Azure Synapse",
#     today: str        = None,
#     spcl_instr: str   = "",
# ) -> str:
#     """
#     Build the system message for SQL generation.

#     Parameters
#     ----------
#     schema      Full database schema context string.
#     db_type     Target database dialect label shown to the LLM.
#     today       ISO date string injected for relative-date queries.
#     spcl_instr  Optional scope / restriction instructions.
#     """
#     today = today or str(date.today())

#     system = (
#         f"You are an AI-powered SQL assistant specializing in generating SQL queries.\n\n"
#         f"Database Type  : {db_type}\n"
#         f"Current Date   : {today}\n\n"
#         f"DATABASE SCHEMA:\n{schema}\n\n"
#         "GENERATION RULES:\n"
#         "1. Return ONLY the raw SQL SELECT statement — no markdown fences, no explanation.\n"
#         "2. Use ONLY table/view names present in the schema above.\n"
#         "3. WITH (NOLOCK) syntax — alias MUST come BEFORE the hint:\n"
#         "     CORRECT  : FROM hub_md.table_name t WITH (NOLOCK)\n"
#         "     INCORRECT: FROM hub_md.table_name WITH (NOLOCK) t\n"
#         "4. Inside subqueries or CTEs, omit WITH (NOLOCK) entirely.\n"
#         "5. For whole-day date filters use: CAST(column AS DATE) = CAST(GETDATE() AS DATE)\n"
#         "6. Do NOT use backtick quotes — use [square brackets] or no quotes.\n"
#     )

#     if spcl_instr:
#         system += f"\nSPECIAL INSTRUCTIONS:\n{spcl_instr}\n"

#     return system


# # ── Main entry point ──────────────────────────────────────────────────────────

# def generate_sql(
#     question: str,
#     context_str: str  = "",
#     spcl_instr: str   = "",
# ) -> QueryStructureSingle:
#     """
#     Generate a SQL query for *question* using LangChain structured output.

#     Parameters
#     ----------
#     question    Natural-language question from the user.
#     context_str Optional pgvector-retrieved knowledge base context.
#     spcl_instr  Optional special scope/restriction instructions.

#     Returns
#     -------
#     QueryStructureSingle
#         Pydantic model — access .sql_query for the bare SQL string.

#     Raises
#     ------
#     ValueError  If the LLM returns an empty or non-SQL response.
#     """
#     system_content = create_query_generator_prompt(spcl_instr=spcl_instr)

#     user_content = question
#     if context_str:
#         user_content = (
#             f"Retrieved knowledge base context:\n\n{context_str}\n\n"
#             f"User question: {question}\n\n"
#             "Generate the SQL query:"
#         )

#     messages = [
#         SystemMessage(content=system_content),
#         HumanMessage(content=user_content),
#     ]

#     logger.info({"event": "sql_generation_start", "question": question[:100]})

#     # Primary path: structured output (Pydantic)
#     try:
#         llm    = _build_llm(with_structured_output=True)
#         result = llm.invoke(messages)
#         sql    = (result.sql_query or "").strip().rstrip(";")
#         logger.info({"event": "sql_generation_structured", "sql_preview": sql[:120]})
#     except Exception as exc:
#         # Fallback: plain text call + regex extraction
#         logger.warning({"event": "sql_generation_structured_failed", "error": str(exc)})
#         llm  = _build_llm(with_structured_output=False)
#         raw  = llm.invoke(messages)
#         text = raw.content if hasattr(raw, "content") else str(raw)
#         m    = _FENCED_SQL_RE.search(text)
#         sql  = (m.group(1) if m else text).strip().rstrip(";")
#         logger.info({"event": "sql_generation_fallback", "sql_preview": sql[:120]})
#         result = QueryStructureSingle(sql_query=sql)

#     if not result.sql_query:
#         raise ValueError("sql_generator: LLM returned an empty SQL query")

#     return result



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
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from db_qa.sql_query_router import SCHEMA_CONTEXT
from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("sql_generator")

_FENCED_SQL_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


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
 