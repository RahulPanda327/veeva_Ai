"""Payer Access service — reads insight360_payer_access."""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.models.payer_access import PayerAccess
from app.schemas.action_center import PayerAccessItem, PayerAccessResponse


def _tier_change_direction(current: int | None, previous: int | None) -> str:
    if current is None or previous is None:
        return "UNCHANGED"
    if current < previous:
        return "UPGRADE"
    if current > previous:
        return "DOWNGRADE"
    return "UNCHANGED"


def _access_impact(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def get_payer_access(db: Session, territory_id: str) -> PayerAccessResponse:
    rows: List[PayerAccess] = (
        db.query(PayerAccess)
        .filter(PayerAccess.territory_id == territory_id)
        .order_by(PayerAccess.ai_impact_score.desc())
        .all()
    )

    items: List[PayerAccessItem] = []
    for r in rows:
        raw_score = r.ai_impact_score or 0.0
        direction = r.ai_tier_change_direction or _tier_change_direction(
            r.product_tier_current, r.product_tier_previous
        )
        impact = r.ai_access_impact or _access_impact(raw_score)

        items.append(
            PayerAccessItem(
                access_id=r.access_id,
                payer_name=r.payer_name or "",
                territory_id=r.territory_id,
                period=r.period,
                product_tier_current=r.product_tier_current,
                product_tier_previous=r.product_tier_previous,
                tier_change_date=str(r.tier_change_date) if r.tier_change_date else None,
                formulary_status=r.formulary_status,
                covered_lives=r.covered_lives or 0,
                affected_hcp_count=r.affected_hcp_count or 0,
                patient_assistance_available=bool(r.patient_assistance_available),
                ai_impact_score=round(raw_score, 2),
                ai_access_impact=impact,
                ai_action_required=r.ai_action_required,
                ai_patient_assistance_note=r.ai_patient_assistance_note,
                ai_tier_change_direction=direction,
                ai_is_flagged=True,
            )
        )

    high_count = sum(1 for i in items if i.ai_access_impact == "High")
    total_lives_at_risk = sum(
        i.covered_lives for i in items if i.ai_access_impact in ("High", "Medium")
    )
    total_hcps = sum(i.affected_hcp_count for i in items)

    return PayerAccessResponse(
        items=items,
        total=len(items),
        ai_high_impact_count=high_count,
        ai_total_covered_lives_at_risk=total_lives_at_risk,
        ai_total_affected_hcps=total_hcps,
    )
