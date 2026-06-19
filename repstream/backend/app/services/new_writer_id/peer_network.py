"""Graph traversal for peer network lookup in Module 2."""
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.new_writer_id import PeerMatch


def load_peer_matches(
    db: Session,
    hcp_ids: List[str],
    territory_id: str,
) -> Dict[str, List[Dict]]:
    """Return peer match records keyed by hcp_id, sorted by match_score desc."""
    if not hcp_ids:
        return {}

    stmt = (
        select(PeerMatch)
        .where(
            PeerMatch.hcp_id.in_(hcp_ids),
            PeerMatch.territory_id == territory_id,
        )
        .order_by(PeerMatch.match_score.desc())
    )
    rows = db.scalars(stmt).all()

    result: Dict[str, List[Dict]] = {}
    for row in rows:
        result.setdefault(row.hcp_id, []).append(
            {
                "peer_hcp_id": row.peer_hcp_id,
                "peer_hcp_name": row.peer_hcp_name,
                "match_score": row.match_score,
                "match_rationale": row.match_rationale,
                "shared_specialty": row.shared_specialty,
                "shared_institution": row.shared_institution,
                "peer_brand_rx_q1": row.peer_brand_rx_q1,
            }
        )
    return result


def get_best_peer(peers: List[Dict]) -> Optional[Dict]:
    """Return the peer with the highest match_score, or None if no peers exist."""
    if not peers:
        return None
    return max(peers, key=lambda p: p["match_score"])
