"""Which vector store backs the assistant — one import site for both options.

    VECTOR_STORE=chroma     (default) local Chroma DB in chroma_db/, no server
    VECTOR_STORE=pgvector             embeddings in PostgreSQL + pgvector

Both classes expose the same methods (store / clear_source / search / count /
ensure_table / close, plus bulk() and sources()), so callers do not care which
one they get.

`chroma` is the default: a real vector database with an HNSW index and metadata
filtering, but persisted to a local directory rather than a server. Nothing to
install, run or credential — which is what made pgvector painful to deploy on
the VM — while still scaling past the point where scanning every row per query
stops being sensible.

Switch to `pgvector` when several machines must share one store; a local Chroma
directory belongs to whichever host holds it.

A third backend, `local`, kept the embeddings in a single .npz file scanned with
numpy. It existed only to avoid pgvector's server dependency, which Chroma
avoids as well and with a real index — so it was removed rather than left as a
second thing to keep in step with every change here. It is in git history if the
brute-force store is ever wanted back.
"""
from __future__ import annotations

import os

_CHROMA = ("chroma", "chromadb")
_PGVECTOR = ("pgvector", "postgres", "pg")


def _backend() -> str:
    return (os.getenv("VECTOR_STORE", "chroma") or "chroma").strip().lower()


def get_vector_store():
    """Return the configured store instance (a process-level singleton)."""
    backend = _backend()
    if backend in _CHROMA:
        from db_qa.chroma_store import get_chroma_store       # noqa: PLC0415

        return get_chroma_store()
    if backend in _PGVECTOR:
        from db_qa.pgvector_store import get_pgvector_store   # noqa: PLC0415

        return get_pgvector_store()
    raise ValueError(
        f"VECTOR_STORE={backend!r} is not a known backend. Use 'chroma' or 'pgvector'."
    )


def store_label() -> str:
    """Human-readable name of where the vectors live, for logs."""
    if _backend() in _PGVECTOR:
        from db_qa.pgvector_store import TABLE_NAME   # noqa: PLC0415

        return f"postgres table '{TABLE_NAME}'"
    from db_qa.chroma_store import CHROMA_DIR, COLLECTION_NAME   # noqa: PLC0415

    return f"chroma collection '{COLLECTION_NAME}' in {CHROMA_DIR}"
