"""Clear ALL caches, then immediately warm everything back up — one command.

Runs scripts/clear_cache.py and scripts/warm_cache.py as two SEPARATE
subprocesses, one after the other (not imported into this same process).
That separation matters: the AI-generation caches (insight/warm-approach/
email) are loaded into an in-memory dict once, at import time, in whichever
process touches them. If clear+warm ran in one process, deleting the disk
file wouldn't clear that process's own already-loaded in-memory copy, so
the warm step would see stale "already cached" data and skip regenerating
it. Two fresh subprocesses means each one loads from disk from scratch,
so the warm step genuinely sees an empty cache and regenerates for real.

Usage:
    python scripts/refresh_cache.py                                 # clear everything, warm every territory
    python scripts/refresh_cache.py --territory-id A0E000000013008  # clear everything, warm just one territory
    python scripts/refresh_cache.py --skip-response-cache           # skip the response-cache warm step
"""
import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent


def _run(args: list) -> int:
    print(f"$ {' '.join(args)}")
    result = subprocess.run([sys.executable, *args], cwd=_SCRIPTS_DIR.parent)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Clear all caches, then warm everything back up.")
    parser.add_argument("--territory-id", default=None, help="After clearing, warm only this territory instead of every territory.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Where the live server is, for response-cache warming.")
    parser.add_argument("--skip-response-cache", action="store_true", help="Skip warming the response cache step.")
    args = parser.parse_args()

    print("=== STEP 1: Clearing all caches ===")
    rc = _run(["scripts/clear_cache.py"])
    if rc != 0:
        print(f"clear_cache.py failed (exit {rc}) — aborting before warming.", file=sys.stderr)
        sys.exit(rc)

    print("\n=== STEP 2: Warming everything back up ===")
    warm_args = ["scripts/warm_cache.py", "--base-url", args.base_url]
    if args.territory_id:
        warm_args += ["--territory-id", args.territory_id]
    if args.skip_response_cache:
        warm_args += ["--skip-response-cache"]
    rc = _run(warm_args)

    print("\nDone — cache cleared and fully re-warmed." if rc == 0 else f"\nwarm_cache.py exited with code {rc}.")
    sys.exit(rc)


if __name__ == "__main__":
    main()
