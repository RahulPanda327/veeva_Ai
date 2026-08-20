# """
# Maps a natural-language question to a SQL query.

# Flow:
#   1. Try each template's regex patterns.
#   2. If one matches, extract its named groups → params dict.
#   3. Substitute params into the template's bind_template list → final binds.
#   4. Return TemplateMatch with intent, SQL, binds, chart hint, description.

# If no template matches and LLM fallback is enabled and an LLM key is configured,
# the caller (DatabaseQAService) can ask the LLM to generate SQL with the schema
# context exposed in `SCHEMA_CONTEXT`.
# """

# from __future__ import annotations

# import re
# from dataclasses import dataclass, field
# from typing import Optional

# from config.settings import get_config
# from db_qa.sql_templates import DB_TEMPLATES
# from utils.logging_util import setup_logging

# logger = setup_logging("sql_router")


# @dataclass
# class TemplateMatch:
#     template_id: str
#     intent: str
#     description: str
#     category: str
#     sql: str
#     binds: list
#     chart_hint: Optional[dict]
#     params: dict[str, str] = field(default_factory=dict)


# # ────────────────────────────────────────────────────────────────────────────────
# # Router
# # ────────────────────────────────────────────────────────────────────────────────

# class SQLQueryRouter:
#     def __init__(self, templates: Optional[list[dict]] = None):
#         self.cfg = get_config()
#         self.templates = templates or DB_TEMPLATES
#         # pre-compile patterns
#         self._compiled: list[tuple[dict, list[re.Pattern]]] = [
#             (t, [re.compile(p, re.IGNORECASE) for p in t["patterns"]])
#             for t in self.templates
#         ]
#         logger.info({"event": "sql_router_ready", "templates": len(self.templates)})

#     def match(self, question: str) -> Optional[TemplateMatch]:
#         q = question.strip()
#         for tmpl, patterns in self._compiled:
#             for rx in patterns:
#                 m = rx.search(q)
#                 if not m:
#                     continue
#                 params = self._extract_params(tmpl, m)
#                 binds = [_substitute(b, params) for b in tmpl["bind_template"]]
#                 description = _substitute(tmpl["description"], params)
#                 logger.info({
#                     "event": "template_match",
#                     "template_id": tmpl["id"],
#                     "intent": tmpl["intent"],
#                     "params": params,
#                 })
#                 return TemplateMatch(
#                     template_id=tmpl["id"],
#                     intent=tmpl["intent"],
#                     description=description,
#                     category=tmpl["category"],
#                     sql=tmpl["sql"],
#                     binds=binds,
#                     chart_hint=tmpl.get("chart_hint"),
#                     params=params,
#                 )
#         logger.info({"event": "no_template_match", "query_preview": question[:80]})
#         return None

#     def list_templates(self) -> list[dict]:
#         """Return a UI-friendly list of all templates (no SQL bodies)."""
#         return [
#             {
#                 "id": t["id"],
#                 "intent": t["intent"],
#                 "description": t["description"],
#                 "category": t["category"],
#                 "param_names": t["param_names"],
#                 "patterns": t["patterns"],
#             }
#             for t in self.templates
#         ]

#     @staticmethod
#     def _extract_params(tmpl: dict, m: re.Match) -> dict[str, str]:
#         params: dict[str, str] = {}
#         # Start with template-level defaults (may be overridden by regex groups)
#         params.update(tmpl.get("default_params", {}))
#         gd = m.groupdict()
#         for name in tmpl["param_names"]:
#             val = gd.get(name)
#             if val is not None:
#                 params[name] = val
#         # also support positional groups if no named groups for backwards compat
#         if not any(gd.get(n) for n in tmpl["param_names"]) and tmpl["param_names"]:
#             groups = m.groups()
#             for i, name in enumerate(tmpl["param_names"]):
#                 if i < len(groups) and groups[i] is not None:
#                     params[name] = groups[i]
#         return params


# def _substitute(template: str, params: dict[str, str]) -> str | int:
#     """{name} → params['name']. Unmatched braces are left as-is.
#     If the fully-substituted result is a bare integer string, return int so
#     pyodbc binds it as SQL integer (avoids 'nvarchar invalid for minus' errors
#     in DATEADD(DAY, -?, ...)).
#     """
#     if not isinstance(template, str) or "{" not in template:
#         return template
#     out = template
#     for k, v in params.items():
#         out = out.replace("{" + k + "}", str(v))
#     # Coerce to int when the whole bind value is numeric (e.g. "{days}" → "3" → 3)
#     if out.lstrip("-").isdigit():
#         return int(out)
#     return out


# # ────────────────────────────────────────────────────────────────────────────────
# # Schema context for LLM fallback
# # ────────────────────────────────────────────────────────────────────────────────

# SCHEMA_CONTEXT = """\
# You are translating Ops questions into T-SQL for SQL Server / Azure Synapse.

# AVAILABLE OBJECTS in schema hub_md — use ONLY these exact names:

# VIEWS (prefix vw_):
#   hub_md.vw_ops_inventory
#       Columns: pipeline_name, subject_area, frequency, schedule_automation,
#                start_time_est, duration_in_mins, automation, status, direction
#       Note   : schedule_automation stores weekday flags e.g. 'Mon;#Tue;#Sat;#Sun'

#   hub_md.vw_runbook_history
#       Columns: subject_area, short_name, processed_date, processing_status,
#                file_id, feed_id
#       Note   : processing_status IN ('MISSED','FAILED','DELAYED','SUCCESS','LOADED')

# BASE TABLES (prefix hub_):
#   hub_md.hub_data_file_log     alias hdfl
#       Columns: file_id, feed_id, processed_date, dds_record_count,
#                stg_record_count, status (5=success), archive_loc, dds_table

#   hub_md.hub_data_feed         alias hdf
#       Columns: feed_id, subject_area, short_name, src_name, file_body,
#                actv_ind, entity_master_order

#   hub_md.hub_data_feed_version alias hdfv
#       Columns: feed_id, stg_table_name, dds_table_name

#   hub_md.hub_qc_sql_result
#       Columns: feed_id, file_id, qc_message, record_cnt, cre_dt

#   hub_md.hub_feed_qc_results
#       Columns: feed_id, file_id, qc_message, cre_dt

# CRITICAL — WRONG NAMES THAT DO NOT EXIST (never use these):
#   ✗ hub_md.hub_runbook_history    → use hub_md.vw_runbook_history
#   ✗ hub_md.runbook_history        → use hub_md.vw_runbook_history
#   ✗ hub_md.hub_ops_inventory      → use hub_md.vw_ops_inventory
#   ✗ hub_md.ops_inventory          → use hub_md.vw_ops_inventory

# Rules:
# 1. WITH (NOLOCK) syntax — CRITICAL:
#    - Without alias : FROM hub_md.vw_runbook_history WITH (NOLOCK)
#    - With alias    : FROM hub_md.vw_runbook_history vrh WITH (NOLOCK)  ← alias BEFORE hint
#    - NEVER         : FROM hub_md.vw_runbook_history WITH (NOLOCK) vrh  ← INVALID T-SQL
#    - In subqueries and CTEs: omit WITH (NOLOCK) entirely.
# 2. Use CAST(column AS DATE) = CAST(GETDATE() AS DATE) for whole-day date filters.
# 3. To match a feed by name: search subject_area, src_name, AND file_body with LIKE '%name%'.
# 4. Use ONLY SELECT statements. Never INSERT/UPDATE/DELETE/DROP/ALTER/EXEC.
# 5. Join hub_data_file_log to hub_data_feed via feed_id when you need feed names.
# 6. Return the SQL only — no explanation, no markdown fences.
# 7. For CTEs: terminate the previous statement with a semicolon — ;WITH cte AS (...)
# """



"""
Maps a natural-language question to a SQL query.

Flow:
  1. Try each template's regex patterns.
  2. If one matches, extract its named groups → params dict.
  3. Substitute params into the template's bind_template list → final binds.
  4. Return TemplateMatch with intent, SQL, binds, chart hint, description.

If no template matches and LLM fallback is enabled and an LLM key is configured,
the caller (DatabaseQAService) can ask the LLM to generate SQL with the schema
context exposed in `SCHEMA_CONTEXT`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from config.settings import get_config
from db_qa.sql_templates import DB_TEMPLATES
from utils.logging_util import setup_logging

logger = setup_logging("sql_router")


@dataclass
class TemplateMatch:
    template_id: str
    intent: str
    description: str
    category: str
    sql: str
    binds: list
    chart_hint: Optional[dict]
    params: dict[str, str] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────────
# Router
# ────────────────────────────────────────────────────────────────────────────────

class SQLQueryRouter:
    def __init__(self, templates: Optional[list[dict]] = None):
        self.cfg = get_config()
        self.templates = templates or DB_TEMPLATES
        # pre-compile patterns
        self._compiled: list[tuple[dict, list[re.Pattern]]] = [
            (t, [re.compile(p, re.IGNORECASE) for p in t["patterns"]])
            for t in self.templates
        ]
        logger.info({"event": "sql_router_ready", "templates": len(self.templates)})

    def match(self, question: str) -> Optional[TemplateMatch]:
        q = question.strip()
        for tmpl, patterns in self._compiled:
            for rx in patterns:
                m = rx.search(q)
                if not m:
                    continue
                params = self._extract_params(tmpl, m)
                binds = [_substitute(b, params) for b in tmpl["bind_template"]]
                description = _substitute(tmpl["description"], params)
                logger.info({
                    "event": "template_match",
                    "template_id": tmpl["id"],
                    "intent": tmpl["intent"],
                    "params": params,
                })
                return TemplateMatch(
                    template_id=tmpl["id"],
                    intent=tmpl["intent"],
                    description=description,
                    category=tmpl["category"],
                    sql=tmpl["sql"],
                    binds=binds,
                    chart_hint=tmpl.get("chart_hint"),
                    params=params,
                )
        logger.info({"event": "no_template_match", "query_preview": question[:80]})
        return None

    def list_templates(self) -> list[dict]:
        """Return a UI-friendly list of all templates (no SQL bodies)."""
        return [
            {
                "id": t["id"],
                "intent": t["intent"],
                "description": t["description"],
                "category": t["category"],
                "param_names": t["param_names"],
                "patterns": t["patterns"],
            }
            for t in self.templates
        ]

    @staticmethod
    def _extract_params(tmpl: dict, m: re.Match) -> dict[str, str]:
        params: dict[str, str] = {}
        # Start with template-level defaults (may be overridden by regex groups)
        params.update(tmpl.get("default_params", {}))
        gd = m.groupdict()
        for name in tmpl["param_names"]:
            val = gd.get(name)
            if val is not None:
                params[name] = val
        # also support positional groups if no named groups for backwards compat
        if not any(gd.get(n) for n in tmpl["param_names"]) and tmpl["param_names"]:
            groups = m.groups()
            for i, name in enumerate(tmpl["param_names"]):
                if i < len(groups) and groups[i] is not None:
                    params[name] = groups[i]
        return params


def _substitute(template: str, params: dict[str, str]) -> str | int:
    """{name} → params['name']. Unmatched braces are left as-is.
    If the fully-substituted result is a bare integer string, return int so
    pyodbc binds it as SQL integer (avoids 'nvarchar invalid for minus' errors
    in DATEADD(DAY, -?, ...)).
    """
    if not isinstance(template, str) or "{" not in template:
        return template
    out = template
    for k, v in params.items():
        out = out.replace("{" + k + "}", str(v))
    # Coerce to int when the whole bind value is numeric (e.g. "{days}" → "3" → 3)
    if out.lstrip("-").isdigit():
        return int(out)
    return out


# ────────────────────────────────────────────────────────────────────────────────
# Schema context for LLM fallback
# ────────────────────────────────────────────────────────────────────────────────

SCHEMA_CONTEXT = """\
You are translating Ops questions into T-SQL for SQL Server / Azure Synapse.

AVAILABLE OBJECTS in schema hub_md — use ONLY these exact names:

VIEWS (prefix vw_):
  hub_md.vw_ops_inventory
      Columns: pipeline_name, subject_area, frequency, schedule_automation,
               start_time_est, duration_in_mins, automation, status, direction
      Note   : schedule_automation stores weekday flags e.g. 'Mon;#Tue;#Sat;#Sun'

  hub_md.vw_runbook_history
      Columns: app, direction, subject_area, deliverable_name, frequency,
               schedule_automation, automation, start_time, status,
               processed_date, processed_day, processing_status
      Note   : processing_status IN ('MISSED','FAILED','DELAYED','SUCCESS','LOADED')
      Note   : has NO file_id, feed_id, or short_name — it cannot be joined to
               QC tables. For failure reasons / QC messages, use
               vw_runbook_history_feed_details or hub_data_file_log instead.

  hub_md.vw_runbook_history_feed_details
      Columns: subject_area, processed_date, processed_date_est, feed_id,
               feed_desc, status, file_id, stg_table, dds_table,
               stg_record_count, dds_record_count
      Note   : this is the view that bridges runbook status to feed_id/file_id
               so results can be joined to hub_feed_qc_results /
               hub_qc_sql_result for failure reasons.

BASE TABLES (prefix hub_):
  hub_md.hub_data_file_log     alias hdfl
      Columns: file_id, feed_id, processed_date, dds_record_count,
               stg_record_count, status (5=success), validation_status,
               stg_validation_error_count, archive_loc, dds_table,
               load_temp_elapsed_time, load_stg_elapsed_time,
               dds_elapsed_time, data_feed_transform_elapsed_time
      Note   : *_elapsed_time columns are numeric durations — use these for
               "longest/slowest load time" questions, not stg_table_name /
               dds_table_name (those are on hub_data_feed_version and mean
               physical table names, not timing).

  hub_md.hub_data_feed         alias hdf
      Columns: feed_id, subject_area, short_name, src_name, file_body,
               actv_ind, entity_master_order

  hub_md.hub_data_feed_version alias hdfv
      Columns: feed_id, stg_table_name, dds_table_name

  hub_md.hub_qc_sql_result
      Columns: feed_id, file_id, qc_message, record_cnt, cre_dt

  hub_md.hub_feed_qc_results
      Columns: feed_id, file_id, qc_message, cre_dt

  hub_md.hub_export_log
      Columns: export_id, step_id, outbound_folder, archive_folder,
               export_table_name, export_table_schema_name, export_file_name,
               quote_strings, record_count, status, log_message, actv_ind,
               cre_dt, updt_dt
      Note   : this is an EXECUTION LOG only — it has NO frequency, source
               name, short_name, or description columns, and is NOT joined to
               hub_data_feed or vw_ops_inventory (outbound lineage is
               self-contained). For export schedule/frequency/source-config
               questions ("export frequency", "delivery cadence per source"),
               use vw_ops_inventory filtered to direction = outbound instead —
               do not look for frequency on hub_export_log.

CRITICAL — WRONG NAMES THAT DO NOT EXIST (never use these):
  ✗ hub_md.hub_runbook_history    → use hub_md.vw_runbook_history
  ✗ hub_md.runbook_history        → use hub_md.vw_runbook_history
  ✗ hub_md.hub_ops_inventory      → use hub_md.vw_ops_inventory
  ✗ hub_md.ops_inventory          → use hub_md.vw_ops_inventory
  ✗ frequency column on hub_export_log, hub_data_file_log, hub_data_feed,
    hub_qc_sql_result, or hub_feed_qc_results → "frequency" only exists on
    vw_ops_inventory and vw_runbook_history (hub_data_feed has "freq" instead,
    a different column on a different table).

Rules:
1. WITH (NOLOCK) syntax — CRITICAL:
   - Without alias : FROM hub_md.vw_runbook_history WITH (NOLOCK)
   - With alias    : FROM hub_md.vw_runbook_history vrh WITH (NOLOCK)  ← alias BEFORE hint
   - NEVER         : FROM hub_md.vw_runbook_history WITH (NOLOCK) vrh  ← INVALID T-SQL
   - In subqueries and CTEs: omit WITH (NOLOCK) entirely.
2. Use CAST(column AS DATE) = CAST(GETDATE() AS DATE) for whole-day date filters.
3. To match a feed by name: search subject_area, src_name, AND file_body with LIKE '%name%'.
4. Use ONLY SELECT statements. Never INSERT/UPDATE/DELETE/DROP/ALTER/EXEC.
5. Join hub_data_file_log to hub_data_feed via feed_id when you need feed names.
6. Return the SQL only — no explanation, no markdown fences.
7. For CTEs: terminate the previous statement with a semicolon — ;WITH cte AS (...)
8. NEVER use named parameters or scalar variables (@startDate, @endDate, etc.) or ? placeholders —
   this SQL runs with no parameter binding, so any undeclared variable fails with
   "Must declare the scalar variable". If a date range is referenced without explicit dates
   (e.g. "the selected date range"), default to the last 30 days using
   CAST(column AS DATE) >= CAST(DATEADD(DAY, -30, GETDATE()) AS DATE).
"""
 