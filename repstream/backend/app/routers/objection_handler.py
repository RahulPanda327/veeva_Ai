"""Module 3 — Objection Handler API endpoints."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.objection import (
    AddToCallPrepRequest,
    AddToCallPrepResponse,
    ObjectionItem,
    ObjectionListResponse,
    ObjectionResponse,
)
from app.services.objection_handler.mlr_response_engine import (
    enrich_objection_list,
    get_best_mlr_response,
    load_all_objections,
    sort_objections,
)
from app.services.filters_service import FilterSelection, filter_params, resolve_territories, salesforce_of
from app.utils.auth import RepIdentity, get_current_rep
from app.utils.cache import cache_get, cache_set, territory_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/objections", tags=["Objection Handler"])

_CACHE_TTL = 3600


def _get_objection_list(
    db: Session, territory_ids: Optional[List[str]] = None, period: Optional[str] = None
) -> List[dict]:
    scope_key = ",".join(sorted(territory_ids)) if territory_ids else "all"
    cache_key = territory_cache_key(f"objections:list_v3:{period or 'all'}", scope_key)
    cached = cache_get(cache_key)
    if cached:
        return cached

    rows = load_all_objections(db, territory_ids, period)
    rows = enrich_objection_list(rows)
    rows = sort_objections(rows)

    cache_set(cache_key, rows, ttl=_CACHE_TTL)
    return rows


@router.get("/list", response_model=List[ObjectionItem])
async def list_objections(
    period: Optional[str] = None,
    sel: FilterSelection = Depends(filter_params),
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Ranked objections with NLP analysis, frequency labels, and AI-optimized responses.

    Pass manager_id/employee_id/territory_id to scope to that selection (filtered on
    the table's Territory_Durable_Id column); unfiltered returns all objections."""
    territories = resolve_territories(db, salesforce_of(rep.territory_id), sel)
    bare = [t.split("|")[-1] for t in territories] if territories else None
    rows = _get_objection_list(db, bare, period)
    return [ObjectionItem(**o) for o in rows]


@router.get("/{objection_id}/response", response_model=ObjectionResponse)
async def get_objection_response(
    objection_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """MLR-approved response with AI enrichment for a single objection."""
    # Try to get from the cached list first (all objections — lookup is by id)
    rows = _get_objection_list(db)
    row = next((r for r in rows if r["objection_id"] == objection_id), None)

    if row:
        return ObjectionResponse(
            objection_id=row["objection_id"],
            objection_type=row["objection_type"],
            objection_text=row["objection_text"],
            hcp_segment=row.get("hcp_segment"),
            ai_mlr_response=row.get("ai_mlr_response", ""),
            ai_response_source=row.get("response_source"),
            ai_sku=row.get("ai_sku"),
            ai_conversion_score=row.get("ai_conversion_score", 0.0),
            ai_date_range=row.get("ai_date_range"),
            ai_supporting_materials=row.get("ai_supporting_materials"),
            analysis_badges=row.get("analysis_badges", []),
        )

    # Fallback: direct DB lookup
    result = get_best_mlr_response(db, objection_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No MLR response for {objection_id}",
        )
    return ObjectionResponse(
        objection_id=result["objection_id"],
        objection_type=result["objection_type"],
        objection_text=result["objection_text"],
        hcp_segment=result.get("hcp_segment"),
        ai_mlr_response=result["recommended_response"],
        ai_response_source=result.get("response_source"),
        ai_sku=result.get("sku"),
        ai_conversion_score=round(float(result.get("success_rate", 0)) * 100, 1),
        ai_supporting_materials=result.get("ai_supporting_materials"),
        analysis_badges=["DETECTED_BY_AI", "NLP_ANALYSIS", "AI_OPTIMIZED"],
    )


@router.post("/{objection_id}/add-to-call-prep", response_model=AddToCallPrepResponse)
async def add_to_call_prep(
    objection_id: str,
    body: AddToCallPrepRequest,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),  # noqa: ARG001
):
    """Flag an objection for the rep's next call prep."""
    call_prep_key = f"call_prep:{body.rep_id}"
    cached: list = cache_get(call_prep_key) or []
    if objection_id not in cached:
        cached.append(objection_id)
        cache_set(call_prep_key, cached, ttl=86400)
    return AddToCallPrepResponse(
        success=True,
        message="Objection added to your next call prep list.",
        objection_id=objection_id,
        rep_id=body.rep_id,
    )


def _extract_response_highlight(response_text: str) -> Optional[str]:
    if not response_text:
        return None
    sentences = response_text.split(".")
    first = sentences[0].strip() if sentences else response_text
    words = first.split()
    if len(words) <= 8:
        return first
    return " ".join(words[:6]) + "…"
