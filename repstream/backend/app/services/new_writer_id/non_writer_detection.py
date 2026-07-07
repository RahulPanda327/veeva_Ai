"""Identify new writer candidates for Module 2.

Reads exclusively from Azure Synapse. Returns [] if the DB is unavailable
or has no matching rows — no sample-data fallback.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def _latest_quarter_with_data(engine) -> Optional[tuple]:
    """Return (year, quarter) of the most recent Month_Ending_Date in the fact view.

    Rx data always lags behind the calendar, so the requested "current quarter"
    frequently has zero rows yet. Falling back to the latest quarter that
    actually has data keeps this module fully DB-driven instead of hardcoding a period.
    """
    try:
        df = pd.read_sql(
            text("""
                SELECT MAX(TRY_CAST(Month_Ending_Date AS DATE)) AS max_dt
                FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting
            """),
            engine,
        )
        max_dt = df["max_dt"].iloc[0]
        if max_dt is None:
            return None
        return (max_dt.year, (max_dt.month - 1) // 3 + 1)
    except Exception as exc:
        log.warning("Could not determine latest available quarter (%s).", exc)
        return None


def _query_non_writers(
    engine, territory_id: str, year_q1: int, quarter_q1: int, year_q4: int, quarter_q4: int
) -> pd.DataFrame:
    # KPI-7-driven candidate list: insight360_peer_match IS the curated set of
    # "likely to start prescribing" HCPs (per the user's CTE query). Enriched with
    # live HCP dim + territory hierarchy + per-HCP Rx aggregates (pre-aggregated
    # in the rx CTE to avoid the fact-table fan-out of a raw join).
    # NOTE: candidates are the KPI list — not filtered by the rep's territory.
    sql = text("""
        WITH rx AS (
            SELECT
                s.HCP_Durable_Id,
                SUM(CASE WHEN YEAR(TRY_CAST(s.Month_Ending_Date AS DATE)) = :yr1
                          AND DATEPART(QUARTER, TRY_CAST(s.Month_Ending_Date AS DATE)) = :q1
                          AND s.Brand_Name != 'ZENPEP' AND s.Brand_Name IS NOT NULL
                     THEN ISNULL(TRY_CAST(s.Total_Rx_Count AS FLOAT), 0) ELSE 0 END) AS in_class_rx_q1,
                SUM(CASE WHEN YEAR(TRY_CAST(s.Month_Ending_Date AS DATE)) = :yr1
                          AND DATEPART(QUARTER, TRY_CAST(s.Month_Ending_Date AS DATE)) = :q1
                          AND s.Brand_Name = 'ZENPEP'
                     THEN ISNULL(TRY_CAST(s.Total_Rx_Count AS FLOAT), 0) ELSE 0 END) AS brand_rx_q1,
                SUM(CASE WHEN YEAR(TRY_CAST(s.Month_Ending_Date AS DATE)) = :yr4
                          AND DATEPART(QUARTER, TRY_CAST(s.Month_Ending_Date AS DATE)) = :q4
                          AND s.Brand_Name = 'ZENPEP'
                     THEN ISNULL(TRY_CAST(s.Total_Rx_Count AS FLOAT), 0) ELSE 0 END) AS brand_rx_q4,
                MAX(CASE WHEN s.Brand_Name != 'ZENPEP'
                          AND ISNULL(TRY_CAST(s.New_Rx_Count AS FLOAT), 0) > 0
                     THEN TRY_CAST(s.Week_Ending_Date AS DATE) END) AS last_nrx_date,
                MAX(CASE WHEN s.Brand_Name != 'ZENPEP' THEN s.Brand_Name END) AS competitor_brand
            FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting s
            WHERE s.HCP_Durable_Id IN (SELECT HCP_Durable_Id FROM hub_insight360.insight360_peer_match)
            GROUP BY s.HCP_Durable_Id
        )
        SELECT
            pm.HCP_Durable_Id          AS hcp_id,
            pm.HCP_Full_Name           AS name,
            pm.Specialty               AS specialty,
            pm.City_State              AS city_state,
            h.Segment_Description      AS segment,
            h.Email_1                  AS email,
            tm.Territory_Durable_Id    AS territory_id,
            tm.Territory_Name          AS territory_name,
            rx.in_class_rx_q1,
            rx.brand_rx_q1,
            rx.brand_rx_q4,
            rx.last_nrx_date,
            rx.competitor_brand
        FROM hub_insight360.insight360_peer_match pm
        LEFT JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting h
               ON h.HCP_Durable_Id = pm.HCP_Durable_Id
        LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting at2
               ON at2.HCP_Durable_Id = pm.HCP_Durable_Id
              AND at2.sales_force = 'Commercial_Sales_Field_Force'
        LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting tm
               ON tm.Territory_Durable_Id = at2.Territory_Durable_Id
        LEFT JOIN rx
               ON rx.HCP_Durable_Id = pm.HCP_Durable_Id
        ORDER BY CAST(REPLACE(pm.Peer_Match_Pct, '%', '') AS DECIMAL(5,1)) DESC
    """)
    return pd.read_sql(sql, engine, params={
        "yr1": year_q1, "q1": quarter_q1, "yr4": year_q4, "q4": quarter_q4,
    })


def _query_top5_by_brand(engine, year: int, quarter: int) -> Dict[str, List[Dict]]:
    """Top 5 in-class brands by Rx volume per peer-match HCP, over the trailing
    4 quarters ending at the effective quarter (single quarters are too sparse —
    HCPs quiet for one quarter would show an empty brand table)."""
    q_start_month = 3 * quarter - 2
    win_end   = pd.Timestamp(year, q_start_month, 1) + pd.DateOffset(months=3) - pd.DateOffset(days=1)
    win_start = pd.Timestamp(year, q_start_month, 1) - pd.DateOffset(months=9)
    sql = text("""
        WITH ranked AS (
            SELECT
                s.HCP_Durable_Id AS hcp_id,
                s.Brand_Name     AS brand,
                SUM(ISNULL(TRY_CAST(s.Total_Rx_Count AS FLOAT), 0)) AS rx,
                ROW_NUMBER() OVER (
                    PARTITION BY s.HCP_Durable_Id
                    ORDER BY SUM(ISNULL(TRY_CAST(s.Total_Rx_Count AS FLOAT), 0)) DESC
                ) AS rn
            FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting s
            WHERE s.HCP_Durable_Id IN (SELECT HCP_Durable_Id FROM hub_insight360.insight360_peer_match)
              AND s.Brand_Name != 'ZENPEP' AND s.Brand_Name IS NOT NULL
              AND TRY_CAST(s.Month_Ending_Date AS DATE) BETWEEN :win_start AND :win_end
            GROUP BY s.HCP_Durable_Id, s.Brand_Name
        )
        SELECT hcp_id, brand, rx FROM ranked WHERE rn <= 5 ORDER BY hcp_id, rn
    """)
    df = pd.read_sql(sql, engine, params={
        "win_start": win_start.strftime("%Y-%m-%d"), "win_end": win_end.strftime("%Y-%m-%d"),
    })
    result: Dict[str, List[Dict]] = {}
    for row in df.to_dict("records"):
        result.setdefault(row["hcp_id"], []).append({"brand": row["brand"], "rx": int(row["rx"])})
    return result


def detect_non_writers(
    db: Session,
    territory_id: str,
    year_q1: int,
    quarter_q1: int,
    year_q4: int,
    quarter_q4: int,
) -> List[Dict]:
    """Return new writer candidates from the DB. Returns [] if the DB is unavailable
    or has no matching rows — no sample-data fallback."""
    try:
        engine = db.bind

        # Rx data lags the calendar — resolve the effective quarter up-front
        # (the KPI 7 candidate list itself is quarter-independent).
        latest = _latest_quarter_with_data(engine)
        if latest and latest != (year_q1, quarter_q1):
            log.info(
                "Using latest available Rx quarter %d-Q%d instead of %d-Q%d.",
                latest[0], latest[1], year_q1, quarter_q1,
            )
            year_q1, quarter_q1 = latest
            if quarter_q1 == 1:
                year_q4, quarter_q4 = year_q1 - 1, 4
            else:
                year_q4, quarter_q4 = year_q1, quarter_q1 - 1

        df = _query_non_writers(engine, territory_id, year_q1, quarter_q1, year_q4, quarter_q4)
        if df.empty:
            log.info("No new writer candidates found in DB.")
            return []
        # LEFT JOIN NULLs become NaN in pandas — NaN is truthy, breaks `or 0` guards,
        # and is rejected by FastAPI's JSON encoder. Normalize to None first.
        df = df.astype(object).where(df.notna(), None)

        # Per-brand breakdown for the same quarter (one windowed query)
        top5_map = _query_top5_by_brand(engine, year_q1, quarter_q1)

        rows = df.to_dict("records")
        for r in rows:
            # City_State "Seattle, WA" → separate city / state keys
            city_state = (r.pop("city_state", None) or "")
            parts = [p.strip() for p in city_state.split(",")]
            r["city"]  = parts[0] if parts and parts[0] else None
            r["state"] = parts[1] if len(parts) > 1 else None
            r["territory_id"] = r.get("territory_id") or ""
            r["in_class_rx_q1"] = float(r.get("in_class_rx_q1") or 0)
            r["brand_rx_q1"]    = float(r.get("brand_rx_q1") or 0)
            r["brand_rx_q4"]    = float(r.get("brand_rx_q4") or 0)
            r["competitor_volume"]  = r["in_class_rx_q1"]  # no separate Competitor_Rx_Count column exists
            r["affiliated_hospital"] = ""   # no source column on the HCP dimension view — send ""
            r["icd10_codes_raw"]     = ""   # no source column on the HCP dimension view
            # NBRx: latest week with a new in-class Rx → "Apr 10, 2026"
            nbrx = r.get("last_nrx_date")
            r["last_nrx_date"] = nbrx.strftime("%b %d, %Y") if nbrx is not None and not pd.isna(nbrx) else None
            top5 = top5_map.get(r["hcp_id"], [])
            r["top_5_in_class_rx"] = top5
            if top5:
                # Primary competitor = highest-volume in-class brand, not alphabetical MAX
                r["competitor_brand"] = top5[0]["brand"]
                # Card totals reflect the same trailing-4-quarter window as the brand table
                r["total_in_class_rx"] = float(sum(b["rx"] for b in top5))
                r["competitor_volume"] = r["total_in_class_rx"]
        log.info("Loaded %d new writer candidates from DB (KPI 7 peer-match driven).", len(rows))
        return rows
    except Exception as exc:
        log.warning("New writer DB load failed (%s). Returning no candidates.", exc)
        return []


def enrich_with_hcp_dimensions(
    db: Session,
    non_writers: List[Dict],
    territory_id: str,
) -> List[Dict]:
    """Already enriched in detect_non_writers (raw SQL join). Pass through."""
    return non_writers
