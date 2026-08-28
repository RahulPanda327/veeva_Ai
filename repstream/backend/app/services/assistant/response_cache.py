"""Answer cache for the assistant — ask the same thing twice, pay for it once.

A question costs an embedding call, a vector search and an LLM generation, which
on phi4-mini is 20-30 seconds. Repeats are common: the same rep re-asks, several
reps ask the same thing, and a demo asks it every time.

WHAT THE KEY INCLUDES, AND WHY EACH PART HAS TO BE THERE
    question          normalised (case, whitespace, trailing punctuation) so
                      "How many HCPs?" and "how many hcps" are one entry.
    conversation      a fingerprint of the turns shown to the model. "what about
                      Pittsburgh?" means different things in different threads;
                      keying on the question alone would serve one thread's
                      answer to another.
    llm model         switching provider changes the answer. Without this,
                      flipping to OpenAI would keep replaying phi4-mini's replies.
    embedding model   decides which chunks are retrieved at all.
    kb fingerprint    row count + store mtime. This is the important one: a
                      warm-up rewrites repstream_live_data.txt and re-embeds it,
                      so yesterday's cached answer states yesterday's numbers as
                      current. The fingerprint changes on re-ingest and the old
                      entries stop matching.

WHAT IS NOT CACHED
    Greetings (already free), empty questions, and every error path. Caching a
    "language model could not be reached" would keep serving that failure long
    after the model came back.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.cache_paths import cache_file

log = logging.getLogger(__name__)

_CACHE_FILE = cache_file("assistant_response_cache.json")
_lock = threading.Lock()
_entries: Dict[str, Dict[str, Any]] = {}
_kb_fingerprint: Optional[str] = None

# Backend follows ASSISTANT_SESSION_STORE: sessions and answers are two halves of
# the same conversation data, and splitting them across a database and a local
# file makes "where is the chat stored" have two answers.
_PG = None


def _use_pg() -> bool:
    return (settings.ASSISTANT_SESSION_STORE or "file").strip().lower() in (
        "postgres", "postgresql", "pg")


# ── Persistence ──────────────────────────────────────────────────────────────

_DDL = """
    CREATE TABLE IF NOT EXISTS assistant_answer_cache (
        cache_key   TEXT PRIMARY KEY,
        question    TEXT,
        answer      TEXT,
        payload     JSONB NOT NULL,
        kb_version  TEXT,
        created_at  DOUBLE PRECISION NOT NULL,
        last_used   DOUBLE PRECISION NOT NULL,
        hits        INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS assistant_answer_cache_last_used_idx
        ON assistant_answer_cache (last_used);
"""


def _connect():
    import psycopg2   # noqa: PLC0415

    return psycopg2.connect(settings.POSTGRES_URL, connect_timeout=5)


def _ensure_pg() -> bool:
    """Create the table on first use. False means fall back to memory only."""
    global _PG
    if _PG is not None:
        return _PG
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(_DDL)
        _PG = True
        log.info("Assistant answer cache: PostgreSQL table assistant_answer_cache ready.")
    except Exception as exc:  # noqa: BLE001
        # In-process caching still works; it just will not survive a restart or
        # be shared. Chat must not fail because a cache table was unreachable.
        _PG = False
        log.warning("Could not prepare assistant_answer_cache (%s); "
                    "caching in memory only for this process.", exc)
    return _PG


def _load() -> None:
    if _use_pg():
        # Not preloaded: rows are fetched by key on demand. The table can hold
        # far more than the file ever did, and pulling all of it into memory at
        # startup would trade the benefit away.
        _ensure_pg()
        return
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _entries.update(json.load(f) or {})
        log.info("Loaded %d cached assistant answer(s) from %s",
                 len(_entries), _CACHE_FILE.name)
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load assistant answer cache (%s); starting empty.", exc)


def _save() -> None:
    if _use_pg():
        return
    try:
        tmp = _CACHE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_entries, f, ensure_ascii=False)
        os.replace(tmp, _CACHE_FILE)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not save assistant answer cache (%s).", exc)


_load()


# ── Key ──────────────────────────────────────────────────────────────────────

_WS = re.compile(r"\s+")


def _normalise(question: str) -> str:
    """Fold away differences that cannot change the answer."""
    q = _WS.sub(" ", (question or "").strip().lower())
    return q.rstrip("?!. ")


def _kb_version() -> str:
    """Fingerprint of the embedded knowledge base.

    Read from the stamp the ingest writes when it FINISHES (see
    ai_assistant/scripts/ingest_to_pgvector.py). It changes on re-ingest and at
    no other time, which is exactly the property this needs.

    It is not derived from the store's files. The first version of this used
    chroma.sqlite3's mtime, and Chroma rewrites that file merely by opening the
    database - so the fingerprint changed on every server start and silently
    threw the whole cache away on each restart. The symptom was a cache that
    "worked" in one process and never survived one.

    Row count is the fallback when no stamp exists yet (a store ingested before
    this was added). It is weaker - a warm-up re-embeds the live data and
    usually keeps the same chunk count - so the stamp is what should normally
    be present.

    Computed once per process: the KB cannot change under a running server.
    """
    global _kb_fingerprint
    if _kb_fingerprint is not None:
        return _kb_fingerprint
    try:
        import sys                                          # noqa: PLC0415
        from pathlib import Path                            # noqa: PLC0415

        assistant = Path(__file__).resolve().parents[3] / "ai_assistant"
        stamp = assistant / "chroma_db" / "ingest_stamp.json"
        if stamp.is_file():
            data = json.loads(stamp.read_text(encoding="utf-8"))
            _kb_fingerprint = str(data.get("ingest_id") or data.get("at") or "stamped")
            return _kb_fingerprint

        if str(assistant) not in sys.path:
            sys.path.insert(0, str(assistant))
        from db_qa.vector_store import get_vector_store     # noqa: PLC0415

        _kb_fingerprint = f"rows:{get_vector_store().count()}"
    except Exception as exc:  # noqa: BLE001
        # Unknown fingerprint disables reuse across restarts rather than risking
        # a stale answer: a per-process value can never match a stored one.
        _kb_fingerprint = f"unknown:{time.time()}"
        log.warning("Could not fingerprint the knowledge base (%s); "
                    "answer cache will not persist across restarts.", exc)
    return _kb_fingerprint


def make_key(question: str, llm_model: str, embed_model: str) -> str:
    """Key on the RESOLVED question - no conversation fingerprint.

    The first version hashed the recent turns into the key, because the model was
    shown those turns and the answer therefore depended on them. That was sound
    and useless: every answered question changes the history, so asking the same
    thing twice in one session could never hit. A rep repeating a question waited
    the full 25 seconds again.

    The conversation is now folded in earlier instead - memory.rewrite_followup()
    turns "what about Pittsburgh?" into a standalone question BEFORE this key is
    built, and the generation call no longer receives the raw turns. So the
    resolved question is the whole input, and two identical resolved questions
    genuinely have the same answer whichever thread they came from.
    """
    raw = "||".join([_normalise(question), llm_model, embed_model, _kb_version()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Public API ───────────────────────────────────────────────────────────────

def get(key: str) -> Optional[Dict[str, Any]]:
    """The cached payload, or None if absent or expired."""
    if not settings.ASSISTANT_RESPONSE_CACHE_ENABLED:
        return None
    ttl = max(1, int(settings.ASSISTANT_RESPONSE_CACHE_TTL_SECONDS))
    now = time.time()

    if _use_pg() and _ensure_pg():
        try:
            with _connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT payload, created_at FROM assistant_answer_cache "
                            "WHERE cache_key = %s", (key,))
                row = cur.fetchone()
                if not row:
                    return None
                if (now - float(row[1])) > ttl:
                    cur.execute("DELETE FROM assistant_answer_cache WHERE cache_key = %s",
                                (key,))
                    return None
                # Touched so eviction drops genuinely cold entries rather than
                # merely old ones - a question asked daily should outlive one
                # asked once.
                cur.execute("UPDATE assistant_answer_cache "
                            "SET last_used = %s, hits = hits + 1 WHERE cache_key = %s",
                            (now, key))
                return row[0]
        except Exception as exc:  # noqa: BLE001
            log.warning("Answer cache read failed (%s); answering without it.", exc)
            return None

    with _lock:
        entry = _entries.get(key)
        if not entry:
            return None
        if (now - float(entry.get("at") or 0)) > ttl:
            _entries.pop(key, None)
            return None
        entry["last_used"] = now
        entry["hits"] = int(entry.get("hits") or 0) + 1
        return json.loads(json.dumps(entry["payload"]))


def put(key: str, payload: Dict[str, Any], question: str = "") -> None:
    if not settings.ASSISTANT_RESPONSE_CACHE_ENABLED:
        return
    now = time.time()
    cap = max(1, int(settings.ASSISTANT_RESPONSE_CACHE_MAX_ENTRIES))

    if _use_pg() and _ensure_pg():
        try:
            with _connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assistant_answer_cache
                        (cache_key, question, answer, payload, kb_version,
                         created_at, last_used, hits)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, 0)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        payload    = EXCLUDED.payload,
                        answer     = EXCLUDED.answer,
                        created_at = EXCLUDED.created_at,
                        last_used  = EXCLUDED.last_used
                    """,
                    (key, question or None, str(payload.get("answer") or "")[:4000],
                     json.dumps(payload), _kb_version(), now, now),
                )
                # Least-recently-USED eviction, done in SQL so two processes
                # sharing the table cannot each keep their own idea of the cap.
                cur.execute(
                    """
                    DELETE FROM assistant_answer_cache WHERE cache_key IN (
                        SELECT cache_key FROM assistant_answer_cache
                        ORDER BY last_used DESC OFFSET %s
                    )
                    """, (cap,))
        except Exception as exc:  # noqa: BLE001
            log.warning("Answer cache write failed (%s); the answer was not cached.", exc)
        return

    with _lock:
        _entries[key] = {"payload": payload, "at": now, "last_used": now, "hits": 0}
        if len(_entries) > cap:
            ordered = sorted(_entries.items(),
                             key=lambda kv: float(kv[1].get("last_used") or 0))
            for stale, _ in ordered[:len(_entries) - cap]:
                _entries.pop(stale, None)
    _save()


def clear() -> int:
    if _use_pg() and _ensure_pg():
        try:
            with _connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM assistant_answer_cache")
                n = int(cur.fetchone()[0])
                cur.execute("DELETE FROM assistant_answer_cache")
            return n
        except Exception as exc:  # noqa: BLE001
            log.warning("Answer cache clear failed (%s).", exc)
            return 0
    with _lock:
        n = len(_entries)
        _entries.clear()
    _save()
    return n


def stats() -> Dict[str, Any]:
    base = {
        "kb_version": _kb_version(),
        "ttl_seconds": int(settings.ASSISTANT_RESPONSE_CACHE_TTL_SECONDS),
        "enabled": bool(settings.ASSISTANT_RESPONSE_CACHE_ENABLED),
        "backend": "postgres" if _use_pg() else "file",
    }
    if _use_pg() and _ensure_pg():
        try:
            with _connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT COUNT(*), COALESCE(SUM(hits), 0) "
                            "FROM assistant_answer_cache")
                n, hits = cur.fetchone()
            return {**base, "entries": int(n), "total_hits": int(hits)}
        except Exception as exc:  # noqa: BLE001
            return {**base, "error": str(exc)[:120]}
    with _lock:
        return {**base, "entries": len(_entries),
                "total_hits": sum(int(e.get("hits") or 0) for e in _entries.values())}
