"""Module 2 — New Writer Identification API endpoints."""
import logging
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.new_writer import ApproachBriefResponse, NewWriterCandidate
from app.services.new_writer_id.approach_brief import build_approach_brief_response, generate_approach_brief
from app.services.new_writer_id.icd10_matching import enrich_with_icd10
from app.services.new_writer_id.match_scoring import enrich_with_peer_match
from app.services.new_writer_id.non_writer_detection import detect_non_writers, enrich_with_hcp_dimensions
from app.services.territory_prioritization.data_ingestion import get_current_and_prior_quarter
from app.utils.auth import RepIdentity, get_current_rep
from app.utils.cache import cache_get, cache_set, territory_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/new-writers", tags=["New Writer Identification"])

_CACHE_TTL = 3600


def _get_candidates(db: Session, territory_id: str) -> List[dict]:
    cache_key = territory_cache_key("new_writers:candidates_v2", territory_id)
    cached = cache_get(cache_key)
    if cached:
        return cached

    (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(date.today())
    raw = detect_non_writers(db, territory_id, yr1, q1, yr4, q4)
    enriched = enrich_with_hcp_dimensions(db, raw, territory_id)
    enriched = enrich_with_icd10(enriched)
    enriched = enrich_with_peer_match(db, enriched, territory_id)

    # Rename to ai_ keys
    for c in enriched:
        c["ai_peer_match_score"] = c.pop("peer_match_pct", 0.0)
        c["ai_peer_name"] = c.pop("peer_name", None)
        c["ai_peer_hcp_id"] = c.pop("peer_hcp_id", None)
        c["ai_icd10_matched_codes"] = c.pop("matched_icd10_codes", [])
        c["ai_icd10_match_count"] = len(c["ai_icd10_matched_codes"])
        c["ai_non_writer_flag"] = True
        c["ai_approach_brief"] = None
        c["ai_approach_highlight"] = None
        c.setdefault("ai_peer_rationale", None)

    cache_set(cache_key, enriched, ttl=_CACHE_TTL)
    return enriched


@router.get("/candidates", response_model=List[NewWriterCandidate])
async def get_new_writer_candidates(
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Non-writer candidates with AI peer match score, ICD-10 matches, and Rx breakdown."""
    return [NewWriterCandidate(**c) for c in _get_candidates(db, rep.territory_id)]


@router.post("/{hcp_id}/approach-brief", response_model=ApproachBriefResponse)
async def generate_warm_approach_brief(
    hcp_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Generate a GPT-4o warm approach brief. Returns ai_approach_brief + ai_approach_highlight."""
    candidates = _get_candidates(db, rep.territory_id)
    # Remap ai_ keys back for the service layer
    hcp = next((c for c in candidates if c["hcp_id"] == hcp_id), None)
    if hcp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate {hcp_id} not found")

    service_hcp = {
        **hcp,
        "peer_name": hcp.get("ai_peer_name"),
        "matched_icd10_codes": hcp.get("ai_icd10_matched_codes", []),
        "competitor_brand": hcp.get("competitor_brand", ""),
        "competitor_volume": hcp.get("competitor_volume", 0.0),
    }
    brief_text = generate_approach_brief(service_hcp)
    result = build_approach_brief_response(service_hcp, brief_text)

    return ApproachBriefResponse(
        hcp_id=result["hcp_id"],
        ai_approach_brief=result["brief_text"],
        ai_approach_highlight=_extract_highlight(result["brief_text"]),
        ai_peer_name=result.get("peer_name"),
        generated_at=result["generated_at"],
        cached=result.get("cached", False),
    )


def _extract_highlight(brief_text: str) -> str:
    """Pull a 5-7 word emphasise phrase from the brief."""
    sentences = brief_text.split(".")
    if len(sentences) >= 2:
        words = sentences[1].strip().split()
        return " ".join(words[:6]) if len(words) > 6 else sentences[1].strip()
    words = brief_text.split()
    return " ".join(words[:6])
