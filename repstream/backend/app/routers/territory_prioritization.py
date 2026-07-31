"""Module 1 — Territory Prioritization API endpoints."""
import logging
import threading
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.territory_prioritization import HCPInsightResponse, HCPRankedItem, TerritorySummary
from app.services.filters_service import (
    FilterSelection,
    filter_params,
    get_org_filters,
    normalize_territory_id,
    recall_filter,
    resolve_territories,
    salesforce_of,
)
from app.utils.response_cache import caller_key
from app.services.territory_prioritization.ai_score import enrich_all_hcps
from app.services.territory_prioritization.data_ingestion import (
    get_current_and_prior_quarter,
    load_territory_data,
    load_call_stats_90d,
    load_rx_for_territory,
    get_hcp_profile,
)
from app.services.territory_prioritization.feature_engineering import build_hcp_features
from app.services.territory_prioritization.llm_insight import (
    count_uncached_insights,
    generate_insights_for_list,
    regenerate_single_hcp_insight,
    warm_insights,
)
from app.services.territory_prioritization.weekly_target import build_territory_summary
from app.utils.auth import RepIdentity, get_current_rep
from app.utils.cache import cache_get, cache_set, territory_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/territory", tags=["Territory Prioritization"])

_CACHE_TTL = 3600

# Background Ollama insight warmer — dedup so one territory doesn't get multiple
# concurrent warmers, and the request path never blocks on the LLM.
_warming_territories: set[str] = set()
_warm_lock = threading.Lock()

# In-process fallback for the ranked-HCP lists. cache_get/cache_set are Redis-
# backed and become silent no-ops when Redis isn't running (the case in this
# environment), which would otherwise force a full recompute (load → features →
# AI scoring) on every call that isn't served by the HTTP response cache — e.g.
# /territory/summary, which is deliberately not response-cached so its tiles can
# follow the remembered filter. This module-level dict keeps the computed lists in
# THIS process's memory so those calls are cheap. Populated on first compute (incl.
# during warm-up) and held until restart, matching the permanent response cache.
_ranked_mem: dict[str, List[dict]] = {}
_ranked_mem_lock = threading.Lock()


# Only the top-ranked HCPs per territory are ever shown (the list is capped to
# HIGH + MEDIUM + a slice of LOW), so only THEY need a real LLM insight. Warming
# every HCP (~500/territory) would fire hundreds of local-model calls that
# saturate Ollama and starve every other endpoint — the rest keep the instant
# rule-based template and get a real insight on-demand if a user opens them.
_INSIGHT_WARM_LIMIT = 60


def _maybe_warm_insights_async(territory_id: str, ranked: List[dict]) -> None:
    """Fire-and-forget: generate real Ollama insights for the top displayed HCPs
    still on the template, in a daemon thread. Next page load serves them from
    cache. Capped to _INSIGHT_WARM_LIMIT so it can't flood a local model."""
    subset = ranked[:_INSIGHT_WARM_LIMIT]
    with _warm_lock:
        if territory_id in _warming_territories:
            return
        if count_uncached_insights(subset) == 0:
            return
        _warming_territories.add(territory_id)

    def _run():
        try:
            warm_insights(subset)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Insight warmer failed for %s: %s", territory_id, exc)
        finally:
            with _warm_lock:
                _warming_territories.discard(territory_id)

    threading.Thread(target=_run, daemon=True, name=f"warm-{territory_id}").start()


def _quarter_label(year: int, q: int) -> str:
    months = {1: "Jan - Mar", 2: "Apr - Jun", 3: "Jul - Sep", 4: "Oct - Dec"}
    return f"Q{q} {year} ({months[q]})"


def _all_territory_ids(db: Session, sf: str) -> List[str]:
    """Every territory in the org filter tree for this sales force, as piped ids —
    i.e. the 'select everything' set. Used as the no-filter default so that
    unfiltered == the whole team, and its counts equal the combined per-territory
    filters (rather than just the rep's own territory)."""
    tree = get_org_filters(db, sf)
    out: List[str] = []
    seen: set[str] = set()
    for m in tree.get("manager_id", []):
        for e in m.get("employee_id", []):
            for t in e.get("territory_id", []):
                piped = normalize_territory_id(t.get("territory_id"), sf)
                if piped and piped not in seen:
                    seen.add(piped)
                    out.append(piped)
    return out


_LOW_PER_TERRITORY = 25   # LOW-tier HCPs shown per territory in scope (UI cap only)
_TIER_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}   # display order: HIGH → MEDIUM → LOW


def _cap_low_priority(ranked: List[dict], scope_label: str) -> List[dict]:
    """Trim the LOW-tier HCPs returned to the UI to 25 per territory in scope
    (so 50 for the whole team, 25 for a single territory) while keeping every
    HIGH/MEDIUM HCP. The ranked list is already sorted by tier then score, so the
    LOW ones kept are the highest-scoring. This ONLY affects the /hcp-list payload
    — the KPI tiles are computed from the full list, so their counts don't change."""
    n_terr = len([t for t in (scope_label or "").split(",") if t]) or 1
    low_cap = _LOW_PER_TERRITORY * n_terr
    out: List[dict] = []
    low_kept = 0
    for h in ranked:
        if h.get("ai_priority_tier") == "LOW":
            if low_kept >= low_cap:
                continue
            low_kept += 1
        out.append(h)
    return out


def _ranked_for_selection(
    db: Session,
    rep_territory: str,
    ref_date: date,
    sel: FilterSelection,
) -> tuple[List[dict], str]:
    """Resolve a manager/employee/territory selection to its territories, load the
    ranked HCPs for each, and return (combined_deduped_hcps, scope_label).

    No selection → ALL territories in the org tree (the whole team), so unfiltered
    counts equal the union of the per-territory filters. Falls back to the rep's
    own territory only if the tree is unavailable/empty."""
    sf = salesforce_of(rep_territory)
    territories = resolve_territories(db, sf, sel)
    if not territories:
        territories = _all_territory_ids(db, sf) or [rep_territory]

    combined: List[dict] = []
    seen: set[str] = set()
    for terr in territories:
        for hcp in _get_ranked_hcps(db, terr, ref_date):
            if hcp["hcp_id"] in seen:
                continue
            seen.add(hcp["hcp_id"])
            combined.append(hcp)

    # Each territory's list is already HIGH → MEDIUM → LOW, but concatenating
    # multiple territories interleaves them. Re-sort the combined list so the whole
    # output is globally ordered by tier (HIGH, then MEDIUM, then LOW), then by
    # score within each tier. (Harmless no-op for a single-territory selection.)
    combined.sort(key=lambda h: (_TIER_ORDER.get(h.get("ai_priority_tier"), 3),
                                  -(h.get("ai_priority_score") or 0)))
    return combined, ",".join(territories)


def _get_ranked_hcps(db: Session, territory_id: str, ref_date: date) -> List[dict]:
    """Load → feature engineer → AI score (all 4 techniques) → LLM insight → cache."""
    cache_key = territory_cache_key("territory:ranked_hcps_v3", territory_id)
    # Redis first; fall back to the in-process copy when Redis is a no-op.
    cached = cache_get(cache_key)
    if cached is None:
        with _ranked_mem_lock:
            cached = _ranked_mem.get(cache_key)
    if cached:
        # Re-attach insights so any Ollama text produced by the background warmer
        # since this list was cached is picked up (cache stores template-only).
        generate_insights_for_list(cached)
        _maybe_warm_insights_async(territory_id, cached)
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

    # Attach insights READ-ONLY (cached real Ollama text, else instant template),
    # then kick off background generation for any HCP still on the template.
    generate_insights_for_list(ranked)
    _maybe_warm_insights_async(territory_id, ranked)

    # Add period metadata
    for hcp in ranked:
        hcp["period"]      = _quarter_label(yr1, q1)
        hcp["ai_is_ranked"] = True

    cache_set(cache_key, ranked, ttl=_CACHE_TTL)
    with _ranked_mem_lock:
        _ranked_mem[cache_key] = ranked
    return ranked


@router.get("/summary", response_model=TerritorySummary)
async def get_territory_summary(
    request: Request,
    sel: FilterSelection = Depends(filter_params),
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """KPI tiles: total HCPs, High/Med/Low counts, weekly target, last refresh.

    The tiles mirror the ranked HCP list: if no filter is passed here, the last
    filter this caller applied to `/territory/hcp-list` is reused, so the counts
    always match the filtered list. Passing an explicit manager_id/employee_id/
    territory_id overrides that; unfiltered falls back to the rep's own territory.
    Always includes the manager → employee → territory `filters` tree.
    """
    # No explicit filter on this request → reuse the caller's last hcp-list filter,
    # so the tiles track whatever the ranked list is showing.
    if sel.is_empty():
        remembered = recall_filter(caller_key(request), scope="territory")
        if remembered is not None:
            sel = remembered

    today = date.today()
    sf = salesforce_of(rep.territory_id)
    ranked, scope_label = _ranked_for_selection(db, rep.territory_id, today, sel)
    (yr1, q1), _ = get_current_and_prior_quarter(today)
    period  = _quarter_label(yr1, q1)
    summary = build_territory_summary(ranked, scope_label, scope_label, period)
    # total_hcps reflects what the UI actually renders: HIGH/MEDIUM in full + the
    # capped LOW sample (same trimming /hcp-list applies). The tier counts stay the
    # true full totals.
    summary["total_hcps"] = len(_cap_low_priority(ranked, scope_label))
    summary["last_refresh"] = datetime.now(timezone.utc).strftime("%b %d, %Y")
    summary["filters"] = get_org_filters(db, sf)
    return TerritorySummary(**summary)


@router.get("/hcp-list", response_model=List[HCPRankedItem])
async def get_hcp_list(
    sel: FilterSelection = Depends(filter_params),
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Ranked HCP list with AI scores, predictive analytics, NLP classification, and Ollama insights.

    LOW-priority HCPs are capped for the UI (25 per territory in scope — so 50 for
    the whole team, 25 for a single territory); HIGH/MEDIUM are returned in full.
    The KPI tiles (/territory/summary) count the FULL list, so they are unchanged.

    Scope with any of ?manager_id=/?employee_id=/?territory_id= or the matching
    ?manager_name=/?employee_name=/?territory_name= (id or name, case-insensitive)."""
    ranked, scope_label = _ranked_for_selection(db, rep.territory_id, date.today(), sel)
    ranked = _cap_low_priority(ranked, scope_label)
    return [HCPRankedItem(**h) for h in ranked]


@router.get("/hcp/{hcp_id}/insight", response_model=HCPInsightResponse)
async def regenerate_hcp_insight(
    hcp_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """On-demand: regenerate Ollama insight for a single HCP."""
    ranked = _get_ranked_hcps(db, rep.territory_id, date.today())
    hcp = next((h for h in ranked if h["hcp_id"] == hcp_id), None)
    if hcp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"HCP {hcp_id} not found")
    return HCPInsightResponse(**regenerate_single_hcp_insight(hcp))


@router.get("/hcp/{hcp_id}/profile")
async def get_hcp_profile_view(
    hcp_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """View Profile button: full HCP dimension details from vw_tdim_healthcarepractitioner_zenpep_reporting_dul."""
    profile = get_hcp_profile(db, hcp_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"HCP {hcp_id} not found")
    return profile
