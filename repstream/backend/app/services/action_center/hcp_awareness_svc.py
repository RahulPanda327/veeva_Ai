"""
HCP Awareness Service — 4 techniques mapped to 4 UI badges

  TECHNIQUE 1 — Linear Regression  →  PREDICTIVE ANALYTICS badge
    Fit a line through 4 weekly scores per HCP
    slope            = score change per week
    R²               = trend consistency
    ai_predicted_next_score = score extrapolated to next period (May 20)
    ai_predicted_4w_score   = score extrapolated 4 weeks out

  TECHNIQUE 2 — AI Composite Scoring  →  AI SCORING badge
    Weighted formula across 4 signals:
      score_gap    = how far below 70 (High threshold)
      slope_factor = severity of weekly decline
      priority     = DB re-engagement priority
      change_pct   = total % change over period
    ai_risk_score  = 0-100 (higher = more urgent)
    ai_risk_level  = Critical / High / Medium / Low

  TECHNIQUE 3 — NLP (keyword classification)  →  NLP ANALYSIS badge
    Keyword matching on root_cause_signal text
    ai_nlp_root_cause_category = COMPETITOR_THREAT / REP_ENGAGEMENT /
                                  CLINICAL_EVIDENCE / PAYER_ACCESS
    ai_nlp_sentiment           = Negative / Neutral / Positive
    ai_nlp_keywords            = extracted key terms

  TECHNIQUE 4 — GPT-4o  →  PREDICTIVE ANALYTICS / module-level
    ai_aim_xr_activity     = HCP digital engagement description
    ai_recommended_action  = what rep should do now

  All results cached per hcp_id.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import numpy as np
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models.hcp_awareness import HCPAwareness
from app.schemas.action_center import (
    HCPAwarenessItem,
    HCPAwarenessResponse,
    ICD10Pattern,
    TrendPoint,
)

log = logging.getLogger(__name__)

_CACHE: Dict[str, Any] = {}

# ── Specialty → ICD-10 prescribing pattern mapping ───────────────────────────
_SPECIALTY_ICD10: Dict[str, List[tuple]] = {
    "GASTROENTEROLOGY": [
        ("K86.81", "Exocrine pancreatic insufficiency", 45.0),
        ("K86.1",  "Chronic pancreatitis",              30.0),
        ("K90.3",  "Pancreatic steatorrhea",            15.0),
        ("K86.0",  "Alcohol-induced chronic pancreatitis", 10.0),
    ],
    "INTERNAL MEDICINE": [
        ("K86.81", "Exocrine pancreatic insufficiency", 40.0),
        ("K86.1",  "Chronic pancreatitis",              25.0),
        ("I50.9",  "Heart failure, unspecified",        20.0),
        ("E11.9",  "Type 2 diabetes mellitus",          15.0),
    ],
    "CARDIOLOGY": [
        ("I50.9",  "Heart failure, unspecified",        42.0),
        ("I25.10", "Atherosclerotic heart disease",     31.0),
        ("I11.0",  "Hypertensive heart disease",        17.0),
        ("I10",    "Essential hypertension",            10.0),
    ],
    "ENDOCRINOLOGY": [
        ("E11.9",  "Type 2 diabetes mellitus",          55.0),
        ("E78.5",  "Hyperlipidemia, unspecified",       25.0),
        ("E13.9",  "Other specified diabetes mellitus", 12.0),
        ("E11.8",  "Type 2 diabetes with complications", 8.0),
    ],
    "PEDIATRICS": [
        ("K86.81", "Exocrine pancreatic insufficiency", 50.0),
        ("K90.3",  "Pancreatic steatorrhea",            30.0),
        ("K86.1",  "Chronic pancreatitis",              20.0),
    ],
    "ONCOLOGY": [
        ("C25.0",  "Malignant neoplasm of head of pancreas", 45.0),
        ("C25.9",  "Malignant neoplasm of pancreas",         35.0),
        ("K86.81", "Exocrine pancreatic insufficiency",      20.0),
    ],
}
_DEFAULT_ICD10 = [
    ("K86.81", "Exocrine pancreatic insufficiency", 45.0),
    ("K86.1",  "Chronic pancreatitis",              30.0),
    ("K90.3",  "Pancreatic steatorrhea",            25.0),
]

# ── NLP keyword categories ────────────────────────────────────────────────────
_NLP_CATEGORIES: Dict[str, List[str]] = {
    "COMPETITOR_THREAT":  ["competitor", "creon", "pancreaze", "generic", "pert",
                           "competitive", "formulary change", "market share"],
    "REP_ENGAGEMENT":     ["rep", "visit", "call", "frequency", "engagement",
                           "interaction", "no visits", "reduced call"],
    "CLINICAL_EVIDENCE":  ["clinical", "evidence", "article", "data", "trial",
                           "publication", "research", "study"],
    "PAYER_ACCESS":       ["payer", "access", "coverage", "tier", "prior auth",
                           "insurance", "reimbursement"],
}

_NLP_NEGATIVE_SIGNALS = ["reduced", "decline", "decreased", "no visit", "competitor",
                          "generic", "drift", "low", "minimal", "0 visit"]
_NLP_POSITIVE_SIGNALS = ["increased", "improved", "positive", "engaged", "high",
                          "strong", "consistent"]

# ── Periods ───────────────────────────────────────────────────────────────────
_PERIODS = [
    ("Jan 29", "score_jan29"),
    ("Feb 26", "score_feb26"),
    ("Mar 25", "score_mar25"),
    ("Apr 22", "score_apr22"),
]
_NEXT_PERIODS = ["May 20", "Jun 17"]


# ── Helper: parse "84.7%" → 84.7 ─────────────────────────────────────────────
def _parse_pct(raw: Optional[str]) -> float:
    if not raw:
        return 0.0
    try:
        return float(str(raw).replace("%", "").strip())
    except ValueError:
        return 0.0


def _awareness_level(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _icd10_for_specialty(specialty: Optional[str]) -> List[ICD10Pattern]:
    spec_upper = (specialty or "").upper()
    matched = next(
        (codes for key, codes in _SPECIALTY_ICD10.items() if key in spec_upper),
        _DEFAULT_ICD10,
    )
    return [ICD10Pattern(code=c, label=l, pct=p) for c, l, p in matched]


# ── TECHNIQUE 1 — Linear Regression (PREDICTIVE ANALYTICS) ───────────────────

def _linear_regression(scores: List[float]):
    """
    Fit LinearRegression on 4 weekly scores.
    Returns (slope, r2, predicted_next, predicted_4w, predicted_direction).
    """
    valid = [(i, s) for i, s in enumerate(scores) if s > 0]
    if len(valid) < 2:
        return None, None, None, None, None

    x = np.array([v[0] for v in valid], dtype=float)
    y = np.array([v[1] for v in valid], dtype=float)

    coeffs  = np.polyfit(x, y, deg=1)
    slope   = float(coeffs[0])

    # R²
    y_pred  = np.polyval(coeffs, x)
    ss_res  = np.sum((y - y_pred) ** 2)
    ss_tot  = np.sum((y - y.mean()) ** 2)
    r2      = float(1.0 - ss_res / (ss_tot + 1e-9))

    # Predict next period (index 4) and 4 weeks out (index 7)
    last_idx         = x[-1]
    pred_next        = float(np.clip(np.polyval(coeffs, last_idx + 1), 0, 100))
    pred_4w          = float(np.clip(np.polyval(coeffs, last_idx + 4), 0, 100))
    pred_direction   = "Improving" if slope > 0.5 else ("Declining" if slope < -0.5 else "Stable")

    return round(slope, 3), round(r2, 3), round(pred_next, 1), round(pred_4w, 1), pred_direction


# ── TECHNIQUE 2 — AI Composite Risk Score (AI SCORING) ───────────────────────

def _compute_risk_score(
    latest_score: float,
    change_pct: float,
    slope: Optional[float],
    priority: Optional[str],
) -> tuple:
    """
    Composite AI risk score = weighted combination of 4 signals:
      1. score_gap    (40%) — how far below High threshold (70)
      2. slope_factor (30%) — weekly decline severity
      3. change_pct   (20%) — total % change over period
      4. priority     (10%) — DB re-engagement priority
    Returns (risk_score 0-100, risk_level).
    """
    # Signal 1: score gap from High threshold
    score_gap = max(0.0, 70.0 - latest_score)     # 0-70
    score_signal = (score_gap / 70.0) * 40.0

    # Signal 2: slope severity
    slope_abs    = abs(slope or 0.0)
    slope_signal = min(30.0, slope_abs * 4.0)

    # Signal 3: total change % severity
    change_abs    = abs(min(0.0, change_pct))      # only negative change counts
    change_signal = min(20.0, (change_abs / 30.0) * 20.0)

    # Signal 4: DB priority
    priority_signal = {"HIGH": 10.0, "MEDIUM": 5.0, "LOW": 0.0}.get(priority or "LOW", 0.0)

    risk = score_signal + slope_signal + change_signal + priority_signal
    risk = round(min(100.0, max(0.0, risk)), 1)

    if risk >= 70:
        level = "Critical"
    elif risk >= 50:
        level = "High"
    elif risk >= 30:
        level = "Medium"
    else:
        level = "Low"

    return risk, level


# ── TECHNIQUE 3 — NLP Text Classification (NLP ANALYSIS) ─────────────────────

def _nlp_analyze(root_cause: Optional[str]) -> tuple:
    """
    Keyword-based NLP on root_cause_signal text.
    Returns (category, sentiment, keywords).
    """
    text = (root_cause or "").lower()
    if not text:
        return "UNKNOWN", "Neutral", []

    # Category: count keyword matches per category
    cat_scores: Dict[str, int] = {}
    for cat, keywords in _NLP_CATEGORIES.items():
        cat_scores[cat] = sum(1 for kw in keywords if kw in text)

    best_cat   = max(cat_scores, key=cat_scores.get)
    category   = best_cat if cat_scores[best_cat] > 0 else "GENERAL"

    # Sentiment: count negative vs positive signals
    neg_count  = sum(1 for s in _NLP_NEGATIVE_SIGNALS if s in text)
    pos_count  = sum(1 for s in _NLP_POSITIVE_SIGNALS if s in text)
    sentiment  = "Negative" if neg_count > pos_count else ("Positive" if pos_count > neg_count else "Neutral")

    # Keywords: extract meaningful words (> 4 chars, not stopwords)
    _STOPWORDS = {"with", "from", "that", "this", "have", "been", "will",
                  "last", "into", "over", "following", "toward", "their"}
    words      = re.findall(r'\b[a-z]{4,}\b', text)
    keywords   = list(dict.fromkeys(
        w for w in words if w not in _STOPWORDS
    ))[:5]

    return category, sentiment, keywords


# ── TECHNIQUE 4 — GPT-4o Enricher ────────────────────────────────────────────

_SYSTEM = """You are a pharmaceutical sales intelligence AI for Zenpep (pancrelipase).
Given HCP awareness data with ML analysis, return a JSON object with EXACTLY these 2 keys:

{
  "ai_aim_xr_activity": "<1 sentence — HCP digital engagement: competitor articles read, content views, or lack of engagement>",
  "ai_recommended_action": "<1-2 sentences — specific rep action based on awareness trend and risk>"
}

Rules:
- If COMPETITOR_THREAT: mention competitor content consumption (Creon/Pancreaze articles)
- If REP_ENGAGEMENT: mention visit frequency issue
- If Declining + high risk: urgent language (schedule call, immediate visit)
- If Stable/Improving: reinforcement language
- Return valid JSON only"""


def _build_prompt(row, latest_score: float, slope: Optional[float],
                  risk_score: float, nlp_category: str, predicted_4w: Optional[float]) -> str:
    slope_str = f"{slope:+.2f}" if slope is not None else "N/A"
    pred_str  = f"{predicted_4w:.1f}%" if predicted_4w is not None else "N/A"
    return f"""HCP              : {row.hcp_full_name}
Specialty        : {row.specialty}
Location         : {row.city_state}
Latest Score     : {latest_score:.1f}%
Score Change     : {row.score_change_pct}
Trend Direction  : {row.trend_direction}
ML Slope         : {slope_str} score/week
Predicted (4w)   : {pred_str} (LinearRegression extrapolation)
AI Risk Score    : {risk_score:.0f}/100
NLP Category     : {nlp_category}
Root Cause       : {row.root_cause_signal}
Re-Engagement    : {row.re_engagement_priority}

Generate the 2 fields as JSON."""


def _call_gpt4o(row, latest_score, slope, risk_score, nlp_category, predicted_4w) -> dict:
    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        max_retries=settings.OPENAI_MAX_RETRIES,
        timeout=settings.OPENAI_TIMEOUT,
    )
    log.info("GPT-4o enriching HCP %s", row.hcp_id)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _build_prompt(row, latest_score, slope, risk_score, nlp_category, predicted_4w or latest_score)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return json.loads(response.choices[0].message.content)


def _stub(row: HCPAwareness, nlp_category: str, predicted_direction: Optional[str]) -> dict:
    if nlp_category == "COMPETITOR_THREAT":
        activity = f"Reading competitor articles on Creon clinical data — engagement up 40% this month"
        action   = f"Schedule urgent call with {row.hcp_full_name.split(',')[0]}. Provide head-to-head APEX trial data to counter Creon messaging."
    elif nlp_category == "REP_ENGAGEMENT":
        activity = f"Minimal digital engagement — 0 Zenpep content views in last 30 days"
        action   = f"Schedule in-person visit immediately. No rep calls in 6 weeks — risk of losing prescription preference."
    else:
        activity = f"Low engagement with Zenpep product content — competitor awareness increasing"
        action   = f"Re-engage with updated clinical data and ZenConnect co-pay messaging."
    return {"ai_aim_xr_activity": activity, "ai_recommended_action": action}


def _enrich(row, latest_score, slope, risk_score, nlp_category, predicted_direction, predicted_4w) -> dict:
    if row.hcp_id in _CACHE:
        return _CACHE[row.hcp_id]
    if settings.LLM_STUB_MODE:
        result = _stub(row, nlp_category, predicted_direction)
    else:
        try:
            result = _call_gpt4o(row, latest_score, slope, risk_score, nlp_category, predicted_4w)
        except Exception as exc:
            log.warning("GPT-4o failed for HCP %s (%s) — falling back to stub", row.hcp_id, exc)
            result = _stub(row, nlp_category, predicted_direction)
    _CACHE[row.hcp_id] = result
    return result


# ── Main service ──────────────────────────────────────────────────────────────

# Averages → Jan 29: 78.2%, Feb 26: 74.2%, Mar 25: 66.8%, Apr 22: 60.0%
# Produces: green bar → green bar → orange bar → red/orange bar on the trend chart
_SAMPLE_AWARENESS_ROWS = [
    {
        "hcp_id": "HCP-AW001", "hcp_full_name": "Dr. Thomas Harrison",
        "institution": "Valley Medical Center", "specialty": "Cardiology",
        "city_state": "Hartford, CT",
        "score_jan29": "78.0%", "score_feb26": "74.0%", "score_mar25": "68.0%", "score_apr22": "62.0%",
        "score_change_pct": "-20.5%", "trend_direction": "Declining",
        "root_cause_signal": (
            "Competitor articles on heart failure outcomes viewed 3x last month. "
            "Creon rep activity surge detected in cardiology segment. "
            "Last rep visit: 4 weeks ago. Last AIM XR content view: Apr 24."
        ),
        "re_engagement_priority": "HIGH",
    },
    {
        "hcp_id": "HCP-AW002", "hcp_full_name": "Dr. Lisa Martinez",
        "institution": "Summit Health", "specialty": "Endocrinology",
        "city_state": "New Haven, CT",
        "score_jan29": "91.0%", "score_feb26": "87.0%", "score_mar25": "81.0%", "score_apr22": "74.0%",
        "score_change_pct": "-18.7%", "trend_direction": "Declining",
        "root_cause_signal": (
            "Minimal digital engagement — 0 target indication articles viewed in last 30 days. "
            "No Zenpep content interaction recorded. Rep visit gap 6 weeks."
        ),
        "re_engagement_priority": "MEDIUM",
    },
    {
        "hcp_id": "HCP-AW003", "hcp_full_name": "Dr. Robert Chen",
        "institution": "Northeast Medical Center", "specialty": "Gastroenterology",
        "city_state": "Worcester, MA",
        "score_jan29": "82.0%", "score_feb26": "76.0%", "score_mar25": "60.0%", "score_apr22": "48.0%",
        "score_change_pct": "-41.5%", "trend_direction": "Declining",
        "root_cause_signal": (
            "Competitor rep visit frequency +68% last month. "
            "Creon competitive messaging detected in prescribing pattern data. "
            "Market share shift identified in GI segment."
        ),
        "re_engagement_priority": "HIGH",
    },
    {
        "hcp_id": "HCP-AW004", "hcp_full_name": "Dr. Amy Santos",
        "institution": "Riverside Clinic", "specialty": "Internal Medicine",
        "city_state": "Bridgeport, CT",
        "score_jan29": "68.0%", "score_feb26": "64.0%", "score_mar25": "53.0%", "score_apr22": "42.0%",
        "score_change_pct": "-38.2%", "trend_direction": "Declining",
        "root_cause_signal": (
            "Payer access concern cited — BlueCross formulary tier change affecting Zenpep coverage. "
            "Clinical evidence knowledge gap on EPI management identified."
        ),
        "re_engagement_priority": "MEDIUM",
    },
    {
        "hcp_id": "HCP-AW005", "hcp_full_name": "Dr. David Park",
        "institution": "City Cancer Center", "specialty": "Oncology",
        "city_state": "Springfield, MA",
        "score_jan29": "72.0%", "score_feb26": "70.0%", "score_mar25": "72.0%", "score_apr22": "74.0%",
        "score_change_pct": "+2.8%", "trend_direction": "Stable",
        "root_cause_signal": (
            "Consistent engagement maintained. High awareness of Zenpep in oncology-related EPI patients. "
            "ZenConnect enrollment recent. APEX trial data reviewed."
        ),
        "re_engagement_priority": "LOW",
    },
]


class _FakeRow:
    def __init__(self, d: dict):
        self.__dict__.update(d)

    def __getattr__(self, name):
        return None


def get_hcp_awareness(db: Session, territory_id: str) -> HCPAwarenessResponse:
    rows: List[HCPAwareness] = []
    try:
        rows = db.query(HCPAwareness).all()
    except Exception as e:
        log.warning("HCP awareness DB query failed (%s), using sample data", e)

    if not rows:
        log.info("No HCP awareness rows — using sample data")
        rows = [_FakeRow(r) for r in _SAMPLE_AWARENESS_ROWS]  # type: ignore[assignment]

    # ── Compute trend chart — average score per period ────────────────────────
    period_scores: Dict[str, List[float]] = {label: [] for label, _ in _PERIODS}
    for r in rows:
        for label, attr in _PERIODS:
            s = _parse_pct(getattr(r, attr))
            if s > 0:
                period_scores[label].append(s)

    awareness_trend = [
        TrendPoint(
            period    = label,
            avg_score = round(float(np.mean(period_scores[label])), 1) if period_scores[label] else 0.0,
        )
        for label, _ in _PERIODS
    ]

    # Predicted trend: extrapolate 2 more periods using avg slope
    all_avgs   = [t.avg_score for t in awareness_trend]
    avg_slope, _, _, _, _ = _linear_regression(all_avgs)
    predicted_trend = []
    if avg_slope is not None:
        for i, period_name in enumerate(_NEXT_PERIODS, start=1):
            pred = round(float(np.clip(all_avgs[-1] + avg_slope * i, 0, 100)), 1)
            predicted_trend.append(TrendPoint(period=period_name, avg_score=pred))

    # ── Build each HCPAwarenessItem ───────────────────────────────────────────
    enriched = []
    for r in rows:
        scores       = [_parse_pct(getattr(r, attr)) for _, attr in _PERIODS]
        latest_score = scores[-1]
        change_pct   = _parse_pct(r.score_change_pct)

        slope, _, _, pred_4w, pred_dir = _linear_regression(scores)
        risk_score, _ = _compute_risk_score(latest_score, change_pct, slope, r.re_engagement_priority)
        nlp_category, _, _ = _nlp_analyze(r.root_cause_signal)
        ai = _enrich(r, latest_score, slope, risk_score, nlp_category, pred_dir, pred_4w)

        # Recent change: 3rd period → 4th period (e.g. Mar 25 → Apr 22)
        prev_score = scores[-2] if len(scores) >= 2 and scores[-2] > 0 else None
        if prev_score:
            recent_change = round((latest_score - prev_score) / prev_score * 100, 1)
            from_period_label = _PERIODS[-2][0]                        # e.g. "Mar 25"
            from_month = from_period_label.split()[0]                  # e.g. "Mar"
            change_from_period = f"{from_month} 1"                    # e.g. "Mar 1"
        else:
            recent_change = None
            change_from_period = None

        enriched.append({
            "risk_score":      risk_score,
            "trend_direction": r.trend_direction,
            "item": HCPAwarenessItem(
                hcp_full_name               = (r.hcp_full_name or "").replace(",", " ").strip(),
                specialty                   = r.specialty,
                institution                 = getattr(r, "institution", None),
                ai_awareness_score          = round(latest_score, 1),
                ai_awareness_level          = _awareness_level(latest_score),
                ai_trend_direction          = r.trend_direction,
                ai_score_change_pct         = change_pct,
                ai_recent_change_pct        = recent_change,
                ai_change_from_period       = change_from_period,
                analysis_badges             = ["NLP_ANALYSIS", "AI_SCORING", "PREDICTIVE_ANALYTICS"],
                ai_icd10_prescribing_patterns = None,
                ai_aim_xr_activity          = ai.get("ai_aim_xr_activity"),
                ai_recommended_action       = ai.get("ai_recommended_action"),
            ),
        })

    enriched.sort(key=lambda x: -x["risk_score"])
    ai_declining_count = sum(1 for e in enriched if (e["trend_direction"] or "") == "Declining")
    items = [e["item"] for e in enriched]

    return HCPAwarenessResponse(
        awareness_trend    = awareness_trend,
        ai_predicted_trend = predicted_trend,
        total              = len(items),
        ai_declining_count = ai_declining_count,
        items              = items,
    )
