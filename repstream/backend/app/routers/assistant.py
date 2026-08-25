"""AI Assistant — one endpoint: ask a question, get an answer.

Answers come from the knowledge base the warm-up embeds into pgvector: RepStream's
own live application data (HCP priorities, prescriptions, calls, new writer
candidates, objections, alerts) plus the reference context files describing what
the fields mean.

Request and response follow the Datastream chatbot's envelope
(ai_assistant/api/models.py), so an existing client can point at this endpoint
without changing how it builds or reads a message.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.services.assistant import rate_limit
from app.services.assistant.chat_svc import chat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


# ── Request ──────────────────────────────────────────────────────────────────

class ChatRequestPayload(BaseModel):
    """Only `user_query` is used; the rest are carried through to the response so
    a caller's session and tenant bookkeeping survives the round trip."""

    tenant_id: str = ""
    project_id: str = ""
    user_id: Optional[str] = None
    app_session_id: Optional[str] = None
    user_query: Optional[str] = Field(default="", max_length=4096)
    request_source: str = "web"
    user_action_status: str = "user_chat"


class ChatRequestBody(BaseModel):
    request: ChatRequestPayload


# ── Response ─────────────────────────────────────────────────────────────────

class OutputQuery(BaseModel):
    response_type: str = "text"      # text | table | chart | dashboard | file | mixed
    answer: str
    data: list = []
    link: Optional[str] = None


class BotStatusItem(BaseModel):
    status_type: str                 # application | user_feedback
    status_code: str                 # SUCCESS | FAILED | PENDING
    status_level: str                # INFO | WARNING | ERROR | CRITICAL
    status_message: str


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ProcessingDetails(BaseModel):
    response_time_ms: int = 0
    model_name: str = ""
    token_usage: TokenUsage = TokenUsage()
    answer_type: str = ""
    # Always empty here: this assistant answers from retrieved text and never
    # generates or runs SQL. The field exists so the envelope matches.
    sql: str = ""
    source: str = ""
    confidence: float = 0
    matched_template: str = ""


class Feedback(BaseModel):
    rating: str = ""
    comments: str = ""
    related_message_id: str = ""
    related_session_id: str = ""


class ResponseBody(BaseModel):
    message_id: str
    message_index: int = 1
    chat_session_id: str
    app_session_id: Optional[str] = None
    tenant_id: str = ""
    project_id: str = ""
    user_id: str = ""
    input_query: str
    output_query: OutputQuery
    bot_status: List[BotStatusItem]
    user_action_status: str
    created_at: str
    updated_at: str
    processing_details: ProcessingDetails
    feedback: Feedback = Feedback()


class StandardApiResponse(BaseModel):
    success: bool
    response: ResponseBody


@router.post("/ai_assistant_chat", response_model=StandardApiResponse,
             summary="Ask a question about the RepStream data")
async def ai_assistant_chat(body: ChatRequestBody, request: Request, response: Response):
    """Ask anything about the RepStream data — no filters, no auth, no territory.

    The embedded chunks carry their own scope labels, so a single question covers
    every territory. The knowledge base is refreshed at the end of a warm-up run,
    so answers reflect the most recent one.

    Rate limited per browser/device (see services/assistant/rate_limit.py). The
    `request`/`response` parameters are injected by FastAPI for the cookie and
    client IP; neither changes the response body.
    """
    req = body.request
    question = (req.user_query or "").strip()
    now = datetime.now(timezone.utc).isoformat()

    # Echo the caller's session id when supplied so a client can keep its own
    # thread; otherwise mint one for this exchange.
    session_id = req.app_session_id or str(uuid.uuid4())

    # Quota is checked BEFORE the model runs, so a blocked request costs nothing.
    decision = rate_limit.check(request)
    rate_limit.apply_cookie(response, decision)

    if not decision.allowed and question:
        logger.info("assistant chat: rate limited (%s) device=%s retry_in=%ss",
                    decision.scope, decision.device_id[:8], decision.retry_after)
        # Same envelope as every other response — only the fields inside differ.
        return _envelope(
            req, question, session_id, now, success=False,
            answer=decision.message,
            status=BotStatusItem(
                status_type="application", status_code="FAILED",
                status_level="WARNING", status_message=decision.message,
            ),
            details=ProcessingDetails(
                answer_type="rate_limited", source="none",
                matched_template="Rate Limit Exceeded",
            ),
        )

    result = chat(question)

    # Count only questions that were actually answered: a blocked or empty one
    # must not consume quota, or a retry loop would extend its own lockout.
    if question:
        rate_limit.record(request, decision)

    # Keep provenance in the log so a wrong answer can still be traced back to the
    # chunks that produced it.
    logger.info("assistant chat: %d chunk(s) used, sources=%s",
                result.get("chunks_used", 0),
                [s.get("source") for s in result.get("sources", [])])

    if not question:
        status = BotStatusItem(
            status_type="application", status_code="FAILED", status_level="WARNING",
            status_message="No question supplied in user_query.",
        )
    else:
        status = BotStatusItem(
            status_type="application", status_code="SUCCESS", status_level="INFO",
            status_message="Response generated successfully",
        )

    return _envelope(
        req, question, session_id, now,
        success=bool(question),
        answer=result["answer"],
        status=status,
        details=ProcessingDetails(
            response_time_ms=result.get("response_time_ms", 0),
            model_name=result.get("model_name", ""),
            token_usage=TokenUsage(**result.get("token_usage", {})),
            answer_type=result.get("answer_type", ""),
            sql=result.get("sql", ""),
            source=result.get("source", ""),
            confidence=result.get("confidence", 0),
            matched_template=result.get("matched_template", ""),
        ),
    )


def _envelope(req: ChatRequestPayload, question: str, session_id: str, now: str, *,
              success: bool, answer: str, status: BotStatusItem,
              details: ProcessingDetails) -> StandardApiResponse:
    """Build the response. One builder for every outcome — answered, empty and
    rate-limited — so a new branch cannot drift from the agreed envelope."""
    return StandardApiResponse(
        success=success,
        response=ResponseBody(
            message_id=str(uuid.uuid4()),
            message_index=1,
            chat_session_id=session_id,
            app_session_id=req.app_session_id,
            tenant_id=req.tenant_id,
            project_id=req.project_id,
            user_id=req.user_id or "",
            input_query=question,
            # Always text: this assistant returns prose, never a table or chart.
            output_query=OutputQuery(response_type="text", answer=answer,
                                     data=[], link=None),
            bot_status=[status],
            user_action_status=req.user_action_status,
            created_at=now,
            updated_at=now,
            processing_details=details,
            feedback=Feedback(),
        ),
    )
