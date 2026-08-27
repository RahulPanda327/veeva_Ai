"""RepStream — FastAPI application entry point."""
import logging
import mimetypes
import os
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
from app.routers import assistant, objection_handler, new_writer_id, territory_prioritization, action_center
from app.utils.masking import BrandMaskingMiddleware
from app.utils.model_banner import log_stage
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


def _refresh_endpoint_cache_background(skip_assistant_kb: bool = True) -> None:
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
    # Named here as well as at startup: this is the point where real model calls
    # begin, and a warm-up log is what someone reads when the AI fields come back
    # empty. Include the embedding line only when the KB is actually re-embedded.
    log_stage("Warm-up", embedding=not skip_assistant_kb,
              store=not skip_assistant_kb, log=logger)

    cleared = clear_all_cached_responses()
    logger.info("Startup: cleared %d in-memory response cache entries.", cleared)

    time.sleep(5)
    try:
        cmd = [sys.executable, "scripts/warm_cache.py", "--only-response-cache",
               "--base-url", _detect_base_url()]
        if skip_assistant_kb:
            # --warmup without --embedding: refresh the caches but leave the
            # assistant's knowledge base as it was.
            cmd.append("--skip-assistant-kb")
        subprocess.run(cmd, cwd=_BACKEND_DIR)
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


def _flag(name: str) -> bool:
    """Read a startup flag set by the launcher below.

    Environment rather than sys.argv because uvicorn's --reload spawns a child
    process; argv is rebuilt there, but the environment is inherited, so the flag
    survives a reload. Absent means off.
    """
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def _embed_only() -> None:
    """Re-embed the assistant knowledge base without warming anything first.

    Exports from whatever the response cache already holds, so it reflects the
    last warm-up rather than this instant.
    """
    logger.info("Startup: --embedding only (no warm-up).")
    log_stage("Embedding", embedding=True, store=True, log=logger)
    try:
        from scripts.warm_cache import refresh_assistant_kb   # noqa: PLC0415

        refresh_assistant_kb(base_url=_detect_base_url())
    except Exception:
        logger.exception("Startup embedding refresh failed")


def _startup_tasks() -> None:
    """Warm-up and/or embedding, per the flags the launcher passed through."""
    do_warmup = _flag("REPSTREAM_WARMUP")
    do_embedding = _flag("REPSTREAM_EMBEDDING")

    if do_warmup:
        # The KB refresh is warm_cache.py's own final step, so let it run there
        # when embedding was also asked for — that keeps the ordering (warm-up
        # first, embed second) defined in one place instead of two.
        _refresh_endpoint_cache_background(skip_assistant_kb=not do_embedding)
    elif do_embedding:
        _embed_only()


def _log_llm_banner() -> None:
    """State the active LLM and embedding models at startup.

    Worth its own lines because every failure downstream is reported per-item
    ("... unavailable for AL-002"), which says nothing about WHICH model was
    being called. A wrong provider or base URL used to be visible only as
    hundreds of identical item-level warnings.

    The embedding model is resolved lazily by log_stage, so a process that only
    serves cached responses still does not pay for loading it here.
    """
    log_stage("Startup", embedding=True, store=True, log=logger)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    _log_llm_banner()
    if _flag("REPSTREAM_WARMUP") or _flag("REPSTREAM_EMBEDDING"):
        threading.Thread(target=_startup_tasks, daemon=True,
                         name="startup-cache-refresh").start()
    else:
        logger.info("Startup: no --warmup or --embedding flag - serving immediately. "
                    "Endpoints will be slow until a warm-up runs.")
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
app.include_router(assistant.router, prefix="/api/v1")

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


# ── Launcher ─────────────────────────────────────────────────────────────────
# Run the server directly, with two optional flags uvicorn itself cannot accept:
#
#   python main.py --reload --host 0.0.0.0 --port 8003
#   python main.py --reload --host 0.0.0.0 --port 8003 --warmup
#   python main.py --reload --host 0.0.0.0 --port 8003 --warmup --embedding
#   python main.py --reload --host 0.0.0.0 --port 8003 --embedding
#
# uvicorn parses its own arguments with click and exits on anything it does not
# recognise, before this module is imported - so `uvicorn main:app --warmup`
# cannot work. Running this file directly gives the flags somewhere to live.
#
# `uvicorn main:app ...` still works exactly as before; this block simply is not
# executed then, and no flags means no warm-up and no embedding.

_LAUNCH_FLAGS = {
    "--warmup": "REPSTREAM_WARMUP",
    "-warmup": "REPSTREAM_WARMUP",
    "--embedding": "REPSTREAM_EMBEDDING",
    "-embedding": "REPSTREAM_EMBEDDING",
    "--embeddings": "REPSTREAM_EMBEDDING",
    "-embeddings": "REPSTREAM_EMBEDDING",
}


def _launch() -> None:
    warmup = embedding = False
    host, port, reload_flag, log_level = "127.0.0.1", 8000, False, None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        flag = _LAUNCH_FLAGS.get(a.lower())
        if flag == "REPSTREAM_WARMUP":
            warmup = True
        elif flag == "REPSTREAM_EMBEDDING":
            embedding = True
        elif a == "--host" and i + 1 < len(args):
            host = args[i + 1]; i += 2; continue
        elif a == "--port" and i + 1 < len(args):
            port = int(args[i + 1]); i += 2; continue
        elif a == "--log-level" and i + 1 < len(args):
            log_level = args[i + 1]; i += 2; continue
        elif a == "--reload":
            reload_flag = True
        else:
            print(f"[main.py] ignoring unrecognised argument: {a}")
        i += 1

    # Passed by environment, not argv: --reload spawns a child process that
    # rebuilds its arguments but inherits the environment, so the flag survives.
    os.environ["REPSTREAM_WARMUP"] = "1" if warmup else "0"
    os.environ["REPSTREAM_EMBEDDING"] = "1" if embedding else "0"

    if warmup and embedding:
        plan = "warm-up, then re-embed the assistant knowledge base"
    elif warmup:
        plan = "warm-up only (knowledge base left as-is)"
    elif embedding:
        plan = "re-embed the assistant knowledge base only (no warm-up)"
    else:
        plan = "serve only - no warm-up, no embedding"
    print(f"[main.py] {plan}", flush=True)

    # _detect_base_url() reads these back to work out where the warm-up should
    # call in, so leave them on argv in the form it expects.
    sys.argv = [sys.argv[0], "--host", host, "--port", str(port)]

    import uvicorn

    kwargs = {"host": host, "port": port, "reload": reload_flag}
    if log_level:
        kwargs["log_level"] = log_level
    uvicorn.run("main:app", **kwargs)


if __name__ == "__main__":
    _launch()