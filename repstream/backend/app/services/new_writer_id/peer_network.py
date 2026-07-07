"""Peer network lookup for new writer candidates in Module 2.

Implements KPI 7 verbatim (kb/sql_queries/sql_query_kpi_7to19.sql, lines 26-58) —
peer network matching + warm approach recommendations, enriched with live HCP
and territory context. Reads exclusively from insight360_peer_match (+ enrichment
joins). Returns {} if the DB is unavailable or has no matches — no sample fallback.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import text
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
    FROM hub_insight360.insight360_peer_match pm
    -- Enrich with live dim data where available
    LEFT JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting h
           ON h.HCP_Durable_Id = pm.HCP_Durable_Id
    LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting at2
           ON at2.HCP_Durable_Id = pm.HCP_Durable_Id
          AND at2.sales_force = 'Commercial_Sales_Field_Force'
    LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting tm
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
