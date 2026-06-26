"""Feature engineering for Territory Prioritization."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import numpy as np


def compute_rx_trend(rx_q1: float, rx_q4: float) -> float:
    if rx_q4 == 0:
        return 0.0
    return round((rx_q1 - rx_q4) / rx_q4 * 100, 2)


def compute_competitor_share(competitor_rx: float, rx_q1: float) -> float:
    total = rx_q1 + competitor_rx
    if total == 0:
        return 0.0
    return round(min(max(competitor_rx / total, 0.0), 1.0), 4)


def compute_percentile_threshold(features: List[Dict], percentile: float = 75.0) -> float:
    rx_values = [f["rx_q1"] for f in features if f["rx_q1"] > 0]
    if not rx_values:
        return 0.0
    return float(np.percentile(rx_values, percentile))


def build_hcp_features(
    hcps: List[dict],
    rx_data: dict,
    last_call_dates: dict,
    sample_rx: Optional[Dict[str, List[float]]] = None,
    sample_comp: Optional[Dict[str, float]] = None,
    ref_date: Optional[date] = None,
) -> List[Dict]:
    """
    Merge HCP dimension data with Rx and call data into unified feature dicts.
    Adds monthly_rx_history for LinearRegression prediction.
    """
    features = []
    ref = ref_date or date.today()

    for hcp in hcps:
        hcp_id = hcp["hcp_id"] if isinstance(hcp, dict) else hcp.hcp_id

        # Support both dict (raw SQL) and ORM objects
        def _get(key, default=None):
            if isinstance(hcp, dict):
                return hcp.get(key, default)
            return getattr(hcp, key, default)

        rx = rx_data.get(hcp_id, {})
        rx_q1 = rx.get("rx_q1", 0.0)
        rx_q4 = rx.get("rx_q4", 0.0)
        competitor_rx = rx.get("competitor_rx", 0.0)

        # Monthly Rx history for LinearRegression
        if sample_rx and hcp_id in sample_rx:
            monthly_history = sample_rx[hcp_id]
        else:
            monthly_history = []   # will be populated from rx_pivot_df in ai_score

        # Last Rx date: most recent non-zero month
        last_rx_date_str = None
        if monthly_history:
            for i in range(len(monthly_history) - 1, -1, -1):
                if monthly_history[i] > 0:
                    months_back = len(monthly_history) - 1 - i
                    from datetime import timedelta
                    d = ref.replace(day=1)
                    for _ in range(months_back):
                        d = (d - timedelta(days=1)).replace(day=1)
                    last_rx_date_str = d.strftime("%b %d, %Y")
                    break

        features.append({
            "hcp_id":               hcp_id,
            "name":                 _get("name") or f"{_get('hcp_first_name','')} {_get('hcp_last_name','')}".strip(),
            "specialty":            _get("specialty"),
            "affiliated_hospital":  _get("affiliated_hospital"),
            "territory_id":         _get("territory_id"),
            "segment":              _get("segment") or _get("hcp_segment"),
            "city":                 _get("city"),
            "state":                _get("state"),
            "decile_rank":          _get("decile_rank"),
            "rx_q1":                rx_q1,
            "rx_q4":                rx_q4,
            "rx_trend_pct":         compute_rx_trend(rx_q1, rx_q4),
            "competitor_rx":        competitor_rx,
            "competitor_brand":     rx.get("competitor_brand", "CREON"),
            "competitor_brand_share": compute_competitor_share(competitor_rx, rx_q1),
            "last_call_date":       last_call_dates.get(hcp_id),
            "monthly_rx_history":   monthly_history,
            "last_rx_date":         last_rx_date_str,
        })
    return features
