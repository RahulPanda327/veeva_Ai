"""
Application Logs API — /logs

Exposes the 3-step interaction lifecycle + read-back endpoints.

Step 1  POST /logs/message                  log_chat_message     (user sends query)
Step 2  PUT  /logs/message/{id}/response    update_bot_response  (bot answers)
Step 3  PUT  /logs/message/{id}/feedback    log_user_feedback    (user rates)

Reads
  GET  /logs/message/{id}                   get single log record
  GET  /logs/session/{chat_session_id}      get all logs for a session
  GET  /logs/tenant/{tenant_id}             get all logs for a tenant
  POST /logs/event                          log an application-level event
  GET  /logs/events                         query application-level events
  POST /logs/auth-event                     log an auth / login event
  GET  /logs/auth-events                    query auth / login events
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from utils.application_logs import (
    get_application_logger,
    ACTION_USER_CHAT,
    ACTION_GOOD_RESPONSE,
    ACTION_BAD_RESPONSE,
    ACTION_REMARK,
    APP_STATUS_SUCCESS,
    APP_STATUS_ERROR,
    STATUS_CODE_SUCCESS,
    STATUS_CODE_FAILED,
    STATUS_LEVEL_INFO,
    STATUS_LEVEL_WARNING,
    STATUS_LEVEL_ERROR,
    STATUS_LEVEL_CRITICAL,
    AUTH_EVENT_CATALOG,
)

router = APIRouter(prefix="/logs", tags=["Application Logs"])


# ── Request / Response models ────────────────────────────────────────────────

class LogMessageRequest(BaseModel):
    tenant_id:          str = Field(..., examples=["1"])
    project_id:         str = Field(..., examples=["1"])
    user_id:            str = Field(..., examples=["121"])
    app_session_id:     str = Field("",  examples=["app-sess-001"])
    user_query:         str = Field(..., examples=["Show me failed pipelines today"])
    request_source:     str = Field("web", examples=["web"])
    user_action_status: str = Field(
        ACTION_USER_CHAT, examples=[ACTION_USER_CHAT],
        description="user_chat | good_response | bad_response | remark",
    )
    chat_session_id: Optional[str] = Field(
        None, examples=["chat-sess-abc123"],
        description="Supply to continue an existing chat session; omit to start fresh.",
    )


class TokenUsage(BaseModel):
    input_tokens:  int = 0
    output_tokens: int = 0
    total_tokens:  int = 0


class ProcessingDetails(BaseModel):
    response_time_ms: float    = Field(..., examples=[1250.0])
    model_name:       str      = Field(..., examples=["gpt-4"])
    token_usage:      TokenUsage = Field(default_factory=TokenUsage)


class AppStatus(BaseModel):
    status_code:    str = Field("SUCCESS", examples=["SUCCESS"])
    status_level:   str = Field("INFO",    examples=["INFO"])
    status_message: str = Field("Response generated successfully",
                                examples=["Response generated successfully"])


class UpdateResponseRequest(BaseModel):
    output_query:       str                         = Field(..., examples=["Found 12 failed pipelines."])
    app_status:         Optional[AppStatus]         = Field(None)
    processing_details: Optional[ProcessingDetails] = Field(None)
    chat_session_id:    Optional[str]               = Field(None, examples=["chat-sess-abc123"])


class FeedbackRequest(BaseModel):
    related_session_id: str   = Field(..., examples=["chat-sess-abc123"])
    user_action_status: str   = Field(
        ACTION_GOOD_RESPONSE, examples=[ACTION_GOOD_RESPONSE],
        description="good_response | bad_response | remark",
    )
    rating:   Optional[float] = Field(None, examples=[5.0], ge=1, le=5)
    comments: str             = Field("",   examples=["Very helpful answer!"])


class FullLogRecord(BaseModel):
    id:                 Optional[int]   = None
    message_id:         str
    message_index:      int
    chat_session_id:    Optional[str]
    app_session_id:     Optional[str]
    tenant_id:          Optional[str]
    project_id:         Optional[str]
    user_id:            Optional[str]
    input_query:        Optional[str]
    output_query:       Optional[str]
    bot_status:         Optional[str]
    app_status:         Optional[dict]
    user_action_status: Optional[str]
    request_source:     Optional[str]
    processing_details: Optional[dict]
    feedback:           Optional[dict]
    created_at:         Optional[str]
    updated_at:         Optional[str]


# ── Step 1: log user query ───────────────────────────────────────────────────

@router.post(
    "/message",
    response_model=FullLogRecord,
    summary="Log a user query",
    description=(
        "Accepts the user input and returns the full log record immediately.\n\n"
        "`user_action_status` values:\n"
        "- `user_chat` — normal chat message\n"
        "- `good_response` — user marked a response as good\n"
        "- `bad_response` — user marked a response as bad\n"
        "- `remark` — user added a text remark\n\n"
        "`output_query`, `processing_details`, and `feedback` will be empty until "
        "updated via the response/feedback endpoints."
    ),
)
def log_message(body: LogMessageRequest):
    app_log = get_application_logger()
    result = app_log.log_chat_message(
        tenant_id          = body.tenant_id,
        project_id         = body.project_id,
        user_id            = body.user_id,
        app_session_id     = body.app_session_id,
        user_query         = body.user_query,
        request_source     = body.request_source,
        user_action_status = body.user_action_status,
        chat_session_id    = body.chat_session_id,
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to log chat message")

    record = app_log.get_message_log(result["message_id"])
    if record is None:
        raise HTTPException(status_code=500, detail="Log created but could not be retrieved")
    return record


# ── Step 2: update with bot response ────────────────────────────────────────

@router.put(
    "/message/{message_id}/response",
    response_model=FullLogRecord,
    summary="Update with bot response",
    description=(
        "Updates `output_query`, `app_status`, `processing_details`, and stamps `updated_at`.\n\n"
        "The `app_status.status_code` reflects whether the application succeeded:\n"
        "- `SUCCESS` — response generated successfully (status_type: **application**)\n"
        "- `FAILED`  — an error occurred during processing"
    ),
)
def update_response(message_id: str, body: UpdateResponseRequest):
    app_log = get_application_logger()
    app_status_dict = body.app_status.model_dump() if body.app_status else APP_STATUS_SUCCESS
    processing_dict = body.processing_details.model_dump() if body.processing_details else None

    ok = app_log.update_bot_response(
        message_id         = message_id,
        output_query       = body.output_query,
        app_status         = app_status_dict,
        processing_details = processing_dict,
        chat_session_id    = body.chat_session_id,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update bot response")

    record = app_log.get_message_log(message_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"message_id '{message_id}' not found")
    return record


# ── Step 3: log user feedback ────────────────────────────────────────────────

@router.put(
    "/message/{message_id}/feedback",
    response_model=FullLogRecord,
    summary="Log user feedback",
    description=(
        "Records user rating/remark on a response.\n\n"
        "- Sets `bot_status` → `status_type: user_feedback`\n"
        "- Updates `user_action_status` to `good_response`, `bad_response`, or `remark`\n"
        "- Stamps `updated_at`\n\n"
        "Returns the full updated log record."
    ),
)
def log_feedback(message_id: str, body: FeedbackRequest):
    app_log = get_application_logger()
    ok = app_log.log_user_feedback(
        related_message_id = message_id,
        related_session_id = body.related_session_id,
        user_action_status = body.user_action_status,
        rating             = body.rating,
        comments           = body.comments,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to log feedback")

    record = app_log.get_message_log(message_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"message_id '{message_id}' not found")
    return record


# ── Read-back endpoints ──────────────────────────────────────────────────────

@router.get(
    "/message/{message_id}",
    response_model=FullLogRecord,
    summary="Get a single log record",
)
def get_message(message_id: str):
    app_log = get_application_logger()
    record = app_log.get_message_log(message_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"message_id '{message_id}' not found")
    return record


@router.get(
    "/session/{chat_session_id}",
    response_model=list[FullLogRecord],
    summary="Get all logs for a chat session",
)
def get_session(
    chat_session_id: str,
    limit: int = Query(100, ge=1, le=500),
):
    app_log = get_application_logger()
    return app_log.get_session_logs(chat_session_id, limit=limit)


@router.get(
    "/tenant/{tenant_id}",
    response_model=list[FullLogRecord],
    summary="Get all logs for a tenant",
)
def get_tenant(
    tenant_id:  str,
    project_id: Optional[str] = Query(None),
    limit:      int            = Query(100, ge=1, le=500),
):
    app_log = get_application_logger()
    return app_log.get_tenant_logs(tenant_id, project_id=project_id, limit=limit)


# ── App-level event endpoints ────────────────────────────────────────────────

class AppEventRequest(BaseModel):
    request: "AppEventBody"

class AppEventBody(BaseModel):
    tenant_id:          str = Field(..., examples=["1"])
    project_id:         str = Field(..., examples=["1"])
    user_id:            str = Field(..., examples=["121"])
    app_session_id:     str = Field("",  examples=[""])
    user_query:         str = Field(..., examples=["Files failed today"])
    request_source:     str = Field("web", examples=["web"])
    user_action_status: str = Field(ACTION_USER_CHAT, examples=[ACTION_USER_CHAT],
                                    description="user_chat | good_response | bad_response | remark")

AppEventRequest.model_rebuild()


class AppEventRecord(BaseModel):
    id:             int
    tenant_id:      Optional[str]
    project_id:     Optional[str]
    user_id:        Optional[str]
    session_id:     Optional[str]
    request_source: Optional[str]
    status_code:    str
    status_level:   str
    status_message: Optional[str]
    timestamp:      Optional[str]


@router.post(
    "/event",
    response_model=AppEventRecord,
    summary="Log an application-level event",
    description=(
        "Logs a single application-level event (`status_type: application`).\n\n"
        "**status_level** values: `INFO` | `WARNING` | `ERROR` | `CRITICAL`\n\n"
        "**status_code** defaults: `SUCCESS` | `FAILED`"
    ),
)
def log_event(body: AppEventRequest):
    app_log = get_application_logger()
    req = body.request
    row_id = app_log.log_app_event(
        tenant_id      = req.tenant_id,
        project_id     = req.project_id,
        user_id        = req.user_id,
        session_id     = req.app_session_id,
        request_source = req.request_source,
        status_code    = STATUS_CODE_SUCCESS,
        status_level   = STATUS_LEVEL_INFO,
        status_message = f"Request received: {req.user_query[:120]}",
    )
    if row_id is None:
        raise HTTPException(status_code=500, detail="Failed to log app event")

    events = app_log.get_app_events(
        tenant_id  = req.tenant_id,
        user_id    = req.user_id,
        session_id = req.app_session_id,
        limit      = 1,
    )
    if not events:
        raise HTTPException(status_code=500, detail="Event logged but could not be retrieved")
    return events[0]


@router.get(
    "/events",
    response_model=list[AppEventRecord],
    summary="Query application-level events",
    description="Returns app-level events newest first. All filters optional.",
)
def get_events(
    tenant_id:    Optional[str] = Query(None, examples=["1"]),
    project_id:   Optional[str] = Query(None, examples=["1"]),
    user_id:      Optional[str] = Query(None, examples=["121"]),
    session_id:   Optional[str] = Query(None),
    status_level: Optional[str] = Query(None, examples=["INFO"],
                                        description="INFO | WARNING | ERROR | CRITICAL"),
    limit:        int            = Query(100, ge=1, le=500),
):
    app_log = get_application_logger()
    return app_log.get_app_events(
        tenant_id    = tenant_id,
        project_id   = project_id,
        user_id      = user_id,
        session_id   = session_id,
        status_level = status_level,
        limit        = limit,
    )


# ── Auth login event endpoints ───────────────────────────────────────────────

_STATUS_CODE_DOCS = "\n".join(
    f"- `{code}` — {msg}"
    for code, (msg, _) in AUTH_EVENT_CATALOG.items()
)


class AuthLoginEventRequest(BaseModel):
    tenant_id:      str           = Field(...,   examples=["1"])
    project_id:     str           = Field(...,   examples=["1"])
    user_id:        str           = Field(...,   examples=["121"])
    session_id:     Optional[str] = Field(None,  examples=["sess-abc123"])
    request_source: str           = Field("web", examples=["web"])
    status_code:    str           = Field(...,   examples=["INVALID_CREDENTIALS"],
                                          description="One of the predefined auth status codes")


class AuthLoginEventRecord(BaseModel):
    id:             int
    tenant_id:      Optional[str]
    project_id:     Optional[str]
    user_id:        Optional[str]
    session_id:     Optional[str]
    request_source: Optional[str]
    status_code:    str
    status_level:   str
    status_message: Optional[str]
    timestamp:      Optional[str]


@router.post(
    "/auth-event",
    response_model=AuthLoginEventRecord,
    summary="Log an auth / login event",
    description=(
        "Logs a login or authentication event (`status_type: user_feedback` is for chat;\n"
        "auth events have their own table).\n\n"
        "`status_level` and `status_message` are resolved automatically from `status_code`.\n\n"
        "**Valid status_code values:**\n\n" + _STATUS_CODE_DOCS
    ),
)
def log_auth_event(body: AuthLoginEventRequest):
    app_log = get_application_logger()
    row_id = app_log.log_auth_login_event(
        status_code    = body.status_code,
        user_id        = body.user_id,
        tenant_id      = body.tenant_id,
        project_id     = body.project_id,
        session_id     = body.session_id or "",
        request_source = body.request_source,
    )
    if row_id is None:
        raise HTTPException(status_code=500, detail="Failed to log auth event")

    record = app_log.get_auth_login_event_by_id(row_id)
    if record is None:
        raise HTTPException(status_code=500, detail="Auth event logged but could not be retrieved")
    return record


@router.get(
    "/auth-events",
    response_model=list[AuthLoginEventRecord],
    summary="Query auth / login events",
    description="Returns auth events newest first. All filters optional.",
)
def get_auth_events_list(
    tenant_id:    Optional[str] = Query(None, examples=["1"]),
    project_id:   Optional[str] = Query(None, examples=["1"]),
    user_id:      Optional[str] = Query(None, examples=["121"]),
    status_code:  Optional[str] = Query(None, examples=["SUCCESS"]),
    status_level: Optional[str] = Query(None, examples=["WARNING"]),
    limit:        int            = Query(100, ge=1, le=500),
):
    app_log = get_application_logger()
    return app_log.get_auth_login_events(
        tenant_id    = tenant_id,
        project_id   = project_id,
        user_id      = user_id,
        status_code  = status_code,
        status_level = status_level,
        limit        = limit,
    )
