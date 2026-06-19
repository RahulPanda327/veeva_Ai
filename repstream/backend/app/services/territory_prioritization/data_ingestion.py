"""Pull and join HCP, prescriber-sales, and call-activity tables for Module 1."""
from datetime import date, timedelta
from typing import List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.territory_prioritization import CallActivity, HealthcarePractitioner, PrescriberSales


def get_current_and_prior_quarter(ref_date: date) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Return (year, quarter) tuples for current and prior quarters relative to ref_date."""
    q = (ref_date.month - 1) // 3 + 1
    year = ref_date.year
    if q == 1:
        return (year, 1), (year - 1, 4)
    return (year, q), (year, q - 1)


def load_territory_hcps(db: Session, territory_id: str) -> List[HealthcarePractitioner]:
    """Return all active HCPs assigned to a territory."""
    stmt = select(HealthcarePractitioner).where(
        HealthcarePractitioner.territory_id == territory_id,
        HealthcarePractitioner.is_active.is_(True),
    )
    return list(db.scalars(stmt).all())


def load_rx_for_territory(
    db: Session,
    territory_id: str,
    year_q1: int,
    quarter_q1: int,
    year_q4: int,
    quarter_q4: int,
) -> dict:
    """Return dict keyed by hcp_id → {"rx_q1": float, "rx_q4": float, "competitor_rx": float, "competitor_brand": str}.

    Aggregates brand Rx and competitor Rx across both quarters.
    """
    stmt = (
        select(
            PrescriberSales.hcp_id,
            PrescriberSales.year,
            PrescriberSales.quarter,
            func.sum(PrescriberSales.total_rx).label("total_rx"),
            func.sum(PrescriberSales.competitor_rx).label("competitor_rx"),
            func.max(PrescriberSales.competitor_brand).label("competitor_brand"),
        )
        .where(
            PrescriberSales.territory_id == territory_id,
            PrescriberSales.is_brand == 1,
            (
                ((PrescriberSales.year == year_q1) & (PrescriberSales.quarter == quarter_q1))
                | ((PrescriberSales.year == year_q4) & (PrescriberSales.quarter == quarter_q4))
            ),
        )
        .group_by(
            PrescriberSales.hcp_id,
            PrescriberSales.year,
            PrescriberSales.quarter,
        )
    )

    rows = db.execute(stmt).all()
    result: dict = {}
    for row in rows:
        if row.hcp_id not in result:
            result[row.hcp_id] = {
                "rx_q1": 0.0,
                "rx_q4": 0.0,
                "competitor_rx": 0.0,
                "competitor_brand": row.competitor_brand or "",
            }
        if row.year == year_q1 and row.quarter == quarter_q1:
            result[row.hcp_id]["rx_q1"] = float(row.total_rx or 0)
            result[row.hcp_id]["competitor_rx"] = float(row.competitor_rx or 0)
        else:
            result[row.hcp_id]["rx_q4"] = float(row.total_rx or 0)
    return result


def load_last_call_dates(db: Session, territory_id: str) -> dict:
    """Return dict keyed by hcp_id → most recent call_date."""
    stmt = (
        select(
            CallActivity.hcp_id,
            func.max(CallActivity.call_date).label("last_call_date"),
        )
        .where(CallActivity.territory_id == territory_id)
        .group_by(CallActivity.hcp_id)
    )
    rows = db.execute(stmt).all()
    return {row.hcp_id: row.last_call_date for row in rows}


def load_call_stats_90d(db: Session, territory_id: str, ref_date: date) -> dict:
    """Return per-HCP 90-day call statistics for interaction impact scoring.

    Returns dict: hcp_id → {
        "days_since_last_call": int | None,
        "call_count_90d": int,
        "last_outcome": str | None,
    }
    """
    cutoff = ref_date - timedelta(days=90)
    stmt = (
        select(
            CallActivity.hcp_id,
            func.count(CallActivity.call_id).label("call_count"),
            func.max(CallActivity.call_date).label("last_call_date"),
            func.max(CallActivity.call_outcome).label("last_outcome"),
        )
        .where(
            CallActivity.territory_id == territory_id,
            CallActivity.call_date >= cutoff,
            CallActivity.is_reached.is_(True),
        )
        .group_by(CallActivity.hcp_id)
    )
    rows = db.execute(stmt).all()

    result = {}
    for row in rows:
        days = (ref_date - row.last_call_date).days if row.last_call_date else None
        result[row.hcp_id] = {
            "days_since_last_call": days,
            "call_count_90d": int(row.call_count or 0),
            "last_outcome": row.last_outcome,
        }
    return result
