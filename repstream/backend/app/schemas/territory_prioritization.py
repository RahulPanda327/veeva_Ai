"""Pydantic schemas for Module 1 — Territory Prioritization.

AI/ML output keys (ai_* prefix) on every HCPRankedItem:

    AI_SCORING badge:
        ai_priority_score       float 0-100  composite (60% TRx + 30% Interaction + 10% Decile)
        ai_priority_tier        HIGH | MEDIUM | LOW
        ai_trx_growth_norm      float 0-100  normalised TRx growth component
        ai_interaction_impact   float 0-100  call recency + frequency + outcome
        ai_decile_score_norm    float 0-100  normalised decile rank component

    PREDICTIVE_ANALYTICS badge (LinearRegression):
        ai_rx_trend_direction   Improving | Stable | Declining
        ai_rx_slope             monthly Rx change (Rx/month)
        ai_predicted_next_q_rx  predicted Rx for next quarter
        ai_predicted_direction  Up | Flat | Down

    NLP_ANALYSIS badge:
        ai_engagement_category  ACTIVE_HIGH_VALUE | LAPSED_RECOVERABLE | NEW_WRITER | AT_RISK | STABLE
        ai_engagement_urgency   Immediate | This Week | This Month | Maintain
        ai_peer_match_hint      warm intro suggestion for New Writers

    AI_INSIGHT badge (GPT-4o):
        ai_generated_insight    one-sentence actionable insight
        ai_insight_highlight    key phrase rendered in green
"""
from datetime import date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class TerritorySummary(BaseModel):
    total_hcps: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    weekly_target: int
    period: str
    last_refresh: str
    territory_id: str
    territory_name: Optional[str] = None


class HCPRankedItem(BaseModel):
    # ── Identity ──────────────────────────────────────────────────────────────
    hcp_id: str
    name: str
    specialty: Optional[str] = None
    affiliated_hospital: Optional[str] = None
    territory_id: str
    segment: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    decile_rank: Optional[int] = None

    # ── Rx metrics ─────────────────────────────────────────────────────────────
    rx_q1: float = Field(default=0.0, description="Total brand Rx in current quarter")
    rx_q4: float = Field(default=0.0, description="Total brand Rx in prior quarter")
    rx_trend_pct: float = Field(default=0.0, description="(Q1-Q4)/Q4 × 100")
    last_rx_date: Optional[str] = None           # most recent date with Zenpep Rx > 0
    competitor_brand: Optional[str] = None
    competitor_brand_share: float = Field(default=0.0, ge=0.0, le=1.0)

    # ── Call interaction ───────────────────────────────────────────────────────
    last_call_date: Optional[date] = None
    days_since_last_call: Optional[int] = None
    call_count_90d: int = 0
    last_call_outcome: Optional[str] = None

    # ── Technique 1: AI Composite Scoring (AI_SCORING badge) ─────────────────
    ai_priority_score: float = Field(default=0.0, description="Composite 0-100 (60% TRx + 30% Interaction + 10% Decile)")
    ai_priority_tier: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    ai_trx_growth_norm: float = Field(default=0.0)
    ai_interaction_impact: float = Field(default=0.0)
    ai_decile_score_norm: float = Field(default=0.0)

    # ── Technique 2: Predictive Analytics — LinearRegression (PREDICTIVE_ANALYTICS badge) ──
    ai_rx_trend_direction: str = "Stable"            # Improving / Stable / Declining
    ai_rx_slope: Optional[float] = None              # Rx/month (positive = growing)
    ai_predicted_next_q_rx: Optional[float] = None  # forecast next quarter total Rx
    ai_predicted_direction: Optional[str] = None    # Up / Flat / Down

    # ── Technique 3: NLP Engagement Classification (NLP_ANALYSIS badge) ──────
    ai_engagement_category: Optional[str] = None    # ACTIVE_HIGH_VALUE / LAPSED_RECOVERABLE / NEW_WRITER / AT_RISK / STABLE
    ai_engagement_urgency: Optional[str] = None     # Immediate / This Week / This Month / Maintain
    ai_peer_match_hint: Optional[str] = None        # warm intro suggestion for New Writers

    # ── Technique 4: GPT-4o Insight (AI_INSIGHT badge) ───────────────────────
    ai_generated_insight: Optional[str] = None
    ai_insight_highlight: Optional[str] = None

    # Badges shown on UI card
    analysis_badges: List[str] = []

    ai_is_ranked: bool = True


class HCPInsightResponse(BaseModel):
    hcp_id: str
    ai_generated_insight: str
    ai_insight_highlight: Optional[str] = None
    generated_at: str
    cached: bool = False
