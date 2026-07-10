"""Pydantic schemas for Module 2 — New Writer Identification."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NewWriterCandidate(BaseModel):
    hcp_id: str
    name: str
    specialty: Optional[str] = None
    affiliated_hospital: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    territory_id: str
    segment: Optional[str] = None
    in_class_rx_q1: float = Field(default=0.0)
    brand_rx_q1: float = Field(default=0.0)
    brand_rx_q4: float = Field(default=0.0)
    competitor_brand: Optional[str] = None
    competitor_volume: float = 0.0
    last_nrx_date: Optional[str] = None
    total_in_class_rx: float = 0.0
    top_5_in_class_rx: List[Dict[str, Any]] = Field(default_factory=list)


class ApproachBriefResponse(BaseModel):
    hcp_id: str
    ai_approach_brief: str
    ai_approach_highlight: Optional[str] = None
    ai_peer_name: Optional[str] = None
    generated_at: str
    cached: bool = False


class NewWriterListResponse(BaseModel):
    items: List[NewWriterCandidate]
    total: int
    ai_candidate_count: int = 0
    ai_high_match_count: int = 0
    ai_icd10_matched_count: int = 0
    ai_top_opportunity_hcp: Optional[str] = None
