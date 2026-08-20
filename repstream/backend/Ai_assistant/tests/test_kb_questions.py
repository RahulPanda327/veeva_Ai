"""
KB question regression test — verifies every canonical sample question from the
knowledge-base doc routes to the correct SQL template AND extracts the right
parameters (feed name, day count, etc.).

Source: kb_chatbot_questions_updated.json / kb_sql_queries_updated.json
        (the doc shipped by the data team)

Run from project root:
    python -m tests.test_kb_questions
or:
    python tests/test_kb_questions.py
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

# Add project root so `db_qa.*` resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub config so we don't need .env loaded
mock_cfg = MagicMock()
mock_cfg.rule_confidence_threshold = 0.80
mock_cfg.rule_max_matches = 3

# ────────────────────────────────────────────────────────────────────────────────
# Each tuple: (query_id, natural-language question, expected template id, expected params)
# `expected_params` only checks the keys present — extras on the match are OK.
# ────────────────────────────────────────────────────────────────────────────────
CASES: list[tuple[str, str, str, dict]] = [
    ("QUERY_001", "Which files are scheduled to load today?",
        "scheduled_today", {}),
    ("QUERY_002", "Which files are scheduled to load tomorrow?",
        "scheduled_tomorrow", {}),
    ("QUERY_003", "Is there any missed file today?",
        "missed_today", {}),
    ("QUERY_004", "What is the status of today's copay file load?",
        "file_status_named_today", {"name": "copay"}),
    ("QUERY_005", "When did the co-pilot file load today?",
        "file_status_named_today", {"name": "co-pilot"}),
    ("QUERY_006", "Which files loaded yesterday?",
        "loaded_yesterday", {}),
    ("QUERY_007", "Which files loaded in the last 24 hours?",
        "loaded_last_24h", {}),
    ("QUERY_008", "What is the DDS count of Walgreens file loaded today?",
        "dds_count_named_today", {"name": "Walgreens"}),
    ("QUERY_009", "Any QC triggered in the last 3 days?",
        "qc_triggered_last_n", {"days": "3"}),
    ("QUERY_010", "Which files failed today?",
        "failed_today", {}),
    ("QUERY_011", "Which files are delayed today?",
        "delayed_today", {}),
    ("QUERY_012", "Search feeds related to copay",
        "feed_search_named", {"name": "copay"}),
    ("QUERY_013", "Show details for Walgreens feed",
        "feed_search_named", {"name": "Walgreens"}),
    ("QUERY_014", "Which table loads Integrichain data?",
        "table_for_named", {"name": "Integrichain"}),
    ("QUERY_015", "Show last 7 days load history for copay",
        "history_last_n_named", {"days": "7", "name": "copay"}),
    ("QUERY_016", "Which subject areas currently have active feeds?",
        "active_subject_areas", {}),
    ("QUERY_017", "For subject area accredo, list all active feeds with their short name, file name, staging and dds table, and load order.",
        "active_feeds_for_subject", {"name": "accredo"}),
    ("QUERY_018", "What is the latest successful load for each feed in subject_area 'accredo' with file_id, processed_date, stg_record_count, and archive_loc?",
        "latest_success_for_subject", {"name": "accredo"}),
    ("QUERY_019", "Which tables failed QC in the most recent run, and what was the failure reason?",
        "qc_failed_recent", {}),
]


def _check_subset(actual: dict, expected: dict) -> tuple[bool, str]:
    """Return (ok, reason) for whether expected ⊆ actual (case-sensitive on values)."""
    for k, v in expected.items():
        if k not in actual:
            return False, f"missing key {k!r}"
        if actual[k] != v:
            return False, f"{k}={actual[k]!r}, expected {v!r}"
    return True, ""


def main() -> int:
    with patch("config.settings.get_config", return_value=mock_cfg):
        from db_qa.sql_query_router import SQLQueryRouter
        router = SQLQueryRouter()

    print(f"Templates loaded: {len(router.templates)}\n")

    ok_count = 0
    failures: list[str] = []

    for qid, question, exp_id, exp_params in CASES:
        m = router.match(question)
        got_id = m.template_id if m else None
        got_params = m.params if m else {}

        id_ok = (got_id == exp_id)
        params_ok, why = _check_subset(got_params, exp_params)
        ok = id_ok and params_ok
        if ok:
            ok_count += 1
        else:
            reason = []
            if not id_ok:
                reason.append(f"template {got_id!r} != {exp_id!r}")
            if not params_ok:
                reason.append(f"params: {why}")
            failures.append(f"{qid}: {' & '.join(reason)}")

        sym = "PASS" if ok else "FAIL"
        params_str = repr(got_params) if got_params else "{}"
        print(f"  [{sym}]  {qid}  -> {got_id!s:30s}  params={params_str}")

    print()
    print("=" * 64)
    print(f"  {ok_count}/{len(CASES)} passed")
    if failures:
        print()
        print("  Failures:")
        for f in failures:
            print(f"    • {f}")
    print("=" * 64)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
