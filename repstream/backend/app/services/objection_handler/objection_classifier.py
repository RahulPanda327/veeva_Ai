"""Frequency rank and High/Medium/Low label assignment for Module 3."""
from typing import Dict, List, Literal

from app.config import settings

FrequencyLabel = Literal["HIGH", "MEDIUM", "LOW"]


def assign_frequency_label(call_count: int) -> FrequencyLabel:
    """HIGH if > 8 calls; MEDIUM if 3–8; LOW otherwise."""
    if call_count > settings.OBJECTION_HIGH_THRESHOLD:
        return "HIGH"
    if call_count >= settings.OBJECTION_MEDIUM_MIN:
        return "MEDIUM"
    return "LOW"


def compute_success_rate(calls_with_rx_30d: int, total_calls: int) -> float:
    """Success rate = calls where Rx followed within 30 days / total calls with objection."""
    if total_calls == 0:
        return 0.0
    return round(calls_with_rx_30d / total_calls, 4)


def classify_objections(
    frequency_data: Dict[str, Dict],
    period: str,
    territory_id: str,
) -> List[Dict]:
    """Build ranked objection list from frequency data dict.

    Returns list sorted by call_count descending.
    """
    results = []
    for objection_type, data in frequency_data.items():
        call_count = data["call_count"]
        results.append(
            {
                "objection_type": objection_type,
                "call_count": call_count,
                "frequency": assign_frequency_label(call_count),
                "success_rate": compute_success_rate(
                    data["calls_with_rx_30d"], call_count
                ),
                "period": period,
                "territory_id": territory_id,
            }
        )

    return sorted(results, key=lambda r: -r["call_count"])
