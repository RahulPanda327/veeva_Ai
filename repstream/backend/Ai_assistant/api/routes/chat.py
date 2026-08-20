# """
# Chat route — POST /chat

# Session lifecycle:
#   • No session_id supplied → new session created in DB, UUID returned.
#   • session_id supplied   → ownership verified, history hydrated from DB,
#                             conversation continues from where it left off.
# """

# import json
# import uuid
# from typing import Optional

# from fastapi import APIRouter, Depends, HTTPException
# from fastapi.responses import StreamingResponse
# from pydantic import BaseModel, Field

# from config.settings import get_config
# from services.base_service import BaseService, ChatRequest
# from api.dependencies import get_current_user, get_service, get_session_store
# from utils.logging_util import setup_logging

# logger = setup_logging("chat_route")
# router = APIRouter(prefix="/chat", tags=["Chat"])


# class ChatRequestBody(BaseModel):
#     message: str = Field(..., min_length=1, max_length=4096)
#     session_id: Optional[str] = Field(
#         None,
#         description="Omit to start a new conversation; supply to resume an existing one.",
#     )
#     system_prompt: Optional[str] = Field(
#         None,
#         description="Override system prompt for scenarios 1 and 2.",
#     )
#     metadata_filter: Optional[dict] = Field(
#         None,
#         description=(
#             "Pinecone metadata filter applied to Scenario 3 retrieval. "
#             "Example: {\"category\": {\"$eq\": \"support\"}}"
#         ),
#     )


# class ChatResponseBody(BaseModel):
#     response: str
#     session_id: str
#     scenario: int
#     provider: str
#     model: str
#     cached: bool
#     rule_matched: Optional[str]
#     retrieved_docs: int
#     cosine_scores: list[float]
#     # Scenario 4 (Database) populates this with sql/rows/chart/intent;
#     # other scenarios leave it empty.
#     metadata: dict = {}


# class MemoryStatsBody(BaseModel):
#     active_sessions: int
#     cache_enabled: bool
#     cache_size: int
#     cache_max: int
#     cache_ttl_seconds: int
#     memory_window_size: int


# @router.post("", response_model=ChatResponseBody, summary="Send a message")
# def chat(
#     body: ChatRequestBody,
#     user=Depends(get_current_user),
#     service: BaseService = Depends(get_service),
#     store=Depends(get_session_store),
# ):
#     cfg = get_config()

#     if body.session_id:
#         # ── Resume existing session ──────────────────────────────────────────────
#         session = store.get_session(body.session_id)
#         if session is None:
#             raise HTTPException(status_code=404, detail="Session not found")
#         if session.user_id != user.username:
#             raise HTTPException(status_code=403, detail="Session belongs to another user")
#         session_id = body.session_id
#         logger.info({
#             "event": "session_resumed",
#             "session_id": session_id,
#             "user": user.username,
#             "prior_messages": session.message_count,
#         })
#     else:
#         # ── New session ──────────────────────────────────────────────────────────
#         session_id = store.create_session(
#             user_id=user.username,
#             client_id=user.client_id,
#             scenario=cfg.active_scenario,
#             provider=cfg.active_api_provider,
#             model=cfg.llm_model_name,
#         )
#         logger.info({
#             "event": "session_created",
#             "session_id": session_id,
#             "user": user.username,
#             "client_id": user.client_id,
#         })

#     request = ChatRequest(
#         query=body.message,
#         session_id=session_id,
#         user_id=user.username,
#         system_prompt=body.system_prompt,
#         metadata_filter=body.metadata_filter,
#     )

#     try:
#         result = service.chat(request)
#     except Exception as exc:
#         logger.error({"event": "chat_error", "user": user.username, "error": str(exc)})
#         raise HTTPException(status_code=500, detail=f"Chat processing failed: {exc}") from exc

#     # Auto-title from first user message (SQL no-ops if title already set)
#     store.set_title(session_id, body.message)

#     return ChatResponseBody(
#         response=result.response,
#         session_id=result.session_id,
#         scenario=result.scenario,
#         provider=result.provider,
#         model=result.model,
#         cached=result.cached,
#         rule_matched=result.rule_matched,
#         retrieved_docs=result.retrieved_docs,
#         cosine_scores=result.cosine_scores,
#         metadata=result.metadata,
#     )


# def _resolve_session(body: ChatRequestBody, user, store) -> str:
#     """Shared session create/verify logic for both /chat and /chat/stream."""
#     cfg = get_config()
#     if body.session_id:
#         session = store.get_session(body.session_id)
#         if session is None:
#             raise HTTPException(status_code=404, detail="Session not found")
#         if session.user_id != user.username:
#             raise HTTPException(status_code=403, detail="Session belongs to another user")
#         return body.session_id
#     return store.create_session(
#         user_id=user.username,
#         client_id=user.client_id,
#         scenario=cfg.active_scenario,
#         provider=cfg.active_api_provider,
#         model=cfg.llm_model_name,
#     )


# @router.post(
#     "/stream",
#     summary="Send a message and stream the response via Server-Sent Events",
#     description=(
#         "Returns SSE events:\n"
#         "  data: {\"type\": \"chunk\", \"content\": \"...\"}\n"
#         "  data: {\"type\": \"meta\",  \"session_id\": \"...\", ...}\n"
#         "  data: [DONE]\n\n"
#         "Scenarios 1 and 2 (LLM fallback) stream token-by-token; "
#         "rule hits and Scenario 3 emit the full response as a single chunk."
#     ),
# )
# def chat_stream(
#     body: ChatRequestBody,
#     user=Depends(get_current_user),
#     service: BaseService = Depends(get_service),
#     store=Depends(get_session_store),
# ):
#     session_id = _resolve_session(body, user, store)
#     store.set_title(session_id, body.message)

#     request = ChatRequest(
#         query=body.message,
#         session_id=session_id,
#         user_id=user.username,
#         system_prompt=body.system_prompt,
#         metadata_filter=body.metadata_filter,
#     )

#     def sse_generator():
#         try:
#             for event in service.chat_stream(request):
#                 yield f"data: {json.dumps(event)}\n\n"
#         except Exception as exc:
#             logger.error({"event": "stream_error", "user": user.username, "error": str(exc)})
#             yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
#         finally:
#             yield "data: [DONE]\n\n"

#     return StreamingResponse(
#         sse_generator(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "X-Accel-Buffering": "no",   # disable proxy buffering (nginx)
#         },
#     )


# @router.delete(
#     "/{session_id}/context",
#     summary="Reset the LLM context window (history preserved in DB)",
# )
# def clear_context(
#     session_id: str,
#     user=Depends(get_current_user),
#     service: BaseService = Depends(get_service),
#     store=Depends(get_session_store),
# ):
#     session = store.get_session(session_id)
#     if session is None:
#         raise HTTPException(status_code=404, detail="Session not found")
#     if session.user_id != user.username:
#         raise HTTPException(status_code=403, detail="Access denied")
#     service.memory.clear_session(session_id)
#     return {"message": "Context window cleared; history preserved in DB", "session_id": session_id}


# @router.get("/memory/stats", response_model=MemoryStatsBody, summary="Memory and cache statistics")
# def memory_stats(
#     user=Depends(get_current_user),
#     service: BaseService = Depends(get_service),
# ):
#     return service.memory.stats()


"""
Chat route — POST /chat

Session lifecycle:
  • No session_id supplied → new session created in DB, UUID returned.
  • session_id supplied   → ownership verified, history hydrated from DB,
                            conversation continues from where it left off.
"""

import json
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


def _map_answer_type(source: str) -> str:
    """
    Map internal source values to 3 user-facing answer types:
      predefined   — answer came from a pre-written KB rule
      ai_generated — AI generated the SQL dynamically via pgvector / LLM
      greeting     — conversational response, no data query
    """
    if source in (
        "rule_match", "kb_search",
        "kb_retry_1", "kb_retry_2",
        "sql_template", "sql_kb_fallback",
    ):
        return "predefined"
    if source in ("pgvector_llm", "llm_sql"):
        return "ai_generated"
    return "greeting"

from config.settings import get_config
from services.base_service import BaseService, ChatRequest
from api.dependencies import get_current_user, get_service, get_session_store
from utils.logging_util import setup_logging
from utils.application_logs import get_application_logger
from api.models import ChatRequestPayload, OutputQuery, BotStatusItem, ResponseBody, StandardApiResponse

logger = setup_logging("chat_route")
router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequestBody(BaseModel):
    request: ChatRequestPayload


ChatResponseBody = StandardApiResponse


class MemoryStatsBody(BaseModel):
    active_sessions: int
    cache_enabled: bool
    cache_size: int
    cache_max: int
    cache_ttl_seconds: int
    memory_window_size: int


@router.post("", response_model=ChatResponseBody, summary="Send a message")
def chat(
    body: ChatRequestBody,
    user=Depends(get_current_user),
    service: BaseService = Depends(get_service),
    store=Depends(get_session_store),
):
    cfg = get_config()
    req = body.request
    start_time = time.time()
    interaction_log = get_application_logger()

    requesting_user = req.user_id or user.username
    if req.app_session_id:
        session = store.get_session(req.app_session_id)
        if session is not None and session.user_id != requesting_user:
            raise HTTPException(status_code=403, detail="Session belongs to another user")
        if session is not None:
            session_id = session.id
            logger.info({"event": "session_resumed", "session_id": session_id, "user": user.username})
        else:
            # Session ID supplied but not found — create a fresh session using the provided ID
            session_id = store.create_session(
                user_id=user.username,
                client_id=user.client_id,
                scenario=cfg.active_scenario,
                provider=cfg.active_api_provider,
                model=cfg.llm_model_name,
            )
            logger.info({"event": "session_auto_created", "requested_id": req.app_session_id,
                         "new_session_id": session_id, "user": user.username})
    else:
        session_id = store.create_session(
            user_id=user.username,
            client_id=user.client_id,
            scenario=cfg.active_scenario,
            provider=cfg.active_api_provider,
            model=cfg.llm_model_name,
        )
        logger.info({"event": "session_created", "session_id": session_id, "user": user.username})

    request = ChatRequest(
        query=req.user_query or "",
        session_id=session_id,
        user_id=req.user_id or user.username,
        system_prompt=None,
        metadata_filter=None,
    )

    try:
        result = service.chat(request)
    except Exception as exc:
        response_time_ms = (time.time() - start_time) * 1000
        logger.error({"event": "chat_error", "user": user.username, "error": str(exc)})
        interaction_log.log_interaction(
            user_id=user.username,
            session_id=session_id,
            message=req.user_query or "",
            response="",
            status="error",
            response_time_ms=response_time_ms,
            scenario=cfg.active_scenario,
            provider=cfg.active_api_provider,
            model=cfg.llm_model_name,
            error_message=str(exc),
        )
        interaction_log.log_error(
            user_id=user.username,
            session_id=session_id,
            error_type="chat_exception",
            error_message=str(exc),
            stack_trace=traceback.format_exc(),
            scenario=cfg.active_scenario,
        )
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {exc}") from exc

    response_time_ms = int((time.time() - start_time) * 1000)

    interaction_log.log_interaction(
        user_id=user.username,
        session_id=session_id,
        message=req.user_query or "",
        response=result.response[:1000],
        status="success",
        response_time_ms=response_time_ms,
        scenario=result.scenario,
        provider=result.provider,
        model=result.model,
        rule_matched=result.rule_matched,
    )

    store.set_title(session_id, req.user_query or "")

    preview_rows = _extract_preview_rows(result.metadata)
    download_id = result.metadata.get("download_id")
    response_type = _determine_response_type(result, preview_rows)
    token_usage = result.metadata.get("token_usage", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    internal_source = result.metadata.get("source", "")
    processing_details = {
        "response_time_ms": response_time_ms,
        "model_name":       result.model,
        "token_usage":      token_usage,
        "answer_type":      _map_answer_type(internal_source),
        "sql":              result.metadata.get("sql", ""),
        "source":           internal_source,
        "confidence":       result.metadata.get("confidence", 0.0),
        "matched_template": result.metadata.get("matched_template", ""),
    }

    # Determine sequential index for this message within its session
    message_id = str(uuid.uuid4())
    existing = store.get_session_interactions(result.session_id) if hasattr(store, "get_session_interactions") else []
    message_index = len(existing)

    now = datetime.now(timezone.utc).isoformat()
    bot_status_list = [
        {"status_type": "application", "status_code": "SUCCESS", "status_level": "INFO",
         "status_message": "Response generated successfully"},
    ]

    store.save_interaction(
        message_id=message_id,
        chat_session_id=result.session_id,
        user_id=req.user_id or user.username,
        input_query=req.user_query or "",
        output_query={
            "response_type": response_type,
            "answer": result.response,
            "data": preview_rows,
            "link": download_id,
        },
        tenant_id=req.tenant_id,
        project_id=req.project_id,
        app_session_id=req.app_session_id or "",
        request_source=req.request_source,
        user_action_status=req.user_action_status or "user_chat",
        bot_status=bot_status_list,
        processing_details=processing_details,
        feedback={"rating": None, "comments": "", "related_message_id": "", "related_session_id": ""},
        message_index=message_index,
    )

    return ChatResponseBody(
        success=True,
        response=ResponseBody(
            message_id=message_id,
            message_index=message_index,
            chat_session_id=result.session_id,
            app_session_id=req.app_session_id,
            tenant_id=req.tenant_id,
            project_id=req.project_id,
            user_id=req.user_id or user.username,
            input_query=req.user_query or "",
            output_query=OutputQuery(
                response_type=response_type,
                answer=result.response,
                data=preview_rows,
                link=download_id,
            ),
            bot_status=[
                BotStatusItem(
                    status_type="application",
                    status_code="SUCCESS",
                    status_level="INFO",
                    status_message="Response generated successfully",
                ),
            ],
            user_action_status=req.user_action_status,
            created_at=now,
            updated_at=now,
            processing_details=processing_details,
            feedback={
                "rating": None,
                "comments": "",
                "related_message_id": "",
                "related_session_id": "",
            },
        ),
    )


def _resolve_session(body: ChatRequestBody, user, store) -> str:
    """Shared session create/verify logic for /chat/stream."""
    cfg = get_config()
    req = body.request
    if req.app_session_id:
        session = store.get_session(req.app_session_id)
        if session is not None and session.user_id != user.username:
            raise HTTPException(status_code=403, detail="Session belongs to another user")
        if session is not None:
            return req.app_session_id
    return store.create_session(
        user_id=user.username,
        client_id=user.client_id,
        scenario=cfg.active_scenario,
        provider=cfg.active_api_provider,
        model=cfg.llm_model_name,
    )


@router.post(
    "/stream",
    summary="Send a message and stream the response via Server-Sent Events",
    description=(
        "Returns SSE events:\n"
        "  data: {\"type\": \"chunk\", \"content\": \"...\"}\n"
        "  data: {\"type\": \"meta\",  \"session_id\": \"...\", ...}\n"
        "  data: [DONE]\n\n"
        "Scenarios 1 and 2 (LLM fallback) stream token-by-token; "
        "rule hits and Scenario 3 emit the full response as a single chunk."
    ),
)
def chat_stream(
    body: ChatRequestBody,
    user=Depends(get_current_user),
    service: BaseService = Depends(get_service),
    store=Depends(get_session_store),
):
    session_id = _resolve_session(body, user, store)
    store.set_title(session_id, body.request.user_query or "")

    request = ChatRequest(
        query=body.request.user_query or "",
        session_id=session_id,
        user_id=body.request.user_id or user.username,
        system_prompt=None,
        metadata_filter=None,
    )

    def sse_generator():
        try:
            for event in service.chat_stream(request):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.error({"event": "stream_error", "user": user.username, "error": str(exc)})
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable proxy buffering (nginx)
        },
    )


@router.delete(
    "/{session_id}/context",
    summary="Reset the LLM context window (history preserved in DB)",
)
def clear_context(
    session_id: str,
    user=Depends(get_current_user),
    service: BaseService = Depends(get_service),
    store=Depends(get_session_store),
):
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.username:
        raise HTTPException(status_code=403, detail="Access denied")
    service.memory.clear_session(session_id)
    return {"message": "Context window cleared; history preserved in DB", "session_id": session_id}


@router.get("/memory/stats", response_model=MemoryStatsBody, summary="Memory and cache statistics")
def memory_stats(
    user=Depends(get_current_user),
    service: BaseService = Depends(get_service),
):
    return service.memory.stats()



def _determine_response_type(result, preview_rows: list) -> str:
    has_chart = bool(result.metadata.get("chart"))
    has_table = bool(preview_rows)
    if has_chart and has_table:
        return "mixed"
    if has_chart:
        return "chart"
    if has_table:
        return "table"
    return "text"


def _extract_preview_rows(metadata: dict) -> list:
    """
    scenario_4 stores preview as:
      metadata["preview"]["columns"] = ["col1", "col2", ...]
      metadata["preview"]["rows"]    = [["v1","v2"], ["v1","v2"], ...]

    Convert to list of dicts so the frontend table works:
      [{"col1": "v1", "col2": "v2"}, ...]
    """
    preview = metadata.get("preview")
    if not preview:
        return []
    cols = preview.get("columns", [])
    rows = preview.get("rows", [])
    return [dict(zip(cols, row)) for row in rows]