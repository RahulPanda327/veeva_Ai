"""
In-memory feedback tracking for chatbot query/response exchanges.

Each chat exchange gets a unique exchange_id and a sequential index
within its session. Users submit thumbs_up or thumbs_down votes via
the /feedback routes; thumbs-down entries are exposed separately for
review in Swagger or the UI.

No database is used — all state lives in FeedbackStore until the
process restarts. Call get_feedback_store() to get the singleton.
"""

import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

from utils.logging_util import setup_logging

logger = setup_logging("feedback_logs")

FeedbackVote = Literal["thumbs_up", "thumbs_down"]


@dataclass
class FeedbackComment:
    """Comment attached to a thumbs-down exchange."""
    related_message_id: str     # message_unique_id of the exchange
    related_session_id: str     # session that owns the exchange
    comments: str               # user-supplied comment text
    rating: Optional[float] = None      # reserved for future star-rating; null for now
    created_at: Optional[str] = None    # ISO-8601 UTC timestamp


@dataclass
class ExchangeRecord:
    """Represents one query/response pair within a session."""
    message_unique_id: str  # globally unique UUID
    session_id: str         # parent session
    index: int              # 1-based sequential position within the session
    query: str              # user's original message
    response: str           # assistant's reply
    created_at: str         # ISO-8601 UTC timestamp of exchange creation
    vote: Optional[FeedbackVote] = None   # None until user votes
    voted_at: Optional[str] = None        # ISO-8601 UTC timestamp of vote
    tenant_id: str = ""
    project_id: str = ""
    user_id: str = ""
    app_session_id: str = ""
    request_source: str = "web"
    updated_at: Optional[str] = None
    processing_details: dict = field(default_factory=dict)
    preview_rows: list = field(default_factory=list)
    download_id: Optional[str] = None
    response_type: str = "text"


class FeedbackStore:
    """
    Thread-safe in-memory store for exchanges and their feedback votes.

    Internally maintains:
      _exchanges     : exchange_id  → ExchangeRecord  (fast lookup)
      _session_index : session_id   → [exchange_id, ...]  (ordered by insertion)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._exchanges: dict[str, ExchangeRecord] = {}
        self._session_index: dict[str, list[str]] = {}
        self._comments: dict[str, FeedbackComment] = {}   # message_unique_id → comment
        self._global_counter: int = 0

    # ── Write operations ────────────────────────────────────────────────────────

    def record_exchange(
        self,
        session_id: str,
        query: str,
        response: str,
        tenant_id: str = "",
        project_id: str = "",
        user_id: str = "",
        app_session_id: str = "",
        request_source: str = "web",
        processing_details: Optional[dict] = None,
        preview_rows: Optional[list] = None,
        download_id: Optional[str] = None,
        response_type: str = "text",
    ) -> ExchangeRecord:
        """Register a new query/response pair."""
        with self._lock:
            if session_id not in self._session_index:
                self._session_index[session_id] = []

            index = self._global_counter
            self._global_counter += 1
            message_unique_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()

            record = ExchangeRecord(
                message_unique_id=message_unique_id,
                session_id=session_id,
                index=index,
                query=query,
                response=response,
                created_at=now,
                updated_at=now,
                tenant_id=tenant_id,
                project_id=project_id,
                user_id=user_id,
                app_session_id=app_session_id,
                request_source=request_source,
                processing_details=processing_details or {},
                preview_rows=preview_rows or [],
                download_id=download_id,
                response_type=response_type,
            )

            self._exchanges[message_unique_id] = record
            self._session_index[session_id].append(message_unique_id)

        logger.info({
            "event": "exchange_recorded",
            "message_unique_id": message_unique_id,
            "session_id": session_id,
            "index": index,
        })
        return record

    def submit_vote(
        self,
        message_unique_id: str,
        vote: FeedbackVote,
    ) -> Optional[ExchangeRecord]:
        """
        Record a thumbs_up or thumbs_down vote for an exchange.

        Returns the updated record, or None if message_unique_id not found.
        Negative votes are logged at WARNING level for easy filtering.
        """
        with self._lock:
            record = self._exchanges.get(message_unique_id)
            if record is None:
                return None
            record.vote = vote
            record.voted_at = datetime.now(timezone.utc).isoformat()
            record.updated_at = record.voted_at

        logger.info({
            "event": "feedback_submitted",
            "message_unique_id": message_unique_id,
            "session_id": record.session_id,
            "index": record.index,
            "vote": vote,
        })

        if vote == "thumbs_down":
            logger.warning({
                "event": "negative_feedback",
                "message_unique_id": message_unique_id,
                "session_id": record.session_id,
                "index": record.index,
                "query": record.query,
                "response": record.response,
                "voted_at": record.voted_at,
            })

        return record

    def add_comment(
        self,
        message_unique_id: str,
        comments: str,
    ) -> Optional[FeedbackComment]:
        """
        Attach a comment to a thumbs-down exchange.

        Returns the created FeedbackComment, or None if message_unique_id
        is not found or the exchange has not been voted thumbs_down.
        """
        with self._lock:
            record = self._exchanges.get(message_unique_id)
            if record is None or record.vote != "thumbs_down":
                return None
            now = datetime.now(timezone.utc).isoformat()
            comment = FeedbackComment(
                related_message_id=message_unique_id,
                related_session_id=record.session_id,
                comments=comments,
                rating=None,
                created_at=now,
            )
            record.updated_at = now
            self._comments[message_unique_id] = comment

        logger.info({
            "event": "comment_added",
            "message_unique_id": message_unique_id,
            "session_id": record.session_id,
        })
        return comment

    def get_comment(self, message_unique_id: str) -> Optional[FeedbackComment]:
        """Return the comment for an exchange, or None if none exists."""
        with self._lock:
            return self._comments.get(message_unique_id)

    # ── Read operations ─────────────────────────────────────────────────────────

    def get_exchange(self, message_unique_id: str) -> Optional[ExchangeRecord]:
        """Return a single exchange by its ID."""
        with self._lock:
            return self._exchanges.get(message_unique_id)

    def get_session_exchanges(self, session_id: str) -> list[ExchangeRecord]:
        """Return all exchanges for a session in insertion order."""
        with self._lock:
            ids = self._session_index.get(session_id, [])
            return [self._exchanges[eid] for eid in ids if eid in self._exchanges]

    def get_negative_feedback(self) -> list[ExchangeRecord]:
        """Return all exchanges that received a thumbs_down vote."""
        with self._lock:
            return [r for r in self._exchanges.values() if r.vote == "thumbs_down"]

    def get_all_exchanges(self) -> list[ExchangeRecord]:
        """Return every recorded exchange regardless of vote status."""
        with self._lock:
            return list(self._exchanges.values())

    def summary(self) -> dict:
        """Return aggregate counts useful for a dashboard widget."""
        with self._lock:
            total = len(self._exchanges)
            positive = sum(1 for r in self._exchanges.values() if r.vote == "thumbs_up")
            negative = sum(1 for r in self._exchanges.values() if r.vote == "thumbs_down")
            voted = positive + negative
            return {
                "total_exchanges": total,
                "voted": voted,
                "thumbs_up": positive,
                "thumbs_down": negative,
                "unvoted": total - voted,
                "active_sessions": len(self._session_index),
            }


# ── Singleton accessor ──────────────────────────────────────────────────────────

_feedback_store: Optional[FeedbackStore] = None


def get_feedback_store() -> FeedbackStore:
    """Return the process-wide FeedbackStore singleton (created on first call)."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore()
    return _feedback_store
