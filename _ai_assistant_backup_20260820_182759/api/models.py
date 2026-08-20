from typing import Optional
from pydantic import BaseModel, Field


class RequestPayload(BaseModel):
    tenant_id: str = ""
    project_id: str = ""
    user_id: Optional[str] = None
    app_session_id: Optional[str] = None
    user_query: Optional[str] = Field(default="", max_length=4096)
    request_source: str = "web"
    user_action_status: str = "user_chat"
    message_id: Optional[str] = None
    comments: Optional[str] = None


class ChatRequestPayload(BaseModel):
    """Request body for POST /chat — no message_id / comments (those are feedback-only)."""
    tenant_id: str = ""
    project_id: str = ""
    user_id: Optional[str] = None
    app_session_id: Optional[str] = None
    user_query: Optional[str] = Field(default="", max_length=4096)
    request_source: str = "web"
    user_action_status: str = "user_chat"


class OutputQuery(BaseModel):
    response_type: str   # text | table | chart | dashboard | file | mixed
    answer: str
    data: list = []
    link: Optional[str] = None


class BotStatusItem(BaseModel):
    status_type: str     # application | user_feedback
    status_code: str     # SUCCESS | FAILED | PENDING
    status_level: str    # INFO | WARNING | ERROR | CRITICAL
    status_message: str


class ResponseBody(BaseModel):
    message_id: str
    message_index: int
    chat_session_id: str
    app_session_id: Optional[str] = None
    tenant_id: str = ""
    project_id: str = ""
    user_id: str = ""
    input_query: str
    output_query: OutputQuery
    bot_status: list[BotStatusItem]
    user_action_status: str
    created_at: str
    updated_at: str
    processing_details: dict
    feedback: dict


class StandardApiResponse(BaseModel):
    success: bool
    response: ResponseBody
