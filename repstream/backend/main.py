"""RepStream — FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import objection_handler, new_writer_id, territory_prioritization, action_center


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


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "RepStream API", "version": "1.0.0"}
