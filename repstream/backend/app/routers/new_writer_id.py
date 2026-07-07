"""Module 2 — New Writer Identification API endpoints."""
import logging
import threading
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.new_writer import ApproachBriefResponse, NewWriterCandidate, NewWriterListResponse
from app.services.new_writer_id.approach_brief import (
    attach_approach_briefs,
    attach_warm_approaches,
    build_approach_brief_response,
    count_unwarmed,
    generate_approach_brief,
    warm_approach_briefs,
    warm_approaches,
)
from app.services.new_writer_id.icd10_matching import enrich_with_icd10
from app.services.new_writer_id.match_scoring import enrich_with_peer_match
from app.services.new_writer_id.non_writer_detection import detect_non_writers, enrich_with_hcp_dimensions
from app.services.territory_prioritization.data_ingestion import get_current_and_prior_quarter
from app.utils.auth import RepIdentity, get_current_rep
from app.utils.cache import cache_get, cache_set, territory_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/new-writers", tags=["New Writer Identification"])

_CACHE_TTL = 3600

# Background GPT-4o warm-approach warmer — one per territory at a time
_warming_territories: set = set()
_warm_lock = threading.Lock()


def _maybe_warm_approaches_async(territory_id: str, candidates: List[dict]) -> None:
    """Fire-and-forget: GPT-4o warm approaches for candidates still null.
    Next page load serves them from the persisted cache."""
    needs_briefs = sum(1 for c in candidates if c.get("approach_brief") is None)
    with _warm_lock:
        if territory_id in _warming_territories:
            return
        if count_unwarmed(candidates) == 0 and needs_briefs == 0:
            return
        _warming_territories.add(territory_id)

    def _run():
        try:
            warm_approaches(candidates)
            warm_approach_briefs(candidates)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Warm approach warmer failed for %s: %s", territory_id, exc)
        finally:
            with _warm_lock:
                _warming_territories.discard(territory_id)

    threading.Thread(target=_run, daemon=True, name=f"warm-approach-{territory_id}").start()


def _build_badges(c: dict) -> List[str]:
    badges = ["ML_PATTERN_MATCHING"]
    if c.get("ai_icd10_match_count", 0) > 0:
        badges.append("AI_MATCHED")
    if c.get("ai_warm_approach_text"):
        badges.append("AI_GENERATED")
    return badges


def _get_candidates(db: Session, territory_id: str) -> List[dict]:
    cache_key = territory_cache_key("new_writers:candidates_v3", territory_id)
    cached = cache_get(cache_key)
    if cached:
        return cached

    (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(date.today())

    # Detect + enrich (raw SQL join or sample fallback)
    raw      = detect_non_writers(db, territory_id, yr1, q1, yr4, q4)
    enriched = enrich_with_hcp_dimensions(db, raw, territory_id)
    enriched = enrich_with_icd10(enriched)
    enriched = enrich_with_peer_match(db, enriched, territory_id)

    # Rename peer-match keys to ai_ prefix
    for c in enriched:
        c["ai_peer_match_score"]    = c.pop("peer_match_pct", c.get("ai_peer_match_score", 0.0))
        c["ai_peer_name"]           = c.pop("peer_name",     c.get("ai_peer_name"))
        c["ai_peer_hcp_id"]         = c.pop("peer_hcp_id",   c.get("ai_peer_hcp_id"))
        c["ai_peer_rationale"]      = c.pop("match_rationale", c.get("ai_peer_rationale"))
        codes = c.pop("matched_icd10_codes", c.get("ai_icd10_matched_codes") or [])
        # No ICD-10 source column exists in the warehouse — send "" when empty
        c["ai_icd10_matched_codes"] = codes if codes else ""
        c["ai_icd10_match_count"]   = len(codes)
        c["ai_non_writer_flag"]     = True
        # Trailing-4-quarter total from the brand table when present, else the quarterly sum
        c["total_in_class_rx"]      = float(c.get("total_in_class_rx") or c.get("in_class_rx_q1", 0) or 0)

    # Warm approach text: real Warm_Approach_Text DB value (KPI 7) wins when a
    # peer match exists; otherwise the cached GPT-4o generation (attach below).
    for c in enriched:
        c["ai_warm_approach_text"] = c.get("ai_peer_rationale")
        c["ai_approach_highlight"] = None
    attach_warm_approaches(enriched)
    attach_approach_briefs(enriched)
    _maybe_warm_approaches_async(territory_id, enriched)

    # Build badges
    for c in enriched:
        c["analysis_badges"] = _build_badges(c)
        c["ai_is_identified"] = True

    cache_set(cache_key, enriched, ttl=_CACHE_TTL)
    return enriched


@router.get("/candidates", response_model=List[NewWriterCandidate])
async def get_new_writer_candidates(
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Non-writer candidates with ML peer match, ICD-10 matching, and AI warm approach."""
    return [NewWriterCandidate(**c) for c in _get_candidates(db, rep.territory_id)]


@router.post("/{hcp_id}/approach-brief", response_model=ApproachBriefResponse)
async def generate_warm_approach_brief(
    hcp_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """On-demand: GPT-4o warm approach brief for a single new writer candidate."""
    candidates = _get_candidates(db, rep.territory_id)
    hcp = next((c for c in candidates if c["hcp_id"] == hcp_id), None)
    if hcp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate {hcp_id} not found",
        )

    service_hcp = {
        **hcp,
        "peer_name":           hcp.get("ai_peer_name"),
        "matched_icd10_codes": hcp.get("ai_icd10_matched_codes", []),
    }
    brief_text = generate_approach_brief(service_hcp)
    result     = build_approach_brief_response(service_hcp, brief_text)

    return ApproachBriefResponse(
        hcp_id=result["hcp_id"],
        ai_approach_brief=result["brief_text"],
        ai_approach_highlight=_extract_highlight(result["brief_text"]),
        ai_peer_name=result.get("peer_name"),
        generated_at=result["generated_at"],
        cached=result.get("cached", False),
    )


def _extract_highlight(brief_text: str) -> str:
    sentences = brief_text.split(".")
    if len(sentences) >= 2:
        words = sentences[1].strip().split()
        return " ".join(words[:6]) if len(words) > 6 else sentences[1].strip()
    words = brief_text.split()
    return " ".join(words[:6])
