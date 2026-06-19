"""
AI Priority Scoring Engine — Territory Prioritization (Module 1)

Formula:
    AI_Priority_Score = (TRx_Growth_Pct_norm × 0.60)
                      + (Interaction_Impact_norm × 0.30)
                      + (Decile_Score_norm      × 0.10)

Tier assignment:
    HIGH   : score >= 65
    MEDIUM : score 35–64
    LOW    : score < 35
"""
from datetime import date
from typing import Dict, List, Optional

WEIGHTS = {"trx_growth": 0.60, "interaction_impact": 0.30, "decile_score": 0.10}

# Tier thresholds
TIER_HIGH = 65.0
TIER_MEDIUM = 35.0


# ── Component scorers ─────────────────────────────────────────────────────────

def normalize_trx_growth(growth_pct: float) -> float:
    """Map [-50%, +150%] linearly to [0, 100]. Growth > 150% → 100."""
    capped = max(-50.0, min(150.0, growth_pct))
    return round((capped + 50) / 200 * 100, 4)


def compute_interaction_impact(
    days_since_last_call: Optional[int],
    call_count_90d: int,
    last_call_outcome: Optional[str],
) -> float:
    """Composite 0-100 interaction quality score.

    Weights:
        50% recency  (0 days = 100, ≥90 days = 0, no call = 0)
        30% frequency (≥3 calls in 90d = 100)
        20% outcome quality
    """
    if days_since_last_call is None:
        recency = 0.0
    else:
        recency = max(0.0, (90.0 - days_since_last_call) / 90.0 * 100)

    frequency = min(call_count_90d / 3.0 * 100, 100.0)

    outcome_scores = {
        "Very Positive": 100.0,
        "Positive": 80.0,
        "Neutral": 50.0,
        "Negative": 20.0,
    }
    outcome = outcome_scores.get(last_call_outcome or "", 40.0)

    return round(recency * 0.50 + frequency * 0.30 + outcome * 0.20, 4)


def normalize_decile(decile_rank: Optional[int]) -> float:
    """Rank 1 (best prescriber) → 100, rank 10 → 0. None → 50."""
    if decile_rank is None or not (1 <= decile_rank <= 10):
        return 50.0
    return round((10 - decile_rank) / 9.0 * 100, 4)


# ── Composite scorer ──────────────────────────────────────────────────────────

def compute_ai_priority_score(
    trx_growth_pct: float,
    interaction_impact: float,
    decile_rank: Optional[int],
) -> Dict[str, float]:
    """Return a dict of all AI score components and the composite.

    Returns:
        {
          "ai_trx_growth_norm":         float 0-100,
          "ai_interaction_impact":      float 0-100,
          "ai_decile_score_norm":       float 0-100,
          "ai_priority_score":          float 0-100,
        }
    """
    trx_norm = normalize_trx_growth(trx_growth_pct)
    interaction_norm = min(max(interaction_impact, 0.0), 100.0)
    decile_norm = normalize_decile(decile_rank)

    composite = round(
        trx_norm * WEIGHTS["trx_growth"]
        + interaction_norm * WEIGHTS["interaction_impact"]
        + decile_norm * WEIGHTS["decile_score"],
        2,
    )

    return {
        "ai_trx_growth_norm": trx_norm,
        "ai_interaction_impact": round(interaction_norm, 2),
        "ai_decile_score_norm": decile_norm,
        "ai_priority_score": composite,
    }


def assign_ai_priority_tier(score: float) -> str:
    if score >= TIER_HIGH:
        return "HIGH"
    if score >= TIER_MEDIUM:
        return "MEDIUM"
    return "LOW"


# ── Enrichment helper ─────────────────────────────────────────────────────────

def enrich_hcp_with_ai_scores(
    hcp: Dict,
    call_stats: Dict,   # {"days_since_last_call": int|None, "call_count_90d": int, "last_outcome": str|None}
) -> Dict:
    """Add all ai_* score keys to a single HCP feature dict in-place.

    call_stats keys:
        days_since_last_call  int | None
        call_count_90d        int
        last_outcome          str | None
    """
    interaction = compute_interaction_impact(
        days_since_last_call=call_stats.get("days_since_last_call"),
        call_count_90d=call_stats.get("call_count_90d", 0),
        last_call_outcome=call_stats.get("last_outcome"),
    )

    scores = compute_ai_priority_score(
        trx_growth_pct=hcp.get("rx_trend_pct", 0.0),
        interaction_impact=interaction,
        decile_rank=hcp.get("decile_rank"),
    )

    hcp.update(scores)
    hcp["ai_priority_tier"] = assign_ai_priority_tier(scores["ai_priority_score"])
    hcp["ai_interaction_impact"] = round(interaction, 2)
    hcp["call_count_90d"] = call_stats.get("call_count_90d", 0)
    hcp["days_since_last_call"] = call_stats.get("days_since_last_call")
    hcp["last_call_outcome"] = call_stats.get("last_outcome")
    return hcp


def enrich_all_hcps(hcps: List[Dict], call_stats_map: Dict[str, Dict]) -> List[Dict]:
    """Enrich all HCP dicts with AI scores. Sort by ai_priority_score desc within tier."""
    tier_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    for hcp in hcps:
        stats = call_stats_map.get(hcp["hcp_id"], {
            "days_since_last_call": None,
            "call_count_90d": 0,
            "last_outcome": None,
        })
        enrich_hcp_with_ai_scores(hcp, stats)

    return sorted(
        hcps,
        key=lambda h: (tier_order[h["ai_priority_tier"]], -h["ai_priority_score"]),
    )
