"""Peer network lookup for new writer candidates in Module 2.

Implements KPI 7 verbatim (kb/sql_queries/sql_query_kpi_7to19.sql, lines 26-58) —
peer network matching + warm approach recommendations, enriched with live HCP
and territory context. Reads exclusively from insight360_peer_match_dul (+ enrichment
joins). Returns {} if the DB is unavailable or has no matches — no sample fallback.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_KPI7_SQL = text("""
    SELECT
        pm.HCP_Durable_Id,
        pm.HCP_Full_Name,
        pm.Specialty,
        pm.City_State,
        -- Peer match details
        pm.Peer_Match_Pct,
        pm.Peer_Connector_HCP_Id,
        pm.Peer_Connector_Name,
        pm.Warm_Approach_Text,
        -- Enrich with live HCP context from dim table
        h.Target_Decile_Zenpep,
        h.is_gia_tgt                                            AS Is_GIA_Target,
        h.Segment_Description                                   AS Zenpep_Segment,
        -- Territory context
        tm.Territory_Durable_Id,
        tm.Territory_Code,
        tm.Territory_Name,
        tm.District_Name,
        tm.Region_Name,
        CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
    FROM hub_insight360.insight360_peer_match_dul pm
    -- Enrich with live dim data where available
    LEFT JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul h
           ON h.HCP_Durable_Id = pm.HCP_Durable_Id
    LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting_dul at2
           ON at2.HCP_Durable_Id = pm.HCP_Durable_Id
          AND at2.sales_force = 'Commercial_Sales_Field_Force'
    LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting_dul tm
           ON tm.Territory_Durable_Id = at2.Territory_Durable_Id
    -- Remove REPLACE to convert percentage string to numeric for sorting
    ORDER BY
        CAST(REPLACE(pm.Peer_Match_Pct, '%', '') AS DECIMAL(5,1)) DESC
""")


def load_peer_matches(
    db: Session,
    hcp_ids: List[str],
    territory_id: str,
) -> Dict[str, List[Dict]]:
    """Return peer match records keyed by hcp_id. Empty dict if none found in DB."""
    if not hcp_ids:
        return {}

    try:
        engine = db.bind
        df = pd.read_sql(_KPI7_SQL, engine)
        wanted = set(hcp_ids)
        result: Dict[str, List[Dict]] = {}
        for row in df.to_dict("records"):
            if row["HCP_Durable_Id"] not in wanted:
                continue
            # Peer_Match_Pct stored as "87%" — parse to float for sorting
            raw_pct = (row["Peer_Match_Pct"] or "0").replace("%", "")
            score = float(raw_pct) if raw_pct else 0.0
            result.setdefault(row["HCP_Durable_Id"], []).append({
                "peer_hcp_id":        row["Peer_Connector_HCP_Id"],
                "peer_hcp_name":      row["Peer_Connector_Name"],
                "match_score":        score,
                "match_rationale":    row["Warm_Approach_Text"],
                "shared_specialty":   row["Specialty"],
                "shared_institution": None,
                "peer_brand_rx_q1":   0.0,
            })
        return result
    except Exception as exc:
        log.warning("Peer match DB load failed (%s). Returning no peer matches.", exc)
        return {}


def get_best_peer(peers: List[Dict]) -> Optional[Dict]:
    if not peers:
        return None
    return max(peers, key=lambda p: p["match_score"])


_NEAREST_WRITER_SQL = text("""
    SELECT
        at2.Territory_Durable_Id AS territory_id,
        s.HCP_Durable_Id         AS peer_hcp_id,
        b.Formatted_Name         AS peer_hcp_name,
        b.Specialty_Description  AS specialty,
        SUM(ISNULL(TRY_CAST(s.Total_Rx_Count AS FLOAT), 0)) AS zenpep_rx
    FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul s
    JOIN hub_insight360.vw_account_territory_zenpep_reporting_dul at2
      ON at2.HCP_Durable_Id = s.HCP_Durable_Id
     AND at2.sales_force = 'Commercial_Sales_Field_Force'
    JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul b
      ON b.HCP_Durable_Id = s.HCP_Durable_Id
    WHERE s.Brand_Name = 'ZENPEP'
      AND at2.Territory_Durable_Id IN :terr_ids
    GROUP BY at2.Territory_Durable_Id, s.HCP_Durable_Id, b.Formatted_Name, b.Specialty_Description
    HAVING SUM(ISNULL(TRY_CAST(s.Total_Rx_Count AS FLOAT), 0)) > 0
""").bindparams(bindparam("terr_ids", expanding=True))

_SAME_SPECIALTY_SCORE = 78.0
_SAME_TERRITORY_SCORE = 55.0


def find_nearest_zenpep_writers(db: Session, candidates: List[Dict]) -> Dict[str, Dict]:
    """Rule-based fallback peer match for candidates not covered by the curated
    KPI-7 insight360_peer_match_dul list — i.e. live-detected candidates from a
    manager/employee/territory filter (see non_writer_detection.detect_new_writers_for_hcps).

    For each candidate, finds the highest-volume existing ZENPEP writer in the
    same territory — preferring the same specialty — to use as a warm-intro
    peer connector. Fully DB-driven: match_score reflects match quality
    (same specialty+territory vs. territory only); peer identity and Rx
    volume are real prescribing data, not invented. Returns {} for any
    candidate whose territory has no current ZENPEP writer to point to.
    """
    if not candidates:
        return {}
    terr_ids = sorted({c.get("territory_id") for c in candidates if c.get("territory_id")})
    if not terr_ids:
        return {}

    try:
        df = pd.read_sql(_NEAREST_WRITER_SQL, db.bind, params={"terr_ids": terr_ids})
    except Exception as exc:  # noqa: BLE001
        log.warning("Nearest ZENPEP-writer fallback failed (%s).", exc)
        return {}
    if df.empty:
        return {}

    by_terr = {t: g for t, g in df.groupby("territory_id")}

    result: Dict[str, Dict] = {}
    for c in candidates:
        pool = by_terr.get(c.get("territory_id"))
        if pool is None or pool.empty:
            continue
        specialty = (c.get("specialty") or "").strip().lower()
        same_spec = pool[pool["specialty"].fillna("").str.strip().str.lower() == specialty] if specialty else pool.iloc[0:0]
        if not same_spec.empty:
            top, score = same_spec.sort_values("zenpep_rx", ascending=False).iloc[0], _SAME_SPECIALTY_SCORE
        else:
            top, score = pool.sort_values("zenpep_rx", ascending=False).iloc[0], _SAME_TERRITORY_SCORE
        result[c["hcp_id"]] = {
            "match_score": score,
            "peer_hcp_name": top["peer_hcp_name"],
            "peer_hcp_id": top["peer_hcp_id"],
            "match_rationale": (
                f"{top['peer_hcp_name']} in the same territory has written "
                f"{int(top['zenpep_rx'])} Product Rx — worth a warm intro conversation."
            ),
        }
    return result
