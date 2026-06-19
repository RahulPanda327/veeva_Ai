"""Enrich new-writer candidates with peer match % from insight360_peer_match."""
from typing import Dict, List

from sqlalchemy.orm import Session

from app.services.new_writer_id.peer_network import get_best_peer, load_peer_matches


def enrich_with_peer_match(
    db: Session,
    candidates: List[Dict],
    territory_id: str,
) -> List[Dict]:
    """Add peer_match_pct, peer_name, peer_hcp_id to each candidate dict."""
    hcp_ids = [c["hcp_id"] for c in candidates]
    peer_map = load_peer_matches(db, hcp_ids, territory_id)

    for candidate in candidates:
        peers = peer_map.get(candidate["hcp_id"], [])
        best = get_best_peer(peers)
        if best:
            candidate["peer_match_pct"] = round(best["match_score"], 1)
            candidate["peer_name"] = best["peer_hcp_name"]
            candidate["peer_hcp_id"] = best["peer_hcp_id"]
        else:
            candidate["peer_match_pct"] = 0.0
            candidate["peer_name"] = None
            candidate["peer_hcp_id"] = None

    # Sort by peer_match_pct descending, then by in_class_rx_q1 descending
    return sorted(
        candidates,
        key=lambda c: (-c["peer_match_pct"], -c["in_class_rx_q1"]),
    )
