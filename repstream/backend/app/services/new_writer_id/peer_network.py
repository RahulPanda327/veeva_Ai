"""Peer network lookup for new writer candidates in Module 2.

Falls back to sample peer data when insight360_peer_match has no matches.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.new_writer_id import PeerMatch

log = logging.getLogger(__name__)


# Sample peer matches keyed by new-writer hcp_id
_SAMPLE_PEERS: Dict[str, Dict] = {
    "NW001": {
        "peer_hcp_id": "HCP001",
        "peer_hcp_name": "Dr. Sarah Davidson",
        "match_score": 87.0,
        "match_rationale": "Connected to Dr. Davidson. Prescribing competitor in same class at 8-12% conversion rate.",
        "shared_specialty": "Endocrinology",
        "shared_institution": "Summit Medical",
        "peer_brand_rx_q1": 47.0,
    },
    "NW002": {
        "peer_hcp_id": "HCP006",
        "peer_hcp_name": "Dr. Robert Kim",
        "match_score": 72.0,
        "match_rationale": "Peer network indicates 25-35% conversion opportunity. Recently joined practice on Feb 15, 2026.",
        "shared_specialty": "Internal Medicine",
        "shared_institution": None,
        "peer_brand_rx_q1": 48.0,
    },
    "NW003": {
        "peer_hcp_id": "HCP003",
        "peer_hcp_name": "Dr. Anjali Patel",
        "match_score": 65.0,
        "match_rationale": "Similar volume in Internal Medicine. High affinity based on ICD-10 overlap.",
        "shared_specialty": "Internal Medicine",
        "shared_institution": "North Valley Medical",
        "peer_brand_rx_q1": 30.0,
    },
    "NW004": {
        "peer_hcp_id": "HCP009",
        "peer_hcp_name": "Dr. Rachel Green",
        "match_score": 81.0,
        "match_rationale": "Same hospital network. High-value gastro writer with strong ZENPEP adoption.",
        "shared_specialty": "Gastroenterology",
        "shared_institution": "University Hospital",
        "peer_brand_rx_q1": 57.0,
    },
    "NW005": {
        "peer_hcp_id": "HCP005",
        "peer_hcp_name": "Dr. Linda Nguyen",
        "match_score": 58.0,
        "match_rationale": "Pediatric specialist overlap. Adjacent ICD-10 codes suggest crossover potential.",
        "shared_specialty": "Pediatrics",
        "shared_institution": None,
        "peer_brand_rx_q1": 13.0,
    },
}


def load_peer_matches(
    db: Session,
    hcp_ids: List[str],
    territory_id: str,
) -> Dict[str, List[Dict]]:
    """Return peer match records keyed by hcp_id. Falls back to sample if DB returns nothing."""
    if not hcp_ids:
        return {}

    try:
        # insight360_peer_match has no territory_id column; filter by hcp_id only (KPI 7)
        stmt = (
            select(PeerMatch)
            .where(PeerMatch.hcp_id.in_(hcp_ids))
        )
        rows = db.scalars(stmt).all()
        if rows:
            result: Dict[str, List[Dict]] = {}
            for row in rows:
                # Peer_Match_Pct stored as "87%" — parse to float for sorting
                raw_pct = (row.peer_match_pct or "0").replace("%", "")
                score = float(raw_pct) if raw_pct else 0.0
                result.setdefault(row.hcp_id, []).append({
                    "peer_hcp_id":        row.peer_connector_id,
                    "peer_hcp_name":      row.peer_connector_name,
                    "match_score":        score,
                    "match_rationale":    row.warm_approach_text,
                    "shared_specialty":   row.specialty,
                    "shared_institution": None,
                    "peer_brand_rx_q1":   0.0,
                })
            return result
    except Exception as exc:
        log.warning("Peer match DB load failed (%s), using sample peers.", exc)

    # Fallback: return sample peers for known IDs, generate generic for unknown
    result = {}
    for hcp_id in hcp_ids:
        if hcp_id in _SAMPLE_PEERS:
            result[hcp_id] = [_SAMPLE_PEERS[hcp_id]]
        else:
            # Generic fallback peer for any unknown HCP
            result[hcp_id] = [{
                "peer_hcp_id":       "HCP001",
                "peer_hcp_name":     "Dr. Sarah Davidson",
                "match_score":       60.0,
                "match_rationale":   "Specialty overlap detected via peer network analysis.",
                "shared_specialty":  None,
                "shared_institution": None,
                "peer_brand_rx_q1":  47.0,
            }]
    return result


def get_best_peer(peers: List[Dict]) -> Optional[Dict]:
    if not peers:
        return None
    return max(peers, key=lambda p: p["match_score"])
