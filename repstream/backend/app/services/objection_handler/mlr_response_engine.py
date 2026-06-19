"""Look up best MLR-approved response for an objection type from Module 3."""
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.objection_handler import ObjectionHandler


def get_best_mlr_response(
    db: Session,
    objection_id: str,
) -> Optional[Dict]:
    """Fetch the ObjectionHandler row directly by objection_id."""
    stmt = select(ObjectionHandler).where(ObjectionHandler.objection_id == objection_id)
    row = db.scalars(stmt).first()
    if row is None:
        return None
    return {
        "objection_id": row.objection_id,
        "objection_type": row.objection_type,
        "objection_text": row.objection_text,
        "recommended_response": row.recommended_response,
        "response_source": row.response_source,
        "sku": row.sku,
        "success_rate": row.success_rate,
        "hcp_segment": row.hcp_segment,
    }


def get_best_response_for_type(
    db: Session,
    objection_type: str,
    hcp_segment: Optional[str] = None,
) -> Optional[Dict]:
    """Return the MLR response row with highest success_rate for a given objection type."""
    stmt = (
        select(ObjectionHandler)
        .where(ObjectionHandler.objection_type == objection_type)
        .order_by(ObjectionHandler.success_rate.desc())
    )
    if hcp_segment:
        stmt = stmt.where(ObjectionHandler.hcp_segment == hcp_segment)

    row = db.scalars(stmt).first()
    if row is None:
        return None

    return {
        "objection_id": row.objection_id,
        "objection_type": row.objection_type,
        "objection_text": row.objection_text,
        "recommended_response": row.recommended_response,
        "response_source": row.response_source,
        "sku": row.sku,
        "success_rate": row.success_rate,
        "hcp_segment": row.hcp_segment,
    }


def load_all_objections(
    db: Session,
    territory_id: str,
    period: Optional[str] = None,
) -> list:
    """Load all objection rows for a territory, optionally filtered by period."""
    stmt = select(ObjectionHandler).where(ObjectionHandler.territory_id == territory_id)
    if period:
        stmt = stmt.where(ObjectionHandler.period == period)
    stmt = stmt.order_by(ObjectionHandler.success_rate.desc())
    return list(db.scalars(stmt).all())
