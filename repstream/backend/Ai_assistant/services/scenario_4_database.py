# """
# Scenario 4 — Database Q&A.

# Flow:
#   1. Try to match the question against a pre-defined SQL template.
#   2. If matched → execute parameterized SQL.
#   3. If not matched AND LLM fallback enabled → ask the LLM to generate SQL
#      with the table schema as context, validate it's read-only, then execute.
#   4. Format the result as a markdown table (top N rows).
#   5. If the data shape supports it (or a chart hint exists) → render a chart.
#   6. Return the answer; metadata carries the SQL, columns, rows, and chart info.
# """

# from __future__ import annotations

# import re
# from collections.abc import Iterator
# from typing import Optional

# from services.base_service import BaseService, ChatRequest, ChatResponse
# from memory.conversation_memory import ConversationMemory
# from db_qa.sql_query_router import SQLQueryRouter, SCHEMA_CONTEXT
# from db_qa.chart_generator import ChartGenerator, detect_chart
# from utils.logging_util import setup_logging

# logger = setup_logging("scenario_4_db")


# _FENCED_SQL_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


# class DatabaseQAService(BaseService):
#     def __init__(
#         self,
#         memory: ConversationMemory,
#         db_client,
#         router: SQLQueryRouter,
#         charter: ChartGenerator,
#         llm=None,
#     ):
#         super().__init__(memory)
#         self.db = db_client
#         self.router = router
#         self.charter = charter
#         self.llm = llm

#     @property
#     def scenario_number(self) -> int:
#         return 4

#     # ── Public entrypoint ──────────────────────────────────────────────────────

#     def chat(self, request: ChatRequest) -> ChatResponse:
#         self.memory.add_message(request.session_id, "user", request.query)

#         match = self.router.match(request.query)
#         sql: Optional[str] = None
#         binds: list = []
#         intent: str
#         description: str
#         chart_hint: Optional[dict] = None
#         source: str = "template"

#         if match is not None:
#             sql, binds = match.sql, match.binds
#             intent = match.intent
#             description = match.description
#             chart_hint = match.chart_hint
#         elif self.cfg.db_llm_fallback_enabled and self.llm is not None:
#             try:
#                 sql = self._llm_generate_sql(request.query)
#                 intent = "llm.generated"
#                 description = "LLM-generated query"
#                 source = "llm"
#             except Exception as exc:
#                 return self._fail(request, f"Could not understand the question and LLM fallback failed: {exc}")
#         else:
#             return self._fail(
#                 request,
#                 "Sorry, I couldn't match your question to a known query template. "
#                 "Try a question like 'Which files are scheduled today?' or 'Show last 7 days load history for copay'.",
#             )

#         # Execute
#         try:
#             cols, rows = self.db.execute(sql, binds)
#         except Exception as exc:
#             logger.error({"event": "query_failed", "intent": intent, "error": str(exc)})
#             return self._fail(
#                 request,
#                 f"Query execution failed.\n\n**Intent:** {intent}\n**SQL:**\n```sql\n{sql}\n```\n\n**Error:** {exc}",
#             )

#         # Generate explanation
#         explanation = self._generate_explanation(request.query, description, cols, rows, intent)

#         # Build answer text
#         answer = self._format_results(description, cols, rows, explanation)

#         # Chart
#         chart_info = None
#         if self.cfg.chart_enabled and rows:
#             spec = chart_hint or detect_chart(rows, cols)
#             if spec:
#                 try:
#                     chart_info = self.charter.generate(rows, cols, spec)
#                     answer += f"\n\n📊 Chart saved: `{chart_info['path']}`"
#                 except Exception as exc:
#                     logger.error({"event": "chart_failed", "error": str(exc)})

#         self.memory.add_message(request.session_id, "assistant", answer)

#         return ChatResponse(
#             response=answer,
#             session_id=request.session_id,
#             scenario=self.scenario_number,
#             provider="db",
#             model=f"synapse:{self.cfg.db_name}" if self.cfg.db_name else "synapse",
#             rule_matched=intent,
#             metadata={
#                 "source": source,
#                 "intent": intent,
#                 "description": description,
#                 "sql": sql,
#                 "binds": [str(b) for b in binds],
#                 "columns": cols,
#                 "row_count": len(rows),
#                 "rows": _serialize_rows(rows[:50]),  # cap inline rows in response
#                 "chart": _chart_for_response(chart_info),
#             },
#         )

#     # Stream interface: DB queries are sync — yield as a single chunk
#     def chat_stream(self, request: ChatRequest) -> Iterator[dict]:
#         result = self.chat(request)
#         yield {"type": "chunk", "content": result.response}
#         yield self._meta_event(
#             request,
#             provider=result.provider,
#             model=result.model,
#             cached=False,
#             rule_matched=result.rule_matched,
#             metadata=result.metadata,
#         )

#     # ── Internal ───────────────────────────────────────────────────────────────

#     def _llm_generate_sql(self, question: str) -> str:
#         """Ask the LLM to generate SQL given the schema context. Strip code fences."""
#         messages = [
#             {"role": "system", "content": SCHEMA_CONTEXT},
#             {"role": "user", "content": question},
#         ]
#         raw = self.llm.chat(messages)
#         m = _FENCED_SQL_RE.search(raw)
#         sql = (m.group(1) if m else raw).strip().rstrip(";")
#         return sql

#     def _generate_explanation(self, question: str, description: str, cols: list[str], rows: list[dict], intent: str) -> str:
#         """Generate a natural-language insight about the query results.
#         Uses LLM if available, otherwise falls back to a template summary."""
#         row_count = len(rows)
#         if row_count == 0:
#             return ""

#         if self.llm is not None:
#             try:
#                 # Build a compact data summary (first 5 rows as text)
#                 sample_lines = []
#                 show = rows[:5]
#                 sample_lines.append("Columns: " + ", ".join(cols))
#                 for r in show:
#                     sample_lines.append(str({k: str(v)[:60] for k, v in r.items()}))
#                 if row_count > 5:
#                     sample_lines.append(f"... ({row_count - 5} more rows not shown)")
#                 data_summary = "\n".join(sample_lines)

#                 messages = [
#                     {
#                         "role": "system",
#                         "content": (
#                             "You are a helpful data analyst assistant. "
#                             "Given a user's question and a sample of the SQL query results, "
#                             "write a concise 2-3 sentence explanation that: "
#                             "(1) directly answers the user's question, "
#                             "(2) highlights the most important insight from the data. "
#                             "Do NOT repeat the raw data. Do NOT use markdown tables. "
#                             "Be direct, clear, and helpful."
#                         ),
#                     },
#                     {
#                         "role": "user",
#                         "content": (
#                             f"Question: {question}\n"
#                             f"Query description: {description}\n"
#                             f"Total rows returned: {row_count}\n"
#                             f"Sample data:\n{data_summary}"
#                         ),
#                     },
#                 ]
#                 explanation = self.llm.chat(messages)
#                 return explanation.strip()
#             except Exception as exc:
#                 logger.warning({"event": "explanation_failed", "error": str(exc)})

#         # Fallback: template-based summary
#         intent_summaries = {
#             "schedule.today":        f"There are **{row_count}** files scheduled to load today.",
#             "schedule.tomorrow":     f"There are **{row_count}** files scheduled to load tomorrow.",
#             "missed.today":          f"**{row_count}** file(s) were missed today.",
#             "failed.today":          f"**{row_count}** file(s) failed today.",
#             "delayed.today":         f"**{row_count}** file(s) are currently delayed.",
#             "qc.recent":             f"**{row_count}** QC issue(s) were found in the selected time range.",
#             "qc.failed.recent":      f"**{row_count}** feed(s) failed QC in the most recent run.",
#             "trend.history":         f"Found **{row_count}** load records for the requested feed and date range.",
#             "feeds.active.subject_areas": f"There are **{row_count}** active subject area(s) with feeds.",
#         }
#         return intent_summaries.get(intent, f"The query returned **{row_count}** record(s) for: {description}.")

#     def _format_results(self, description: str, cols: list[str], rows: list[dict], explanation: str = "") -> str:
#         if not rows:
#             return f"**{description}** — no rows returned."

#         lines = []

#         # Prepend explanation if available
#         if explanation:
#             lines.append(explanation)
#             lines.append("")  # blank line before the table header

#         lines.append(f"**{description}** — {len(rows)} row{'s' if len(rows) != 1 else ''}")
#         show = rows[: min(5, len(rows))]
#         lines.append("\n| " + " | ".join(cols) + " |")
#         lines.append("|" + "|".join("---" for _ in cols) + "|")
#         for r in show:
#             cells = [_cell(r.get(c)) for c in cols]
#             lines.append("| " + " | ".join(cells) + " |")
#         if len(rows) > 5:
#             lines.append(f"\n_… plus {len(rows) - 5} more rows (see `metadata.rows` for the full set, capped at {self.cfg.db_max_rows})._")
#         return "\n".join(lines)


#     def _fail(self, request: ChatRequest, msg: str) -> ChatResponse:
#         self.memory.add_message(request.session_id, "assistant", msg)
#         return ChatResponse(
#             response=msg,
#             session_id=request.session_id,
#             scenario=self.scenario_number,
#             provider="db",
#             model="unmatched",
#             metadata={"source": "fallback", "error": True},
#         )


# # ────────────────────────────────────────────────────────────────────────────────
# # Serialization helpers
# # ────────────────────────────────────────────────────────────────────────────────

# def _cell(v) -> str:
#     if v is None:
#         return ""
#     s = str(v).replace("\n", " ").replace("|", "\\|")
#     return s[:80] + ("…" if len(s) > 80 else "")


# def _serialize_rows(rows: list[dict]) -> list[dict]:
#     out = []
#     for r in rows:
#         item = {}
#         for k, v in r.items():
#             # FastAPI handles datetime, but pyodbc returns some types JSON doesn't like
#             if hasattr(v, "isoformat"):
#                 item[k] = v.isoformat()
#             else:
#                 item[k] = v
#         out.append(item)
#     return out


# def _chart_for_response(chart_info: Optional[dict]) -> Optional[dict]:
#     """Strip the heavy base64 payload from the response by default."""
#     if not chart_info:
#         return None
#     # Keep base64 — clients may want to render inline. If you want to slim API
#     # payloads, drop png_base64 here and serve via a separate /charts/{file} route.
#     return chart_info

#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

# """
# Scenario 4 — Database Q&A  (Local KB Edition)

# Flow:
#   1. ── LOCAL KB FIRST ──
#      a. Check if message is a greeting → return greeting response immediately.
#      b. Use sentence-transformers (local, no Pinecone) to find best matching
#         question from kb_chatbot_questions_updated.json.
#      c. If confidence >= 0.55 → fetch SQL from kb_sql_queries_updated.json
#         and execute against Azure Synapse.
#      d. If confidence < 0.55 → return low-confidence fallback message.

#   2. ── ORIGINAL TEMPLATE ROUTER (fallback) ──
#      If local KB returns no SQL, try the existing SQLQueryRouter (sql_templates.py).

#   3. ── LLM FALLBACK (optional) ──
#      If both above fail AND db_llm_fallback_enabled → ask LLM to generate SQL.

#   4. Format results as markdown table + optional chart.
# """

# from __future__ import annotations

# import re
# from collections.abc import Iterator
# from typing import Optional

# from services.base_service import BaseService, ChatRequest, ChatResponse
# from memory.conversation_memory import ConversationMemory
# from db_qa.sql_query_router import SQLQueryRouter, SCHEMA_CONTEXT
# from db_qa.chart_generator import ChartGenerator, detect_chart

# # ── NEW: Local KB matcher (no Pinecone) ───────────────────────────────────────
# from db_qa.local_kb_matcher import get_local_kb

# from utils.logging_util import setup_logging

# logger = setup_logging("scenario_4_db")

# _FENCED_SQL_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


# class DatabaseQAService(BaseService):
#     def __init__(
#         self,
#         memory: ConversationMemory,
#         db_client,
#         router: SQLQueryRouter,
#         charter: ChartGenerator,
#         llm=None,
#     ):
#         super().__init__(memory)
#         self.db      = db_client
#         self.router  = router
#         self.charter = charter
#         self.llm     = llm

#         # Initialise local KB matcher once (loads & encodes all questions)
#         self._kb = get_local_kb()

#     @property
#     def scenario_number(self) -> int:
#         return 4

#     # ── Public entrypoint ──────────────────────────────────────────────────────

#     def chat(self, request: ChatRequest) -> ChatResponse:
#         self.memory.add_message(request.session_id, "user", request.query)

#         # ── Extract display name from user_id for greeting responses ──────────
#         user_name = request.user_id.replace(".", " ").replace("_", " ").title() \
#                     if request.user_id else "there"

#         # ══════════════════════════════════════════════════════════════════════
#         # STEP 1 — Local KB match (greeting OR sql)
#         # ══════════════════════════════════════════════════════════════════════
#         kb_result = self._kb.match(request.query, user_name=user_name)

#         # ── 1a. Greeting / fallback → return immediately, no SQL ──────────────
#         if kb_result.is_greeting():
#             response_text = kb_result.response

#             # # Optionally append example prompts
#             # if kb_result.show_examples and kb_result.example_prompts:
#             #     examples = "\n".join(f"• {p}" for p in kb_result.example_prompts)
#             #     response_text += f"\n\n**Try asking:**\n{examples}"

#             if kb_result.show_examples and kb_result.example_prompts:
#                 examples = "  |  ".join(kb_result.example_prompts)
#                 response_text += f"\n\nTry asking: {examples}"

#             self.memory.add_message(request.session_id, "assistant", response_text)
#             return ChatResponse(
#                 response=response_text,
#                 session_id=request.session_id,
#                 scenario=self.scenario_number,
#                 provider="local_kb",
#                 model="greeting",
#                 rule_matched=f"greeting:{kb_result.result_type}",
#                 metadata={"source": "greeting", "kb_type": kb_result.result_type},
#             )

#         # ── 1b. SQL match from local KB ───────────────────────────────────────
#         sql: Optional[str]  = None
#         binds: list         = []
#         intent: str         = ""
#         description: str    = ""
#         chart_hint          = None
#         source: str         = "local_kb"

#         if kb_result.is_sql():
#             sql         = kb_result.sql
#             binds       = []                    # KB queries use no bind params
#             intent      = kb_result.query_variable
#             description = kb_result.description
#             logger.info({
#                 "event": "local_kb_sql_match",
#                 "query_var": kb_result.query_variable,
#                 "confidence": round(kb_result.confidence, 4),
#                 "matched_question": kb_result.matched_question,
#             })

#         # ══════════════════════════════════════════════════════════════════════
#         # STEP 2 — Original template router (if local KB found nothing)
#         # ══════════════════════════════════════════════════════════════════════
#         if not sql:
#             match = self.router.match(request.query)
#             if match is not None:
#                 sql         = match.sql
#                 binds       = match.binds
#                 intent      = match.intent
#                 description = match.description
#                 chart_hint  = match.chart_hint
#                 source      = "template"

#         # ══════════════════════════════════════════════════════════════════════
#         # STEP 3 — LLM SQL generation fallback
#         # ══════════════════════════════════════════════════════════════════════
#         if not sql:
#             if self.cfg.db_llm_fallback_enabled and self.llm is not None:
#                 try:
#                     sql         = self._llm_generate_sql(request.query)
#                     intent      = "llm.generated"
#                     description = "LLM-generated query"
#                     source      = "llm"
#                 except Exception as exc:
#                     return self._fail(
#                         request,
#                         f"Could not understand the question and LLM fallback failed: {exc}"
#                     )
#             else:
#                 return self._fail(
#                     request,
#                     f"Sorry {user_name}, I couldn't match your question to a known query. "
#                     "Try: 'Which files are scheduled today?' or 'Show last 7 days load history for copay'.",
#                 )

#         # ══════════════════════════════════════════════════════════════════════
#         # STEP 4 — Execute SQL
#         # ══════════════════════════════════════════════════════════════════════
#         try:
#             cols, rows = self.db.execute(sql, binds)
#         except Exception as exc:
#             logger.error({"event": "query_failed", "intent": intent, "error": str(exc)})
#             return self._fail(
#                 request,
#                 f"Query execution failed.\n\n**Intent:** {intent}\n"
#                 f"**SQL:**\n```sql\n{sql}\n```\n\n**Error:** {exc}",
#             )

#         # ── Generate explanation ───────────────────────────────────────────────
#         explanation = self._generate_explanation(
#             request.query, description, cols, rows, intent
#         )

#         # ── Format markdown table ──────────────────────────────────────────────
#         answer = self._format_results(description, cols, rows, explanation)

#         # ── Optional chart ─────────────────────────────────────────────────────
#         chart_info = None
#         if self.cfg.chart_enabled and rows:
#             spec = chart_hint or detect_chart(rows, cols)
#             if spec:
#                 try:
#                     chart_info = self.charter.generate(rows, cols, spec)
#                     answer += f"\n\n📊 Chart saved: `{chart_info['path']}`"
#                 except Exception as exc:
#                     logger.error({"event": "chart_failed", "error": str(exc)})

#         self.memory.add_message(request.session_id, "assistant", answer)

#         return ChatResponse(
#             response=answer,
#             session_id=request.session_id,
#             scenario=self.scenario_number,
#             provider="db",
#             model=f"synapse:{self.cfg.db_name}" if self.cfg.db_name else "synapse",
#             rule_matched=intent,
#             metadata={
#                 "source": source,
#                 "intent": intent,
#                 "description": description,
#                 "sql": sql,
#                 "binds": [str(b) for b in binds],
#                 "columns": cols,
#                 "row_count": len(rows),
#                 "rows": _serialize_rows(rows[:50]),
#                 "chart": _chart_for_response(chart_info),
#             },
#         )

#     # Stream: DB queries are sync — yield as a single chunk
#     def chat_stream(self, request: ChatRequest) -> Iterator[dict]:
#         result = self.chat(request)
#         yield {"type": "chunk", "content": result.response}
#         yield self._meta_event(
#             request,
#             provider=result.provider,
#             model=result.model,
#             cached=False,
#             rule_matched=result.rule_matched,
#             metadata=result.metadata,
#         )

#     # ── Internal helpers ───────────────────────────────────────────────────────

#     def _llm_generate_sql(self, question: str) -> str:
#         messages = [
#             {"role": "system", "content": SCHEMA_CONTEXT},
#             {"role": "user",   "content": question},
#         ]
#         raw = self.llm.chat(messages)
#         m   = _FENCED_SQL_RE.search(raw)
#         sql = (m.group(1) if m else raw).strip().rstrip(";")
#         return sql

#     def _generate_explanation(
#         self, question: str, description: str,
#         cols: list[str], rows: list[dict], intent: str
#     ) -> str:
#         row_count = len(rows)
#         if row_count == 0:
#             return ""

#         if self.llm is not None:
#             try:
#                 sample_lines = ["Columns: " + ", ".join(cols)]
#                 for r in rows[:5]:
#                     sample_lines.append(str({k: str(v)[:60] for k, v in r.items()}))
#                 if row_count > 5:
#                     sample_lines.append(f"... ({row_count - 5} more rows not shown)")
#                 data_summary = "\n".join(sample_lines)
#                 messages = [
#                     {
#                         "role": "system",
#                         "content": (
#                             "You are a helpful data analyst assistant. "
#                             "Given a user's question and a sample of SQL query results, "
#                             "write a concise 2-3 sentence explanation that: "
#                             "(1) directly answers the user's question, "
#                             "(2) highlights the most important insight. "
#                             "Do NOT repeat raw data. Do NOT use markdown tables. "
#                             "Be direct, clear, and helpful."
#                         ),
#                     },
#                     {
#                         "role": "user",
#                         "content": (
#                             f"Question: {question}\n"
#                             f"Description: {description}\n"
#                             f"Total rows: {row_count}\n"
#                             f"Sample:\n{data_summary}"
#                         ),
#                     },
#                 ]
#                 return self.llm.chat(messages).strip()
#             except Exception as exc:
#                 logger.warning({"event": "explanation_failed", "error": str(exc)})

#         # Template fallback
#         intent_summaries = {
#             "schedule.today":             f"There are **{row_count}** files scheduled to load today.",
#             "schedule.tomorrow":          f"There are **{row_count}** files scheduled to load tomorrow.",
#             "missed.today":               f"**{row_count}** file(s) were missed today.",
#             "failed.today":               f"**{row_count}** file(s) failed today.",
#             "delayed.today":              f"**{row_count}** file(s) are currently delayed.",
#             "qc.recent":                  f"**{row_count}** QC issue(s) found in the selected time range.",
#             "qc.failed.recent":           f"**{row_count}** feed(s) failed QC in the most recent run.",
#             "trend.history":              f"Found **{row_count}** load records.",
#             "feeds.active.subject_areas": f"There are **{row_count}** active subject area(s).",
#         }
#         return intent_summaries.get(
#             intent,
#             f"The query returned **{row_count}** record(s) for: {description}."
#         )

#     def _format_results(
#         self, description: str, cols: list[str],
#         rows: list[dict], explanation: str = ""
#     ) -> str:
#         if not rows:
#             return f"**{description}** — no rows returned."

#         lines = []
#         if explanation:
#             lines.append(explanation)
#             lines.append("")
#         lines.append(f"**{description}** — {len(rows)} row{'s' if len(rows) != 1 else ''}")
#         show = rows[:min(5, len(rows))]
#         lines.append("\n| " + " | ".join(cols) + " |")
#         lines.append("|" + "|".join("---" for _ in cols) + "|")
#         for r in show:
#             cells = [_cell(r.get(c)) for c in cols]
#             lines.append("| " + " | ".join(cells) + " |")
#         if len(rows) > 5:
#             lines.append(
#                 f"\n_… plus {len(rows) - 5} more rows "
#                 f"(capped at {self.cfg.db_max_rows})._"
#             )
#         return "\n".join(lines)

#     def _fail(self, request: ChatRequest, msg: str) -> ChatResponse:
#         self.memory.add_message(request.session_id, "assistant", msg)
#         return ChatResponse(
#             response=msg,
#             session_id=request.session_id,
#             scenario=self.scenario_number,
#             provider="db",
#             model="unmatched",
#             metadata={"source": "fallback", "error": True},
#         )


# # ── Serialization helpers ──────────────────────────────────────────────────────

# def _cell(v) -> str:
#     if v is None:
#         return ""
#     s = str(v).replace("\n", " ").replace("|", "\\|")
#     return s[:80] + ("…" if len(s) > 80 else "")


# def _serialize_rows(rows: list[dict]) -> list[dict]:
#     out = []
#     for r in rows:
#         item = {}
#         for k, v in r.items():
#             item[k] = v.isoformat() if hasattr(v, "isoformat") else v
#         out.append(item)
#     return out


# def _chart_for_response(chart_info: Optional[dict]) -> Optional[dict]:
#     if not chart_info:
#         return None
#     return chart_info


"""
Scenario 4 — Database Q&A (Local KB + Export Edition)

Flow:
  1. LOCAL KB FIRST
     a. Greeting check  → sentence-transformer match against kb_greetings.json
     b. Question match  → sentence-transformer match against kb_chatbot_questions_updated.json
     c. confidence >= 0.55 → fetch SQL from kb_sql_queries_updated.json

  2. ORIGINAL TEMPLATE ROUTER (fallback if KB finds nothing)

  3. LLM FALLBACK (optional, if db_llm_fallback_enabled)

  4. Execute SQL → save full results to result_store → return:
       - text explanation
       - top 3 rows preview in metadata
       - download_id for CSV/XLSX/JSON export
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Optional

from services.base_service import BaseService, ChatRequest, ChatResponse
from memory.conversation_memory import ConversationMemory
from db_qa.sql_query_router import SQLQueryRouter, SCHEMA_CONTEXT
from db_qa.chart_generator import ChartGenerator, detect_chart
from db_qa.local_kb_matcher import get_local_kb
from db_qa.sql_explainer import explain_results
from results.result_store import save_query_results
from utils.logging_util import setup_logging

logger = setup_logging("scenario_4_db")

_FENCED_SQL_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class DatabaseQAService(BaseService):

    def __init__(
        self,
        memory: ConversationMemory,
        db_client,
        router: SQLQueryRouter,
        charter: ChartGenerator,
        llm=None,
        rules=None,        # kept for compatibility — local KB handles greetings now
    ):
        super().__init__(memory)
        self.db      = db_client
        self.router  = router
        self.charter = charter
        self.llm     = llm
        self.rules   = rules

        # Load local KB once at startup
        self._kb = get_local_kb()

    @property
    def scenario_number(self) -> int:
        return 4

    # ── Main chat ──────────────────────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.memory.add_message(request.session_id, "user", request.query)

        # Build display name: "govinda.sahu" → "Govinda Sahu"
        user_name = (
            request.user_id.replace(".", " ").replace("_", " ").title()
            if request.user_id else "there"
        )

        # ══════════════════════════════════════════════════════════════════════
        # STEP 1 — Local KB (greeting OR sql)
        # ══════════════════════════════════════════════════════════════════════
        kb_result = self._kb.match(request.query, user_name=user_name)

        # ── 1a. Greeting → return immediately ─────────────────────────────────
        if kb_result.is_greeting():
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
                metadata={"source": "greeting"},
            )

        # ── 1b. SQL from local KB ──────────────────────────────────────────────
        sql: Optional[str] = None
        binds: list        = []
        intent: str        = ""
        description: str   = ""
        chart_hint         = None
        source: str        = "local_kb"

        if kb_result.is_sql():
            sql         = kb_result.sql
            binds       = []
            intent      = kb_result.query_variable
            description = kb_result.description
            logger.info({
                "event": "local_kb_sql_match",
                "query_var": kb_result.query_variable,
                "confidence": round(kb_result.confidence, 4),
                "matched_question": kb_result.matched_question,
            })

        # ══════════════════════════════════════════════════════════════════════
        # STEP 2 — Original template router
        # ══════════════════════════════════════════════════════════════════════
        if not sql:
            match = self.router.match(request.query)
            if match is not None:
                sql         = match.sql
                binds       = match.binds
                intent      = match.intent
                description = match.description
                chart_hint  = match.chart_hint
                source      = "template"

        # ══════════════════════════════════════════════════════════════════════
        # STEP 3 — LLM fallback
        # ══════════════════════════════════════════════════════════════════════
        if not sql:
            if self.cfg.db_llm_fallback_enabled and self.llm is not None:
                try:
                    sql         = self._llm_generate_sql(request.query)
                    intent      = "llm.generated"
                    description = "LLM-generated query"
                    source      = "llm"
                except Exception as exc:
                    return self._fail(
                        request,
                        f"Could not understand the question and LLM fallback failed: {exc}"
                    )
            else:
                return self._fail(
                    request,
                    f"Sorry {user_name}, I couldn't match your question. "
                    "Try: 'Which files are scheduled today?' or 'Which files failed today?'",
                )

        # ══════════════════════════════════════════════════════════════════════
        # STEP 4 — Execute SQL
        # ══════════════════════════════════════════════════════════════════════
        try:
            cols, rows = self.db.execute(sql, binds)
        except Exception as exc:
            logger.error({"event": "query_failed", "intent": intent, "error": str(exc)})
            return self._fail(
                request,
                f"Query execution failed.\n\nIntent: {intent}\nError: {exc}",
            )

        # ── Save full results for export ───────────────────────────────────────
        download_id = save_query_results(
            title=description,
            sql=sql,
            columns=cols,
            rows=rows,
        )

        # ── Top 3 rows preview ─────────────────────────────────────────────────
        preview_rows = rows[:3]
        preview_data = []
        for row in preview_rows:
            if isinstance(row, dict):
                preview_data.append([str(row.get(col, "")) for col in cols])
            else:
                preview_data.append([str(v) for v in row])

        # ── Explanation text ───────────────────────────────────────────────────
        row_count     = len(rows)
        response_text = explain_results(
            question=request.query,
            columns=cols,
            rows=rows,
        )

        # ── Optional chart ─────────────────────────────────────────────────────
        chart_info = None
        if self.cfg.chart_enabled and rows:
            spec = chart_hint or detect_chart(rows, cols)
            if spec:
                try:
                    chart_info = self.charter.generate(rows, cols, spec)
                except Exception as exc:
                    logger.error({"event": "chart_failed", "error": str(exc)})

        self.memory.add_message(request.session_id, "assistant", response_text)

        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            scenario=self.scenario_number,
            provider="db",
            model=f"synapse:{self.cfg.db_name}" if self.cfg.db_name else "synapse",
            rule_matched=intent,
            metadata={
                "source": source,
                "results": f"{row_count} rows found",
                "preview": {
                    "columns": cols,
                    "rows": preview_data,
                },
                "download_id": download_id,
                "export_formats": ["csv", "xlsx", "json"],
                "sql": sql,
                "matched_template": description,
                "chart": _chart_for_response(chart_info),
            },
        )

    # Stream: DB queries are sync — single chunk
    def chat_stream(self, request: ChatRequest) -> Iterator[dict]:
        result = self.chat(request)
        yield {"type": "chunk", "content": result.response}
        yield self._meta_event(
            request,
            provider=result.provider,
            model=result.model,
            cached=False,
            rule_matched=result.rule_matched,
            metadata=result.metadata,
        )

    # ── Internals ──────────────────────────────────────────────────────────────

    def _llm_generate_sql(self, question: str) -> str:
        messages = [
            {"role": "system", "content": SCHEMA_CONTEXT},
            {"role": "user",   "content": question},
        ]
        raw = self.llm.chat(messages)
        m   = _FENCED_SQL_RE.search(raw)
        return (m.group(1) if m else raw).strip().rstrip(";")

    def _fail(self, request: ChatRequest, msg: str) -> ChatResponse:
        self.memory.add_message(request.session_id, "assistant", msg)
        return ChatResponse(
            response=msg,
            session_id=request.session_id,
            scenario=self.scenario_number,
            provider="db",
            model="unmatched",
            metadata={"source": "fallback", "error": True},
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _chart_for_response(chart_info: Optional[dict]) -> Optional[dict]:
    if not chart_info:
        return None
    return chart_info