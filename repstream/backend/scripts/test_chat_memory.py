"""Manual test for conversation memory — a scripted multi-turn chat.

    python scripts/test_chat_memory.py                  # in-process, no server
    python scripts/test_chat_memory.py --url http://localhost:8004

WHAT IT CHECKS
    1. The session id is carried across turns (memory is keyed on it).
    2. A follow-up with no subject of its own ("what about Pittsburgh?") is
       rewritten into a standalone question before retrieval.
    3. The answer to that follow-up differs from the previous answer - which is
       the failure this whole exercise is really about: a model that repeats its
       last reply looks like it remembered, and is wrong.

WHY IT DISABLES THE RATE LIMIT
    ASSISTANT_RATE_LIMIT_QUESTIONS defaults to 2 in this .env. A three-turn
    conversation trips it on turn 3 and the test reports a limit message instead
    of an answer, which reads like a memory failure. Set before app import,
    because settings are read once at import time.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TURNS = [
    "which HCPs are high priority in San Francisco CA?",
    "what about Pittsburgh?",
    "how many HCPs are there in total?",
]


def _safe(text: str) -> str:
    """Windows consoles are cp1252; answers contain em dashes and emoji."""
    return (text or "").encode("ascii", "replace").decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="", help="Base URL of a running server. "
                                              "Omitted = run the app in-process.")
    ap.add_argument("--keep-rate-limit", action="store_true",
                    help="Do NOT disable the question limit for this run.")
    ap.add_argument("--session", default="", help="Reuse an existing session id.")
    args = ap.parse_args()

    if not args.keep_rate_limit:
        os.environ["ASSISTANT_RATE_LIMIT_ENABLED"] = "false"

    if args.url:
        import httpx

        client = httpx.Client(base_url=args.url.rstrip("/"), timeout=300)
        post = lambda body: client.post("/api/v1/assistant/ai_assistant_chat", json=body)  # noqa: E731
    else:
        from fastapi.testclient import TestClient   # noqa: PLC0415
        from main import app                        # noqa: PLC0415

        tc = TestClient(app)
        post = lambda body: tc.post("/api/v1/assistant/ai_assistant_chat", json=body)  # noqa: E731

    session_id = args.session or None
    answers = []

    for n, question in enumerate(TURNS, 1):
        body = {"request": {
            "tenant_id": "test", "project_id": "test",
            # THE point of the test: hand back the id the last response gave us.
            # Sending null here starts a new session and there is no memory.
            "app_session_id": session_id,
            "user_query": question,
        }}
        resp = post(body)
        if resp.status_code != 200:
            print(f"turn {n}: HTTP {resp.status_code} — {resp.text[:200]}")
            return 1
        data = resp.json()["response"]
        session_id = data["chat_session_id"]
        answer = data["output_query"]["answer"]
        answers.append(answer)

        print(f"--- turn {n} " + "-" * 52)
        print(f"session : {session_id}")
        print(f"type    : {data['processing_details']['answer_type']}")
        print(f"Q       : {question}")
        print(f"A       : {_safe(answer)[:400]}")
        print()

    print("=" * 64)
    ok = True
    if len(set(answers)) < len(answers):
        # Not proof of a bug on its own - two questions can share an answer - but
        # for THESE three turns it means the model replayed a previous reply
        # instead of reading the freshly retrieved context.
        print("FAIL  two turns returned an identical answer — history is being")
        print("      copied instead of the retrieved context being read.")
        ok = False
    else:
        print("OK    every turn produced a distinct answer.")

    try:
        from app.services.assistant import memory   # noqa: PLC0415

        print(f"stored: {memory.stats()}")
        turns = memory.history_for_llm(session_id)
        print(f"OK    {len(turns)} message(s) held for this session.")
        if not turns:
            print("FAIL  nothing stored — is ASSISTANT_MEMORY_ENABLED=true?")
            ok = False
    except Exception as exc:  # noqa: BLE001
        print(f"could not read memory stats: {exc}")

    print("=" * 64)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
