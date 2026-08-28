"""Chat over the RepStream data embedded in the assistant's vector store.

The pipeline this reads from:

    warm-up  ->  cache/endpoint_response_cache.json
             ->  scripts/export_live_to_kb.py   (renders it as sentences)
             ->  ai_assistant/kb/repstream_live_data.txt
             ->  scripts.ingest_to_pgvector     (embeds it)
             ->  the configured vector store (VECTOR_STORE)

A question is embedded with the same model the store was built with, the nearest
chunks come back, and the configured LLM answers from them. No SQL is generated
and the model never touches the database — it only reads text this application
already produced.

No filters and no territory scoping: the embedded chunks carry their own scope
labels, so one question covers every territory.
"""
from __future__ import annotations

import logging
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.assistant import memory, response_cache

log = logging.getLogger(__name__)

# The chatbot lives inside backend/ and owns the vector store; both run on the
# same virtualenv, so importing it is a path insert rather than a dependency.
#   this file: backend/app/services/assistant/chat_svc.py
# parents[3] is backend/, which contains ai_assistant.
_ASSISTANT_DIR = str(Path(__file__).resolve().parents[3] / "ai_assistant")

_SYSTEM = """You are the RepStream assistant for a pharmaceutical sales rep.

Answer using ONLY the CONTEXT below. It is drawn from the rep's own live
application data - HCP priorities, prescriptions, calls, new writer candidates,
objections and alerts - plus reference material explaining the terminology.

EARLIER TURNS ARE NOT A SOURCE
Messages before this one exist so you can resolve what the rep is referring to -
"what about Pittsburgh?", "the second one", "her". That is their ONLY job.
- Every fact in your answer must come from the CONTEXT block in the latest
  message. Never from an earlier answer.
- The CONTEXT is rebuilt for each question and describes THIS question's
  subject. If the previous answer named two HCPs and this question is about a
  different territory, those names are almost certainly wrong now - read the
  CONTEXT and answer from it.
- Repeating your last answer because it looks similar is the most damaging
  mistake available to you here. Check the CONTEXT first, every time.

ACCURACY
- Quote figures exactly as they appear. Never estimate or invent a number.
- If the context does not answer the question, say so and say what you would
  need. Do not guess.
- If a number is specific to one territory, say which.

ANSWER EXACTLY WHAT WAS ASKED
The shape of the answer follows the shape of the question. Decide what was
actually asked before writing a word.
- Asked for a number, a name, a date or a count: lead with that value. One
  sentence is a complete answer. Do not pad it with related figures nobody
  asked for.
- Asked "how many": give the number. Do not then list the items unless the
  question also asked which ones.
- Asked for a list ("which HCPs...", "show me...", "list..."): give EVERY item
  in the context that meets the condition, not a sample. Do not stop at five,
  do not say "and others" - if the context has fourteen matches, name fourteen.
  Truncating a list the rep asked for is a wrong answer, not a shorter one.
- Asked how or why something works: explain the mechanism. Definitions and
  reasoning are the answer here, not figures.
- Asked to compare: address every item named in the question, even if the
  answer for one of them is "no data in the context".

Never answer a narrower question than the one asked, and never a wider one.

COMPLETENESS
- If the context answers only part of the question, answer that part and say
  plainly which part is missing.
- If the context looks truncated mid-list, say the list may be incomplete
  rather than presenting it as the whole.

HOW TO WRITE
Talk like a colleague answering across a desk, not like a database printout.
- Write in prose for explanations and short answers.
- Use a list ONLY when the question asked for a list - then one line per item,
  each carrying the one or two figures that justify it.
    Good: "Jurate Kunickaite - prescriptions up 350% to 900 this quarter, last
           spoken to on Aug 8."
    Bad:  "**Jurate Kunickaite**
           - Specialty: Family Medicine
           - Rx Q1: 900.0
           - City: San Francisco"
- Never dump every field of a record. Quote only the figures bearing on the
  question: asked who is growing fastest, the growth number matters and the
  address does not.
- No preamble. Do not restate the question or open with "Based on the context".
- Length is whatever the question needs - one line for one fact, a full list
  for a list. Do not stretch a short answer, and do not compress a long one."""


# ── Greetings ────────────────────────────────────────────────────────────────

_GREETINGS_FILE = Path(_ASSISTANT_DIR) / "kb" / "kb_greetings.json"
_greetings: List[dict] = []
_greetings_loaded = False


def _load_greetings() -> List[dict]:
    """kb_greetings.json — curated openers keyed by trigger word.

    Deliberately NOT embedded. "hi" is two characters with no semantic content;
    vector search would match it against whatever chunk happens to be nearest and
    answer a greeting with prescription figures. An exact trigger lookup is both
    correct and free — no embedding, no LLM call.
    """
    global _greetings, _greetings_loaded
    if _greetings_loaded:
        return _greetings
    _greetings_loaded = True
    try:
        import json   # noqa: PLC0415

        data = json.loads(_GREETINGS_FILE.read_text(encoding="utf-8"))
        _greetings = data if isinstance(data, list) else []
        log.info("Loaded %d greeting rule(s) from %s", len(_greetings), _GREETINGS_FILE.name)
    except FileNotFoundError:
        log.info("No kb_greetings.json — greetings will be answered by the model.")
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read kb_greetings.json (%s).", exc)
    return _greetings


def _match_greeting(question: str) -> Optional[str]:
    """A curated reply when the whole message is a greeting, else None.

    Matches only when the message IS the trigger — not merely contains it — so
    "hi, how many HIGH priority HCPs do I have?" still reaches retrieval instead
    of being answered with a wave.
    """
    rules = _load_greetings()
    if not rules:
        return None
    normalised = re.sub(r"[^a-z0-9' ]", "", question.lower()).strip()
    if not normalised or len(normalised.split()) > 4:
        return None

    for rule in sorted(rules, key=lambda r: r.get("priority", 99)):
        triggers = [str(t).lower().strip() for t in (rule.get("triggers") or [])]
        if normalised not in triggers:
            continue
        responses = [r for r in (rule.get("responses") or []) if r]
        if not responses:
            return None
        # No signed-in user on this endpoint. Drop the placeholder together with
        # any comma introducing it — substituting a word gives "Bye there!",
        # which reads worse than simply "Bye!".
        reply = re.sub(r",?\s*\{user_name\}", "", random.choice(responses)).strip()

        # The file's own example prompts belong to a different application
        # (file loads, feed status). Offer RepStream ones instead.
        if rule.get("show_examples"):
            reply += ("\n\nYou can ask me things like:\n"
                      "  - How many HIGH priority HCPs do I have?\n"
                      "  - Who should I call first this week?\n"
                      "  - Which objection comes up most often?\n"
                      "  - Are there any critical alerts right now?")
        return reply
    return None


# ── Models and store ─────────────────────────────────────────────────────────

def _answer_model() -> str:
    """Which model writes the answer.

    Defaults to the application-wide LLM_MODEL so nothing changes unless
    ASSISTANT_LLM_MODEL is set. Overriding it lets chat answers use a different
    model from the warm-up, which makes hundreds of calls where chat makes one.
    """
    import os   # noqa: PLC0415

    return os.getenv("ASSISTANT_LLM_MODEL", "").strip() or settings.LLM_MODEL


def _store():
    if _ASSISTANT_DIR not in sys.path:
        sys.path.insert(0, _ASSISTANT_DIR)
    from db_qa.vector_store import get_vector_store   # noqa: PLC0415

    return get_vector_store()


def _embed_model_name() -> str:
    """Active embedding model, for the answer-cache key.

    Part of the key because it decides which chunks are retrieved: the same
    question answered under MiniLM and under bge is two different answers, and
    they must not share an entry.
    """
    if _ASSISTANT_DIR not in sys.path:
        sys.path.insert(0, _ASSISTANT_DIR)
    try:
        from db_qa.embedder import get_embedder   # noqa: PLC0415

        e = get_embedder()
        return f"{e.backend}:{e.model}"
    except Exception:  # noqa: BLE001
        return "unknown"


def _result(answer: str, hits: Optional[List[dict]] = None, *, started: float,
            answer_type: str, matched_template: str,
            source: str = "vector_store_llm") -> Dict[str, Any]:
    """Assemble the fields the response envelope reports under processing_details."""
    hits = hits or []
    return {
        "answer": answer,
        "sources": [
            {
                "source": h.get("source"),
                "title": (h.get("title") or "")[:120],
                "score": round(float(h.get("score") or 0), 4),
            }
            for h in hits
        ],
        "chunks_used": len(hits),
        "response_time_ms": int((time.time() - started) * 1000),
        "model_name": _answer_model() if answer_type == "ai_generated" else source,
        "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "answer_type": answer_type,
        # Always empty: this assistant answers from retrieved text and never
        # generates or runs SQL. The key exists so the envelope matches.
        "sql": "",
        "source": source,
        # Confidence is the best retrieval similarity, 0-1 — the honest signal
        # available here: how close the nearest chunk was to the question.
        "confidence": round(float(hits[0].get("score") or 0), 4) if hits else 0,
        "matched_template": matched_template,
    }


def chat(question: str, top_k: int = 6, min_score: float = 0.15, *,
         session_id: str = "", device_id: str = "") -> Dict[str, Any]:
    """Answer `question` from the embedded knowledge base.

    `session_id` turns on conversation memory: prior turns are shown to the model
    and the question is resolved against them before retrieval. Omitting it keeps
    the old stateless behaviour exactly, so every other caller is unaffected.
    """
    started = time.time()
    question = (question or "").strip()
    if not question:
        return _result("Please ask a question.", started=started,
                       answer_type="validation", matched_template="Empty Query",
                       source="none")

    greeting = _match_greeting(question)
    if greeting:
        # Not recorded: a greeting is not part of the conversation being had, and
        # keeping it would push a real turn out of the window.
        return _result(greeting, started=started, answer_type="greeting",
                       matched_template="Greeting", source="kb_greetings")

    history = memory.history_for_llm(session_id) if session_id else []

    # ORDER MATTERS: resolve the question against the conversation FIRST, then
    # look it up. The conversation is not part of the cache key any more, so the
    # resolved question has to be what both the lookup and the retrieval see -
    # otherwise "what about Pittsburgh?" would be cached under those four words
    # and served to a different thread that meant something else by them.
    #
    # A question asked with no history skips the rewrite entirely, so the common
    # case still costs nothing extra.
    search_query = memory.rewrite_followup(question, history) if history else question

    cache_key = response_cache.make_key(
        search_query, _answer_model(), _embed_model_name())
    cached = response_cache.get(cache_key)
    if cached is not None:
        log.info("Assistant answer cache HIT (%s)", search_query[:60])
        # Timing is recomputed rather than replayed: reporting the original
        # 25 000 ms on an instant reply would make the cache look broken.
        cached["response_time_ms"] = int((time.time() - started) * 1000)
        # The turn is still recorded, so the conversation reads correctly even
        # when a reply came from cache.
        if session_id and cached.get("answer"):
            memory.record_turn(session_id, question, cached["answer"], device_id)
        return cached

    # Logged per question, not once at startup: the retrieval model and the
    # answering model are configured independently, and when an answer looks
    # wrong the first thing worth knowing is which pair produced it.
    try:
        from app.utils.model_banner import embedding_line, llm_line   # noqa: PLC0415

        log.info("Chat: embedding=%s | llm=%s", embedding_line(), llm_line())
    except Exception:  # noqa: BLE001
        pass

    try:
        hits: List[dict] = _store().search(search_query, top_k=top_k, min_score=min_score)
    except Exception as exc:  # noqa: BLE001
        # Name the store that actually failed rather than assuming Postgres: which
        # backend is in use depends on VECTOR_STORE, and telling someone running
        # the file-based store to "check that PostgreSQL is running" sends them
        # after a service this deployment does not even have.
        try:
            from db_qa.vector_store import store_label   # noqa: PLC0415

            where = store_label()
        except Exception:  # noqa: BLE001
            where = "the configured vector store"
        log.warning("vector search failed against %s (%s)", where, exc)
        return _result(
            f"The knowledge base is unavailable - {where} could not be reached.",
            started=started, answer_type="error",
            matched_template="Vector Store Unavailable", source="none")

    if not hits:
        return _result(
            "I don't have anything on that. The knowledge base holds HCP "
            "priorities, prescriptions, calls, new writers, objections and alerts "
            "from the last warm-up.",
            started=started, answer_type="no_match",
            matched_template="No Match", source="vector_store")

    context = "\n\n".join(
        f"[{h.get('source')}] {h.get('title') or ''}\n{h.get('content') or ''}"
        for h in hits
    )

    try:
        from app.utils.llm_client import make_llm_client   # noqa: PLC0415

        resp = make_llm_client().chat.completions.create(
            model=_answer_model(),
            messages=[
                {"role": "system", "content": _SYSTEM},
                # The conversation is deliberately NOT replayed here. It reaches
                # this call already folded into search_query by the rewrite, and
                # sending the raw turns as well caused two concrete problems:
                #
                #   1. phi4-mini copied its own previous answer instead of
                #      reading the fresh CONTEXT - asked about Pittsburgh right
                #      after San Francisco, it repeated San Francisco's numbers.
                #   2. The answer then depended on the conversation, so the
                #      conversation had to be in the cache key, so a repeated
                #      question could never hit the cache.
                #
                # Resolving the question up front and generating from it alone
                # fixes both: one input, one answer, reproducible and cacheable.
                {"role": "user", "content":
                    f"=== CONTEXT ===\n{context}\n\n=== QUESTION ===\n{search_query}"},
            ],
            temperature=0.2,
        )
        answer = (resp.choices[0].message.content or "").strip()
        usage = getattr(resp, "usage", None)
    except Exception as exc:  # noqa: BLE001
        log.warning("Assistant chat LLM call failed via %s/%s: %s",
                    settings.LLM_PROVIDER, settings.LLM_MODEL, exc)
        return _result(
            "The language model could not be reached, so I cannot summarise an "
            "answer right now.",
            hits, started=started, answer_type="error",
            matched_template="LLM Unavailable")

    result = _result(answer or "The model returned an empty response. Please rephrase.",
                     hits, started=started, answer_type="ai_generated",
                     matched_template="Knowledge Base")

    # Recorded only for a real answer. Errors, no-match replies and greetings are
    # not part of the conversation and would evict genuine turns from the window.
    if session_id and answer:
        memory.record_turn(session_id, question, answer, device_id)

    # The LangChain-backed shim does not always surface usage; report what it has
    # rather than inventing counts.
    if usage is not None:
        result["token_usage"] = {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }

    # Stored only when the model actually answered. An empty generation, an
    # error, or a no-match reply must not be cached - the point of retrying is
    # that the next attempt might work, and a cached failure removes that.
    if answer:
        # The resolved question is stored alongside the hash so a bad cached
        # answer can be found and understood in the table. The key alone is a
        # sha256 and tells nobody what was asked.
        response_cache.put(cache_key, result, question=search_query)

    return result
