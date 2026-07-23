"""Single home for all persisted JSON caches: backend/cache/.

Every module that keeps a disk-backed JSON cache (LLM insights, New Writer
warm-approach / email text, per-territory candidates, the endpoint response
cache) resolves its file through cache_file() so they all live in one folder
instead of scattered dotfiles in the backend root.
"""
from pathlib import Path

# app/utils/cache_paths.py -> app/utils -> app -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = BACKEND_DIR / "cache"


def cache_file(name: str) -> Path:
    """Return backend/cache/<name>, creating the cache folder on first use."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name
