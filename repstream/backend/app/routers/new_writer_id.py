"""Module 2 — New Writer Identification API endpoints."""
import json
import logging
import os
import threading
import time
from datetime import date
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.new_writer import ApproachBriefResponse, NewWriterCandidate, NewWriterListResponse
from app.services.filters_service import (
    FilterSelection,
    filter_params,
    get_org_filters,
    hcps_for_territories,
    normalize_territory_id,
    resolve_territories,
    salesforce_of,
)
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
from app.services.new_writer_id.non_writer_detection import (
    detect_new_writers_for_hcps,
    detect_non_writers,
    enrich_with_hcp_dimensions,
)
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


def _enrich_candidates(
    db: Session, raw: List[dict], territory_id: str, block_on_ai: bool = False
) -> List[dict]:
    """Shared enrichment chain (ICD-10, peer match, warm approach, badges) —
    territory_id here is only a label threaded through to the enrichment
    functions' signatures; none of them actually filter by it (peer_network's
    load_peer_matches already scopes to the candidates' own hcp_ids).

    block_on_ai=True waits for GPT-4o warm-approach/brief generation to finish
    before returning, instead of the normal fire-and-forget background warmer.
    Used only by the startup pre-warm pass (see warm_all_territory_candidates)
    so the per-territory cache is stored fully populated — never with nulls
    the UI would otherwise see on a request that lands before background
    warming finishes."""
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

    if block_on_ai:
        warm_approaches(enriched)
        warm_approach_briefs(enriched)
        attach_warm_approaches(enriched)
        attach_approach_briefs(enriched)
    else:
        _maybe_warm_approaches_async(territory_id, enriched)

    # Build badges
    for c in enriched:
        c["analysis_badges"] = _build_badges(c)
        c["ai_is_identified"] = True

    return enriched


def _get_candidates(db: Session, territory_id: str) -> List[dict]:
    """Default (unfiltered) candidate list — the small, curated KPI-7
    insight360_peer_match_dul set. This module was never territory-scoped
    by default; see _get_candidates_for_hcp_set for the live, per-territory
    derivation used when a manager/employee/territory filter is given."""
    cache_key = territory_cache_key("new_writers:candidates_v3", territory_id)
    cached = cache_get(cache_key)
    if cached:
        return cached

    (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(date.today())

    raw = detect_non_writers(db, territory_id, yr1, q1, yr4, q4)
    enriched = _enrich_candidates(db, raw, territory_id)

    cache_set(cache_key, enriched, ttl=_CACHE_TTL)
    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# Per-territory candidate cache — persisted to disk as JSON, same style as the
# GPT-4o warm-approach / approach-brief caches (approach_brief.py).
#
# Flow: on startup, warm_all_territory_candidates() CLEARS this, regenerates
# every territory's candidate list (live Synapse detection + full GPT-4o
# enrichment, blocking so nothing is null), and writes it to
# .new_writer_candidates_cache.json. At request time the filter reads ONLY from
# this cache (in memory, loaded from that JSON) — it never regenerates at the
# application level. A manager/employee selection is served by unioning the
# already-warmed territory lists.
# ─────────────────────────────────────────────────────────────────────────────

_CANDIDATE_CACHE_FILE = Path(__file__).resolve().parents[2] / ".new_writer_candidates_cache.json"
_CANDIDATE_CACHE: dict[str, List[dict]] = {}   # bare territory_id -> enriched candidates
_candidate_io_lock = threading.Lock()


def _load_candidate_cache() -> None:
    try:
        with open(_CANDIDATE_CACHE_FILE, encoding="utf-8") as f:
            _CANDIDATE_CACHE.update(json.load(f))
        logger.info("Loaded New Writer candidates for %d territories from %s",
                    len(_CANDIDATE_CACHE), _CANDIDATE_CACHE_FILE.name)
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load New Writer candidate cache (%s).", exc)


def _save_candidate_cache() -> None:
    try:
        with _candidate_io_lock:
            tmp = _CANDIDATE_CACHE_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_CANDIDATE_CACHE, f, default=str)
            os.replace(tmp, _CANDIDATE_CACHE_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save New Writer candidate cache (%s).", exc)


_load_candidate_cache()


def _generate_candidates_for_territory(db: Session, territory_id: str, sf: str) -> List[dict]:
    """Live-detect + fully enrich (blocking on GPT-4o) the candidates for ONE
    real territory. Generation only — used by the startup warm-up; the request
    path never calls this, it reads the cache."""
    hcp_ids = hcps_for_territories(db, [normalize_territory_id(territory_id, sf)])
    if not hcp_ids:
        return []
    (yr1, q1), _ = get_current_and_prior_quarter(date.today())
    raw = detect_new_writers_for_hcps(db, hcp_ids, yr1, q1)
    if not raw:
        return []
    return _enrich_candidates(db, raw, territory_id, block_on_ai=True)


def warm_all_territory_candidates(db: Session, max_workers: int = 3) -> None:
    """Startup warm-up: CLEAR the previous candidate cache, regenerate every
    territory's list fresh (live detection + full GPT-4o enrichment), and save
    it to .new_writer_candidates_cache.json — so the filter can serve straight
    from that JSON without regenerating.

    Must run IN-PROCESS (see main.py's startup thread) so it populates THIS
    running server's _CANDIDATE_CACHE, not a subprocess's separate copy.
    Regeneration is fast after the first run because the per-HCP GPT-4o text
    (warm approach + email) is itself disk-cached by hcp_id in approach_brief.py
    — so a restart re-runs the Synapse queries + GPT cache hits, not fresh
    GPT-4o calls. Territories run a few at a time, each with its own DB session
    (SQLAlchemy sessions aren't thread-safe)."""
    from concurrent.futures import ThreadPoolExecutor
    from app.database import SessionLocal

    sf = salesforce_of(None)
    tree = get_org_filters(db, sf)
    territory_ids = sorted({
        t["territory_id"]
        for m in tree.get("manager_id", [])
        for e in m["employee_id"]
        for t in e["territory_id"]
    })

    # Clear the previous cache first (per the "restart clears + regenerates" flow)
    with _candidate_io_lock:
        _CANDIDATE_CACHE.clear()

    logger.info("Warming New Writer ID candidates for %d territories (%d at a time)...",
                len(territory_ids), max_workers)
    start = time.time()

    def _warm_one(terr: str) -> None:
        worker_db = SessionLocal()
        try:
            candidates = _generate_candidates_for_territory(worker_db, terr, sf)
            with _candidate_io_lock:
                _CANDIDATE_CACHE[terr] = candidates
            logger.info("  %s: %d candidates warmed.", terr, len(candidates))
        except Exception:  # noqa: BLE001
            logger.exception("Failed to warm New Writer candidates for territory %s", terr)
        finally:
            worker_db.close()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(_warm_one, territory_ids))

    _save_candidate_cache()
    logger.info("New Writer ID territory warm-up done in %.1fs (%d territories in JSON).",
                time.time() - start, len(_CANDIDATE_CACHE))


@router.get("/candidates", response_model=List[NewWriterCandidate])
async def get_new_writer_candidates(
    sel: FilterSelection = Depends(filter_params),
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Non-writer candidates with ML peer match, ICD-10 matching, and AI warm approach.

    Pass manager_id/employee_id/territory_id to scope candidates to that
    territory's real HCP population; unfiltered returns the default KPI-7 list."""
    if not sel.is_empty():
        sf = salesforce_of(rep.territory_id)
        territories = resolve_territories(db, sf, sel) or []
        bare_terrs = sorted({t.split("|")[-1] for t in territories})

        # Read ONLY from the warmed JSON cache — never regenerate at request time.
        merged: dict[str, dict] = {}
        with _candidate_io_lock:
            for terr in bare_terrs:
                for c in _CANDIDATE_CACHE.get(terr, []):
                    merged[c["hcp_id"]] = c
        # Re-cap to the top 10 by competitor Rx volume across the whole
        # selection — same "highest-value targets first" intent as a single
        # territory, whether the scope is one territory or a manager's 8.
        candidates = sorted(merged.values(), key=lambda c: -(c.get("in_class_rx_q1") or 0))[:10]
    else:
        candidates = _get_candidates(db, rep.territory_id)

    return [NewWriterCandidate(**c) for c in candidates]


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
