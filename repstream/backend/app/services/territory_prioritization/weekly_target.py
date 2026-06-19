"""Compute this-week's rep visit target count for Module 1."""
import math
from typing import Dict, List

from app.config import settings


def compute_weekly_target(ranked_hcps: List[Dict]) -> int:
    """Weekly target = ceil(count(HIGH priority HCPs) * 0.65).

    Uses ai_priority_tier if present, otherwise falls back to priority_tier.
    """
    tier_key = "ai_priority_tier" if ranked_hcps and "ai_priority_tier" in ranked_hcps[0] else "priority_tier"
    high_count = sum(1 for h in ranked_hcps if h.get(tier_key) == "HIGH")
    return math.ceil(high_count * settings.WEEKLY_TARGET_RATIO)


def build_territory_summary(
    ranked_hcps: List[Dict],
    territory_id: str,
    territory_name: str,
    period: str,
) -> dict:
    """Aggregate KPI counts from ranked HCP list."""
    tier_key = "ai_priority_tier" if ranked_hcps and "ai_priority_tier" in ranked_hcps[0] else "priority_tier"
    high = sum(1 for h in ranked_hcps if h.get(tier_key) == "HIGH")
    med = sum(1 for h in ranked_hcps if h.get(tier_key) == "MEDIUM")
    low = sum(1 for h in ranked_hcps if h.get(tier_key) == "LOW")
    return {
        "total_hcps": len(ranked_hcps),
        "high_priority_count": high,
        "medium_priority_count": med,
        "low_priority_count": low,
        "weekly_target": compute_weekly_target(ranked_hcps),
        "period": period,
        "territory_id": territory_id,
        "territory_name": territory_name,
        "last_refresh": "",   # filled by router
    }
