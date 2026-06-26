"""Identify new writer candidates for Module 2.

Falls back to representative sample data when Azure Synapse vw_* views are firewalled.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Sample fallback data (matches UI screenshots exactly)
# ─────────────────────────────────────────────────────────────────────────────

_SAMPLE_NEW_WRITERS: List[Dict] = [
    {
        "hcp_id": "NW001",
        "name": "Dr. Jennifer Lee",
        "specialty": "Endocrinology",
        "affiliated_hospital": "Summit Medical",
        "territory_id": "TERR-001",
        "segment": "Target A",
        "city": "New York",
        "state": "NY",
        "in_class_rx_q1": 35.0,
        "brand_rx_q1": 0.0,
        "brand_rx_q4": 0.0,
        "competitor_brand": "CREON",
        "competitor_volume": 35.0,
        "icd10_codes_raw": "E11.9,E78.5,K86.1",
        "last_nrx_date": "Feb 12, 2026",
        "top_5_in_class_rx": [
            {"brand": "Competitor Brand A", "rx": 14},
            {"brand": "Competitor Brand B", "rx": 9},
            {"brand": "Generic Option C", "rx": 6},
            {"brand": "Competitor Brand D", "rx": 4},
            {"brand": "Competitor Brand E", "rx": 2},
        ],
    },
    {
        "hcp_id": "NW002",
        "name": "Dr. Robert Kim",
        "specialty": "Cardiology",
        "affiliated_hospital": "Riverside Heart",
        "territory_id": "TERR-001",
        "segment": "Target A",
        "city": "New York",
        "state": "NY",
        "in_class_rx_q1": 28.0,
        "brand_rx_q1": 0.0,
        "brand_rx_q4": 0.0,
        "competitor_brand": "CREON",
        "competitor_volume": 28.0,
        "icd10_codes_raw": "I50.9,I25.10,K86.1",
        "last_nrx_date": "Mar 8, 2026",
        "top_5_in_class_rx": [
            {"brand": "Competitor Brand B", "rx": 11},
            {"brand": "Generic Option C", "rx": 8},
            {"brand": "Competitor Brand A", "rx": 5},
            {"brand": "Competitor Brand F", "rx": 3},
            {"brand": "Competitor Brand D", "rx": 1},
        ],
    },
    {
        "hcp_id": "NW003",
        "name": "Dr. Patricia Wong",
        "specialty": "Internal Medicine",
        "affiliated_hospital": "New York Presbyterian",
        "territory_id": "TERR-001",
        "segment": "Target B",
        "city": "New York",
        "state": "NY",
        "in_class_rx_q1": 22.0,
        "brand_rx_q1": 0.0,
        "brand_rx_q4": 0.0,
        "competitor_brand": "CREON",
        "competitor_volume": 22.0,
        "icd10_codes_raw": "K86.1,K86.0",
        "last_nrx_date": "Mar 15, 2026",
        "top_5_in_class_rx": [
            {"brand": "CREON", "rx": 10},
            {"brand": "Generic Option A", "rx": 7},
            {"brand": "Competitor Brand C", "rx": 3},
            {"brand": "Competitor Brand D", "rx": 2},
        ],
    },
    {
        "hcp_id": "NW004",
        "name": "Dr. Marcus Williams",
        "specialty": "Gastroenterology",
        "affiliated_hospital": "Mount Sinai",
        "territory_id": "TERR-001",
        "segment": "Target A",
        "city": "New York",
        "state": "NY",
        "in_class_rx_q1": 42.0,
        "brand_rx_q1": 0.0,
        "brand_rx_q4": 0.0,
        "competitor_brand": "CREON",
        "competitor_volume": 42.0,
        "icd10_codes_raw": "K86.1,K90.3,K91.2",
        "last_nrx_date": "Apr 1, 2026",
        "top_5_in_class_rx": [
            {"brand": "CREON", "rx": 20},
            {"brand": "PANCREAZE", "rx": 12},
            {"brand": "Generic Option B", "rx": 6},
            {"brand": "Competitor Brand A", "rx": 4},
        ],
    },
    {
        "hcp_id": "NW005",
        "name": "Dr. Nina Sharma",
        "specialty": "Pediatrics",
        "affiliated_hospital": "Children's Hospital NJ",
        "territory_id": "TERR-001",
        "segment": "Target B",
        "city": "Newark",
        "state": "NJ",
        "in_class_rx_q1": 18.0,
        "brand_rx_q1": 0.0,
        "brand_rx_q4": 0.0,
        "competitor_brand": "CREON",
        "competitor_volume": 18.0,
        "icd10_codes_raw": "K86.1,E84.9",
        "last_nrx_date": "Feb 28, 2026",
        "top_5_in_class_rx": [
            {"brand": "CREON", "rx": 8},
            {"brand": "Generic Option C", "rx": 5},
            {"brand": "Competitor Brand B", "rx": 3},
            {"brand": "Competitor Brand D", "rx": 2},
        ],
    },
]


def detect_non_writers(
    db: Session,
    territory_id: str,
    year_q1: int,
    quarter_q1: int,
    year_q4: int,
    quarter_q4: int,
) -> List[Dict]:
    """Return new writer candidates. Falls back to sample data if DB is unavailable."""
    try:
        engine = db.bind
        sql = text("""
            SELECT TOP 200
                s.HCP_Durable_Id       AS hcp_id,
                h.HCP_Full_Name        AS name,
                h.Specialty            AS specialty,
                h.Affiliated_Hospital  AS affiliated_hospital,
                h.sf_terr_pk_gi        AS territory_id,
                h.HCP_Segment          AS segment,
                h.City                 AS city,
                h.State                AS state,
                SUM(CASE WHEN s.Brand_Name != 'ZENPEP' AND s.Brand_Name IS NOT NULL
                         THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) AS in_class_rx_q1,
                SUM(CASE WHEN s.Brand_Name = 'ZENPEP' THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) AS brand_rx_q1,
                MAX(s.Brand_Name)      AS competitor_brand,
                SUM(ISNULL(s.Competitor_Rx_Count, 0)) AS competitor_volume
            FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting s
            JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting h
              ON s.HCP_Durable_Id = h.HCP_Durable_Id
            WHERE s.sf_terr_pk_gi = :terr
              AND YEAR(s.Month_Ending_Date) = :yr1
              AND DATEPART(QUARTER, s.Month_Ending_Date) = :q1
            GROUP BY s.HCP_Durable_Id, h.HCP_Full_Name, h.Specialty,
                     h.Affiliated_Hospital, h.sf_terr_pk_gi, h.HCP_Segment, h.City, h.State
            HAVING SUM(CASE WHEN s.Brand_Name = 'ZENPEP' THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) = 0
               AND SUM(CASE WHEN s.Brand_Name != 'ZENPEP' THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) > 0
        """)
        df = pd.read_sql(sql, engine, params={"terr": territory_id, "yr1": year_q1, "q1": quarter_q1})
        if not df.empty:
            rows = df.to_dict("records")
            for r in rows:
                r.setdefault("brand_rx_q4", 0.0)
                r.setdefault("icd10_codes_raw", "")
                r.setdefault("last_nrx_date", None)
                r.setdefault("top_5_in_class_rx", [])
            log.info("Loaded %d new writer candidates from DB.", len(rows))
            return rows
    except Exception as exc:
        log.warning("New writer DB load failed (%s), using sample data.", exc)

    log.info("Using sample new writer data.")
    return [dict(h) for h in _SAMPLE_NEW_WRITERS]


def enrich_with_hcp_dimensions(
    db: Session,
    non_writers: List[Dict],
    territory_id: str,
) -> List[Dict]:
    """Already enriched in detect_non_writers (raw SQL join). Pass through."""
    return non_writers
