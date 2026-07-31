"""Transient-disconnect retry for Azure Synapse queries.

Synapse serverless drops pooled connections that sat idle, and with a local
Ollama model an Action Center request can spend 5+ minutes on LLM enrichment
before (or between) its DB reads — long enough for the pool's connection to be
killed server-side. `pool_pre_ping` only proves the connection was alive at
CHECKOUT; if Synapse tears it down a moment later the real query still fails
with 08S01 / 10054 "communication link failure".

That failure is transient: a fresh connection works immediately. Retrying is
the standard Azure SQL transient-fault pattern, and it matters here because the
alternative in the Action Center services was to silently fall back to
hardcoded SAMPLE rows — which the permanent response cache would then store as
a 200 and serve as if it were real payer/competitor data.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from sqlalchemy.exc import DBAPIError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# SQLSTATE / driver text that means "the connection died", not "your SQL is wrong".
_TRANSIENT_MARKERS = (
    "08s01",                      # communication link failure
    "08003",                      # connection not open
    "10054",                      # WinError: forcibly closed by remote host
    "communication link failure",
    "connection is closed",
    "server closed the connection",
)


def is_transient_disconnect(exc: BaseException) -> bool:
    """True when the error is a dropped connection rather than a bad query."""
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


def run_with_retry(db, fn: Callable[[], T], attempts: int = 3, what: str = "query") -> T:
    """Run `fn()`, retrying only on transient disconnects.

    Anything else (bad SQL, missing column, permissions) is raised immediately —
    retrying those just wastes time. If every attempt hits a disconnect the last
    exception propagates, so the caller fails LOUDLY instead of quietly serving
    sample data that would get cached as though it were real.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if not is_transient_disconnect(exc) or attempt == attempts:
                raise
            logger.warning(
                "%s: connection dropped (attempt %d/%d) — reconnecting and retrying.",
                what, attempt, attempts,
            )
            # Discard the dead connection so the next attempt checks out a fresh
            # one; without this the session stays in a failed state.
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5 * attempt)
    raise RuntimeError(f"{what}: retry loop exited unexpectedly")  # pragma: no cover
