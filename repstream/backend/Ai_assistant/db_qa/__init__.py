"""
db_qa — Scenario 4 (Database Q&A) toolkit.

Self-contained subsystem that translates natural-language questions into
read-only T-SQL against the Ops warehouse, executes via the shared SQL Server
client, and optionally renders a chart from the result set.

Modules:
  sql_templates      — DB_TEMPLATES list (~19 parameterised template dicts)
  sql_query_router   — SQLQueryRouter, TemplateMatch, SCHEMA_CONTEXT
  chart_generator    — ChartGenerator + detect_chart heuristic
"""

from db_qa.sql_query_router import SQLQueryRouter, TemplateMatch, SCHEMA_CONTEXT
from db_qa.sql_templates import DB_TEMPLATES
from db_qa.chart_generator import ChartGenerator, detect_chart

__all__ = [
    "SQLQueryRouter",
    "TemplateMatch",
    "SCHEMA_CONTEXT",
    "DB_TEMPLATES",
    "ChartGenerator",
    "detect_chart",
]
