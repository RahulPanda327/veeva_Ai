"""Compute Rx trend, competitor share, and enriched HCP feature dict for Module 1."""
from typing import Dict, List

import numpy as np

from app.models.territory_prioritization import HealthcarePractitioner


def compute_rx_trend(rx_q1: float, rx_q4: float) -> float:
    """Rx trend = (Q1 - Q4) / Q4 * 100. Returns 0 if Q4 == 0."""
    if rx_q4 == 0:
        return 0.0
    return round((rx_q1 - rx_q4) / rx_q4 * 100, 2)


def compute_competitor_share(competitor_rx: float, rx_q1: float) -> float:
    """Competitor share as fraction of total market Rx. Capped at [0, 1]."""
    total = rx_q1 + competitor_rx
    if total == 0:
        return 0.0
    return round(min(max(competitor_rx / total, 0.0), 1.0), 4)


def build_hcp_features(
    hcps: List[HealthcarePractitioner],
    rx_data: dict,
    last_call_dates: dict,
) -> List[Dict]:
    """Merge HCP dimension data with Rx and call data into a unified feature dict."""
    features = []
    for hcp in hcps:
        rx = rx_data.get(hcp.hcp_id, {})
        rx_q1 = rx.get("rx_q1", 0.0)
        rx_q4 = rx.get("rx_q4", 0.0)
        competitor_rx = rx.get("competitor_rx", 0.0)

        features.append(
            {
                "hcp_id": hcp.hcp_id,
                "name": hcp.hcp_full_name or f"{hcp.hcp_first_name} {hcp.hcp_last_name}",
                "specialty": hcp.specialty,
                "affiliated_hospital": hcp.affiliated_hospital,
                "territory_id": hcp.territory_id,
                "segment": hcp.hcp_segment,
                "city": hcp.city,
                "state": hcp.state,
                "decile_rank": hcp.decile_rank,
                "rx_q1": rx_q1,
                "rx_q4": rx_q4,
                "rx_trend_pct": compute_rx_trend(rx_q1, rx_q4),
                "competitor_rx": competitor_rx,
                "competitor_brand": rx.get("competitor_brand", ""),
                "competitor_brand_share": compute_competitor_share(competitor_rx, rx_q1),
                "last_call_date": last_call_dates.get(hcp.hcp_id),
            }
        )
    return features


def compute_percentile_threshold(features: List[Dict], percentile: float = 75.0) -> float:
    """Return the Nth-percentile value of rx_q1 across all HCPs."""
    rx_values = [f["rx_q1"] for f in features if f["rx_q1"] > 0]
    if not rx_values:
        return 0.0
    return float(np.percentile(rx_values, percentile))
