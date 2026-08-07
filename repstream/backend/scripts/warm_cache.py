"""Pre-warms ALL caches — the 3 GPT-4o AI caches (Territory Prioritization
insights, New Writer ID warm-approach text + outreach emails) for every real
territory, PLUS the endpoint response cache for every GET endpoint — BEFORE
reps start hitting the app for the day.

Two different mechanisms, back to back:

1. AI caches: calls the service layer directly (no HTTP, server doesn't need
   to be running), synchronously, so nothing gets killed early the way the
   live API's fire-and-forget background thread would if run from a
   short-lived script.

2. Response cache: the response cache is keyed per-CALLER (Bearer token/IP),
   not just per-territory, so it can only be usefully pre-warmed by making
   REAL HTTP requests against the ACTUAL running server — that writes
   straight into that live process's own in-memory cache, not a throwaway
   copy. This step requires the FastAPI server to already be running and
   reachable at --base-url; if it isn't, this step is skipped with a warning
   (the AI-cache warming above still completes normally either way).

Usage:
    python scripts/warm_cache.py                                 # every territory
    python scripts/warm_cache.py --territory-id A0E000000013008  # just one (useful for testing)
    python scripts/warm_cache.py --base-url http://localhost:8000  # where the live server is (default shown)
    python scripts/warm_cache.py --skip-response-cache           # only warm the 3 AI caches
"""
import argparse
import logging
import os
import sys
import time
from datetime import date

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Also logged to disk (not just the console) — the Windows scheduled task
# runs headless with nowhere to see console output, so without this a
# failure like a broken DB column mapping is invisible until someone
# manually re-runs the script to reproduce it.
_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".warm_cache.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(_LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger("warm_cache")

from sqlalchemy import distinct, select

from app.database import SessionLocal
from app.models.territory_models import TerritoryHierarchy
from app.routers.territory_prioritization import _get_ranked_hcps
from app.routers.new_writer_id import _get_candidates
from app.services.territory_prioritization.llm_insight import warm_insights, count_uncached_insights
from app.services.new_writer_id.approach_brief import warm_approaches, warm_approach_briefs


def _all_territory_ids(db) -> list:
    rows = db.execute(select(distinct(TerritoryHierarchy.territory_id))).scalars().all()
    return [r for r in rows if r]


def warm_territory(db, territory_id: str) -> None:
    log.info("Warming territory %s ...", territory_id)

    ranked = _get_ranked_hcps(db, territory_id, date.today())
    pending = count_uncached_insights(ranked)
    if pending:
        log.info("  Territory Prioritization: warming %d/%d HCP insights...", pending, len(ranked))
        warm_insights(ranked)
    else:
        log.info("  Territory Prioritization: all %d HCP insights already warm.", len(ranked))

    candidates = _get_candidates(db, territory_id)
    if candidates:
        log.info("  New Writer ID: warming approach text + emails for %d candidates...", len(candidates))
        warm_approaches(candidates)
        warm_approach_briefs(candidates)
    else:
        log.info("  New Writer ID: no candidates for this territory.")


# GET endpoints that get response-cached. No query params here because the
# real ones (territory/rep) are derived server-side from the caller's auth —
# this hits whatever the server resolves the caller to (the single dev
# identity while DEV_SKIP_AUTH=true), same as any real user would.
_RESPONSE_CACHE_ENDPOINTS = [
    "/api/v1/territory/summary",
    "/api/v1/territory/hcp-list",
    "/api/v1/new-writers/candidates",
    "/api/v1/action-center/alerts",
    "/api/v1/action-center/alerts/summary",
    "/api/v1/action-center/hcp-awareness",
    "/api/v1/action-center/competitive-intel",
    "/api/v1/action-center/payer-access",
    "/api/v1/objections/list",
]

# Data endpoints whose per-TERRITORY filtered variant is pre-warmed, so the first
# filtered request is a cache hit from endpoint_response_cache.json — no DB/GPT
# round-trip. Kept deliberately small:
#   • only territory_id variants (employee/manager selections just re-combine these
#     already-warmed per-territory caches, so their first hit is cheap anyway);
#   • new-writers/candidates is NOT here — it's warmed in-process by the New Writer
#     pre-warm step, so warming it over HTTP too would be duplicate GPT work;
#   • summaries are excluded — they recompute from the remembered filter and are
#     never response-cached.
_FILTERABLE_ENDPOINTS = [
    "/api/v1/territory/hcp-list",
    "/api/v1/objections/list",
    "/api/v1/action-center/alerts",
    "/api/v1/action-center/hcp-awareness",
    "/api/v1/action-center/competitive-intel",
    "/api/v1/action-center/payer-access",
]

# List endpoints that record the caller's "last filter". Re-hitting them unfiltered
# (a cache hit, instant) resets that memory to empty after variant warming.
_LIST_RESET_ENDPOINTS = [
    "/api/v1/territory/hcp-list",
    "/api/v1/action-center/alerts",
]


def _territory_ids(client) -> list:
    """Territory ids to pre-warm, read from the live org filter tree (returned
    inside any summary endpoint)."""
    try:
        tree = client.get("/api/v1/territory/summary").json().get("filters", {})
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load filter tree for variant warming (%s).", exc)
        return []

    out, seen = [], set()
    for m in tree.get("manager_id", []):
        for e in m.get("employee_id", []):
            for t in e.get("territory_id", []):
                tid = t.get("territory_id")
                if tid and tid not in seen:
                    seen.add(tid)
                    out.append(tid)
    return out


def warm_response_cache(base_url: str) -> None:
    """Hits every response-cached GET endpoint on the REAL running server, so
    the entries land in that live process's own memory — not a throwaway copy.
    Requires the server to already be up; skips gracefully if not.

    Order matters:
      1) unfiltered baseline for every endpoint FIRST — this is the fast (~3 min)
         'app is usable' warm, same as before the filter variants existed;
      2) per-territory filtered variants AFTER — an optimization that fills in while
         the app is already serving unfiltered requests from cache;
      3) a cheap reset (cache-hit unfiltered list calls) so the per-caller 'last
         filter' memory ends empty and a fresh summary shows unfiltered counts.
    """
    try:
        httpx.get(f"{base_url}/health", timeout=5)
    except httpx.RequestError:
        log.warning(
            "Server not reachable at %s — skipping response-cache warm-up "
            "(the 3 AI caches above are already warmed regardless).",
            base_url,
        )
        return

    log.info("Warming response cache via live server at %s ...", base_url)
    # No timeout: warming is a background job with nothing waiting on it, and the
    # LLM-enriched endpoints legitimately run for minutes on a cold cache — a local
    # model is slower than a hosted one, and every alert/HCP needs its own call.
    # A deadline here doesn't cancel that work (the server keeps going and still
    # fills the cache), it only makes the client stop listening and log a
    # misleading "failed (timed out)". Waiting is correct; the server's own
    # LLM_TIMEOUT / LLM_MAX_RETRIES remain the real per-call limits.
    with httpx.Client(base_url=base_url, timeout=None) as client:
        # 1) Unfiltered baseline FIRST — restores the ~3-min 'app ready' timing.
        for path in _RESPONSE_CACHE_ENDPOINTS:
            try:
                start = time.time()
                r = client.get(path)
                log.info("  %s -> %d (%.1fs)", path, r.status_code, time.time() - start)
            except Exception as exc:
                log.warning("  %s -> failed (%s)", path, exc)

        # 2) Per-territory filtered variants — after the app is already usable.
        territory_ids = _territory_ids(client)
        if territory_ids:
            log.info(
                "Warming %d territory variant(s) x %d endpoint(s) (background optimization) ...",
                len(territory_ids), len(_FILTERABLE_ENDPOINTS),
            )
            for path in _FILTERABLE_ENDPOINTS:
                for tid in territory_ids:
                    try:
                        start = time.time()
                        r = client.get(path, params={"territory_id": tid})
                        log.info("  %s?territory_id=%s -> %d (%.1fs)", path, tid, r.status_code, time.time() - start)
                    except Exception as exc:
                        log.warning("  %s?territory_id=%s -> failed (%s)", path, tid, exc)

            # 3) Reset the 'last filter' memory to empty (cache-hit calls, instant).
            for path in _LIST_RESET_ENDPOINTS:
                try:
                    client.get(path)
                except Exception as exc:
                    log.warning("  reset %s -> failed (%s)", path, exc)


def main():
    parser = argparse.ArgumentParser(description="Pre-warm all AI caches, and the response cache, before business hours.")
    parser.add_argument("--territory-id", default=None, help="Warm only this territory instead of every territory.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Where the live server is, for response-cache warming.")
    parser.add_argument("--skip-response-cache", action="store_true", help="Only warm the 3 AI caches, skip the response cache step.")
    parser.add_argument("--only-response-cache", action="store_true",
                         help="Skip the AI-cache warming loop entirely (no DB territory scan, no GPT-4o calls) "
                              "and only run the fast endpoint/response-cache warming step. Uses whatever is "
                              "already in the 3 AI-generation caches as-is, without regenerating anything.")
    args = parser.parse_args()

    failed = 0
    total = 0

    if not args.only_response_cache:
        db = SessionLocal()
        try:
            try:
                territory_ids = [args.territory_id] if args.territory_id else _all_territory_ids(db)
            except Exception:
                log.exception("Could not load territory list — aborting run (nothing was warmed).")
                sys.exit(1)
            total = len(territory_ids)
            log.info("Warming %d territor%s...", total, "y" if total == 1 else "ies")

            start = time.time()
            for territory_id in territory_ids:
                try:
                    warm_territory(db, territory_id)
                except Exception:
                    log.exception("Failed to warm territory %s", territory_id)
                    failed += 1

            log.info("AI caches done in %.1fs (%d/%d territories failed).", time.time() - start, failed, total)
        finally:
            db.close()

    if not args.skip_response_cache:
        warm_response_cache(args.base_url)

    log.info("Warm-up run complete.")

    if total and failed == total:
        # Every single territory failed — this is not a successful run,
        # even though we didn't crash. Let callers (e.g. refresh_cache.py)
        # know via a non-zero exit code instead of silently reporting success.
        sys.exit(1)


if __name__ == "__main__":
    main()
