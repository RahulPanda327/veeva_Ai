"""Which vector store backs the assistant — one import site for both options.

    VECTOR_STORE=local      (default) embeddings in kb/embeddings.npz, no server
    VECTOR_STORE=pgvector             embeddings in PostgreSQL + pgvector

Both classes expose the same methods (store / clear_source / search / count /
ensure_table / close), so callers do not care which one they get.

`local` is the default because it removes a deployment dependency: no Postgres
to install, configure, credential, or keep running, and the embeddings ship with
the checkout instead of having to be rebuilt on every machine. At ~128 chunks a
brute-force scan is faster than the network round-trip to a database would be.

Switch to `pgvector` when the corpus outgrows memory (roughly 50k-100k chunks)
or when several processes must write to the store concurrently.
"""
from __future__ import annotations

import os


def _backend() -> str:
    return (os.getenv("VECTOR_STORE", "local") or "local").strip().lower()


def get_vector_store():
    """Return the configured store instance (a process-level singleton)."""
    backend = _backend()
    if backend in ("local", "file", "npz"):
        from db_qa.local_vector_store import get_local_store   # noqa: PLC0415

        return get_local_store()
    if backend in ("pgvector", "postgres", "pg"):
        from db_qa.pgvector_store import get_pgvector_store   # noqa: PLC0415

        return get_pgvector_store()
    raise ValueError(
        f"VECTOR_STORE={backend!r} is not a known backend. Use 'local' or 'pgvector'."
    )


def store_label() -> str:
    """Human-readable name of where the vectors live, for logs."""
    if _backend() in ("pgvector", "postgres", "pg"):
        from db_qa.pgvector_store import TABLE_NAME   # noqa: PLC0415

        return f"postgres table '{TABLE_NAME}'"
    from db_qa.local_vector_store import VECTORS_FILE   # noqa: PLC0415

    return str(VECTORS_FILE)
