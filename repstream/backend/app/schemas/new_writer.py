"""Pydantic schemas for Module 2 — New Writer Identification.

AI output keys:
    ai_peer_match_score     float 0-100   from insight360_peer_match.match_score
    ai_icd10_match_count    int           number of target ICD-10 codes matched
    ai_match_rationale      str | None    why the peer match was made
    ai_non_writer_flag      bool          True = in-class Rx > 0 AND brand Rx = 0
    ai_approach_brief       str | None    GPT-4o warm outreach brief text
    ai_approach_highlight   str | None    key phrase to render in green in the UI
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class NewWriterCandidate(BaseModel):
    # ── Identity ─────────────────────────────────────────────────────────────
    hcp_id: str
    name: str
    specialty: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    territory_id: str
    segment: Optional[str] = None

    # ── Rx profile ────────────────────────────────────────────────────────────
    in_class_rx_q1: float = Field(description="In-class Rx written in current quarter")
    brand_rx_q1: float = Field(description="Brand Rx current quarter (0 for non-writer)")
    brand_rx_q4: float = Field(description="Brand Rx prior quarter (0 for non-writer)")
    competitor_brand: Optional[str] = None
    competitor_volume: float = 0.0

    # ── AI output keys ────────────────────────────────────────────────────────
    ai_peer_match_score: float = Field(description="Peer affinity score 0-100")
    ai_peer_name: Optional[str] = None
    ai_peer_hcp_id: Optional[str] = None
    ai_peer_rationale: Optional[str] = None
    ai_icd10_matched_codes: List[str] = Field(default_factory=list)
    ai_icd10_match_count: int = 0
    ai_non_writer_flag: bool = True
    ai_approach_brief: Optional[str] = None
    ai_approach_highlight: Optional[str] = None


class ApproachBriefResponse(BaseModel):
    hcp_id: str
    ai_approach_brief: str
    ai_approach_highlight: Optional[str] = None
    ai_peer_name: Optional[str] = None
    generated_at: str
    cached: bool = False
