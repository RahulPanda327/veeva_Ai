"""Conversation memory, session management and memory management for the assistant.

THREE CONCERNS, KEPT SEPARATE
    Conversation memory   what the model is shown: the last N turns of this chat.
    Session management    identity and lifecycle: creating a session, touching
                          it, expiring it when idle.
    Memory management     bounding growth: a per-session turn window, an idle
                          TTL, and a cap on total sessions.

    The third one is the one that gets skipped and then bites. Without it, an
    endpoint anyone on the network can hit grows a file on disk forever, one
    entry per browser that ever loaded the page.

WHAT IS STORED
    Only the user's question and the assistant's answer. NOT the retrieved
    context - that is regenerated per question, would multiply the file size by
    the size of six chunks, and is stale the moment the KB is re-embedded.

WHAT IS NOT REMEMBERED
    Greetings, validation failures, rate-limit refusals and errors. None of them
    is part of the conversation the rep is having, and keeping them would push
    real turns out of the window.

FOLLOW-UP QUESTIONS
    History alone does not make "what about Pittsburgh?" answerable: that string
    embeds to nothing useful, so retrieval returns noise and the model is handed
    history it cannot ground. rewrite_followup() below resolves the question
    against recent turns BEFORE the vector search. That step is what makes
    memory an improvement rather than a regression.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.assistant import interaction_store
from app.services.assistant.session_store import get_session_store

log = logging.getLogger(__name__)


# ── Session management ───────────────────────────────────────────────────────

def _now() -> float:
    return time.time()


def _new_session(device_id: str = "") -> Dict[str, Any]:
    return {"created_at": _now(), "last_seen": _now(),
            "device_id": device_id, "turns": []}


def get_or_create(session_id: str, device_id: str = "") -> Dict[str, Any]:
    """Load a session, creating it if absent or expired.

    An expired session is replaced rather than resumed: picking up a
    conversation from two days ago produces stranger answers than starting
    fresh, because the model treats stale turns as current.
    """
    store = get_session_store()
    session = store.get(session_id)
    if session is None or _is_expired(session):
        session = _new_session(device_id)
    session["last_seen"] = _now()
    if device_id and not session.get("device_id"):
        session["device_id"] = device_id
    return session


def _is_expired(session: Dict[str, Any]) -> bool:
    ttl = max(1, int(settings.ASSISTANT_SESSION_TTL_HOURS)) * 3600
    return (_now() - float(session.get("last_seen") or 0)) > ttl


# ── Conversation memory ──────────────────────────────────────────────────────

def history_for_llm(session_id: str) -> List[Dict[str, str]]:
    """Recent turns as chat messages, oldest first.

    Trimmed to ASSISTANT_MEMORY_WINDOW_TURNS *pairs*, not messages: cutting
    mid-pair leaves an assistant reply with no question above it, which reads to
    the model as something it said unprompted.
    """
    if not settings.ASSISTANT_MEMORY_ENABLED:
        return []

    # On Postgres the conversation lives in chat_interactions - the same rows the
    # API envelope is stored as. Reading the window from there rather than from a
    # parallel copy means there is one record of what was said, and the audit
    # trail and the model can never disagree about it.
    if interaction_store.enabled():
        return interaction_store.history_for_llm(
            session_id, int(settings.ASSISTANT_MEMORY_WINDOW_TURNS))

    session = get_session_store().get(session_id)
    if not session or _is_expired(session):
        return []
    window = max(1, int(settings.ASSISTANT_MEMORY_WINDOW_TURNS)) * 2
    turns = session.get("turns") or []
    return [{"role": t["role"], "content": t["content"]} for t in turns[-window:]]


def record_turn(session_id: str, question: str, answer: str,
                device_id: str = "") -> None:
    """Append one question/answer pair and persist.

    Both messages are written together so the stored history can never hold a
    question whose answer was lost to a crash between two writes.
    """
    if not settings.ASSISTANT_MEMORY_ENABLED or not session_id:
        return
    # On Postgres the router writes the full envelope to chat_interactions, which
    # IS the turn. Writing a second copy here would duplicate every exchange and
    # give the window two sources that drift apart.
    if interaction_store.enabled():
        return
    try:
        session = get_or_create(session_id, device_id)
        now = _now()
        session["turns"].extend([
            {"role": "user", "content": question, "at": now},
            {"role": "assistant", "content": answer, "at": now},
        ])
        # Trim on write as well as on read: the read-side window controls what the
        # model sees, this controls what the file holds. Without it a long chat
        # grows without limit even though only the tail is ever used.
        keep = max(1, int(settings.ASSISTANT_MEMORY_WINDOW_TURNS)) * 2 * 2
        if len(session["turns"]) > keep:
            session["turns"] = session["turns"][-keep:]
        get_session_store().put(session_id, session)
        prune()
    except Exception as exc:  # noqa: BLE001
        # Memory is an enhancement; failing to store a turn must never fail the
        # answer that was already produced.
        log.warning("Could not record chat turn for %s (%s).", session_id[:8], exc)


def clear(session_id: str) -> None:
    get_session_store().delete(session_id)


# ── Memory management ────────────────────────────────────────────────────────

def prune() -> None:
    """Drop expired sessions, then the oldest if still over the cap.

    Runs after each recorded turn rather than on a timer: there is no scheduler
    in this process, and doing it inline means the bound holds even if the app
    is only ever hit sporadically.
    """
    store = get_session_store()
    sessions = store.all_sessions()
    kept = {sid: s for sid, s in sessions.items() if not _is_expired(s)}

    cap = max(1, int(settings.ASSISTANT_MAX_SESSIONS))
    if len(kept) > cap:
        # Oldest-touched first: a conversation nobody has continued is the one
        # whose loss is least noticeable.
        ordered = sorted(kept.items(), key=lambda kv: float(kv[1].get("last_seen") or 0))
        kept = dict(ordered[-cap:])

    if len(kept) != len(sessions):
        log.info("Pruned %d chat session(s); %d remain.",
                 len(sessions) - len(kept), len(kept))
        store.replace_all(kept)


def stats() -> Dict[str, Any]:
    """Session counts, for an admin endpoint or a log line."""
    if interaction_store.enabled():
        return {**interaction_store.stats(),
                "window_turns": int(settings.ASSISTANT_MEMORY_WINDOW_TURNS)}
    sessions = get_session_store().all_sessions()
    return {
        "sessions": len(sessions),
        "active": sum(1 for s in sessions.values() if not _is_expired(s)),
        "turns": sum(len(s.get("turns") or []) for s in sessions.values()),
        "window_turns": int(settings.ASSISTANT_MEMORY_WINDOW_TURNS),
        "ttl_hours": int(settings.ASSISTANT_SESSION_TTL_HOURS),
        "backend": settings.ASSISTANT_SESSION_STORE,
    }


# ── Follow-up resolution ─────────────────────────────────────────────────────

_REWRITE_SYSTEM = """Rewrite the user's latest message as a standalone question.

Resolve pronouns and implied subjects using the conversation above - "what about
Pittsburgh?" after a question about San Francisco becomes the same question
asked of Pittsburgh.

Rules:
- Output ONLY the rewritten question. No preamble, no quotes, no explanation.
- If the message is already standalone, output it unchanged.
- Never invent detail that is not in the conversation or the message.
- Keep it one sentence."""


# Words and shapes that mean "this question leans on the previous one".
_REFERENTIAL = re.compile(
    # "there" is deliberately absent: "how many X are there?" is a perfectly
    # standalone question, and including it sent every one of them through an
    # unnecessary rewrite that could only corrupt them.
    r"\b(it|its|they|them|their|he|she|her|his|that|those|these|this|"
    r"same|others?|another|instead|too|also|as well)\b"
    r"|^\s*(what|how)\s+about\b|^\s*and\b|^\s*(ok|okay|then)\b",
    re.IGNORECASE,
)


def _looks_like_followup(question: str) -> bool:
    """Does this question need the conversation to be understood?

    Guarding the rewrite matters more than it looks. Asked to rewrite an ALREADY
    standalone question, phi4-mini does not return it unchanged as instructed -
    it folds in whatever the previous turn was about. A repeat of "What is the
    total HCP count in the territory prioritization?" came back as a question
    about Pittsburgh, purely because Pittsburgh appeared earlier in the thread.
    The answer changed and the cache could not hit.

    Three signals, any of which means "cannot stand alone":

      short         "what about Pittsburgh?", "and Boston?"
      referential   contains it / they / that / this / the same ...
      no subject    mentions nothing this knowledge base is about

    The third exists because of "What was the total number ?" - five words, no
    pronoun, so the first two signals both missed it. It sailed through to
    retrieval as a vague query and came back with objection call counts, having
    silently dropped "New Writer IDs" from the previous turn. A question naming
    none of the domain's nouns cannot be answered on its own here, whatever its
    length.
    """
    q = (question or "").strip()
    if not q:
        return False
    if len(q.split()) <= 4:
        return True
    if _REFERENTIAL.search(q):
        return True
    return not _SUBJECT.search(q)


# The things this knowledge base is about. A question naming none of them is
# leaning on the previous turn for its subject.
_SUBJECT = re.compile(
    r"\b(hcps?|doctors?|prescribers?|writers?|objections?|alerts?|territor(?:y|ies)|"
    r"prescriptions?|rx|calls?|scores?|priorit(?:y|ies)|candidates?|payers?|"
    r"competitors?|insights?|segments?|tiers?|quarters?|managers?|employees?|"
    r"brands?|specialt(?:y|ies)|deciles?|reps?|targets?)\b",
    re.IGNORECASE,
)


def rewrite_followup(question: str, history: List[Dict[str, str]]) -> str:
    """Resolve a follow-up into a standalone question before retrieval.

    Returns the original question unchanged when there is no history, when the
    feature is off, or on any failure - retrieval with the raw question is a
    worse search, but a working one, and this must not be able to break chat.
    """
    if not settings.ASSISTANT_QUERY_REWRITE_ENABLED or not history:
        return question
    if not _looks_like_followup(question):
        return question
    try:
        from app.utils.llm_client import make_llm_client   # noqa: PLC0415

        convo = "\n".join(f"{t['role']}: {t['content'][:400]}" for t in history[-6:])
        resp = make_llm_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM},
                {"role": "user", "content":
                    f"=== CONVERSATION ===\n{convo}\n\n=== LATEST ===\n{question}"},
            ],
            temperature=0.0,
            max_tokens=120,
        )
        rewritten = (resp.choices[0].message.content or "").strip().strip('"')
        # A rewrite that comes back empty, or wildly longer than the original, is
        # the model explaining itself rather than answering. Prefer the original.
        if not rewritten or len(rewritten) > max(200, len(question) * 6):
            return question
        if rewritten != question:
            log.info("Rewrote follow-up: %r -> %r", question[:60], rewritten[:60])
        return rewritten
    except Exception as exc:  # noqa: BLE001
        log.warning("Follow-up rewrite failed (%s); using the original question.", exc)
        return question


def get_or_create_session_id(supplied: Optional[str]) -> str:
    """The caller's session id, or a new one.

    Kept here rather than in the router so 'what counts as a session' has one
    home once other entry points need it.
    """
    import uuid   # noqa: PLC0415

    return (supplied or "").strip() or str(uuid.uuid4())
