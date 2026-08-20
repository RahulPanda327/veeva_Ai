
"""
Scenario 2 — Enterprise RAG + SQL Chatbot Pipeline

10-layer pipeline:
  1.  User question received
  2.  Rule-Based Matching       greetings + FAQ questions at 0.90 threshold
  3.  KB Search Layer           top_k semantic search at 0.90 threshold
  4.  Query Reformulation       LLM rewrites query using top 3 KB candidates
  5.  Retry Search #1           KB search with reformulated query
  6.  Retry Search #2           LLM generates second query using top 5 candidates; KB search
  7.  SQL Generation Layer      SQL template router or below-threshold KB match
  9.  LLM Fallback              LLM SQL or general answer (db_llm_fallback_enabled)
  10. Failure                   "I could not find relevant information"
"""

from __future__ import annotations
import re
from collections.abc import Iterator
from typing import Optional

from services.base_service import BaseService, ChatRequest, ChatResponse
from memory.conversation_memory import ConversationMemory
from models.llm_client import LLMClient
from models.rule_based_model import RuleBasedModel
from db_qa.local_kb_matcher import get_local_kb, KBResult
from db_qa.sql_query_router import SQLQueryRouter, SCHEMA_CONTEXT
from db_qa.chart_generator import ChartGenerator, detect_chart
from db_qa.pgvector_sql_generator import get_pgvector_sql_generator
from db_qa.sql_explainer import explain_results
from results.result_store import save_query_results
from utils.logging_util import setup_logging

logger = setup_logging("scenario_2_rag_sql")

# Shared confidence threshold for layers 2-7
_HIGH_CONF = 0.90

# Minimum threshold for layer 8 SQL fallback (existing KB standard)
_SQL_FALLBACK_CONF = 0.65

_FENCED_SQL_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_GENERAL_SYSTEM_PROMPT = (
    "You are DataStream, a helpful AI assistant specialized in data pipeline operations. "
    "Answer concisely and accurately. "
    "If a question is outside your knowledge, say so honestly."
)

_REFORMULATE_SYSTEM = (
    "You are a query reformulation expert for a data pipeline operations chatbot.\n"
    "Your ONLY job is to rewrite the user's question as an optimized retrieval query.\n"
    "Rules:\n"
    "- Identify the core business intent\n"
    "- Remove filler words; keep precise data-pipeline terminology\n"
    "- Output ONLY the rewritten query — one line, no explanation\n"
    "- Do NOT answer the question"
)

_REFORMULATE_CANDIDATES_SYSTEM = (
    "You are a retrieval optimization expert for a data pipeline operations chatbot.\n"
    "Given the original question and candidate topics already retrieved, "
    "output ONE improved search query.\n"
    "Rules:\n"
    "- Analyze what the user needs based on the candidates shown\n"
    "- Synthesize the best possible retrieval query to find the exact answer\n"
    "- Output ONLY the query string — one line, no explanation\n"
    "- Do NOT answer the question"
)


class LLMWithRulesService(BaseService):
    """
    Scenario 2 — Enterprise RAG + SQL Chatbot.

    Greetings → Rule match (0.90) → KB semantic search (0.90) →
    LLM query reformulation × 2 retries → SQL template router →
    LLM SQL generation → LLM general fallback → Failure.
    """

    def __init__(
        self,
        memory: ConversationMemory,
        llm: LLMClient,
        rules: RuleBasedModel,
        db_client=None,
        router: Optional[SQLQueryRouter] = None,
        charter: Optional[ChartGenerator] = None,
    ):
        super().__init__(memory)
        self.llm     = llm
        self.rules   = rules
        self.db      = db_client
        self.router  = router
        self.charter = charter
        self._kb     = get_local_kb()

    @property
    def scenario_number(self) -> int:
        return 2

    # ══════════════════════════════════════════════════════════════════════════
    # Main entrypoint
    # ══════════════════════════════════════════════════════════════════════════

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.memory.add_message(request.session_id, "user", request.query)

        provider       = self.cfg.active_api_provider
        original_query = request.query
        user_name      = (
            request.user_id.replace(".", " ").replace("_", " ").title()
            if request.user_id else "there"
        )

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 2 — Rule-Based Matching (questions FIRST, then greetings)
        #
        # Questions are checked before greetings so that data questions that
        # accidentally score high on greeting triggers are never blocked here.
        # Greeting is only returned when the best question score is very low
        # (< 0.45), meaning the query is almost certainly conversational.
        # ══════════════════════════════════════════════════════════════════════
        top_k      = self.cfg.top_k_retrieval
        candidates = self._kb.search_topk(original_query, k=top_k)
        best       = candidates[0] if candidates else None
        best_score = best.confidence if best else 0.0

        # High-confidence KB question match → run pre-written SQL immediately
        if best and best_score >= _HIGH_CONF:
            logger.info({
                "event": "layer2_rule_hit",
                "query_var": best.query_variable,
                "confidence": round(best_score, 4),
            })
            return self._execute_kb_result(request, best, source="rule_match")

        # Greeting check — only for actual greetings, never for fallbacks.
        # is_greeting() returns True for both "greeting" and "fallback" types,
        # so we check result_type directly to avoid blocking data questions.
        if best_score < 0.45:
            kb_initial = self._kb.match(original_query, user_name=user_name)
            if kb_initial.result_type == "greeting":
                logger.info({"event": "layer2_greeting", "confidence": round(best_score, 4)})
                return self._greeting_response(request, kb_initial)

        logger.info({
            "event": "layer2_no_hit",
            "best_score": round(best_score, 4),
        })

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 3 — Knowledge Base Search already done above (reuse candidates)
        # ══════════════════════════════════════════════════════════════════════
        logger.info({
            "event": "layer3_kb_search",
            "top_k": len(candidates),
            "best_score": round(best_score, 4),
        })

        if best and best_score >= _HIGH_CONF:
            logger.info({
                "event": "layer3_kb_hit",
                "query_var": best.query_variable,
                "confidence": round(best_score, 4),
            })
            return self._execute_kb_result(request, best, source="kb_search")

        # ══════════════════════════════════════════════════════════════════════
        # LAYERS 4-7 — LLM Query Reformulation + 3 Retry Cycles
        # ══════════════════════════════════════════════════════════════════════
        ctx3 = self._format_candidates(candidates[:3])
        ctx5 = self._format_candidates(candidates[:5])

        for retry in range(1, 3):
            # Retry 1: original query + top 3 context  (Layer 4-5)
            # Retry 2: top 5 context                   (Layer 6)
            if retry == 1:
                rewritten = self._reformulate(original_query, ctx3)
            else:
                rewritten = self._reformulate_with_candidates(
                    original_query, ctx5, attempt=retry
                )

            logger.info({
                "event": "kb_retry",
                "retry": retry,
                "rewritten_query": rewritten,
            })

            retry_cands = self._kb.search_topk(rewritten, k=top_k)
            retry_best  = retry_cands[0] if retry_cands else None
            retry_score = retry_best.confidence if retry_best else 0.0

            logger.info({
                "event": "kb_retry_result",
                "retry": retry,
                "score": round(retry_score, 4),
            })

            if retry_best and retry_score >= _HIGH_CONF:
                logger.info({
                    "event": "kb_retry_hit",
                    "retry": retry,
                    "query_var": retry_best.query_variable,
                    "confidence": round(retry_score, 4),
                })
                return self._execute_kb_result(
                    request, retry_best,
                    source=f"kb_retry_{retry}",
                    reformulated_query=rewritten,
                )

            # Refresh top-5 context with the latest candidate set
            if retry_cands:
                ctx5 = self._format_candidates(retry_cands[:5])

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 8 — SQL Generation Layer
        # ══════════════════════════════════════════════════════════════════════
        logger.info({"event": "layer8_sql_generation", "query": original_query})

        # 8a. Regex SQL template router
        if self.router is not None:
            sql_match = self.router.match(original_query)
            if sql_match is not None:
                logger.info({
                    "event": "sql_template_hit",
                    "intent": sql_match.intent,
                })
                return self._execute_sql(
                    request,
                    sql=sql_match.sql,
                    binds=sql_match.binds,
                    intent=sql_match.intent,
                    description=sql_match.description,
                    chart_hint=sql_match.chart_hint,
                    source="sql_template",
                )

        # 8b. Best KB candidate above minimum SQL threshold
        if best and best.is_sql() and best.confidence >= _SQL_FALLBACK_CONF and best.sql:
            logger.info({
                "event": "sql_kb_below_high_conf",
                "query_var": best.query_variable,
                "confidence": round(best.confidence, 4),
            })
            return self._execute_kb_result(request, best, source="sql_kb_fallback")

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 8c — pgvector Search + LangChain SQL Generation + Validation
        #
        # Orchestrated by db_qa/pgvector_sql_generator.py:
        #   1. pgvector search (top-5 context chunks)
        #   2. sql_generator.py  → LangChain generates SQL (Pydantic output)
        #   3. sql_validator.py  → executes + corrects up to 5 times
        #   4. sql_executor.py   → runs each attempt against the DB
        #
        # Returns (sql, description, cols, rows) — already executed, so we
        # build the ChatResponse directly without calling _execute_sql() again.
        # ══════════════════════════════════════════════════════════════════════
        if self.db is not None:
            try:
                pg_sql, pg_description, pg_cols, pg_rows = (
                    get_pgvector_sql_generator().generate(original_query, self.db)
                )

                logger.info({
                    "event":       "layer8c_pgvector_hit",
                    "description": pg_description,
                    "rows":        len(pg_rows),
                })

                # SQL already executed by the validator — build response directly
                download_id  = save_query_results(
                    title=pg_description, sql=pg_sql,
                    columns=pg_cols, rows=pg_rows,
                )
                preview_data: list[list[str]] = []
                for row in pg_rows[:3]:
                    if isinstance(row, dict):
                        preview_data.append([str(row.get(c, "")) for c in pg_cols])
                    else:
                        preview_data.append([str(v) for v in row])

                row_count     = len(pg_rows)
                response_text = explain_results(
                    question=original_query,
                    columns=pg_cols,
                    rows=pg_rows,
                )
                self.memory.add_message(request.session_id, "assistant", response_text)

                return ChatResponse(
                    response=response_text,
                    session_id=request.session_id,
                    scenario=self.scenario_number,
                    provider="db",
                    model="pgvector.generated",
                    rule_matched="pgvector.generated",
                    metadata={
                        "source":           "pgvector_llm",
                        "sql":              pg_sql,
                        "matched_template": pg_description,
                        "results":          f"{row_count} rows found",
                        "preview":          {"columns": pg_cols, "rows": preview_data},
                        "download_id":      download_id,
                        "export_formats":   ["csv", "xlsx", "json"],
                        "confidence":       0.0,
                    },
                )

            except Exception as exc:
                logger.warning({"event": "layer8c_pgvector_failed", "error": str(exc)})

                

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 9 — LLM Fallback
        # ══════════════════════════════════════════════                        
        if self.cfg.db_llm_fallback_enabled and self.llm is not None:
            logger.info({"event": "layer9_llm_fallback"})

            # 9a. LLM generates SQL (requires DB connection)
            if self.db is not None:
                try:
                    gen_sql = self._llm_generate_sql(original_query)
                    logger.info({"event": "llm_sql_generated"})
                    return self._execute_sql(
                        request,
                        sql=gen_sql,
                        binds=[],
                        intent="llm.generated",
                        description="LLM-generated query",
                        chart_hint=None,
                        source="llm_sql",
                    )
                except Exception as exc:
                    logger.warning({"event": "llm_sql_failed", "error": str(exc)})

            # 9b. General LLM answer (no DB required)
            messages = self.memory.get_messages_for_llm(
                request.session_id,
                system_prompt=request.system_prompt or _GENERAL_SYSTEM_PROMPT,
            )
            response_text = self.llm.chat(messages)
            self.memory.add_message(request.session_id, "assistant", response_text)
            return ChatResponse(
                response=response_text,
                session_id=request.session_id,
                scenario=self.scenario_number,
                provider=provider,
                model=self.cfg.llm_model_name,
                metadata={"source": "llm_general", "layer": "llm_fallback"},
            )

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 10 — Failure
        # ══════════════════════════════════════════════════════════════════════
        return self._fail(
            request,
            "I could not find relevant information for your request.",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Streaming — pipeline is sync; wrap as single chunk
    # ══════════════════════════════════════════════════════════════════════════

    def chat_stream(self, request: ChatRequest) -> Iterator[dict]:
        result = self.chat(request)
        yield {"type": "chunk", "content": result.response}
        yield self._meta_event(
            request,
            provider=result.provider,
            model=result.model,
            cached=result.cached,
            rule_matched=result.rule_matched,
            metadata=result.metadata,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Private: response builders
    # ══════════════════════════════════════════════════════════════════════════

    def _greeting_response(self, request: ChatRequest, kb_result: KBResult) -> ChatResponse:
        response_text = kb_result.response
        if kb_result.show_examples and kb_result.example_prompts:
            examples = "  |  ".join(kb_result.example_prompts)
            response_text += f"\n\nTry asking: {examples}"
        self.memory.add_message(request.session_id, "assistant", response_text)
        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            scenario=self.scenario_number,
            provider="local_kb",
            model="greeting",
            rule_matched=f"greeting:{kb_result.result_type}",
            metadata={"source": "greeting", "layer": "rule_based"},
        )

    def _execute_kb_result(
        self,
        request: ChatRequest,
        kb_result: KBResult,
        source: str,
        reformulated_query: Optional[str] = None,
    ) -> ChatResponse:
        return self._execute_sql(
            request,
            sql=kb_result.sql,
            binds=[],
            intent=kb_result.query_variable,
            description=kb_result.description,
            chart_hint=None,
            source=source,
            reformulated_query=reformulated_query,
            confidence=kb_result.confidence,
        )

    def _execute_sql(
        self,
        request: ChatRequest,
        sql: str,
        binds: list,
        intent: str,
        description: str,
        chart_hint: Optional[dict],
        source: str,
        reformulated_query: Optional[str] = None,
        confidence: float = 0.0,
    ) -> ChatResponse:
        if self.db is None:
            return self._fail(request, "Database connection not configured for this scenario.")

        try:
            print("\n==========SQL TO EXECUTE==========")
            print(sql)
            print("==================================\n")
            cols, rows = self.db.execute(sql, binds)
        except Exception as exc:
            logger.error({"event": "query_failed", "intent": intent, "error": str(exc)})
            return self._fail(
                request,
                f"Query execution failed.\n\nIntent: {intent}\nError: {exc}",
                extra_meta={
                    "sql":              sql,
                    "source":           source,
                    "matched_template": description,
                    "confidence":       round(confidence, 4),
                },
            )

        download_id = save_query_results(
            title=description, sql=sql, columns=cols, rows=rows
        )

        preview_data: list[list[str]] = []
        for row in rows[:3]:
            if isinstance(row, dict):
                preview_data.append([str(row.get(col, "")) for col in cols])
            else:
                preview_data.append([str(v) for v in row])

        row_count     = len(rows)
        response_text = explain_results(
            question=request.query,
            columns=cols,
            rows=rows,
        )

        chart_info = None
        if self.cfg.chart_enabled and rows and self.charter:
            spec = chart_hint or detect_chart(rows, cols)
            if spec:
                try:
                    chart_info = self.charter.generate(rows, cols, spec)
                except Exception as exc:
                    logger.error({"event": "chart_failed", "error": str(exc)})

        self.memory.add_message(request.session_id, "assistant", response_text)

        meta: dict = {
            "source": source,
            "results": f"{row_count} rows found",
            "preview": {"columns": cols, "rows": preview_data},
            "download_id": download_id,
            "export_formats": ["csv", "xlsx", "json"],
            "sql": sql,
            "matched_template": description,
            "chart": chart_info,
            "confidence": round(confidence, 4),
        }
        if reformulated_query:
            meta["reformulated_query"] = reformulated_query

        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            scenario=self.scenario_number,
            provider="db",
            model=f"synapse:{self.cfg.db_name}" if self.cfg.db_name else "synapse",
            rule_matched=intent,
            cosine_scores=[confidence] if confidence else [],
            metadata=meta,
        )

    def _fail(self, request: ChatRequest, msg: str, extra_meta: dict = None) -> ChatResponse:
        self.memory.add_message(request.session_id, "assistant", msg)
        meta = {"source": "failure", "error": True}
        if extra_meta:
            meta.update(extra_meta)
        return ChatResponse(
            response=msg,
            session_id=request.session_id,
            scenario=self.scenario_number,
            provider="db",
            model="unmatched",
            metadata=meta,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Private: LLM query reformulation
    # ══════════════════════════════════════════════════════════════════════════

    def _reformulate(self, original: str, ctx: str) -> str:
        """Layer 4: Rewrite query using original question + top 3 KB context."""
        messages = [
            {"role": "system", "content": _REFORMULATE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Original question: {original}\n\n"
                    f"Top KB topics retrieved:\n{ctx}\n\n"
                    "Rewrite as an optimized retrieval query:"
                ),
            },
        ]
        try:
            return self.llm.chat(messages, temperature=0.2, max_tokens=100).strip()
        except Exception as exc:
            logger.warning({"event": "reformulate_failed", "error": str(exc)})
            return original

    def _reformulate_with_candidates(
        self, original: str, ctx: str, attempt: int
    ) -> str:
        """Layers 6-7: Generate optimized query from top 5 candidates."""
        messages = [
            {"role": "system", "content": _REFORMULATE_CANDIDATES_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Original question: {original}\n\n"
                    f"Candidate topics (attempt {attempt}):\n{ctx}\n\n"
                    "Generate ONE optimized search query:"
                ),
            },
        ]
        try:
            return self.llm.chat(messages, temperature=0.1, max_tokens=100).strip()
        except Exception as exc:
            logger.warning({
                "event": "reformulate_candidates_failed",
                "attempt": attempt,
                "error": str(exc),
            })
            return original

    def _format_candidates(self, candidates: list[KBResult]) -> str:
        lines = [
            f"{i}. [{c.query_variable}] {c.title} "
            f"(score: {c.confidence:.3f}) — {c.description}"
            for i, c in enumerate(candidates, 1)
        ]
        return "\n".join(lines) or "No candidates found."

    def _llm_generate_sql(self, question: str) -> str:
        """Layer 9a: Ask LLM to generate SQL using the schema context."""
        messages = [
            {"role": "system", "content": SCHEMA_CONTEXT},
            {"role": "user",   "content": question},
        ]
        raw = self.llm.chat(messages)
 
        print("\n===== LLM SQL RAW =====")
        print(raw)
        print("=======================\n")
 
        m   = _FENCED_SQL_RE.search(raw)
        sql = (m.group(1) if m else raw).strip().rstrip(";")

        if not sql or len(sql) < 20:
            raise ValueError(f"LLM returned incomplete SQL: {sql!r}")

        return sql

