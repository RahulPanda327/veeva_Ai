"""Module 1 — Territory Prioritization API endpoints."""
import logging
from datetime import date, datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.territory_prioritization import HCPInsightResponse, HCPRankedItem, TerritorySummary
from app.services.territory_prioritization.ai_score import enrich_all_hcps
from app.services.territory_prioritization.data_ingestion import (
    get_current_and_prior_quarter,
    load_territory_data,
    load_call_stats_90d,
    load_rx_for_territory,
)
from app.services.territory_prioritization.feature_engineering import build_hcp_features
from app.services.territory_prioritization.llm_insight import (
    generate_insights_for_list,
    regenerate_single_hcp_insight,
)
from app.services.territory_prioritization.weekly_target import build_territory_summary
from app.utils.auth import RepIdentity, get_current_rep
from app.utils.cache import cache_get, cache_set, territory_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/territory", tags=["Territory Prioritization"])

_CACHE_TTL = 3600


def _quarter_label(year: int, q: int) -> str:
    months = {1: "Jan - Mar", 2: "Apr - Jun", 3: "Jul - Sep", 4: "Oct - Dec"}
    return f"Q{q} {year} ({months[q]})"


def _get_ranked_hcps(db: Session, territory_id: str, ref_date: date) -> List[dict]:
    """Load → feature engineer → AI score (all 4 techniques) → LLM insight → cache."""
    cache_key = territory_cache_key("territory:ranked_hcps_v3", territory_id)
    cached = cache_get(cache_key)
    if cached:
        return cached

    (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(ref_date)

    # Load all data (real DB or fallback)
    data = load_territory_data(db, territory_id, ref_date)
    hcps            = data["hcps"]
    rx_pivot_df     = data["rx_pivot_df"]
    sample_rx       = data["sample_rx"]
    sample_comp     = data["sample_comp"]
    sample_calls    = data["sample_calls"]
    using_fallback  = data["using_fallback"]

    # Build Rx dict for legacy feature_engineering
    rx_data: dict = {}
    if rx_pivot_df is not None and not rx_pivot_df.empty:
        for hcp_id, grp in rx_pivot_df.groupby("hcp_id"):
            grp_sorted = grp.sort_values(["yr", "mo"])
            rx_q1_val = grp_sorted[grp_sorted["mo"].isin([1,2,3])]["zenpep_rx"].sum() if q1 == 1 else 0.0
            rx_q4_val = 0.0
            comp_rx   = grp_sorted["competitor_rx"].mean()
            rx_data[hcp_id] = {
                "rx_q1": float(rx_q1_val),
                "rx_q4": float(rx_q4_val),
                "competitor_rx": float(comp_rx),
                "competitor_brand": "CREON",
            }
    elif using_fallback and sample_rx:
        for hcp in hcps:
            hid = hcp["hcp_id"]
            hist = sample_rx.get(hid, [0]*12)
            rx_data[hid] = {
                "rx_q1":          float(sum(hist[-3:])),
                "rx_q4":          float(sum(hist[-6:-3])),
                "competitor_rx":  float((sample_comp or {}).get(hid, 5)),
                "competitor_brand": "CREON",
            }
    else:
        rx_data = load_rx_for_territory(db, territory_id, yr1, q1, yr4, q4)

    # Call stats
    if using_fallback and sample_calls:
        call_stats_map = {}
        for hcp in hcps:
            hid = hcp["hcp_id"]
            c = sample_calls.get(hid, {})
            lc = c.get("last_call_date")
            days = (ref_date - lc).days if lc else None
            call_stats_map[hid] = {
                "days_since_last_call": days,
                "call_count_90d":       c.get("call_count_90d", 0),
                "last_outcome":         c.get("last_outcome"),
                "last_call_date":       lc,
            }
    else:
        call_stats_map = load_call_stats_90d(db, territory_id, ref_date)

    # Last call dates for feature_engineering
    last_calls = {hid: v.get("last_call_date") for hid, v in call_stats_map.items()}

    # Build features (includes monthly_rx_history)
    features = build_hcp_features(
        hcps=hcps,
        rx_data=rx_data,
        last_call_dates=last_calls,
        sample_rx=sample_rx,
        sample_comp=sample_comp,
        ref_date=ref_date,
    )

    # Enrich with all 4 AI/ML techniques (scores + prediction + NLP + badges)
    ranked = enrich_all_hcps(features, call_stats_map)

    # GPT-4o insights (Technique 4)
    generate_insights_for_list(ranked)

    # Add period metadata
    for hcp in ranked:
        hcp["period"]      = _quarter_label(yr1, q1)
        hcp["ai_is_ranked"] = True

    cache_set(cache_key, ranked, ttl=_CACHE_TTL)
    return ranked


@router.get("/summary", response_model=TerritorySummary)
async def get_territory_summary(
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """KPI tiles: total HCPs, High/Med/Low counts, weekly target, last refresh."""
    today = date.today()
    ranked = _get_ranked_hcps(db, rep.territory_id, today)
    (yr1, q1), _ = get_current_and_prior_quarter(today)
    period  = _quarter_label(yr1, q1)
    summary = build_territory_summary(ranked, rep.territory_id, rep.territory_id, period)
    summary["last_refresh"] = datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p")
    return TerritorySummary(**summary)


@router.get("/hcp-list", response_model=List[HCPRankedItem])
async def get_hcp_list(
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Ranked HCP list with AI scores, predictive analytics, NLP classification, and GPT-4o insights."""
    ranked = _get_ranked_hcps(db, rep.territory_id, date.today())
    return [HCPRankedItem(**h) for h in ranked]


@router.get("/hcp/{hcp_id}/insight", response_model=HCPInsightResponse)
async def regenerate_hcp_insight(
    hcp_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """On-demand: regenerate GPT-4o insight for a single HCP."""
    ranked = _get_ranked_hcps(db, rep.territory_id, date.today())
    hcp = next((h for h in ranked if h["hcp_id"] == hcp_id), None)
    if hcp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"HCP {hcp_id} not found")
    return HCPInsightResponse(**regenerate_single_hcp_insight(hcp))
