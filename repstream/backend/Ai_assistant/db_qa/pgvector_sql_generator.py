"""
PGVector SQL Generator — Orchestrator
======================================

Pipeline for questions that fall through rule-based matching (Layer 8c):

  Step 1 — pgvector search
            Retrieve top-5 most similar knowledge base chunks from PostgreSQL.

  Step 2 — SQL generation   [db_qa/sql_generator.py]
            LangChain + Pydantic structured output forces the LLM to return
            a QueryStructureSingle object with the SQL string.

  Step 3 — SQL validation   [db_qa/sql_validator.py]
            Execute the SQL.  On failure, the LLM reads the database error
            and returns a CorrectedSQL object.  Repeats up to MAX_TRY (5) times.
            Uses [db_qa/sql_executor.py] for the actual DB call.

  Step 4 — Return (sql, description, columns, rows) to scenario_2_llm_rules.py.

This module is intentionally self-contained — the prompt text, retry logic,
and execution details all live in the three specialist files above.
"""
from __future__ import annotations

from typing import Optional

from db_qa.pgvector_store   import get_pgvector_store
from db_qa.sql_generator    import generate_sql
from db_qa.sql_validator    import validate_and_correct
from db_qa.sql_executor     import SQLExecutor
from utils.logging_util     import setup_logging

logger = setup_logging("pgvector_sql_generator")


class PGVectorSQLGenerator:
    """
    Orchestrates pgvector search → SQL generation → SQL validation/correction.

    Usage
    -----
    generator = get_pgvector_sql_generator()
    sql, description, cols, rows = generator.generate(question, db_client)
    """

    TOP_K = 5   # number of pgvector chunks passed to the LLM

    def generate(
        self,
        question:  str,
        db_client,
    ) -> tuple[str, str, list, list]:
        """
        Parameters
        ----------
        question    Natural-language question from the user.
        db_client   Database client (SQLServerClient).  Passed to SQLExecutor
                    so the validator can execute and correct in a retry loop.

        Returns
        -------
        (sql, description, columns, rows)
            sql         — final SQL string that executed successfully.
            description — title of the best-matching pgvector chunk.
            columns     — list of column name strings from the DB result.
            rows        — list of row objects from the DB result.

        Raises
        ------
        ValueError   If the pgvector store is empty.
        RuntimeError If SQL still fails after MAX_TRY correction attempts.
        """

        # ── Step 1: Retrieve context from pgvector ────────────────────────────
        store  = get_pgvector_store()
        chunks = store.search(question, top_k=self.TOP_K, min_score=0.0)

        logger.info({
            "event":     "pgvector_search",
            "question":  question,
            "hits":      len(chunks),
            "top_score": round(chunks[0]["score"], 4) if chunks else 0.0,
        })

        if not chunks:
            raise ValueError(
                "pgvector store is empty — run scripts/ingest_to_pgvector.py first"
            )

        # Build numbered context block
        context_parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            label = chunk.get("title") or chunk.get("chunk_id") or f"chunk_{i}"
            context_parts.append(
                f"[{i}] {label}  (similarity: {chunk['score']:.3f})\n"
                f"{chunk['content']}"
            )
        context_str = "\n\n".join(context_parts)

        best_label = (
            chunks[0].get("title") or chunks[0].get("chunk_id") or "pgvector result"
        )

        # ── Step 2: Generate SQL [sql_generator.py] ───────────────────────────
        logger.info({"event": "sql_generation_start"})
        generated = generate_sql(question=question, context_str=context_str)
        sql        = generated.sql_query.strip().rstrip(";")

        logger.info({
            "event":       "sql_generation_done",
            "sql_preview": sql[:120],
        })

        # ── Step 3: Validate + correct SQL [sql_validator.py + sql_executor.py]
        logger.info({"event": "sql_validation_start"})
        executor  = SQLExecutor(db_client)
        final_sql, cols, rows = validate_and_correct(
            question=question,
            sql=sql,
            executor_fn=executor.execute,
        )

        logger.info({
            "event":       "sql_validation_done",
            "final_sql":   final_sql[:120],
            "rows":        len(rows),
        })

        return final_sql, best_label, cols, rows


# ── Process-level singleton ───────────────────────────────────────────────────

_instance: Optional[PGVectorSQLGenerator] = None


def get_pgvector_sql_generator() -> PGVectorSQLGenerator:
    global _instance
    if _instance is None:
        _instance = PGVectorSQLGenerator()
    return _instance
