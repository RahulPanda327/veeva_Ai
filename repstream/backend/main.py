"""RepStream — FastAPI application entry point."""
import logging
import mimetypes
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import objection_handler, new_writer_id, territory_prioritization, action_center
from app.utils.masking import BrandMaskingMiddleware
from app.utils.response_cache import DailyResponseCacheMiddleware, clear_all as clear_all_cached_responses

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
_BACKEND_DIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)

# Windows' mimetypes DB often lacks modern Office formats — register explicitly
# so served .docx/.xlsx/.pptx files get the right Content-Type, not none.
mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx")
mimetypes.add_type("application/pdf", ".pdf")


def _refresh_endpoint_cache_background() -> None:
    """Clear the response cache and re-warm the endpoints themselves — runs
    once on every app startup (no fixed clock time; tied to the process
    lifecycle instead). Runs in a background thread so server startup itself
    isn't blocked. Fast: only the 9 response-cached endpoints get hit, using
    whatever is already in the 3 AI-generation caches as-is.

    Deliberately does NOT touch the 3 AI-generation caches (insight/warm-
    approach/email) — regenerating those means a real DB scan across all
    204 territories plus real GPT-4o calls per HCP, which realistically
    takes 50+ hours end to end. Doing that on every --reload restart (which
    fires on every file save during dev) would mean it never actually
    finishes and just keeps restarting from zero. Full AI-cache regeneration
    is still available on demand via `python scripts/refresh_cache.py` or
    `python scripts/warm_cache.py`, run manually or on an external schedule
    (e.g. the VM's own cron/Task Scheduler) — just not tied to app startup.

    The response cache IS cleared HERE, in-process, first — the warming
    subprocess spawned below runs as a separate process, and that process
    clearing the disk file has no effect on THIS process's already-loaded
    in-memory copy (loaded once, at import time, from whatever was on disk
    from before this restart). Without this explicit in-process clear, any
    endpoint that was already cached before the restart would keep silently
    serving that old, stale data forever.

    The short sleep just lets uvicorn finish binding the port before the
    subprocess tries to call back into this same server over HTTP.

    base_url is detected from THIS process's own --port argument (uvicorn
    runs main.py in the same process it was launched in, so sys.argv still
    has whatever was typed on the command line) — without this, the warm-up
    would always call back to a hardcoded localhost:8000, which silently
    does nothing whenever the server is actually started on a different
    port (e.g. `uvicorn main:app --port 8006`)."""
    cleared = clear_all_cached_responses()
    logger.info("Startup: cleared %d in-memory response cache entries.", cleared)

    time.sleep(5)
    try:
        subprocess.run(
            [sys.executable, "scripts/warm_cache.py", "--only-response-cache", "--base-url", _detect_base_url()],
            cwd=_BACKEND_DIR,
        )
    except Exception:
        logger.exception("Startup endpoint-cache refresh failed")

    # New Writer ID per-territory warm-up runs LAST, sequentially — AFTER the
    # response-cache warm-up above has fully finished. It's minutes of Synapse
    # queries + GPT-4o calls; running it concurrently starves the DB pool
    # (15 conns max) and GPT throughput, which made the response-cache
    # endpoints above crawl (summary timed out, hcp-list 40s). Sequential =
    # the fast response cache is warm in ~3 min like before, then this runs
    # with the field to itself.
    _warm_new_writer_territories()


def _detect_base_url() -> str:
    """Read --port (and --host, if not a bind-all address) from sys.argv —
    the same argv uvicorn itself was launched with, since main.py runs in
    that same process. Falls back to localhost:8000 if not found."""
    argv = sys.argv
    port = "8000"
    host = "localhost"
    for i, arg in enumerate(argv):
        if arg == "--port" and i + 1 < len(argv):
            port = argv[i + 1]
        elif arg == "--host" and i + 1 < len(argv):
            candidate = argv[i + 1]
            if candidate not in ("0.0.0.0", "::"):  # not connectable as a destination
                host = candidate
    return f"http://{host}:{port}"


def _warm_new_writer_territories() -> None:
    """Warm the New Writer ID per-territory candidate cache and persist it to
    .new_writer_candidates_cache.json. Runs IN-PROCESS (writes THIS server's
    _CANDIDATE_CACHE dict, not a subprocess copy) and is called sequentially at
    the end of _refresh_endpoint_cache_background — never concurrently with the
    response-cache warm-up, to avoid starving the DB pool / GPT throughput."""
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            new_writer_id.warm_all_territory_candidates(db)
        finally:
            db.close()
    except Exception:
        logger.exception("New Writer ID territory pre-warm failed")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    threading.Thread(target=_refresh_endpoint_cache_background, daemon=True, name="startup-cache-refresh").start()
    yield


app = FastAPI(
    title="RepStream API",
    description="AI-powered CRM intelligence platform for pharmaceutical sales reps",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Middleware order (Starlette: last added = outermost = runs first on request):
#   CORS (outer) -> DailyResponseCache (middle) -> BrandMasking (inner, closest to routes)
# Masking runs first so the cache stores the already-masked body.
app.add_middleware(BrandMaskingMiddleware)
app.add_middleware(DailyResponseCacheMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(territory_prioritization.router, prefix="/api/v1")
app.include_router(new_writer_id.router, prefix="/api/v1")
app.include_router(objection_handler.router, prefix="/api/v1")
app.include_router(action_center.router, prefix="/api/v1")

# Serves the real files in backend/resources/ (e.g. payer-access support docs)
# at /api/v1/resources/<filename> — real, clickable, downloadable links.
RESOURCES_DIR.mkdir(exist_ok=True)
app.mount("/api/v1/resources", StaticFiles(directory=RESOURCES_DIR), name="resources")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "RepStream API", "version": "1.0.0"}


@app.post("/admin/cache/clear", tags=["Admin"])
async def clear_response_cache():
    """Clear the 24h GET-response cache in THIS running process's memory.

    Runs inside the live server, unlike scripts/clear_cache.py (a separate
    process that can only touch the disk file) — so this takes effect
    immediately, no restart needed.
    """
    cleared = clear_all_cached_responses()
    return {"cleared": cleared}
