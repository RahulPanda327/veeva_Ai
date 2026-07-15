"""Clear ALL RepStream local disk caches (backend/.*.json).

Clears all 4 disk-persisted caches used across the project:
  - .endpoint_response_cache.json  (24h/N-min GET-response cache, response_cache.py)
  - .insight_cache.json            (Territory Prioritization GPT-4o insights)
  - .warm_approach_cache.json      (New Writer ID GPT-4o warm-approach text)
  - .approach_email_cache.json     (New Writer ID GPT-4o outreach emails)

The response cache has a real TTL and expires on its own; the 3 AI-generation
caches never expire on their own (regenerating them means real GPT-4o calls),
so this script clears all 4 by default and lets you narrow it down with flags.

IMPORTANT: if the backend server is already running, it holds its own
in-memory copy of each cache. Clearing the files here does not affect a
live server's memory — restart the server after running this (or use
POST /admin/cache/clear for the response cache specifically, the only one
with a live-clear endpoint that doesn't require a restart).

Usage:
    python scripts/clear_cache.py                # clear all 4 caches
    python scripts/clear_cache.py --expired       # response cache: only expired entries; AI caches untouched
    python scripts/clear_cache.py --response-only # only the response cache, skip the 3 AI-generation caches
    python scripts/clear_cache.py --ai-only       # only the 3 AI-generation caches, skip the response cache
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.response_cache import clear_all as clear_response_cache, clear_expired, _cache as _response_cache

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_AI_CACHE_FILES = {
    "insight cache":        _BACKEND_DIR / ".insight_cache.json",
    "warm approach cache":  _BACKEND_DIR / ".warm_approach_cache.json",
    "approach email cache": _BACKEND_DIR / ".approach_email_cache.json",
}


def _clear_ai_caches() -> None:
    for label, path in _AI_CACHE_FILES.items():
        if path.exists():
            path.unlink()
            print(f"Cleared {label} ({path.name}).")
        else:
            print(f"{label} ({path.name}) was already empty/not present.")


def main():
    parser = argparse.ArgumentParser(description="Clear all of RepStream's local disk caches.")
    parser.add_argument(
        "--expired", action="store_true",
        help="Response cache: only remove entries past their TTL, keep fresh ones. "
             "Does not apply to the AI-generation caches — they have no expiry, "
             "so --expired never touches them.",
    )
    parser.add_argument(
        "--response-only", action="store_true",
        help="Only clear the endpoint response cache, skip the 3 AI-generation caches.",
    )
    parser.add_argument(
        "--ai-only", action="store_true",
        help="Only clear the 3 AI-generation caches (insight/warm-approach/email), skip the response cache.",
    )
    args = parser.parse_args()

    if not args.ai_only:
        before = len(_response_cache)
        if args.expired:
            removed = clear_expired()
            print(f"Response cache: removed {removed} expired entr{'y' if removed == 1 else 'ies'} "
                  f"({before - removed} still fresh, left in place).")
        else:
            removed = clear_response_cache()
            print(f"Response cache: cleared all {removed} cached response(s).")

    if not args.response_only:
        _clear_ai_caches()

    print("\nIf the backend server is currently running, restart it now (or hit")
    print("POST /admin/cache/clear for the response cache) so it picks up the clear —")
    print("it keeps its own copy of each cache in memory.")


if __name__ == "__main__":
    main()
