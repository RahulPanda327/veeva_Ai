"""Module 2 and Module 3 KPI tiles for the Territory Prioritization summary.

WHY THESE LIVE HERE AND NOT IN THEIR OWN MODULES
    They are counted over the SAME lists /new-writers/candidates and
    /objections/list return for the current filter — not from fresh SQL. Two
    queries answering "how many non-writers" would eventually disagree with each
    other, and the tile that disagrees with the screen it links to is the one
    users report as a bug. Counting the served list makes that impossible.

    Both source lists are already cached per territory, so this adds a pass over
    a few hundred dicts, not a database round trip.

EVERY COUNT IS DERIVED, NOT READ
    None of these four fields exists in the warehouse; each is a predicate over
    fields that do. The predicates are written out below rather than hidden in a
    comprehension so the definition of a tile is reviewable by someone who does
    not read Python.
"""
from __future__ import annotations

from typing import Any, Dict, List

# A candidate counts as "warm" at this many independent positive signals. Two
# rather than three: requiring all three would mean one missing ICD-10 code
# disqualifies an HCP who is prescribing in class AND matches a peer, and the
# warehouse has no ICD-10 source column at all for some territories - the tile
# would read 0 and look broken rather than selective.
_WARM_SIGNAL_THRESHOLD = 2


def _num(value: Any) -> float:
    """Coerce a possibly-None / possibly-string numeric field to a float."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_new_writer_kpis(population: Dict[str, Any]) -> Dict[str, int]:
    """Module 2 tiles, from the uncapped new-writer population for this filter.

    `population` is what _new_writer_population() returns:
        rows       uncapped live detection (zero brand Rx AND positive in-class
                   Rx), peer-enriched
        hcp_total  every HCP in the scoped territories
        writers    how many of those currently write the brand

    Three separate figures because the tiles measure three different sets, and
    two earlier attempts got this wrong in instructive ways:

    Counting the list /new-writers/candidates serves pinned every tile at <=10,
    because that endpoint caps to the top 10 targets for its card UI - so a
    narrower filter could report a LARGER number than a wider one.

    Counting the ranked HCP list gave a flat zero, because that list is built
    from HCPs with prescribing history: it contains no non-writers at all, by
    construction.

    So non-writers is (all HCPs in territory - those who write the brand), which
    is the only one of the three that counts HCPs prescribing nothing in the
    class as well.
    """
    rows: List[Dict[str, Any]] = population.get("rows") or []
    hcp_total = int(_num(population.get("hcp_total")))
    writers = int(_num(population.get("writers")))
    # max(0, ...) guards the case where the two figures come from different
    # queries and disagree at the edges; a negative tile is never the right answer.
    non_writers = max(0, hcp_total - writers)

    prescribing_in_class = diagnosis_match = warm = 0
    for c in rows:
        # The detection query already guarantees positive in-class Rx (and zero
        # brand Rx) for every row it returns, so membership is the signal. The
        # column is still checked rather than assumed: a future change to that
        # query should show up here as a number moving, not as a silent lie.
        is_in_class = _num(c.get("in_class_rx_q1") or c.get("total_in_class_rx")) > 0
        # Patient diagnoses line up with what the product treats.
        has_diagnosis = _num(c.get("ai_icd10_match_count") or c.get("icd10_match_count")) > 0
        # Behaves like an HCP who already writes the brand.
        has_peer = _num(c.get("peer_match_pct") or c.get("ai_peer_match_score")) > 0

        prescribing_in_class += is_in_class
        diagnosis_match += has_diagnosis
        if (is_in_class + has_diagnosis + has_peer) >= _WARM_SIGNAL_THRESHOLD:
            warm += 1

    return {
        "Non_writers_in_Territory": non_writers,
        "Prescribing_in_class": prescribing_in_class,
        "Diagnosis_match": diagnosis_match,
        "Warm_condidates": warm,
    }


def build_objection_kpis(objections: List[Dict[str, Any]]) -> Dict[str, int]:
    """Module 3 tiles from the enriched objection list."""
    calls = recurring = high = 0

    for o in objections:
        # Each row carries how many calls that objection was heard in; the total
        # across rows is the call volume the analysis covered.
        call_count = int(_num(o.get("ai_call_count")))
        calls += call_count
        # Heard more than once = a pattern, not a one-off remark. This is what
        # "recurring" has to mean here: rows are already grouped by objection
        # type, so counting duplicate types would always return zero.
        if call_count > 1:
            recurring += 1
        if str(o.get("ai_frequency_label") or "").upper() == "HIGH":
            high += 1

    return {
        "calls_analysed": calls,
        "objections_detected": len(objections),
        "recurring_patterns": recurring,
        "High_frequency": high,
    }
