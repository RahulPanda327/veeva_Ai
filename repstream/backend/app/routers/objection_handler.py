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
    ObjectionResponse,
)
from app.services.objection_handler.mlr_response_engine import (
    get_best_mlr_response,
    load_all_objections,
)
from app.services.objection_handler.objection_classifier import assign_frequency_label
from app.utils.auth import RepIdentity, get_current_rep
from app.utils.cache import cache_get, cache_set, territory_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/objections", tags=["Objection Handler"])

_CACHE_TTL = 3600


def _get_objection_list(db: Session, territory_id: str, period: Optional[str] = None) -> List[dict]:
    cache_key = territory_cache_key(f"objections:list:{period or 'all'}", territory_id)
    cached = cache_get(cache_key)
    if cached:
        return cached

    rows = load_all_objections(db, territory_id, period)
    result = [
        {
            "objection_id": r.objection_id,
            "objection_type": r.objection_type,
            "objection_text": r.objection_text,
            "period": r.period or "",
            "territory_id": r.territory_id,
            # AI keys
            "ai_frequency_label": assign_frequency_label(r.call_count or 0),
            "ai_call_count": r.call_count or 0,
            "ai_success_rate": r.success_rate or 0.0,
            "ai_conversion_score": round((r.success_rate or 0.0) * 100, 1),
        }
        for r in rows
    ]
    cache_set(cache_key, result, ttl=_CACHE_TTL)
    return result


@router.get("/list", response_model=List[ObjectionItem])
async def list_objections(
    period: Optional[str] = None,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Ranked objections with AI frequency label and success rate."""
    return [ObjectionItem(**o) for o in _get_objection_list(db, rep.territory_id, period)]


@router.get("/{objection_id}/response", response_model=ObjectionResponse)
async def get_objection_response(
    objection_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """MLR-approved response with AI keys: ai_mlr_response, ai_sku, ai_success_rate."""
    result = get_best_mlr_response(db, objection_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No MLR response for {objection_id}")

    # Rename to ai_ keys
    return ObjectionResponse(
        objection_id=result["objection_id"],
        objection_type=result["objection_type"],
        objection_text=result["objection_text"],
        hcp_segment=result.get("hcp_segment"),
        ai_mlr_response=result["recommended_response"],
        ai_response_source=result.get("response_source"),
        ai_sku=result.get("sku"),
        ai_success_rate=result.get("success_rate", 0.0),
        ai_conversion_score=round((result.get("success_rate", 0.0)) * 100, 1),
        ai_response_highlight=_extract_response_highlight(result["recommended_response"]),
    )


@router.post("/{objection_id}/add-to-call-prep", response_model=AddToCallPrepResponse)
async def add_to_call_prep(
    objection_id: str,
    body: AddToCallPrepRequest,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),  # noqa: ARG001
):
    """Flag an objection for the rep's next call prep (stored in Redis)."""
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
    """Extract a 4-8 word highlight phrase from the first sentence."""
    if not response_text:
        return None
    sentences = response_text.split(".")
    first = sentences[0].strip() if sentences else response_text
    words = first.split()
    if len(words) <= 8:
        return first
    return " ".join(words[:6]) + "…"
