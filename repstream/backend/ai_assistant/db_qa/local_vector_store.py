"""File-backed vector store — embeddings live inside the project, not in Postgres.

Same public interface as PGVectorStore (store / clear_source / search / count /
ensure_table / close), so the two are interchangeable. Pick one with the
VECTOR_STORE setting; see db_qa/vector_store.py.

WHY THIS EXISTS
    pgvector needs a PostgreSQL server with the `vector` extension installed,
    configured, and reachable. That is a real dependency to satisfy on every
    machine the project runs on, and the embeddings do not travel with the repo:
    a fresh checkout has an empty store until someone re-ingests. Most of the
    deployment friction on the VM came from exactly that.

    At this corpus size none of that buys anything. The knowledge base is ~128
    chunks of 384 dimensions - 196 KB as float32. A brute-force dot product over
    that is well under a millisecond, so an HNSW index is solving a problem this
    project does not have.

WHEN TO GO BACK TO PGVECTOR
    This loads the whole matrix into memory and scans all of it per query. That
    is the right trade until roughly 50k-100k chunks, or if several processes
    need to write concurrently - there is no locking here beyond one atomic
    file replace. At that point switch VECTOR_STORE back to pgvector.

STORAGE
    kb/embeddings.npz        float32 matrix, one normalised row per chunk
    kb/embeddings_meta.json  the rows themselves (source, title, content, ...)

    Two files rather than one so the metadata stays greppable and reviewable in
    a diff; the matrix is opaque either way. Vectors are L2-normalised on write,
    which makes cosine similarity a plain dot product at query time.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import numpy as np

from utils.logging_util import setup_logging

logger = setup_logging("local_vector_store")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# Default location: kb/ inside this package. Deliberately NOT kb/vectors/, which
# .gitignore excludes - the whole point is that these files are committed and
# ship with the project.
_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "kb"
STORE_DIR = Path(os.getenv("VECTOR_STORE_DIR", str(_DEFAULT_DIR)))
VECTORS_FILE = STORE_DIR / "embeddings.npz"
META_FILE = STORE_DIR / "embeddings_meta.json"

# Reported where PGVectorStore would name its table, so log lines and the
# ingest script's output read the same for either backend.
TABLE_NAME = str(VECTORS_FILE.name)


class LocalVectorStore:
    """Brute-force cosine search over an in-memory matrix, persisted to disk."""

    def __init__(self) -> None:
        self._model = None
        self._vectors: Optional[np.ndarray] = None   # (N, dim) float32, normalised
        self._rows: list[dict] = []
        self._loaded = False
        self._defer = 0          # >0 while inside bulk(): suppresses per-row writes
        self._dirty = False

    @contextmanager
    def bulk(self):
        """Batch an ingest into a single write.

        Without this, store() persists the whole archive on every row: a 138-chunk
        ingest rewrote ~125 KB 138 times, which is slow and — more to the point —
        gives a concurrent process or a virus scanner 138 chances to be holding
        the file during os.replace instead of one.
        """
        self._defer += 1
        try:
            yield self
        finally:
            self._defer -= 1
            if self._defer == 0 and self._dirty:
                self._flush()
                self._dirty = False

    def _maybe_flush(self) -> None:
        if self._defer:
            self._dirty = True
            return
        self._flush()

    # ── Model ────────────────────────────────────────────────────────────────

    def _get_model(self):
        """Load the encoder on first use.

        Deferred because importing sentence-transformers pulls in torch: seconds
        of startup and hundreds of MB of RSS that a process which never searches
        should not pay.
        """
        if self._model is None:
            from sentence_transformers import SentenceTransformer   # noqa: PLC0415

            logger.info({"event": "local_store_loading_model", "model": EMBEDDING_MODEL})
            self._model = SentenceTransformer(EMBEDDING_MODEL)
            actual = self._model.get_sentence_embedding_dimension()
            if actual != EMBEDDING_DIM:
                raise ValueError(
                    f"EMBEDDING_DIMENSION={EMBEDDING_DIM} but {EMBEDDING_MODEL} produces "
                    f"{actual}. Fix the setting, or re-ingest with a matching model - "
                    f"vectors of different widths cannot be compared."
                )
        return self._model

    def _encode(self, text: str) -> np.ndarray:
        vec = self._get_model().encode(text, show_progress_bar=False)
        vec = np.asarray(vec, dtype=np.float32)
        # Normalise once here so search is a dot product rather than a division
        # per row. Guard the zero vector: an empty string would divide by zero.
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else vec

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not VECTORS_FILE.is_file():
            self._vectors = np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
            self._rows = []
            return
        try:
            with np.load(VECTORS_FILE, allow_pickle=False) as data:
                self._vectors = data["vectors"].astype(np.float32)
                if "meta" in data.files:
                    self._rows = json.loads(str(data["meta"]))
                else:
                    # Archive written by the earlier two-file layout, where the
                    # metadata lived only in embeddings_meta.json. Read it from
                    # there; the next _flush() rewrites in the single-file format.
                    logger.info({"event": "local_store_legacy_format"})
                    self._rows = (json.loads(META_FILE.read_text(encoding="utf-8"))
                                  if META_FILE.is_file() else [])
            if len(self._rows) != len(self._vectors):
                # Cannot happen while both live in one archive, but a hand-edited
                # or truncated file still gets caught rather than silently pairing
                # a vector with someone else's text.
                raise ValueError(
                    f"{VECTORS_FILE.name} has {len(self._vectors)} vectors but "
                    f"{len(self._rows)} metadata rows. Re-run the ingest."
                )
            logger.info({"event": "local_store_loaded", "rows": len(self._rows)})
        except Exception as exc:  # noqa: BLE001
            logger.warning({"event": "local_store_load_failed", "error": str(exc)})
            raise

    def _flush(self) -> None:
        """Persist the store as ONE archive, replaced atomically.

        Vectors and metadata live in the same .npz on purpose. They were two
        files, which meant two os.replace calls: if the second failed — and on
        Windows it does whenever another process has the file open — the store
        was left with N vectors and N-1 rows, i.e. every vector after the break
        paired with the wrong text. One archive makes that state unreachable:
        either the replace lands and both are current, or it does not and both
        stay as they were.

        embeddings_meta.json is still written afterwards, but only as a
        human-readable convenience copy. Nothing reads it; if it is stale or
        missing, the store is unaffected.

        The retry exists because os.replace on Windows fails with Access Denied
        while any other process holds the destination open — a concurrent ingest,
        or an antivirus scanner that grabbed the file the moment it appeared.
        Backing off briefly clears both far more often than not.
        """
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        vectors = self._vectors if self._vectors is not None else np.zeros(
            (0, EMBEDDING_DIM), dtype=np.float32)
        meta = json.dumps(self._rows, ensure_ascii=False)

        last: Optional[Exception] = None
        for attempt in range(5):
            fd, tmp = tempfile.mkstemp(dir=str(STORE_DIR), suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as fh:
                    np.savez_compressed(fh, vectors=vectors, meta=np.array(meta))
                os.replace(tmp, VECTORS_FILE)
                break
            except PermissionError as exc:
                last = exc
                if os.path.exists(tmp):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                time.sleep(0.2 * (attempt + 1))
            except Exception:
                if os.path.exists(tmp):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                raise
        else:
            raise RuntimeError(
                f"Could not write {VECTORS_FILE.name} after 5 attempts: {last}. "
                f"Another process is most likely writing the same store — check for "
                f"a second server or ingest running against this checkout."
            ) from last

        # Best-effort sidecar for humans. Never read back, so a failure here is
        # not worth failing the ingest over.
        try:
            META_FILE.write_text(json.dumps(self._rows, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        except OSError as exc:
            logger.warning({"event": "local_store_sidecar_failed", "error": str(exc)})

    # ── Write ────────────────────────────────────────────────────────────────

    def ensure_table(self) -> None:
        """No schema to create — just make sure the directory exists."""
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def store(self, source: str, chunk_id: str, title: str, content: str,
              metadata: Optional[dict] = None) -> None:
        """Embed *content* and append one row."""
        self._load()
        vec = self._encode(content).reshape(1, -1)
        self._vectors = vec if self._vectors is None or len(self._vectors) == 0 \
            else np.vstack([self._vectors, vec])
        self._rows.append({
            "id": len(self._rows) + 1,
            "source": source,
            "chunk_id": chunk_id,
            "title": title,
            "content": content,
            "metadata": metadata or {},
        })
        self._maybe_flush()

    def clear_source(self, source: str) -> None:
        """Drop every row for *source* so it can be re-ingested cleanly."""
        self._load()
        keep = [i for i, r in enumerate(self._rows) if r.get("source") != source]
        removed = len(self._rows) - len(keep)
        self._rows = [self._rows[i] for i in keep]
        self._vectors = (self._vectors[keep] if len(keep)
                         else np.zeros((0, EMBEDDING_DIM), dtype=np.float32))
        for n, row in enumerate(self._rows, 1):
            row["id"] = n
        self._maybe_flush()
        logger.info({"event": "local_store_cleared", "source": source, "removed": removed})

    # ── Read ─────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> list[dict]:
        """Top-k rows most similar to *query*. Score is cosine similarity (0-1)."""
        self._load()
        if self._vectors is None or len(self._vectors) == 0:
            return []
        q = self._encode(query)
        # Both sides are normalised, so the dot product IS the cosine.
        scores = self._vectors @ q
        k = min(top_k, len(scores))
        # argpartition finds the top k without sorting all N; sort just those.
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        return [
            {**self._rows[i], "score": float(scores[i])}
            for i in idx
            if float(scores[i]) >= min_score
        ]

    def count(self) -> int:
        self._load()
        return len(self._rows)

    def close(self) -> None:
        """Nothing to release — every mutation is already flushed."""
        return


_instance: Optional[LocalVectorStore] = None


def get_local_store() -> LocalVectorStore:
    global _instance
    if _instance is None:
        _instance = LocalVectorStore()
    return _instance
