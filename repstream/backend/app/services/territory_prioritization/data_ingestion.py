"""
Data ingestion for Territory Prioritization.

Uses raw SQL with confirmed column names from the live DB.
Falls back to representative sample data when Azure Synapse is firewalled.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Quarter helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_current_and_prior_quarter(ref_date: date) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    q = (ref_date.month - 1) // 3 + 1
    year = ref_date.year
    if q == 1:
        return (year, 1), (year - 1, 4)
    return (year, q), (year, q - 1)


# ─────────────────────────────────────────────────────────────────────────────
# Sample fallback data (used when DB is firewalled)
# ─────────────────────────────────────────────────────────────────────────────

_SAMPLE_HCPS = [
    {"hcp_id": "HCP001", "name": "Dr. Sarah Davidson",   "specialty": "Gastroenterology",    "affiliated_hospital": "Memorial Hospital",    "territory_id": "TERR-001", "segment": "Target A", "city": "New York",      "state": "NY", "decile_rank": 2},
    {"hcp_id": "HCP002", "name": "Dr. Michael Chen",     "specialty": "Internal Medicine",   "affiliated_hospital": "Westside Clinic",      "territory_id": "TERR-001", "segment": "New Writer","city": "Brooklyn",     "state": "NY", "decile_rank": 5},
    {"hcp_id": "HCP003", "name": "Dr. Anjali Patel",     "specialty": "Family Practice",     "affiliated_hospital": "North Valley Medical",  "territory_id": "TERR-001", "segment": "Target B", "city": "Newark",       "state": "NJ", "decile_rank": 4},
    {"hcp_id": "HCP004", "name": "Dr. James Morrison",   "specialty": "Gastroenterology",    "affiliated_hospital": "St. Luke's Hospital",  "territory_id": "TERR-001", "segment": "Target A", "city": "New York",      "state": "NY", "decile_rank": 1},
    {"hcp_id": "HCP005", "name": "Dr. Linda Nguyen",     "specialty": "Endocrinology",       "affiliated_hospital": "City Medical Center",   "territory_id": "TERR-001", "segment": "Target B", "city": "Jersey City",   "state": "NJ", "decile_rank": 3},
    {"hcp_id": "HCP006", "name": "Dr. Robert Kim",       "specialty": "Internal Medicine",   "affiliated_hospital": "Harbor Health",        "territory_id": "TERR-001", "segment": "Target A", "city": "New York",      "state": "NY", "decile_rank": 3},
    {"hcp_id": "HCP007", "name": "Dr. Maria Santos",     "specialty": "Gastroenterology",    "affiliated_hospital": "Riverside Medical",    "territory_id": "TERR-001", "segment": "New Writer","city": "Hoboken",       "state": "NJ", "decile_rank": 6},
    {"hcp_id": "HCP008", "name": "Dr. David Thompson",   "specialty": "Family Practice",     "affiliated_hospital": "Elmwood Clinic",       "territory_id": "TERR-001", "segment": "Target B", "city": "Staten Island", "state": "NY", "decile_rank": 5},
    {"hcp_id": "HCP009", "name": "Dr. Rachel Green",     "specialty": "Gastroenterology",    "affiliated_hospital": "University Hospital",  "territory_id": "TERR-001", "segment": "Target A", "city": "New York",      "state": "NY", "decile_rank": 2},
    {"hcp_id": "HCP010", "name": "Dr. Thomas Okafor",    "specialty": "Internal Medicine",   "affiliated_hospital": "Bronx Medical Center", "territory_id": "TERR-001", "segment": "Target B", "city": "Bronx",         "state": "NY", "decile_rank": 7},
    {"hcp_id": "HCP011", "name": "Dr. Emily Walsh",      "specialty": "Endocrinology",       "affiliated_hospital": "Queens General",       "territory_id": "TERR-001", "segment": "Target A", "city": "Queens",        "state": "NY", "decile_rank": 3},
    {"hcp_id": "HCP012", "name": "Dr. Carlos Rivera",    "specialty": "Gastroenterology",    "affiliated_hospital": "Brooklyn Hospital",    "territory_id": "TERR-001", "segment": "New Writer","city": "Brooklyn",      "state": "NY", "decile_rank": 8},
    {"hcp_id": "HCP013", "name": "Dr. Susan Park",       "specialty": "Family Practice",     "affiliated_hospital": "Manhattan Clinic",     "territory_id": "TERR-001", "segment": "Target B", "city": "New York",      "state": "NY", "decile_rank": 6},
    {"hcp_id": "HCP014", "name": "Dr. Andrew Wilson",    "specialty": "Internal Medicine",   "affiliated_hospital": "Summit Health",        "territory_id": "TERR-001", "segment": "Target A", "city": "Newark",        "state": "NJ", "decile_rank": 4},
    {"hcp_id": "HCP015", "name": "Dr. Jessica Lee",      "specialty": "Gastroenterology",    "affiliated_hospital": "Atlantic Medical",     "territory_id": "TERR-001", "segment": "Target B", "city": "Jersey City",   "state": "NJ", "decile_rank": 5},
]

# Monthly Rx history (12 months): realistic patterns per HCP
_SAMPLE_RX: Dict[str, List[float]] = {
    "HCP001": [32, 35, 38, 40, 37, 42, 44, 45, 43, 47, 45, 47],  # growing
    "HCP002": [0,  0,  0,  0,  0,  0,  0,  0,  0,  4,  8,  12],  # new writer
    "HCP003": [28, 29, 30, 29, 31, 30, 31, 32, 30, 31, 31, 31],  # stable
    "HCP004": [50, 52, 55, 58, 54, 60, 62, 65, 63, 67, 66, 68],  # high volume growing
    "HCP005": [22, 24, 23, 22, 20, 19, 18, 17, 16, 15, 14, 13],  # declining
    "HCP006": [38, 40, 39, 41, 43, 42, 45, 44, 46, 48, 47, 48],  # steady growth
    "HCP007": [0,  0,  0,  0,  0,  0,  0,  2,  5,  7, 10, 12],  # new writer ramp
    "HCP008": [18, 19, 20, 19, 18, 20, 19, 21, 20, 21, 21, 21],  # stable medium
    "HCP009": [45, 47, 49, 50, 48, 52, 54, 55, 53, 56, 55, 57],  # high value
    "HCP010": [15, 14, 13, 12, 11, 11, 10, 10,  9,  9,  8,  8],  # declining
    "HCP011": [30, 32, 33, 35, 34, 36, 38, 39, 38, 40, 41, 42],  # improving
    "HCP012": [0,  0,  0,  0,  0,  0,  0,  0,  3,  5,  8, 12],  # new writer
    "HCP013": [16, 17, 16, 17, 17, 16, 17, 18, 17, 17, 18, 18],  # stable low
    "HCP014": [35, 36, 38, 37, 39, 40, 42, 41, 43, 44, 45, 46],  # growing
    "HCP015": [20, 21, 22, 21, 22, 23, 22, 24, 23, 25, 24, 26],  # gradual growth
}

# Competitor Rx per HCP (last 3 months average)
_SAMPLE_COMP: Dict[str, float] = {
    "HCP001": 8, "HCP002": 3, "HCP003": 12, "HCP004": 10,
    "HCP005": 18, "HCP006": 7, "HCP007": 2, "HCP008": 9,
    "HCP009": 6,  "HCP010": 15,"HCP011": 5, "HCP012": 1,
    "HCP013": 11, "HCP014": 6, "HCP015": 8,
}

_SAMPLE_CALLS = {
    "HCP001": {"last_call_date": date(2026, 3, 31), "call_count_90d": 3, "last_outcome": "Positive"},
    "HCP002": {"last_call_date": date(2026, 4, 23), "call_count_90d": 1, "last_outcome": "Neutral"},
    "HCP003": {"last_call_date": date(2026, 4, 21), "call_count_90d": 2, "last_outcome": "Positive"},
    "HCP004": {"last_call_date": date(2026, 4, 25), "call_count_90d": 4, "last_outcome": "Very Positive"},
    "HCP005": {"last_call_date": date(2026, 2, 10), "call_count_90d": 1, "last_outcome": "Negative"},
    "HCP006": {"last_call_date": date(2026, 4, 18), "call_count_90d": 3, "last_outcome": "Positive"},
    "HCP007": {"last_call_date": date(2026, 4, 20), "call_count_90d": 1, "last_outcome": "Neutral"},
    "HCP008": {"last_call_date": date(2026, 3, 15), "call_count_90d": 2, "last_outcome": "Neutral"},
    "HCP009": {"last_call_date": date(2026, 4, 27), "call_count_90d": 4, "last_outcome": "Very Positive"},
    "HCP010": {"last_call_date": date(2026, 1, 20), "call_count_90d": 0, "last_outcome": None},
    "HCP011": {"last_call_date": date(2026, 4, 10), "call_count_90d": 3, "last_outcome": "Positive"},
    "HCP012": {"last_call_date": date(2026, 4, 22), "call_count_90d": 1, "last_outcome": "Neutral"},
    "HCP013": {"last_call_date": date(2026, 3, 28), "call_count_90d": 2, "last_outcome": "Neutral"},
    "HCP014": {"last_call_date": date(2026, 4, 15), "call_count_90d": 3, "last_outcome": "Positive"},
    "HCP015": {"last_call_date": date(2026, 4, 8),  "call_count_90d": 2, "last_outcome": "Positive"},
}


def _last_rx_date_for(hcp_id: str, ref_date: date) -> Optional[str]:
    history = _SAMPLE_RX.get(hcp_id, [])
    for i in range(len(history) - 1, -1, -1):
        if history[i] > 0:
            months_back = len(history) - 1 - i
            d = date(ref_date.year, ref_date.month, 1)
            for _ in range(months_back):
                d = (d.replace(day=1) - timedelta(days=1)).replace(day=1)
            return d.strftime("%b %d, %Y")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Real DB loaders (raw SQL, confirmed column names from alert_detector)
# ─────────────────────────────────────────────────────────────────────────────

_PROFILE_COLUMNS = """
    b.Is_AMA_Do_Not_Contact     AS is_ama_do_not_contact,
    b.Email_1                   AS email,
    b.HCP_Status_Description    AS hcp_status,
    b.HCP_Type_Description      AS hcp_type,
    b.Medical_Degree_1          AS medical_degree,
    b.NPI_int                   AS npi,
    b.PDRP_Optout                AS pdrp_output,
    b.Url_1                      AS website,
    b.Target                     AS target,
    b.City                       AS city,
    b.address                    AS address,
    b.State_Province             AS state
"""

_HCP_PRIORITY_SQL = text(f"""
    WITH rx_agg AS (
        SELECT
            s.HCP_Durable_Id,
            SUM(CASE WHEN YEAR(TRY_CAST(s.Month_Ending_Date AS DATE)) = :yr1
                      AND DATEPART(QUARTER, TRY_CAST(s.Month_Ending_Date AS DATE)) = :q1
                 THEN ISNULL(TRY_CAST(s.Total_Rx_Quantity AS FLOAT), 0) ELSE 0 END) AS total_rx_q1,
            SUM(CASE WHEN YEAR(TRY_CAST(s.Month_Ending_Date AS DATE)) = :yr4
                      AND DATEPART(QUARTER, TRY_CAST(s.Month_Ending_Date AS DATE)) = :q4
                 THEN ISNULL(TRY_CAST(s.Total_Rx_Quantity AS FLOAT), 0) ELSE 0 END) AS total_rx_q4,
            MAX(CASE WHEN ISNULL(TRY_CAST(s.Total_Rx_Quantity AS FLOAT), 0) > 0
                 THEN TRY_CAST(s.Month_Ending_Date AS DATE) END) AS last_rx_date
        FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul s
        WHERE s.sf_terr_pk_gi = :terr
        GROUP BY s.HCP_Durable_Id
    ),
    target_ranked AS (
        SELECT
            d.HCP_Durable_Id,
            d.Segment,
            d.Decile,
            ROW_NUMBER() OVER (PARTITION BY d.HCP_Durable_Id ORDER BY TRY_CAST(d.End_Date AS DATE) DESC) AS rn
        FROM hub_insight360.vw_tfact_target_plan_reporting_dul d
    )
    SELECT TOP 500
        b.HCP_Durable_Id            AS hcp_id,
        b.Formatted_Name            AS name,
        b.Specialty_Description     AS specialty,
        a.Re_Engagement_Priority    AS priority,
        r.last_rx_date              AS last_rx_date,
        r.total_rx_q1               AS rx_q1,
        r.total_rx_q4               AS rx_q4,
        b.Segment_Description       AS segment,
        TRY_CAST(t.Decile AS INT)   AS decile_rank,
        {_PROFILE_COLUMNS}
    FROM rx_agg r
    JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul b
      ON b.HCP_Durable_Id = r.HCP_Durable_Id
    LEFT JOIN hub_insight360.insight360_hcp_awareness_dul a
      ON a.HCP_Durable_Id = r.HCP_Durable_Id
    LEFT JOIN target_ranked t
      ON t.HCP_Durable_Id = r.HCP_Durable_Id AND t.rn = 1
""")


def _latest_quarter_with_rx_data(engine) -> Optional[Tuple[int, int]]:
    """Rx data always lags behind the calendar. If the requested (year, quarter)
    has no rows yet, callers should retry with the most recent quarter that does."""
    try:
        df = pd.read_sql(
            text("""
                SELECT MAX(TRY_CAST(Month_Ending_Date AS DATE)) AS max_dt
                FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul
            """),
            engine,
        )
        max_dt = df["max_dt"].iloc[0]
        if max_dt is None:
            return None
        return (max_dt.year, (max_dt.month - 1) // 3 + 1)
    except Exception as exc:
        log.warning("Could not determine latest available Rx quarter (%s).", exc)
        return None


def load_hcp_priority_data(
    db: Session,
    territory_id: str,
    year_q1: int,
    quarter_q1: int,
    year_q4: int,
    quarter_q4: int,
) -> Optional[List[dict]]:
    """Base query for Territory Prioritization: HCP identity + awareness priority +
    per-quarter Rx totals + target-plan segment, one row per HCP (pre-aggregated
    before joining to avoid the Rx-fact x target-plan row explosion).
    Returns None on any error or empty result.
    """
    try:
        engine = db.bind

        latest = _latest_quarter_with_rx_data(engine)
        if latest and latest != (year_q1, quarter_q1):
            log.info(
                "Requested quarter %d-Q%d has no Rx data yet, using latest available %d-Q%d instead.",
                year_q1, quarter_q1, latest[0], latest[1],
            )
            year_q1, quarter_q1 = latest
            # prior quarter relative to the substituted "current" quarter
            if quarter_q1 == 1:
                year_q4, quarter_q4 = year_q1 - 1, 4
            else:
                year_q4, quarter_q4 = year_q1, quarter_q1 - 1

        df = pd.read_sql(
            _HCP_PRIORITY_SQL,
            engine,
            params={"terr": territory_id, "yr1": year_q1, "q1": quarter_q1, "yr4": year_q4, "q4": quarter_q4},
        )
        if df.empty:
            return None
        df = df.astype(object).where(df.notna(), None)  # NaN -> None so it serializes as JSON null
        df["territory_id"] = territory_id
        df["affiliated_hospital"] = None  # no such column on the HCP dimension view
        return df.to_dict("records")
    except Exception as exc:
        log.warning("HCP priority data load failed (%s), using fallback.", exc)
        return None


def get_hcp_profile(db: Session, hcp_id: str) -> Optional[dict]:
    """View Profile fields for a single HCP, straight from the HCP dimension view."""
    try:
        engine = db.bind
        sql = text(f"""
            SELECT
                b.HCP_Durable_Id            AS hcp_id,
                b.Formatted_Name            AS formatted_name,
                b.Specialty_Description     AS specialist_description,
                {_PROFILE_COLUMNS.replace('is_ama_do_not_contact', 'is_ama_do_not_contact').strip()}
            FROM hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul b
            WHERE b.HCP_Durable_Id = :hcp_id
        """)
        df = pd.read_sql(sql, engine, params={"hcp_id": hcp_id})
        if df.empty:
            return None
        return df.to_dict("records")[0]
    except Exception as exc:
        log.warning("HCP profile load failed (%s).", exc)
        return None


def _load_hcps_from_db(db: Session, territory_id: str) -> Optional[List[dict]]:
    """Try loading HCPs from real DB. Returns None on any error."""
    try:
        engine = db.bind
        sql = text("""
            SELECT TOP 500
                HCP_Durable_Id       AS hcp_id,
                Formatted_Name        AS name,
                Specialty_Description AS specialty,
                Segment_Description   AS segment,
                City                 AS city,
                State_Province       AS state,
                Decile               AS decile_rank
            FROM hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul
        """)
        df = pd.read_sql(sql, engine)
        if df.empty:
            return None
        df["affiliated_hospital"] = None
        df["territory_id"] = territory_id
        return df.to_dict("records")
    except Exception as exc:
        log.warning("HCP dim load failed (%s), using fallback.", exc)
        return None


def _load_rx_pivot_from_db(db: Session, territory_id: str) -> Optional[pd.DataFrame]:
    """12-month monthly Rx pivot per HCP. Returns None on any error."""
    try:
        engine = db.bind
        sql = text("""
            SELECT
                s.HCP_Durable_Id AS hcp_id,
                YEAR(s.Month_Ending_Date) AS yr,
                MONTH(s.Month_Ending_Date) AS mo,
                CAST(s.Month_Ending_Date AS DATE) AS period_date,
                SUM(CASE WHEN s.Brand_Name = 'ZENPEP'
                         THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) AS zenpep_rx,
                SUM(CASE WHEN s.Brand_Name IN ('CREON','PANCREAZE')
                         THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) AS competitor_rx
            FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul s
            WHERE CAST(s.Month_Ending_Date AS DATE) >= CAST(DATEADD(MONTH, -12, GETDATE()) AS DATE)
              AND s.HCP_Durable_Id IS NOT NULL
              AND s.sf_terr_pk_gi = :terr
            GROUP BY s.HCP_Durable_Id,
                     YEAR(s.Month_Ending_Date),
                     MONTH(s.Month_Ending_Date),
                     CAST(s.Month_Ending_Date AS DATE)
            HAVING SUM(CASE WHEN s.Brand_Name = 'ZENPEP'
                            THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) > 0
        """)
        df = pd.read_sql(sql, engine, params={"terr": territory_id})
        return df if not df.empty else None
    except Exception as exc:
        log.warning("Rx pivot load failed (%s), using fallback.", exc)
        return None


def _load_calls_from_db(db: Session, territory_id: str, ref_date: date) -> Optional[dict]:
    """90-day call stats per HCP. Returns None on any error.

    No Is_Reached column and no Call_Outcome column exist on
    vw_tfact_callactivitydetails_zenpep_reporting_dul (verified against
    INFORMATION_SCHEMA.COLUMNS) — every logged call counts, and
    last_outcome always comes back None since there's no source column
    for it anywhere on this view."""
    try:
        engine = db.bind
        cutoff = ref_date - timedelta(days=90)
        sql = text("""
            SELECT
                c.HCP_Durable_Id                      AS hcp_id,
                MAX(TRY_CAST(c.Call_Date AS DATE))     AS last_call_date,
                COUNT(c.Call_Id)                       AS call_count
            FROM hub_insight360.vw_tfact_callactivitydetails_zenpep_reporting_dul c
            WHERE c.sf_terr_pk_gi = :terr
              AND TRY_CAST(c.Call_Date AS DATE) >= :cutoff
            GROUP BY c.HCP_Durable_Id
        """)
        df = pd.read_sql(sql, engine, params={"terr": territory_id, "cutoff": str(cutoff)})
        if df.empty:
            return None
        result = {}
        for _, row in df.iterrows():
            lc = row["last_call_date"]
            if lc is not None and not pd.isna(lc):
                lc_date = lc.date() if hasattr(lc, "date") else lc
                days = (ref_date - lc_date).days
            else:
                lc_date = None
                days = None
            result[row["hcp_id"]] = {
                "last_call_date": lc_date,
                "call_count_90d": int(row["call_count"] or 0),
                "last_outcome": None,
                "days_since_last_call": days,
            }
        return result
    except Exception as exc:
        log.warning("Call stats load failed (%s), using fallback.", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API consumed by the router
# ─────────────────────────────────────────────────────────────────────────────

def load_territory_data(db: Session, territory_id: str, ref_date: date) -> dict:
    """
    Load all data needed for territory prioritization.
    Returns a dict with keys: hcps, rx_pivot_df, call_stats, using_fallback.
    """
    (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(ref_date)
    hcps        = load_hcp_priority_data(db, territory_id, yr1, q1, yr4, q4)
    rx_pivot_df = _load_rx_pivot_from_db(db, territory_id)
    call_stats  = _load_calls_from_db(db, territory_id, ref_date)
    using_fallback = False

    if not hcps:
        log.info("Using sample HCP data (DB unavailable or no territory match).")
        hcps = [dict(h) for h in _SAMPLE_HCPS]
        using_fallback = True

    if rx_pivot_df is None or rx_pivot_df.empty:
        log.info("Using sample Rx data.")
        rx_pivot_df = None  # handled in feature_engineering
        using_fallback = True

    if not call_stats:
        log.info("Using sample call data.")
        call_stats = None  # handled below
        using_fallback = True

    return {
        "hcps": hcps,
        "rx_pivot_df": rx_pivot_df,
        "call_stats": call_stats,
        "using_fallback": using_fallback,
        "sample_rx": _SAMPLE_RX if using_fallback else None,
        "sample_comp": _SAMPLE_COMP if using_fallback else None,
        "sample_calls": _SAMPLE_CALLS if using_fallback else None,
        "ref_date": ref_date,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Legacy helpers (kept for backward compat with router)
# ─────────────────────────────────────────────────────────────────────────────

def load_territory_hcps(db: Session, territory_id: str):
    """Legacy: returns list of HCP dicts (not ORM objects)."""
    return _load_hcps_from_db(db, territory_id) or [dict(h) for h in _SAMPLE_HCPS]


def load_rx_for_territory(db, territory_id, year_q1, quarter_q1, year_q4, quarter_q4):
    """Legacy: returns {hcp_id: {rx_q1, rx_q4, competitor_rx, competitor_brand}}."""
    try:
        engine = db.bind
        sql = text("""
            SELECT
                s.HCP_Durable_Id AS hcp_id,
                YEAR(s.Month_Ending_Date) AS yr,
                DATEPART(QUARTER, s.Month_Ending_Date) AS qtr,
                SUM(CASE WHEN s.Brand_Name = 'ZENPEP' THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) AS zenpep_rx,
                SUM(CASE WHEN s.Brand_Name IN ('CREON','PANCREAZE') THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) AS competitor_rx
            FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul s
            WHERE s.HCP_Durable_Id IS NOT NULL
              AND (
                (YEAR(s.Month_Ending_Date) = :yr1 AND DATEPART(QUARTER, s.Month_Ending_Date) = :q1)
                OR
                (YEAR(s.Month_Ending_Date) = :yr4 AND DATEPART(QUARTER, s.Month_Ending_Date) = :q4)
              )
            GROUP BY s.HCP_Durable_Id,
                     YEAR(s.Month_Ending_Date),
                     DATEPART(QUARTER, s.Month_Ending_Date)
        """)
        df = pd.read_sql(sql, engine, params={"yr1": year_q1, "q1": quarter_q1, "yr4": year_q4, "q4": quarter_q4})
        result = {}
        for _, row in df.iterrows():
            hid = row["hcp_id"]
            if hid not in result:
                result[hid] = {"rx_q1": 0.0, "rx_q4": 0.0, "competitor_rx": 0.0, "competitor_brand": "CREON"}
            if row["yr"] == year_q1 and row["qtr"] == quarter_q1:
                result[hid]["rx_q1"] = float(row["zenpep_rx"] or 0)
                result[hid]["competitor_rx"] = float(row["competitor_rx"] or 0)
            else:
                result[hid]["rx_q4"] = float(row["zenpep_rx"] or 0)
        return result
    except Exception as exc:
        log.warning("Legacy load_rx_for_territory failed: %s", exc)
        # Return sample data
        out = {}
        for h in _SAMPLE_HCPS:
            hist = _SAMPLE_RX.get(h["hcp_id"], [0]*12)
            rx_q1 = sum(hist[-3:])
            rx_q4 = sum(hist[-6:-3])
            out[h["hcp_id"]] = {
                "rx_q1": float(rx_q1),
                "rx_q4": float(rx_q4),
                "competitor_rx": float(_SAMPLE_COMP.get(h["hcp_id"], 5)),
                "competitor_brand": "CREON",
            }
        return out


def load_last_call_dates(db: Session, territory_id: str) -> dict:
    """Legacy: returns {hcp_id: last_call_date}."""
    try:
        engine = db.bind
        sql = text("""
            SELECT HCP_Durable_Id AS hcp_id, MAX(Call_Date) AS last_call_date
            FROM hub_insight360.vw_tfact_callactivitydetails_zenpep_reporting_dul
            WHERE sf_terr_pk_gi = :terr
            GROUP BY HCP_Durable_Id
        """)
        df = pd.read_sql(sql, engine, params={"terr": territory_id})
        return {row["hcp_id"]: row["last_call_date"] for _, row in df.iterrows()}
    except Exception:
        return {h["hcp_id"]: _SAMPLE_CALLS[h["hcp_id"]]["last_call_date"] for h in _SAMPLE_HCPS if h["hcp_id"] in _SAMPLE_CALLS}


def load_call_stats_90d(db: Session, territory_id: str, ref_date: date) -> dict:
    """Legacy: returns {hcp_id: {days_since_last_call, call_count_90d, last_outcome}}."""
    result = _load_calls_from_db(db, territory_id, ref_date)
    if result:
        # Normalize keys
        return {
            hid: {
                "days_since_last_call": v.get("days_since_last_call"),
                "call_count_90d": v.get("call_count_90d", 0),
                "last_outcome": v.get("last_outcome"),
            }
            for hid, v in result.items()
        }
    # Fallback
    out = {}
    for h in _SAMPLE_HCPS:
        hid = h["hcp_id"]
        c = _SAMPLE_CALLS.get(hid, {})
        lc = c.get("last_call_date")
        days = (ref_date - lc).days if lc else None
        out[hid] = {
            "days_since_last_call": days,
            "call_count_90d": c.get("call_count_90d", 0),
            "last_outcome": c.get("last_outcome"),
        }
    return out
