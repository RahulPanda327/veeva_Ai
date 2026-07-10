"""Clear the local response cache (backend/.endpoint_response_cache.json).

Only clears the 24h GET-response cache (app/utils/response_cache.py) — the
one built for "same user hits same endpoint within 24h = instant response".
Does NOT touch the AI-generation caches (.insight_cache.json,
.warm_approach_cache.json, .approach_email_cache.json) — those are cleared
separately since wiping them means real GPT-4o calls have to re-run.

IMPORTANT: if the backend server is already running, it holds its own
in-memory copy of the cache. Clearing the file here does not affect a live
server's memory — restart the server after running this so it reloads the
now-empty file.

Usage:
    python scripts/clear_cache.py            # clear everything
    python scripts/clear_cache.py --expired  # clear only expired entries
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.response_cache import clear_all, clear_expired, _cache


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expired", action="store_true",
        help="Only remove entries older than 24h, keep everything still fresh",
    )
    args = parser.parse_args()

    before = len(_cache)

    if args.expired:
        removed = clear_expired()
        print(f"Removed {removed} expired entr{'y' if removed == 1 else 'ies'} "
              f"({before - removed} still fresh, left in place).")
    else:
        removed = clear_all()
        print(f"Cleared all {removed} cached response(s).")

    print("\nIf the backend server is currently running, restart it now")
    print("so it picks up the cleared cache (it keeps its own copy in memory).")


if __name__ == "__main__":
    main()
