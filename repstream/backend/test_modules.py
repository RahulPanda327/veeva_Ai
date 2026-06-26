"""
Quick smoke-test: call Active Alerts and HCP Awareness endpoints,
then verify every key the UI panel expects is present in the response.

Run from repstream/backend/:
    python test_modules.py

Requires the FastAPI server to be running:
    uvicorn app.main:app --reload
"""
import json
import sys
import urllib.request

BASE = "http://localhost:8000/api/v1/action-center"


def get(path: str) -> dict:
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  ERROR calling {url}: {e}")
        sys.exit(1)


def check_keys(obj: dict, required: list[str], label: str):
    missing = [k for k in required if k not in obj]
    if missing:
        print(f"  [FAIL] {label} missing keys: {missing}")
    else:
        print(f"  [PASS] {label} — all {len(required)} keys present")


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== ACTIVE ALERTS ===")
data = get("/alerts")

# Top-level response
check_keys(data, ["summary", "alerts", "total"], "AlertListResponse (root)")

# Summary KPI tiles (what the UI shows in the 4 pill tiles)
if "summary" in data:
    check_keys(
        data["summary"],
        [
            "territory_id", "period",
            "ai_critical_count",          # KPI tile: CRITICAL
            "ai_high_priority_count",     # KPI tile: HIGH
            "ai_medium_priority_count",   # KPI tile: MEDIUM
            "ai_hcp_drift_detected_count",# KPI tile: HCP Drift
            "ai_early_detection_weeks",   # "2.8 weeks earlier" banner
            "ai_new_unread_count",        # yellow banner badge
        ],
        "summary (KPI tiles)",
    )

# First alert card fields
if data.get("alerts"):
    a = data["alerts"][0]
    check_keys(
        a,
        [
            "alert_id", "alert_type",
            "title", "description", "detected_at",
            "ai_severity",              # CRITICAL / HIGH / MEDIUM
            "ai_detection_method",      # ANOMALY_DETECTION / AUTO_DETECTED
            "ai_affected_hcp_count",    # "47 HCPs affected"
            "ai_territory_reach",       # "3/12" territories
            "ai_rx_risk",               # High / Medium / Low
            "ai_icd10_codes_affected",  # ICD-10 section in card
            "ai_counter_script",        # counter-script text
            "recommended_actions",      # action buttons
            "analysis_badges",          # badges not in AlertItem yet — skip if missing
        ],
        "alerts[0] (card fields)",
    )
    print(f"\n  Sample alert:")
    print(f"    id       : {a.get('alert_id')}")
    print(f"    type     : {a.get('alert_type')}")
    print(f"    severity : {a.get('ai_severity')}")
    print(f"    title    : {a.get('title')}")
    print(f"    HCPs     : {a.get('ai_affected_hcp_count')}")
    print(f"    reach    : {a.get('ai_territory_reach')}")
    print(f"    ICD-10   : {a.get('ai_icd10_codes_affected', [])[:2]}")
    print(f"    counter  : {str(a.get('ai_counter_script',''))[:80]}...")

print(f"\n  KPI tiles:")
s = data.get("summary", {})
print(f"    Critical alerts : {s.get('ai_critical_count')}")
print(f"    High alerts     : {s.get('ai_high_priority_count')}")
print(f"    Medium alerts   : {s.get('ai_medium_priority_count')}")
print(f"    HCP drift count : {s.get('ai_hcp_drift_detected_count')}")
print(f"    Total alerts    : {data.get('total')}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== HCP AWARENESS ===")
data = get("/hcp-awareness")

# Top-level response (bar chart data + KPI tiles)
check_keys(
    data,
    [
        "items", "total",
        "awareness_trend",           # bar chart data (4 bars)
        "ai_predicted_trend",        # predicted future bars
        "ai_high_awareness_count",   # KPI tile
        "ai_medium_awareness_count", # KPI tile
        "ai_low_awareness_count",    # KPI tile
        "ai_declining_count",        # KPI tile: declining HCPs
        "ai_at_risk_count",          # KPI tile: at-risk HCPs
    ],
    "HCPAwarenessResponse (root + bar chart)",
)

# Bar chart trend points
if data.get("awareness_trend"):
    t = data["awareness_trend"][0]
    check_keys(t, ["period", "avg_score"], "awareness_trend[0]")
    print(f"\n  Bar chart (avg scores):")
    for pt in data["awareness_trend"]:
        bar = int(pt["avg_score"] / 5) * "█"
        print(f"    {pt['period']:6s} : {pt['avg_score']:5.1f}%  {bar}")
    if data.get("ai_predicted_trend"):
        print(f"  Predicted:")
        for pt in data["ai_predicted_trend"]:
            print(f"    {pt['period']:6s} : {pt['avg_score']:5.1f}%  (predicted)")

# First HCP card fields
if data.get("items"):
    h = data["items"][0]
    check_keys(
        h,
        [
            "hcp_id", "hcp_full_name",
            "specialty",
            "institution",              # "Valley Medical Center"
            "city_state",
            "ai_trend_scores",          # individual sparkline
            "ai_awareness_score",       # "62%" number on card
            "ai_awareness_level",       # High / Medium / Low badge
            "ai_score_change_pct",      # "↓ 18%"
            "ai_trend_direction",       # Declining / Stable / Improving
            "ai_trend_slope",           # LinReg slope
            "ai_predicted_next_score",  # predicted May 20
            "ai_predicted_4w_score",    # predicted 4 weeks
            "ai_risk_score",            # 0-100 composite
            "ai_risk_level",            # Critical / High / Medium / Low
            "ai_re_engagement_priority",# HIGH / MEDIUM / LOW
            "ai_root_cause_signal",     # raw DB text
            "ai_nlp_root_cause_category", # COMPETITOR_THREAT etc.
            "ai_nlp_sentiment",
            "ai_nlp_keywords",
            "ai_icd10_prescribing_patterns",  # ICD-10 section
            "ai_aim_xr_activity",       # AIM XR Activity text
            "ai_recommended_action",    # rep action
            "analysis_badges",          # NLP_ANALYSIS, AI_SCORING etc.
        ],
        "items[0] (HCP card fields)",
    )

    print(f"\n  Top 2 HCPs by risk:")
    for h in data["items"][:2]:
        icd = [f"{p['code']} ({p['pct']}%)" for p in h.get("ai_icd10_prescribing_patterns", [])[:2]]
        print(f"\n    {h.get('hcp_full_name')} — {h.get('institution')}")
        print(f"      Specialty  : {h.get('specialty')} | {h.get('city_state')}")
        print(f"      Score      : {h.get('ai_awareness_score')}% ({h.get('ai_awareness_level')}) | {h.get('ai_score_change_pct'):+.1f}% | {h.get('ai_trend_direction')}")
        print(f"      Risk       : {h.get('ai_risk_score')}/100 ({h.get('ai_risk_level')}) | Re-engage: {h.get('ai_re_engagement_priority')}")
        print(f"      NLP        : {h.get('ai_nlp_root_cause_category')} | {h.get('ai_nlp_sentiment')}")
        print(f"      ICD-10     : {', '.join(icd)}")
        print(f"      AIM XR     : {str(h.get('ai_aim_xr_activity',''))[:80]}...")
        print(f"      Action     : {str(h.get('ai_recommended_action',''))[:80]}...")
        print(f"      Badges     : {h.get('analysis_badges')}")

print(f"\n  KPI tiles:")
print(f"    High awareness  : {data.get('ai_high_awareness_count')} HCPs")
print(f"    Medium          : {data.get('ai_medium_awareness_count')} HCPs")
print(f"    Low             : {data.get('ai_low_awareness_count')} HCPs")
print(f"    Declining       : {data.get('ai_declining_count')} HCPs")
print(f"    At risk (>60)   : {data.get('ai_at_risk_count')} HCPs")
print(f"    Total           : {data.get('total')} HCPs")

print("\n=== DONE ===\n")
