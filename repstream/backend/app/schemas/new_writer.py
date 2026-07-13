"""Pydantic schemas for Module 2 — New Writer Identification."""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class NewWriterCandidate(BaseModel):
    # ── Identity ─────────────────────────────────────────────────────────────
    hcp_id: str
    name: str
    specialty: Optional[str] = None
    affiliated_hospital: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    territory_id: str
    segment: Optional[str] = None

    # ── Rx profile ────────────────────────────────────────────────────────────
    in_class_rx_q1: float = Field(default=0.0)
    brand_rx_q1: float = Field(default=0.0)
    brand_rx_q4: float = Field(default=0.0)
    competitor_brand: Optional[str] = None
    competitor_volume: float = 0.0
    last_nrx_date: Optional[str] = None
    total_in_class_rx: float = 0.0
    top_5_in_class_rx: List[Dict[str, Any]] = Field(default_factory=list)

    # ── AI output keys ────────────────────────────────────────────────────────
    ai_peer_match_score: float = Field(default=0.0, description="Peer affinity score 0-100")
    ai_peer_name: Optional[str] = None
    ai_peer_hcp_id: Optional[str] = None
    ai_peer_rationale: Optional[str] = None
    # No ICD-10 source column in the warehouse — "" when empty, list when matched
    ai_icd10_matched_codes: Union[List[str], str] = ""
    ai_icd10_match_count: int = 0
    ai_non_writer_flag: bool = True
    ai_warm_approach_text: Optional[str] = None   # short inline text on card
    ai_approach_highlight: Optional[str] = None   # key phrase in green
    ai_approach_brief: Optional[str] = None       # full GPT-4o brief (on-demand)
    # GPT-4o email-style brief: {subject, email_body, key_discussion_points}
    approach_brief: Optional[Dict[str, Any]] = None
    analysis_badges: List[str] = Field(default_factory=list)
    ai_is_identified: bool = True


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
