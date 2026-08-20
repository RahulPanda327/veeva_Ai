"""
Feedback routes — thumbs-up / thumbs-down votes and text comments.

All feedback is persisted to the same store (SQLite or PostgreSQL) that
chat.py writes to, keyed by message_id returned from POST /chat.

Endpoints (all require a valid JWT Bearer token):
  POST /feedback/vote     — thumbs_up | thumbs_down via RequestPayload
  POST /feedback/comment  — attach a comment to any voted message
"""

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_current_user, get_session_store
from api.models import RequestPayload, OutputQuery, BotStatusItem, ResponseBody, StandardApiResponse

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class VoteRequest(BaseModel):
    request: RequestPayload


class CommentRequest(BaseModel):
    request: RequestPayload


# ── Routes ───────────────────────────────────────────────────────────────────────

@router.post(
    "/vote",
    response_model=StandardApiResponse,
    summary="Submit thumbs-up or thumbs-down for a message",
    description=(
        "Use `message_id` from `POST /chat` response.\n\n"
        "- `user_action_status: good_response` — thumbs up\n"
        "- `user_action_status: bad_response`  — thumbs down"
    ),
)
def submit_vote(
    body: VoteRequest,
    user=Depends(get_current_user),
    store=Depends(get_session_store),
):
    start = time.time()
    req = body.request

    interaction = store.get_interaction(req.message_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="Message not found")

    is_bad = req.user_action_status == "bad_response"
    bot_status = list(interaction.bot_status or [])
    bot_status.append({
        "status_type": "user_feedback",
        "status_code": "SUCCESS",
        "status_level": "WARNING" if is_bad else "INFO",
        "status_message": "User marked as bad response" if is_bad else "User marked as good response",
    })

    updated = store.update_feedback(
        message_id=req.message_id,
        feedback=interaction.feedback or {},
        user_action_status=req.user_action_status,
        bot_status=bot_status,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update feedback")

    interaction = store.get_interaction(req.message_id)
    response_time_ms = int((time.time() - start) * 1000)

    output = interaction.output_query or {}
    return StandardApiResponse(
        success=True,
        response=ResponseBody(
            message_id=interaction.message_id,
            message_index=interaction.message_index,
            chat_session_id=interaction.chat_session_id,
            app_session_id=interaction.app_session_id or req.app_session_id,
            tenant_id=interaction.tenant_id or req.tenant_id,
            project_id=interaction.project_id or req.project_id,
            user_id=interaction.user_id or req.user_id or user.username,
            input_query=interaction.input_query,
            output_query=OutputQuery(
                response_type=output.get("response_type", "text"),
                answer=output.get("answer", ""),
                data=output.get("data", []),
                link=output.get("link"),
            ),
            bot_status=[BotStatusItem(**item) for item in (interaction.bot_status or [])],
            user_action_status=interaction.user_action_status,
            created_at=interaction.created_at,
            updated_at=interaction.updated_at,
            processing_details={
                **(interaction.processing_details or {}),
                "response_time_ms": response_time_ms,
            },
            feedback=interaction.feedback or {},
        ),
    )


@router.post(
    "/comment",
    response_model=StandardApiResponse,
    summary="Add a comment to a message",
    description="Attach free-text feedback to any message (typically a thumbs-down one).",
)
def add_comment(
    body: CommentRequest,
    user=Depends(get_current_user),
    store=Depends(get_session_store),
):
    start = time.time()
    req = body.request

    interaction = store.get_interaction(req.message_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="Message not found")

    bot_status = list(interaction.bot_status or [])
    bot_status.append({
        "status_type": "user_feedback",
        "status_code": "SUCCESS",
        "status_level": "WARNING",
        "status_message": "User comment submitted",
    })

    feedback_data = dict(interaction.feedback or {})
    feedback_data["comments"] = req.comments or ""
    feedback_data["related_message_id"] = req.message_id
    feedback_data["related_session_id"] = interaction.chat_session_id

    updated = store.update_feedback(
        message_id=req.message_id,
        feedback=feedback_data,
        user_action_status=req.user_action_status or "remark",
        bot_status=bot_status,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update feedback")

    interaction = store.get_interaction(req.message_id)
    response_time_ms = int((time.time() - start) * 1000)

    output = interaction.output_query or {}
    return StandardApiResponse(
        success=True,
        response=ResponseBody(
            message_id=interaction.message_id,
            message_index=interaction.message_index,
            chat_session_id=interaction.chat_session_id,
            app_session_id=interaction.app_session_id or req.app_session_id,
            tenant_id=interaction.tenant_id or req.tenant_id,
            project_id=interaction.project_id or req.project_id,
            user_id=interaction.user_id or req.user_id or user.username,
            input_query=interaction.input_query,
            output_query=OutputQuery(
                response_type=output.get("response_type", "text"),
                answer=output.get("answer", ""),
                data=output.get("data", []),
                link=output.get("link"),
            ),
            bot_status=[BotStatusItem(**item) for item in (interaction.bot_status or [])],
            user_action_status=interaction.user_action_status,
            created_at=interaction.created_at,
            updated_at=interaction.updated_at,
            processing_details={
                **(interaction.processing_details or {}),
                "response_time_ms": response_time_ms,
            },
            feedback=interaction.feedback or {},
        ),
    )
