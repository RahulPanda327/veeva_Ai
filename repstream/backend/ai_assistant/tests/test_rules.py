"""Quick isolated test for rule matching — no server/app needed.

Run from project root:
    python -m tests.test_rules
or:
    python tests/test_rules.py
"""
import sys, os
# Add project root (one level up from tests/) so `models.*` resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch get_config to not need .env
from unittest.mock import MagicMock, patch

mock_cfg = MagicMock()
mock_cfg.rule_confidence_threshold = 0.80
mock_cfg.rule_max_matches = 3

with patch("config.settings.get_config", return_value=mock_cfg):
    from models.rule_based_model import RuleBasedModel
    r = RuleBasedModel()

print(f"Rules loaded: {len(r.rules)}\n")

tests = [
    ("give me weather update",        "out_of_scope"),
    ("what is the weather today",      "out_of_scope"),
    ("list your knowledge base",       "capabilities"),
    ("what can you do",                "capabilities"),
    ("what can you help me with",      "capabilities"),
    ("what topics do you know",        "capabilities"),
    ("hello",                          "greeting"),
    ("hi there",                       "greeting"),
    ("what is the pricing",            "pricing_inquiry"),
    ("how does it work",               "scenario_info"),
    ("which files failed yesterday",   None),   # no rule → embeddings/fallback
    ("show me the schedule",           None),   # no rule → embeddings/fallback
    ("reset my password",              "password_reset"),
    ("rate limit exceeded",            "api_rate_limits"),
]

all_ok = True
for query, expected in tests:
    m = r.get_best_match(query)
    actual = m.rule.intent if m else None
    ok = (actual == expected) if expected is not None else (actual is None)
    if not ok:
        all_ok = False
    sym = "PASS" if ok else "FAIL"
    exp_str = repr(expected).ljust(22)
    print(f"  [{sym}]  {query!r:45s}  expected={exp_str}  got={actual!r}")

print()
print("=" * 60)
print("  ALL PASSED" if all_ok else "  SOME FAILED")
print("=" * 60)
sys.exit(0 if all_ok else 1)
