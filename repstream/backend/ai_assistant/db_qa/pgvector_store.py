"""
PGVector Store — stores and retrieves embeddings from PostgreSQL with the pgvector extension.

Table: chatbot_embeddings
  source     — 'context_file' or 'kb_question'
  chunk_id   — section key or Query_variable
  title      — human-readable label
  content    — text that was embedded
  metadata   — JSONB (question, description, module, etc.)
  embedding  — vector(384) from all-MiniLM-L6-v2

Connection is read from env vars with the project defaults:
  PGVECTOR_HOST      localhost
  PGVECTOR_PORT      5432
  PGVECTOR_DB        postgres
  PGVECTOR_USER      postgres
  PGVECTOR_PASSWORD  password@123
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer

from utils.logging_util import setup_logging

logger = setup_logging("pgvector_store")

# ── Embedding configuration — set in ai_assistant/.env, not here ─────────────
#
#   EMBEDDING_MODEL_NAME   any sentence-transformers model
#   EMBEDDING_DIMENSION    that model's output size
#   PGVECTOR_TABLE         which table holds the vectors
#
# The .env is loaded explicitly because this module is imported from two places:
# the chatbot itself (whose CWD is this folder) and the RepStream backend (whose
# CWD is backend/, where a plain env_file=".env" would pick up the wrong file).
# Explicit beats implicit here — otherwise the setting silently has no effect
# depending on which process imported the module.
try:
    from dotenv import load_dotenv

    # One .env for the whole project, at the repstream root.
    #   this file: repstream/backend/ai_assistant/db_qa/pgvector_store.py
    # parents[1] is ai_assistant, parents[2] backend, parents[3] repstream.
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
except Exception:  # noqa: BLE001 — a missing .env just means defaults apply
    pass

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
EMBEDDING_DIM   = int(os.getenv("EMBEDDING_DIMENSION", "384"))
TABLE_NAME      = os.getenv("PGVECTOR_TABLE", "chatbot_embeddings")


def _dsn() -> dict:
    return {
        "host":     os.getenv("PGVECTOR_HOST",     "localhost"),
        "port":     int(os.getenv("PGVECTOR_PORT", "5432")),
        "dbname":   os.getenv("PGVECTOR_DB",       "postgres"),
        "user":     os.getenv("PGVECTOR_USER",      "postgres"),
        "password": os.getenv("PGVECTOR_PASSWORD",  "password@123"),
    }


class PGVectorStore:
    """Thin wrapper around psycopg2 + pgvector for embedding storage and retrieval."""

    def __init__(self) -> None:
        self._model: Optional[SentenceTransformer] = None
        self._conn = None

    # ── Internal helpers ─────────────────────────────────────────────────────────

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info({"event": "pgvector_loading_model", "model": EMBEDDING_MODEL})
            self._model = SentenceTransformer(EMBEDDING_MODEL)

            # A model and a dimension that disagree produce a Postgres error on
            # every insert ("expected N dimensions, not M") with no hint as to
            # which setting is wrong. Say it plainly, once, at load time.
            actual = self._model.get_sentence_embedding_dimension()
            if actual and actual != EMBEDDING_DIM:
                raise ValueError(
                    f"EMBEDDING_DIMENSION={EMBEDDING_DIM} does not match "
                    f"EMBEDDING_MODEL_NAME={EMBEDDING_MODEL!r}, which produces "
                    f"{actual} dimensions. Set EMBEDDING_DIMENSION={actual} in "
                    f"ai_assistant/.env. Note that changing the model also means "
                    f"re-ingesting: existing vectors in '{TABLE_NAME}' came from a "
                    f"different model and cannot be compared with new ones — drop "
                    f"the table or set PGVECTOR_TABLE to a new name, then re-run "
                    f"scripts.ingest_to_pgvector."
                )
        return self._model

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**_dsn())
        return self._conn

    @staticmethod
    def _vec_to_str(vec: list[float]) -> str:
        """Format a float list as a pgvector literal: '[0.123,...]'"""
        return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"

    def _encode(self, text: str) -> str:
        vec = self._get_model().encode(
            text, convert_to_tensor=False, show_progress_bar=False
        ).tolist()
        return self._vec_to_str(vec)

    # ── Schema management ────────────────────────────────────────────────────────

    def ensure_table(self) -> None:
        """Create the vector extension, table, and HNSW index if they do not exist."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id         SERIAL PRIMARY KEY,
                    source     VARCHAR(50)              NOT NULL,
                    chunk_id   VARCHAR(200),
                    title      TEXT,
                    content    TEXT                     NOT NULL,
                    metadata   JSONB                    DEFAULT '{{}}',
                    embedding  vector({EMBEDDING_DIM})  NOT NULL,
                    created_at TIMESTAMPTZ              DEFAULT NOW()
                );
            """)
            # HNSW index works on any dataset size and needs no minimum row count
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS {TABLE_NAME}_hnsw_idx
                ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops);
            """)
        conn.commit()
        logger.info({"event": "pgvector_table_ready", "table": TABLE_NAME})

    # ── Write ────────────────────────────────────────────────────────────────────

    def store(
        self,
        source: str,
        chunk_id: str,
        title: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Embed *content* and insert one row."""
        vec_str = self._encode(content)
        conn    = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {TABLE_NAME}
                    (source, chunk_id, title, content, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                """,
                (
                    source,
                    chunk_id,
                    title,
                    content,
                    json.dumps(metadata or {}),
                    vec_str,
                ),
            )
        conn.commit()

    def clear_source(self, source: str) -> None:
        """Delete all rows for *source* so it can be re-ingested cleanly."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLE_NAME} WHERE source = %s", (source,))
        conn.commit()
        logger.info({"event": "pgvector_cleared", "source": source})

    # ── Read ─────────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict]:
        """
        Return the top_k rows most similar to *query*, filtered by *min_score*.
        Score = 1 − cosine_distance  (0–1; higher is more similar).
        """
        vec_str = self._encode(query)
        conn    = self._get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT
                    id, source, chunk_id, title, content, metadata,
                    1 - (embedding <=> %s::vector) AS score
                FROM {TABLE_NAME}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_str, vec_str, top_k),
            )
            rows = cur.fetchall()

        return [
            {
                "id":       row["id"],
                "source":   row["source"],
                "chunk_id": row["chunk_id"],
                "title":    row["title"],
                "content":  row["content"],
                "metadata": dict(row["metadata"]) if row["metadata"] else {},
                "score":    float(row["score"]),
            }
            for row in rows
            if float(row["score"]) >= min_score
        ]

    def count(self) -> int:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            return cur.fetchone()[0]

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()


# ── Process-level singleton ───────────────────────────────────────────────────────

_instance: Optional[PGVectorStore] = None


def get_pgvector_store() -> PGVectorStore:
    global _instance
    if _instance is None:
        _instance = PGVectorStore()
    return _instance
