"""
AI Scoring Engine — Territory Prioritization

4 AI/ML techniques:

  Technique 1 — AI Composite Scoring (AI_SCORING badge)
    Formula: score = (TRx_growth_norm × 0.60)
                   + (interaction_impact × 0.30)
                   + (decile_norm × 0.10)
    Tier: HIGH ≥ 65 | MEDIUM 35-64 | LOW < 35

  Technique 2 — Linear Regression Prediction (PREDICTIVE_ANALYTICS badge)
    Input:  monthly Rx history (12 months)
    Output: slope (Rx/month), R², predicted next-quarter Rx
    Direction: Improving (slope > 0.5) | Declining (slope < -0.5) | Stable

  Technique 3 — NLP Engagement Classification (NLP_ANALYSIS badge)
    Input:  segment, call history, trend direction, competitor share
    Output: category (ACTIVE_HIGH_VALUE / LAPSED_RECOVERABLE / NEW_WRITER / AT_RISK / STABLE)
            urgency (Immediate / This Week / This Month / Maintain)
            peer_match_hint for New Writers

  Technique 4 — GPT-4o Insight (AI_INSIGHT badge) — in llm_insight.py
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

WEIGHTS = {"trx_growth": 0.60, "interaction_impact": 0.30, "decile_score": 0.10}
TIER_HIGH   = 65.0
TIER_MEDIUM = 35.0


# ─────────────────────────────────────────────────────────────────────────────
# Technique 1 — Composite Scoring
# ─────────────────────────────────────────────────────────────────────────────

def normalize_trx_growth(growth_pct: float) -> float:
    capped = max(-50.0, min(150.0, growth_pct))
    return round((capped + 50) / 200 * 100, 4)


def compute_interaction_impact(
    days_since_last_call: Optional[int],
    call_count_90d: int,
    last_call_outcome: Optional[str],
) -> float:
    recency = max(0.0, (90.0 - days_since_last_call) / 90.0 * 100) if days_since_last_call is not None else 0.0
    frequency = min(call_count_90d / 3.0 * 100, 100.0)
    outcome_scores = {"Very Positive": 100.0, "Positive": 80.0, "Neutral": 50.0, "Negative": 20.0}
    outcome = outcome_scores.get(last_call_outcome or "", 40.0)
    return round(recency * 0.50 + frequency * 0.30 + outcome * 0.20, 4)


def normalize_decile(decile_rank: Optional[int]) -> float:
    if decile_rank is None or not (1 <= decile_rank <= 10):
        return 50.0
    return round((10 - decile_rank) / 9.0 * 100, 4)


def compute_ai_priority_score(trx_growth_pct: float, interaction_impact: float, decile_rank: Optional[int]) -> Dict:
    trx_norm     = normalize_trx_growth(trx_growth_pct)
    inter_norm   = min(max(interaction_impact, 0.0), 100.0)
    decile_norm  = normalize_decile(decile_rank)
    composite    = round(trx_norm * WEIGHTS["trx_growth"] + inter_norm * WEIGHTS["interaction_impact"] + decile_norm * WEIGHTS["decile_score"], 2)
    return {
        "ai_trx_growth_norm":    trx_norm,
        "ai_interaction_impact": round(inter_norm, 2),
        "ai_decile_score_norm":  decile_norm,
        "ai_priority_score":     composite,
    }


def assign_ai_priority_tier(score: float) -> str:
    if score >= TIER_HIGH:
        return "HIGH"
    if score >= TIER_MEDIUM:
        return "MEDIUM"
    return "LOW"


# ─────────────────────────────────────────────────────────────────────────────
# Technique 2 — Linear Regression: monthly Rx → next-quarter prediction
# ─────────────────────────────────────────────────────────────────────────────

def _r_squared(y: np.ndarray, y_hat: np.ndarray) -> float:
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return 0.0 if ss_tot == 0 else float(1 - ss_res / ss_tot)


def predict_rx_trend(monthly_rx_history: List[float]) -> Dict:
    """
    Fit linear regression on monthly Rx history.
    Predicts next quarter (sum of 3 months ahead).
    Returns slope, r2, predicted_next_q, trend_direction, predicted_direction.
    """
    data = [x for x in monthly_rx_history if x is not None]
    if len(data) < 3:
        return {
            "ai_rx_slope":           None,
            "ai_predicted_next_q_rx": None,
            "ai_rx_trend_direction": "Stable",
            "ai_predicted_direction": "Flat",
        }

    x = np.arange(len(data), dtype=float)
    y = np.array(data, dtype=float)
    coeffs = np.polyfit(x, y, 1)
    slope  = float(coeffs[0])
    y_hat  = np.polyval(coeffs, x)
    r2     = _r_squared(y, y_hat)

    # Predict 3 months ahead (next quarter)
    n = len(data)
    pred_months = [max(0.0, float(np.polyval(coeffs, n + i))) for i in range(3)]
    predicted_q = round(sum(pred_months), 1)

    # Direction thresholds
    if slope > 0.5:
        trend_dir = "Improving"
        pred_dir  = "Up"
    elif slope < -0.5:
        trend_dir = "Declining"
        pred_dir  = "Down"
    else:
        trend_dir = "Stable"
        pred_dir  = "Flat"

    return {
        "ai_rx_slope":            round(slope, 3),
        "ai_predicted_next_q_rx": predicted_q if r2 > 0.2 else None,
        "ai_rx_trend_direction":  trend_dir,
        "ai_predicted_direction": pred_dir,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Technique 3 — NLP Engagement Classification
# ─────────────────────────────────────────────────────────────────────────────

_SEGMENT_KEYWORDS = {
    "NEW_WRITER":          ["new writer", "new_writer"],
    "TARGET_A":            ["target a", "target_a", "high value"],
    "TARGET_B":            ["target b", "target_b"],
}


def _classify_segment(segment: Optional[str]) -> str:
    lower = (segment or "").lower()
    for cat, kws in _SEGMENT_KEYWORDS.items():
        if any(k in lower for k in kws):
            return cat
    return "OTHER"


def classify_engagement(
    segment: Optional[str],
    days_since_last_call: Optional[int],
    call_count_90d: int,
    trend_direction: str,
    competitor_brand_share: float,
    rx_q1: float,
) -> Tuple[str, str]:
    """
    NLP-style rule-based classification.
    Returns (engagement_category, urgency).
    """
    seg_cat = _classify_segment(segment)

    # New Writer
    if seg_cat == "NEW_WRITER" or rx_q1 < 5:
        return "NEW_WRITER", "This Week"

    # Lapsed: hasn't been called in >60 days AND declining
    if (days_since_last_call or 999) > 60 and trend_direction == "Declining":
        return "LAPSED_RECOVERABLE", "Immediate"

    # At Risk: declining + high competitor share
    if trend_direction == "Declining" and competitor_brand_share > 0.35:
        return "AT_RISK", "Immediate"

    # High Value Active
    if seg_cat == "TARGET_A" and trend_direction in ("Improving", "Stable") and rx_q1 >= 30:
        return "ACTIVE_HIGH_VALUE", "This Month"

    # Stable
    if trend_direction == "Stable" and call_count_90d >= 2:
        return "STABLE", "Maintain"

    # Default
    if seg_cat == "TARGET_A":
        return "ACTIVE_HIGH_VALUE", "This Week"

    return "STABLE", "This Month"


def _get_peer_hint(hcp: Dict, all_hcps: List[Dict]) -> Optional[str]:
    """For NEW_WRITER HCPs, suggest a warm intro via a high-value writer in same specialty."""
    if hcp.get("ai_engagement_category") != "NEW_WRITER":
        return None
    spec = (hcp.get("specialty") or "").lower()
    for candidate in all_hcps:
        if (candidate["hcp_id"] != hcp["hcp_id"]
                and (candidate.get("specialty") or "").lower() == spec
                and candidate.get("ai_priority_tier") == "HIGH"
                and candidate.get("rx_q1", 0) > 20):
            return f"Warm intro via {candidate['name']}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Analysis badges builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_badges(hcp: Dict) -> List[str]:
    badges = ["AI_SCORING"]
    if hcp.get("ai_predicted_next_q_rx") is not None:
        badges.append("PREDICTIVE_ANALYTICS")
    if hcp.get("ai_engagement_category"):
        badges.append("NLP_ANALYSIS")
    if hcp.get("ai_generated_insight"):
        badges.append("AI_INSIGHT")
    return badges


# ─────────────────────────────────────────────────────────────────────────────
# Main enrichment functions
# ─────────────────────────────────────────────────────────────────────────────

def enrich_hcp_with_ai_scores(hcp: Dict, call_stats: Dict) -> Dict:
    """Add all ai_* score keys to a single HCP feature dict in-place."""
    # Technique 1: composite score
    interaction = compute_interaction_impact(
        days_since_last_call=call_stats.get("days_since_last_call"),
        call_count_90d=call_stats.get("call_count_90d", 0),
        last_call_outcome=call_stats.get("last_outcome") or call_stats.get("last_call_outcome"),
    )
    scores = compute_ai_priority_score(
        trx_growth_pct=hcp.get("rx_trend_pct", 0.0),
        interaction_impact=interaction,
        decile_rank=hcp.get("decile_rank"),
    )
    hcp.update(scores)
    hcp["ai_priority_tier"]    = assign_ai_priority_tier(scores["ai_priority_score"])
    hcp["ai_interaction_impact"] = round(interaction, 2)
    hcp["call_count_90d"]      = call_stats.get("call_count_90d", 0)
    hcp["days_since_last_call"] = call_stats.get("days_since_last_call")
    hcp["last_call_outcome"]   = call_stats.get("last_outcome") or call_stats.get("last_call_outcome")
    hcp["last_call_date"]      = call_stats.get("last_call_date") or hcp.get("last_call_date")

    # Technique 2: linear regression
    history = hcp.get("monthly_rx_history") or []
    pred    = predict_rx_trend(history)
    hcp.update(pred)

    # Technique 3: NLP engagement
    cat, urgency = classify_engagement(
        segment=hcp.get("segment"),
        days_since_last_call=hcp.get("days_since_last_call"),
        call_count_90d=hcp.get("call_count_90d", 0),
        trend_direction=hcp.get("ai_rx_trend_direction", "Stable"),
        competitor_brand_share=hcp.get("competitor_brand_share", 0.0),
        rx_q1=hcp.get("rx_q1", 0.0),
    )
    hcp["ai_engagement_category"] = cat
    hcp["ai_engagement_urgency"]  = urgency

    return hcp


def enrich_all_hcps(hcps: List[Dict], call_stats_map: Dict[str, Dict]) -> List[Dict]:
    """Enrich all HCPs. After enrichment, add peer hints and badges. Sort by tier then score."""
    tier_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    for hcp in hcps:
        stats = call_stats_map.get(hcp["hcp_id"], {
            "days_since_last_call": None,
            "call_count_90d": 0,
            "last_outcome": None,
        })
        enrich_hcp_with_ai_scores(hcp, stats)

    sorted_hcps = sorted(
        hcps,
        key=lambda h: (tier_order[h["ai_priority_tier"]], -h["ai_priority_score"]),
    )

    # Add peer match hints (needs full sorted list)
    for hcp in sorted_hcps:
        hcp["ai_peer_match_hint"] = _get_peer_hint(hcp, sorted_hcps)

    # Badges (AI_INSIGHT not yet set, added later by llm_insight)
    for hcp in sorted_hcps:
        hcp["analysis_badges"] = _build_badges(hcp)

    return sorted_hcps
