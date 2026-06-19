"""Pydantic schemas for Module 1 — Territory Prioritization.

AI output keys (all prefixed ai_) surfaced in every HCPRankedItem:

    ai_priority_score       float 0-100  weighted composite (60/30/10)
    ai_priority_tier        HIGH | MEDIUM | LOW
    ai_trx_growth_norm      float 0-100  normalised TRx growth component
    ai_interaction_impact   float 0-100  call recency + frequency + outcome
    ai_decile_score_norm    float 0-100  normalised decile rank component
    ai_generated_insight    str          GPT-4o one-sentence insight
    ai_insight_highlight    str | None   key phrase to render in green
    ai_is_ranked            bool         always True for scored HCPs
"""
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class TerritorySummary(BaseModel):
    total_hcps: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    weekly_target: int
    period: str                      # e.g. "Q1 2026 (Jan - Mar)"
    last_refresh: str                # ISO datetime string
    territory_id: str
    territory_name: Optional[str] = None


class HCPRankedItem(BaseModel):
    # ── Identity ─────────────────────────────────────────────────────────────
    hcp_id: str
    name: str
    specialty: Optional[str] = None
    affiliated_hospital: Optional[str] = None
    territory_id: str
    segment: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    decile_rank: Optional[int] = None

    # ── Rx metrics ────────────────────────────────────────────────────────────
    rx_q1: float = Field(description="Total brand Rx in current quarter")
    rx_q4: float = Field(description="Total brand Rx in prior quarter")
    rx_trend_pct: float = Field(description="(Q1-Q4)/Q4 × 100")
    competitor_brand: Optional[str] = None
    competitor_brand_share: float = Field(default=0.0, ge=0.0, le=1.0)

    # ── Call interaction ──────────────────────────────────────────────────────
    last_call_date: Optional[date] = None
    days_since_last_call: Optional[int] = None
    call_count_90d: int = 0
    last_call_outcome: Optional[str] = None

    # ── AI output keys ────────────────────────────────────────────────────────
    ai_priority_score: float = Field(description="Composite score 0-100 (60% TRx + 30% Interaction + 10% Decile)")
    ai_priority_tier: Literal["HIGH", "MEDIUM", "LOW"]
    ai_trx_growth_norm: float = Field(description="TRx growth component normalised to 0-100")
    ai_interaction_impact: float = Field(description="Interaction quality score 0-100")
    ai_decile_score_norm: float = Field(description="Decile score normalised to 0-100")
    ai_generated_insight: Optional[str] = Field(default=None, description="GPT-4o one-sentence insight")
    ai_insight_highlight: Optional[str] = Field(default=None, description="Key phrase rendered in green in the UI")
    ai_is_ranked: bool = True


class HCPInsightResponse(BaseModel):
    hcp_id: str
    ai_generated_insight: str
    ai_insight_highlight: Optional[str] = None
    generated_at: str
    cached: bool = False
