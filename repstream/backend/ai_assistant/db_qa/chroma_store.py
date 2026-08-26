"""Chroma-backed vector store — a real vector DB, still entirely local.

Same public interface as LocalVectorStore and PGVectorStore (store /
clear_source / search / count / ensure_table / close, plus bulk() and
sources()), so the three are interchangeable. Pick one with VECTOR_STORE; see
db_qa/vector_store.py.

WHY CHROMA RATHER THAN THE .npz STORE
    The .npz store loads the whole matrix into memory and scans every row per
    query. That is the right trade at a few hundred chunks and the wrong one
    later: Chroma keeps an HNSW index, so query time grows with log(N) rather
    than N, and it does not need the entire corpus resident to answer.

    It also gives real metadata filtering (`where={"source": ...}`) instead of
    a Python list comprehension over every row, and it handles concurrent
    readers properly — the .npz store has no locking beyond one atomic replace.

WHY IT IS STILL LOCAL
    PersistentClient writes a SQLite database plus index files under
    ai_assistant/chroma_db/. There is no server to install, run, or
    credential — the same deployment story as the .npz store, which is what
    made pgvector painful on the VM.

EMBEDDINGS ARE COMPUTED HERE, NOT BY CHROMA
    Chroma will happily embed documents itself using its own bundled ONNX
    model. We deliberately pass precomputed vectors instead, from the same
    SentenceTransformer the other two backends use. Otherwise EMBEDDING_MODEL_NAME
    would silently stop being the setting that decides how text is embedded, and
    switching VECTOR_STORE would quietly change the answers rather than just
    where they are stored.

DISTANCE
    The collection is created with hnsw:space=cosine, and vectors are
    L2-normalised on write. Chroma returns a DISTANCE, so search() converts it
    back to a similarity (1 - distance) before returning — callers compare
    scores against COSINE_SIMILARITY_THRESHOLD and must see the same 0-1
    similarity scale from every backend.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import numpy as np

from utils.logging_util import setup_logging

logger = setup_logging("chroma_store")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSION", "384"))


def _env(name: str, default: str) -> str:
    """Environment value, treating blank as absent.

    os.getenv returns "" for a key that is present but empty, and `CHROMA_DIR=`
    in .env is exactly that. Taken literally it becomes Path("") - the current
    working directory - so the database lands wherever the process happened to
    be started from. That is how chroma.sqlite3 first appeared in the package
    root instead of chroma_db/.
    """
    return (os.getenv(name) or "").strip() or default


# Sits beside kb/ and embeddings/, inside the package, so it travels with the
# checkout like the .npz store does.
_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "chroma_db"
CHROMA_DIR = Path(_env("CHROMA_DIR", str(_DEFAULT_DIR)))
COLLECTION_NAME = _env("CHROMA_COLLECTION", "repstream_kb")

# Reported where PGVectorStore names its table, so logs read the same either way.
TABLE_NAME = COLLECTION_NAME

# One upsert per chunk is a separate SQLite transaction and index insert. Batching
# turns a 298-chunk ingest into a handful of calls instead of 298.
_BATCH = 256


class ChromaStore:
    """HNSW search over a local Chroma collection."""

    def __init__(self) -> None:
        self._model = None
        self._client = None
        self._collection = None
        self._defer = 0
        self._pending: list[dict] = []

    # ── Model ────────────────────────────────────────────────────────────────

    def _get_model(self):
        """Load the encoder on first use.

        Deferred because importing sentence-transformers pulls in torch: seconds
        of startup and hundreds of MB of RSS that a process which never searches
        should not pay.
        """
        if self._model is None:
            from sentence_transformers import SentenceTransformer   # noqa: PLC0415

            logger.info({"event": "chroma_loading_model", "model": EMBEDDING_MODEL})
            self._model = SentenceTransformer(EMBEDDING_MODEL)
            actual = self._model.get_sentence_embedding_dimension()
            if actual != EMBEDDING_DIM:
                raise ValueError(
                    f"EMBEDDING_DIMENSION={EMBEDDING_DIM} but {EMBEDDING_MODEL} produces "
                    f"{actual}. Fix the setting, or re-ingest with a matching model - "
                    f"vectors of different widths cannot be compared."
                )
        return self._model

    def _encode(self, text: str) -> list[float]:
        vec = self._get_model().encode(text, show_progress_bar=False)
        vec = np.asarray(vec, dtype=np.float32)
        # Normalised here so cosine distance behaves identically to the .npz
        # backend. Guard the zero vector: an empty string would divide by zero.
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    # ── Connection ───────────────────────────────────────────────────────────

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        import chromadb                                   # noqa: PLC0415
        from chromadb.config import Settings              # noqa: PLC0415

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        logger.info({"event": "chroma_open", "path": str(CHROMA_DIR),
                     "collection": COLLECTION_NAME})
        self._client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            # Telemetry is an outbound HTTP call on startup. Off: it is noise in
            # the logs, it fails on an air-gapped VM, and nothing here needs it.
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            # Default is L2. Cosine is what every other backend and the
            # COSINE_SIMILARITY_THRESHOLD setting assume, and it is only settable
            # at creation time - a collection made without this keeps L2 for good.
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    # ── Batching ─────────────────────────────────────────────────────────────

    @contextmanager
    def bulk(self):
        """Batch an ingest into a handful of writes instead of one per chunk.

        Mirrors LocalVectorStore.bulk() so the ingest script does not care which
        backend it is talking to. Rows still flush automatically every _BATCH,
        so a long ingest does not hold the whole corpus in memory before any of
        it reaches disk.
        """
        self._defer += 1
        try:
            yield self
        finally:
            self._defer -= 1
            if self._defer == 0:
                self._flush_pending()

    def _flush_pending(self) -> None:
        """Write buffered rows in batches."""
        if not self._pending:
            return
        col = self._get_collection()
        rows, self._pending = self._pending, []
        for start in range(0, len(rows), _BATCH):
            batch = rows[start:start + _BATCH]
            # upsert rather than add: a re-ingest that produces the same chunk id
            # should replace that chunk, not raise a duplicate-id error and
            # abandon the run halfway through.
            col.upsert(
                ids=[r["id"] for r in batch],
                embeddings=[r["embedding"] for r in batch],
                documents=[r["content"] for r in batch],
                metadatas=[r["metadata"] for r in batch],
            )
        logger.info({"event": "chroma_flushed", "rows": len(rows)})

    # ── Write ────────────────────────────────────────────────────────────────

    def ensure_table(self) -> None:
        """Open (creating if needed) the collection."""
        self._get_collection()

    def store(self, source: str, chunk_id: str, title: str, content: str,
              metadata: Optional[dict] = None) -> None:
        """Embed *content* and buffer one row."""
        meta = {
            # Chroma metadata values must be scalars, so nested dicts from the
            # ingest are flattened to strings rather than silently rejected.
            **{k: (v if isinstance(v, (str, int, float, bool)) else str(v))
               for k, v in (metadata or {}).items()},
            "source": source,
            "chunk_id": chunk_id,
            "title": title,
        }
        self._pending.append({
            "id": chunk_id,
            "embedding": self._encode(content),
            "content": content,
            "metadata": meta,
        })
        if not self._defer or len(self._pending) >= _BATCH:
            self._flush_pending()

    def clear_source(self, source: str) -> None:
        """Drop every row for *source* so it can be re-ingested cleanly.

        Pending rows are flushed first. The ingest clears a source and then
        immediately re-adds it, so a delete that jumped ahead of buffered writes
        would remove rows that had not been written yet - and, worse, leave the
        ones that had.
        """
        self._flush_pending()
        col = self._get_collection()
        before = col.count()
        col.delete(where={"source": source})
        logger.info({"event": "chroma_cleared", "source": source,
                     "removed": before - col.count()})

    # ── Read ─────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> list[dict]:
        """Top-k rows most similar to *query*. Score is cosine similarity (0-1)."""
        self._flush_pending()
        col = self._get_collection()
        total = col.count()
        if not total:
            return []

        res = col.query(
            query_embeddings=[self._encode(query)],
            n_results=min(top_k, total),
            include=["documents", "metadatas", "distances"],
        )
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        ids = (res.get("ids") or [[]])[0]

        out: list[dict] = []
        for n, (doc, meta, dist, rid) in enumerate(zip(docs, metas, dists, ids), 1):
            meta = dict(meta or {})
            # cosine distance -> similarity, so every backend returns the same scale.
            score = 1.0 - float(dist)
            if score < min_score:
                continue
            out.append({
                "id": n,
                "source": meta.get("source", ""),
                "chunk_id": meta.get("chunk_id", rid),
                "title": meta.get("title", ""),
                "content": doc or "",
                "metadata": meta,
                "score": score,
            })
        return out

    def count(self) -> int:
        self._flush_pending()
        return self._get_collection().count()

    def sources(self) -> list[str]:
        """Every distinct source currently held — used by the ingest to drop
        sources whose file has been deleted from kb/."""
        self._flush_pending()
        col = self._get_collection()
        if not col.count():
            return []
        got = col.get(include=["metadatas"])
        return sorted({str((m or {}).get("source", ""))
                       for m in (got.get("metadatas") or [])} - {""})

    def close(self) -> None:
        """Flush anything buffered. PersistentClient writes through on its own,
        so there is no connection to tear down."""
        self._flush_pending()


_instance: Optional[ChromaStore] = None


def get_chroma_store() -> ChromaStore:
    global _instance
    if _instance is None:
        _instance = ChromaStore()
    return _instance
