"""
Session management routes.

GET  /sessions            — list all conversations for the current user
GET  /sessions/{id}       — full conversation history (for resume display)
PATCH /sessions/{id}      — rename a conversation
DELETE /sessions/{id}     — permanently delete conversation + all messages
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import dataclasses
from api.dependencies import get_current_user, get_service, get_session_store

router = APIRouter(prefix="/sessions", tags=["Sessions"])


# ── Response models ─────────────────────────────────────────────────────────────

class SessionSummary(BaseModel):
    id: str
    title: Optional[str]
    scenario: int = 1
    provider: str = "groq"
    model: str = ""
    message_count: int
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str


class SessionDetail(BaseModel):
    id: str
    title: Optional[str]
    scenario: int = 1
    provider: str = "groq"
    model: str = ""
    client_id: str = "api"
    message_count: int
    created_at: str
    updated_at: str
    messages: list[MessageOut]


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)


# ── Routes ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[SessionSummary], summary="List your conversations")
def list_sessions(
    limit: int = 50,
    user=Depends(get_current_user),
    store=Depends(get_session_store),
):
    sessions = store.list_sessions(user.username, limit=limit)
    return [
        SessionSummary(
            id=s.id,
            title=s.title or "(untitled)",
            scenario=getattr(s, "scenario", 1),
            provider=getattr(s, "provider", "groq"),
            model=getattr(s, "model", ""),
            message_count=s.message_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.get(
    "/recent-interactions",
    summary="Get recent chat interactions for logged-in user",
    description="Returns recent interactions only for the authenticated user, ordered by latest first.",
)
def get_recent_interactions(
    limit: int = 5,
    user=Depends(get_current_user),
    store=Depends(get_session_store),
):
    if not hasattr(store, "get_user_recent_interactions"):
        raise HTTPException(
            status_code=501,
            detail="Current session store does not support this operation.",
        )
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


@router.get(
    "/{session_id}",
    response_model=SessionDetail,
    summary="Get full conversation history",
    description="Returns all messages — use this to show the user what was discussed before resuming.",
)
def get_session(
    session_id: str,
    user=Depends(get_current_user),
    store=Depends(get_session_store),
):
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.username:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = store.get_messages(session_id)
    return SessionDetail(
        id=session.id,
        title=session.title or "(untitled)",
        scenario=getattr(session, "scenario", 1),
        provider=getattr(session, "provider", "groq"),
        model=getattr(session, "model", ""),
        client_id=getattr(session, "client_id", "api"),
        message_count=session.message_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            MessageOut(role=m.role, content=m.content, created_at=m.created_at)
            for m in messages
        ],
    )


@router.patch("/{session_id}", summary="Rename a conversation")
def rename_session(
    session_id: str,
    body: RenameRequest,
    user=Depends(get_current_user),
    store=Depends(get_session_store),
):
    updated = store.update_title(session_id, body.title, user.username)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found or access denied")
    return {"message": "Title updated", "session_id": session_id, "title": body.title}


@router.delete("/{session_id}", summary="Permanently delete a conversation and all its messages")
def delete_session(
    session_id: str,
    user=Depends(get_current_user),
    service=Depends(get_service),
    store=Depends(get_session_store),
):
    deleted = store.delete_session(session_id, user.username)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found or access denied")
    # Evict from in-memory cache so RAM is freed immediately
    service.memory.evict_session(session_id)
    return {"message": "Session deleted", "session_id": session_id}
