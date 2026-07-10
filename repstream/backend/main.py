"""RepStream — FastAPI application entry point."""
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import objection_handler, new_writer_id, territory_prioritization, action_center
from app.utils.envelope import EnvelopeMiddleware
from app.utils.response_cache import DailyResponseCacheMiddleware, clear_all as clear_all_cached_responses

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"

# Windows' mimetypes DB often lacks modern Office formats — register explicitly
# so served .docx/.xlsx/.pptx files get the right Content-Type, not none.
mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx")
mimetypes.add_type("application/pdf", ".pdf")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
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
#   CORS (outer) -> DailyResponseCache (middle) -> Envelope (inner, closest to routes)
# Envelope wraps the raw route output into {success, response} FIRST, so the
# cache stores/serves the already-wrapped body; CORS stays outermost so its
# headers still apply even when Cache returns early on a hit.
app.add_middleware(EnvelopeMiddleware)
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
