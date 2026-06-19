"""Competitive Intel service — reads insight360_competitive_intel."""
from __future__ import annotations

import json
from typing import List

from sqlalchemy.orm import Session

from app.models.competitive_intel import CompetitiveIntel
from app.schemas.action_center import CompetitiveIntelItem, CompetitiveIntelResponse, ICD10Affected


def _threat_level(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _parse_icd10(raw: str | None) -> List[ICD10Affected]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
        return [ICD10Affected(**i) for i in items if isinstance(i, dict)]
    except Exception:
        return []


def get_competitive_intel(db: Session, territory_id: str) -> CompetitiveIntelResponse:
    rows: List[CompetitiveIntel] = (
        db.query(CompetitiveIntel)
        .filter(CompetitiveIntel.territory_id == territory_id)
        .order_by(CompetitiveIntel.ai_threat_score.desc())
        .all()
    )

    items: List[CompetitiveIntelItem] = []
    for r in rows:
        raw_score = r.ai_threat_score or 0.0
        level = r.ai_threat_level or _threat_level(raw_score)
        items.append(
            CompetitiveIntelItem(
                intel_id=r.intel_id,
                competitor_name=r.competitor_name or "",
                territory_id=r.territory_id,
                period=r.period,
                message_theme=r.message_theme,
                detection_date=str(r.detection_date) if r.detection_date else None,
                affected_hcp_count=r.affected_hcp_count or 0,
                market_share_change_pct=r.market_share_change_pct or 0.0,
                icd10_focus=_parse_icd10(r.icd10_focus),
                source_channel=r.source_channel,
                ai_threat_score=round(raw_score, 2),
                ai_threat_level=level,
                ai_counter_strategy=r.ai_counter_strategy,
                ai_supporting_evidence=r.ai_supporting_evidence,
                ai_detection_method=r.ai_detection_method,
                ai_is_analyzed=True,
            )
        )

    high_count = sum(1 for i in items if i.ai_threat_level == "High")
    med_count = sum(1 for i in items if i.ai_threat_level == "Medium")
    avg_score = sum(i.ai_threat_score for i in items) / max(len(items), 1)

    return CompetitiveIntelResponse(
        items=items,
        total=len(items),
        ai_high_threat_count=high_count,
        ai_medium_threat_count=med_count,
        ai_avg_threat_score=round(avg_score, 2),
    )
