"""Pydantic schemas for Module 3 — Objection Handler.

AI output keys:
    ai_frequency_label      HIGH | MEDIUM | LOW   based on call count thresholds
    ai_success_rate         float 0-1             Rx within 30d / total objection calls
    ai_mlr_response         str                   best MLR-approved response text
    ai_response_source      str | None            MLR document reference (e.g. "MLR-v3.1")
    ai_sku                  str | None            recommended product SKU
    ai_conversion_score     float 0-100           ML predicted conversion probability × 100
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ObjectionItem(BaseModel):
    objection_id: str
    objection_type: str
    objection_text: str
    period: str
    territory_id: str

    # ── AI output keys ────────────────────────────────────────────────────────
    ai_frequency_label: Literal["HIGH", "MEDIUM", "LOW"]
    ai_call_count: int
    ai_success_rate: float = Field(ge=0.0, le=1.0)
    ai_conversion_score: float = Field(default=0.0, description="ML predicted conversion 0-100")


class ObjectionResponse(BaseModel):
    objection_id: str
    objection_type: str
    objection_text: str
    hcp_segment: Optional[str] = None

    # ── AI output keys ────────────────────────────────────────────────────────
    ai_mlr_response: str
    ai_response_source: Optional[str] = None
    ai_sku: Optional[str] = None
    ai_success_rate: float
    ai_conversion_score: float = 0.0
    ai_response_highlight: Optional[str] = None   # key phrase rendered in green


class AddToCallPrepRequest(BaseModel):
    rep_id: str
    call_date: Optional[str] = None
    notes: Optional[str] = None


class AddToCallPrepResponse(BaseModel):
    success: bool
    message: str
    objection_id: str
    rep_id: str
