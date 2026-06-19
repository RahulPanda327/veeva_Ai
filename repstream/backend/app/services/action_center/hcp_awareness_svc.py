"""HCP Awareness service — reads insight360_hcp_awareness."""
from __future__ import annotations

import json
from typing import List

from sqlalchemy.orm import Session

from app.models.hcp_awareness import HCPAwareness
from app.schemas.action_center import HCPAwarenessItem, HCPAwarenessResponse


def _awareness_level(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _parse_json_list(raw: str | None) -> List[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []


def get_hcp_awareness(db: Session, territory_id: str) -> HCPAwarenessResponse:
    rows: List[HCPAwareness] = (
        db.query(HCPAwareness)
        .filter(HCPAwareness.territory_id == territory_id)
        .order_by(HCPAwareness.ai_awareness_score.desc())
        .all()
    )

    items: List[HCPAwarenessItem] = []
    for r in rows:
        raw_score = r.ai_awareness_score or 0.0
        level = r.ai_awareness_level or _awareness_level(raw_score)
        items.append(
            HCPAwarenessItem(
                awareness_id=r.awareness_id,
                hcp_id=r.hcp_id,
                hcp_full_name=r.hcp_full_name or r.hcp_id,
                specialty=r.specialty,
                territory_id=r.territory_id,
                period=r.period,
                product_awareness_score=r.product_awareness_score or 0.0,
                competitor_awareness_score=r.competitor_awareness_score or 0.0,
                clinical_evidence_score=r.clinical_evidence_score or 0.0,
                total_interactions=r.total_interactions or 0,
                last_interaction_date=str(r.last_interaction_date) if r.last_interaction_date else None,
                ai_awareness_score=round(raw_score, 2),
                ai_awareness_level=level,
                ai_key_messages_delivered=_parse_json_list(r.ai_key_messages_delivered),
                ai_knowledge_gaps=_parse_json_list(r.ai_knowledge_gaps),
                ai_recommended_action=r.ai_recommended_action,
                ai_is_assessed=True,
            )
        )

    high_count = sum(1 for i in items if i.ai_awareness_level == "High")
    med_count = sum(1 for i in items if i.ai_awareness_level == "Medium")
    low_count = sum(1 for i in items if i.ai_awareness_level == "Low")

    return HCPAwarenessResponse(
        items=items,
        total=len(items),
        ai_high_awareness_count=high_count,
        ai_medium_awareness_count=med_count,
        ai_low_awareness_count=low_count,
    )
