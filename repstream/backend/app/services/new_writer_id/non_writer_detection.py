"""Identify in-class non-brand Rx HCPs (new writer candidates) for Module 2."""
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.territory_prioritization import HealthcarePractitioner, PrescriberSales


def detect_non_writers(
    db: Session,
    territory_id: str,
    year_q1: int,
    quarter_q1: int,
    year_q4: int,
    quarter_q4: int,
) -> List[Dict]:
    """Return HCPs who write in-class Rx but zero brand Rx in both Q1 and Q4.

    Non-writer = in_class_rx_q1 > 0  AND  brand_rx_q1 == 0  AND  brand_rx_q4 == 0
    """
    # Aggregate both brand and in-class Rx per HCP per quarter
    stmt = (
        select(
            PrescriberSales.hcp_id,
            PrescriberSales.year,
            PrescriberSales.quarter,
            func.sum(PrescriberSales.total_rx).label("total_rx"),
            PrescriberSales.is_brand,
            func.max(PrescriberSales.competitor_brand).label("competitor_brand"),
            func.sum(PrescriberSales.competitor_rx).label("competitor_rx"),
        )
        .where(
            PrescriberSales.territory_id == territory_id,
            (
                ((PrescriberSales.year == year_q1) & (PrescriberSales.quarter == quarter_q1))
                | ((PrescriberSales.year == year_q4) & (PrescriberSales.quarter == quarter_q4))
            ),
        )
        .group_by(
            PrescriberSales.hcp_id,
            PrescriberSales.year,
            PrescriberSales.quarter,
            PrescriberSales.is_brand,
        )
    )
    rows = db.execute(stmt).all()

    # Build per-HCP aggregation
    hcp_rx: Dict[str, Dict] = {}
    for row in rows:
        if row.hcp_id not in hcp_rx:
            hcp_rx[row.hcp_id] = {
                "in_class_rx_q1": 0.0,
                "brand_rx_q1": 0.0,
                "brand_rx_q4": 0.0,
                "competitor_brand": row.competitor_brand or "",
                "competitor_volume": 0.0,
            }
        is_current_q = row.year == year_q1 and row.quarter == quarter_q1
        is_prior_q = row.year == year_q4 and row.quarter == quarter_q4

        if row.is_brand == 0 and is_current_q:
            hcp_rx[row.hcp_id]["in_class_rx_q1"] += float(row.total_rx or 0)
            hcp_rx[row.hcp_id]["competitor_volume"] += float(row.competitor_rx or 0)
        elif row.is_brand == 1 and is_current_q:
            hcp_rx[row.hcp_id]["brand_rx_q1"] += float(row.total_rx or 0)
        elif row.is_brand == 1 and is_prior_q:
            hcp_rx[row.hcp_id]["brand_rx_q4"] += float(row.total_rx or 0)

    # Filter to non-writers
    return [
        {"hcp_id": hcp_id, **rx_data}
        for hcp_id, rx_data in hcp_rx.items()
        if rx_data["in_class_rx_q1"] > 0
        and rx_data["brand_rx_q1"] == 0
        and rx_data["brand_rx_q4"] == 0
    ]


def enrich_with_hcp_dimensions(
    db: Session,
    non_writers: List[Dict],
    territory_id: str,
) -> List[Dict]:
    """Join non-writer Rx data with HCP dimension data."""
    hcp_ids = [nw["hcp_id"] for nw in non_writers]
    if not hcp_ids:
        return []

    stmt = select(HealthcarePractitioner).where(
        HealthcarePractitioner.hcp_id.in_(hcp_ids),
        HealthcarePractitioner.territory_id == territory_id,
        HealthcarePractitioner.is_active.is_(True),
    )
    hcp_map = {h.hcp_id: h for h in db.scalars(stmt).all()}

    enriched = []
    for nw in non_writers:
        hcp = hcp_map.get(nw["hcp_id"])
        if hcp is None:
            continue
        enriched.append(
            {
                **nw,
                "name": hcp.hcp_full_name or f"{hcp.hcp_first_name} {hcp.hcp_last_name}",
                "specialty": hcp.specialty,
                "city": hcp.city,
                "state": hcp.state,
                "segment": hcp.hcp_segment,
                "icd10_codes_raw": hcp.icd10_codes or "",
            }
        )
    return enriched
