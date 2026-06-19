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
    load_call_stats_90d,
    load_territory_hcps,
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
    """Load → feature engineer → AI score → LLM insight → cache."""
    cache_key = territory_cache_key("territory:ranked_hcps_v2", territory_id)
    cached = cache_get(cache_key)
    if cached:
        return cached

    (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(ref_date)

    hcps = load_territory_hcps(db, territory_id)
    rx_data = load_rx_for_territory(db, territory_id, yr1, q1, yr4, q4)
    call_stats_map = load_call_stats_90d(db, territory_id, ref_date)

    # Build base feature dicts (rx trend, competitor share, last call date)
    from app.services.territory_prioritization.data_ingestion import load_last_call_dates
    last_calls = load_last_call_dates(db, territory_id)
    features = build_hcp_features(hcps, rx_data, last_calls)

    # Add decile_rank from HCP dimension
    hcp_dim = {h.hcp_id: h for h in hcps}
    for f in features:
        f["decile_rank"] = hcp_dim[f["hcp_id"]].decile_rank if f["hcp_id"] in hcp_dim else None
        f["affiliated_hospital"] = hcp_dim[f["hcp_id"]].affiliated_hospital if f["hcp_id"] in hcp_dim else None

    # 60/30/10 AI scoring
    ranked = enrich_all_hcps(features, call_stats_map)

    # GPT-4o insights (LLM client handles per-HCP caching)
    generate_insights_for_list(ranked)

    # Add period metadata
    for hcp in ranked:
        hcp["period"] = _quarter_label(yr1, q1)
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
    period = _quarter_label(yr1, q1)

    summary = build_territory_summary(ranked, rep.territory_id, rep.territory_id, period)
    summary["last_refresh"] = datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p")
    return TerritorySummary(**summary)


@router.get("/hcp-list", response_model=List[HCPRankedItem])
async def get_hcp_list(
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Ranked HCP list with AI scores, insights, and Rx metrics."""
    ranked = _get_ranked_hcps(db, rep.territory_id, date.today())
    return [HCPRankedItem(**h) for h in ranked]


@router.get("/hcp/{hcp_id}/insight", response_model=HCPInsightResponse)
async def regenerate_hcp_insight(
    hcp_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """On-demand: regenerate AI insight for a single HCP."""
    ranked = _get_ranked_hcps(db, rep.territory_id, date.today())
    hcp = next((h for h in ranked if h["hcp_id"] == hcp_id), None)
    if hcp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"HCP {hcp_id} not found")
    return HCPInsightResponse(**regenerate_single_hcp_insight(hcp))
