"""Score and rank HCPs into High / Medium / Low priority tiers for Module 1."""
from typing import Dict, List, Literal

from app.config import settings
from app.services.territory_prioritization.feature_engineering import compute_percentile_threshold


PriorityTier = Literal["HIGH", "MEDIUM", "LOW"]


def assign_priority_tier(
    rx_trend_pct: float,
    rx_q1: float,
    percentile_threshold: float,
    high_trend: float = settings.RX_TREND_HIGH_THRESHOLD,
    low_trend: float = settings.RX_TREND_LOW_THRESHOLD,
) -> PriorityTier:
    """Assign priority tier per business rules:
    - HIGH  : trend > 15%  OR  rx_q1 > 75th-percentile
    - LOW   : trend < -10%
    - MEDIUM: everything else
    """
    if rx_trend_pct > high_trend or rx_q1 > percentile_threshold:
        return "HIGH"
    if rx_trend_pct < low_trend:
        return "LOW"
    return "MEDIUM"


def rank_hcps(features: List[Dict]) -> List[Dict]:
    """Add priority_tier to each feature dict and sort: HIGH → MEDIUM → LOW, then by rx_q1 desc."""
    threshold = compute_percentile_threshold(features, settings.RX_HIGH_PERCENTILE)
    tier_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    for hcp in features:
        hcp["priority_tier"] = assign_priority_tier(
            rx_trend_pct=hcp["rx_trend_pct"],
            rx_q1=hcp["rx_q1"],
            percentile_threshold=threshold,
        )

    return sorted(features, key=lambda h: (tier_order[h["priority_tier"]], -h["rx_q1"]))
