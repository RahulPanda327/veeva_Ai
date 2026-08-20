"""
db_qa — vector store and charting helpers.

Was the Scenario 4 (Database Q&A) toolkit: natural language -> read-only T-SQL
-> execute -> chart. That SQL path has been removed; RepStream answers from
embedded text and never generates SQL.

What remains:
  pgvector_store     — PGVectorStore, the embedding store RepStream retrieves from
  chart_generator    — ChartGenerator + detect_chart heuristic
  local_kb_matcher   — local KB similarity matching

Nothing is imported eagerly here. pgvector_store pulls in sentence-transformers
and torch, so importing it costs seconds and hundreds of MB — callers should
import the module they actually need:

    from db_qa.pgvector_store import get_pgvector_store
"""

__all__: list[str] = []
