"""Pydantic schemas for Module 3 — Objection Handler."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ObjectionItem(BaseModel):
    objection_id: str
    objection_type: str
    objection_text: str
    period: str
    territory_id: str
    hcp_segment: Optional[str] = None

    # ── AI output keys ────────────────────────────────────────────────────────
    ai_frequency_label: Literal["HIGH", "MEDIUM", "LOW"]
    ai_call_count: int
    ai_date_range: Optional[str] = None
    ai_conversion_score: float = Field(default=0.0)
    ai_mlr_response: Optional[str] = None
    ai_sku: Optional[str] = None
    ai_supporting_materials: Optional[str] = None
    analysis_badges: List[str] = Field(default_factory=list)


class ObjectionResponse(BaseModel):
    objection_id: str
    objection_type: str
    objection_text: str
    hcp_segment: Optional[str] = None

    # ── AI output keys ────────────────────────────────────────────────────────
    ai_mlr_response: str
    ai_response_source: Optional[str] = None
    ai_sku: Optional[str] = None
    ai_conversion_score: float = 0.0
    ai_date_range: Optional[str] = None
    ai_supporting_materials: Optional[str] = None
    analysis_badges: List[str] = Field(default_factory=list)


class AddToCallPrepRequest(BaseModel):
    rep_id: str
    call_date: Optional[str] = None
    notes: Optional[str] = None


class AddToCallPrepResponse(BaseModel):
    success: bool
    message: str
    objection_id: str
    rep_id: str


class ObjectionListResponse(BaseModel):
    items: List[ObjectionItem]
    total: int
    ai_high_count: int = 0
    ai_medium_count: int = 0
    ai_low_count: int = 0
    ai_avg_success_rate: float = 0.0
    period: Optional[str] = None
