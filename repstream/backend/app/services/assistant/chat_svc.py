"""Chat over the RepStream data embedded in the chatbot's pgvector store.

The pipeline this reads from:

    warm-up  ->  cache/endpoint_response_cache.json
             ->  scripts/export_live_to_kb.py   (renders it as sentences)
             ->  ai_assistant/kb/repstream_live_data.txt
             ->  scripts.ingest_to_pgvector     (embeds it)
             ->  pgvector

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

ACCURACY
- Quote figures exactly as they appear. Never estimate or invent a number.
- If the context does not answer the question, say so and say what you would
  need. Do not guess.
- If a number is specific to one territory, say which.

HOW TO WRITE
Talk like a colleague answering across a desk, not like a database printout.
- Open with the direct answer in one sentence, then support it.
- Write in prose. Do NOT reproduce every field of a record as a bulleted list of
  "Field: value" lines - that is the single most common mistake here.
- Quote only the figures that bear on the question. If asked who is growing
  fastest, the growth number matters and the address does not.
- Naming several HCPs: one short sentence each, weaving in the one or two numbers
  that justify including them.
    Good: "Jurate Kunickaite is the standout - prescriptions are up 350% to 900
           this quarter, and you last spoke on Aug 8."
    Bad:  "**Jurate Kunickaite**
           - Specialty: Family Medicine
           - Rx Q1: 900.0"
- Cap it at about five names. If there are more, finish with how many remain
  rather than listing them all.
- Two or three short paragraphs at most. A rep is reading this between calls."""


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
    from db_qa.pgvector_store import get_pgvector_store   # noqa: PLC0415

    return get_pgvector_store()


def _result(answer: str, hits: Optional[List[dict]] = None, *, started: float,
            answer_type: str, matched_template: str,
            source: str = "pgvector_llm") -> Dict[str, Any]:
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


def chat(question: str, top_k: int = 6, min_score: float = 0.15) -> Dict[str, Any]:
    """Answer `question` from the embedded knowledge base."""
    started = time.time()
    question = (question or "").strip()
    if not question:
        return _result("Please ask a question.", started=started,
                       answer_type="validation", matched_template="Empty Query",
                       source="none")

    greeting = _match_greeting(question)
    if greeting:
        return _result(greeting, started=started, answer_type="greeting",
                       matched_template="Greeting", source="kb_greetings")

    try:
        hits: List[dict] = _store().search(question, top_k=top_k, min_score=min_score)
    except Exception as exc:  # noqa: BLE001
        log.warning("pgvector search failed (%s)", exc)
        return _result(
            "The knowledge base is unavailable - its vector database could not be "
            "reached. Check that PostgreSQL is running.",
            started=started, answer_type="error",
            matched_template="Vector Store Unavailable", source="none")

    if not hits:
        return _result(
            "I don't have anything on that. The knowledge base holds HCP "
            "priorities, prescriptions, calls, new writers, objections and alerts "
            "from the last warm-up.",
            started=started, answer_type="no_match",
            matched_template="No Match", source="pgvector")

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
                {"role": "user", "content":
                    f"=== CONTEXT ===\n{context}\n\n=== QUESTION ===\n{question}"},
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

    # The LangChain-backed shim does not always surface usage; report what it has
    # rather than inventing counts.
    if usage is not None:
        result["token_usage"] = {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }
    return result
