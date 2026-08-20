"""
Database admin and introspection routes.

GET  /db/test            — verify connectivity (SELECT @@VERSION)
GET  /db/templates       — list all pre-defined question templates
GET  /db/schema          — return the LLM schema context (tables + rules)
POST /db/sql             — execute an arbitrary read-only SQL (admin only)
GET  /charts/{file}      — serve a generated chart PNG
"""

import dataclasses
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_session_store
from config.settings import get_config
from services.base_service import ServiceFactory
from utils.logging_util import setup_logging

logger = setup_logging("db_route")

router = APIRouter(prefix="/db", tags=["Database"])


class SQLRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=20000)
    params: list = Field(default_factory=list)


class SQLResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int


@router.get("/recent-interactions", summary="Get recent chat interactions for logged-in user")
def get_recent_interactions(
    limit: int = 5,
    user=Depends(get_current_user),
    store=Depends(get_session_store),
):
    """
    Returns the most recent interactions for the authenticated user.
    Filters by user_id so each user only sees their own sessions and messages.
    """
    if not hasattr(store, "get_user_recent_interactions"):
        raise HTTPException(status_code=501, detail="Session store does not support this operation.")

    records = store.get_user_recent_interactions(user_id=user.username, limit=limit)

    return {
        "user_id": user.username,
        "count":   len(records),
        "interactions": [
            {
                "message_id":         r.message_id,
                "message_index":      r.message_index,
                "chat_session_id":    r.chat_session_id,
                "app_session_id":     r.app_session_id,
                "tenant_id":          r.tenant_id,
                "project_id":         r.project_id,
                "user_id":            r.user_id,
                "input_query":        r.input_query,
                "output_query":       r.output_query,
                "bot_status":         r.bot_status,
                "processing_details": r.processing_details,
                "feedback":           r.feedback,
                "user_action_status": r.user_action_status,
                "created_at":         r.created_at,
                "updated_at":         r.updated_at,
            }
            for r in records
        ],
    }


@router.get("/test", summary="Verify database connectivity")
def test_connection(user=Depends(get_current_user)):
    db = ServiceFactory.get_db()
    return db.ping()


@router.get("/templates", summary="List all pre-defined Q&A templates")
def list_templates(user=Depends(get_current_user)):
    router_ = ServiceFactory.get_sql_router()
    templates = router_.list_templates()
    return {"count": len(templates), "templates": templates}


@router.get("/schema", summary="Schema context used for LLM-generated SQL")
def get_schema(user=Depends(get_current_user)):
    from db_qa.sql_query_router import SCHEMA_CONTEXT
    return {"schema_context": SCHEMA_CONTEXT}


@router.post("/sql", response_model=SQLResponse, summary="Execute read-only SQL (admin)")
def exec_sql(body: SQLRequest, user=Depends(get_current_user)):
    db = ServiceFactory.get_db()
    try:
        cols, rows = db.execute(body.sql, body.params)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Query failed: {exc}") from exc
    # Make datetimes JSON-serializable
    for r in rows:
        for k, v in list(r.items()):
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
    return SQLResponse(columns=cols, rows=rows, row_count=len(rows))


# ── Charts ──────────────────────────────────────────────────────────────────────

charts_router = APIRouter(prefix="/charts", tags=["Charts"])


@charts_router.get("/{filename}", summary="Serve a generated chart PNG")
def get_chart(filename: str, user=Depends(get_current_user)):
    cfg = get_config()
    # Path-traversal guard + restrict to PNGs we actually generate.
    if (
        "/" in filename
        or "\\" in filename
        or ".." in filename
        or not filename.lower().endswith(".png")
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(cfg.chart_output_dir, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Chart not found")
    return FileResponse(path, media_type="image/png")
