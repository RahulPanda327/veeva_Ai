"""
Test script — verifies Case 1 (KB rule-based matching) is working correctly.

Tests the LocalKBMatcher directly, no server or database required.
Shows confidence score, which layer would fire, and the SQL that would run.

Run from the Datastream-Chatbot folder:
    python -m scripts.test_kb_matching
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db_qa.local_kb_matcher import get_local_kb   # noqa: E402

# ── Thresholds (must match scenario_2_llm_rules.py) ──────────────────────────
HIGH_CONF       = 0.90   # Layer 2 / Layer 3 -> run KB SQL directly
SQL_FALLBACK    = 0.55   # Layer 8b          -> run KB SQL at lower confidence
GREETING_CONF   = 0.75   # Layer 2           -> greeting response

# ── Test questions ────────────────────────────────────────────────────────────
TEST_QUERIES = [
    # --- exact KB questions (should hit Layer 2 at very high confidence) ---
    "Which files are scheduled to load today?",
    "Which files failed today?",
    "Is there any missed file today?",
    "Which files loaded yesterday?",
    "Any QC triggered in the last 3 days?",

    # --- paraphrased (should still hit Layer 2 or 3) ---
    "Show me today's file schedule",
    "What files are failing right now?",
    "Files that didn't load today",
    "Yesterday's loaded files",

    # --- greetings (should return greeting, not SQL) ---
    "Hello",
    "Hi there",
    "Good morning",

    # --- out of context (should fall through to Layer 8c / pgvector) ---
    "Total record count by feed for last 30 days",
    "What is the weather today?",
]

# ─────────────────────────────────────────────────────────────────────────────

def layer_label(result) -> str:
    if result.is_greeting():
        return "GREETING"
    score = result.confidence
    if score >= HIGH_CONF:
        return "LAYER 2/3  -> KB SQL (high confidence)"
    if score >= SQL_FALLBACK and result.is_sql():
        return "LAYER 8b   -> KB SQL (low confidence fallback)"
    return "LAYER 8c+  -> pgvector / LLM fallback"


def run_tests():
    print("Loading LocalKBMatcher (embedding model loads once) …\n")
    kb = get_local_kb()

    W = 70
    print("=" * W)
    print(f"{'QUERY':<45} {'SCORE':>6}  LAYER")
    print("=" * W)

    for query in TEST_QUERIES:
        result = kb.match(query, user_name="Tester")
        score  = result.confidence
        label  = layer_label(result)

        print(f"{query[:44]:<45} {score:>6.3f}  {label}")

        # Show extra detail for SQL hits
        if result.is_sql() and score >= SQL_FALLBACK:
            print(f"  +- query_var : {result.query_variable}")
            print(f"  +- title     : {result.title}")
            if result.sql:
                preview = result.sql[:80].replace("\n", " ")
                print(f"  +- sql       : {preview}...")
            else:
                print(f"  +- sql       : (empty - not mapped in kb_sql_queries_updated.json)")

        # Show top-k detail for out-of-context queries
        if not result.is_greeting() and score < SQL_FALLBACK:
            top = kb.search_topk(query, k=3)
            print(f"  +- top-3 KB matches:")
            for r in top:
                print(f"       {r.confidence:.3f}  [{r.query_variable}] {r.title}")

        print()

    print("=" * W)
    print("Done.")


if __name__ == "__main__":
    run_tests()
