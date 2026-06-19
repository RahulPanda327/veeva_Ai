"""Pydantic v2 schemas for Action Center — Launch & Market Defense."""
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel


# ──────────────────────────────────────────────────
# Shared sub-objects
# ──────────────────────────────────────────────────

class ICD10Affected(BaseModel):
    code: str
    label: str
    hcp_count: int


class SupportingMaterial(BaseModel):
    title: str
    sku: Optional[str] = None


# ──────────────────────────────────────────────────
# Active Alerts
# ──────────────────────────────────────────────────

class AlertItem(BaseModel):
    alert_id: str
    alert_type: str                          # COMPETITIVE, PAYER, HCP_DRIFT, FORMULARY
    title: str
    description: str
    detected_at: str                         # ISO datetime string for UI
    period: Optional[str] = None

    # AI detection metadata
    ai_severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    ai_detection_method: Literal["ANOMALY_DETECTION", "AUTO_DETECTED", "ML_MODEL"]

    # AI impact analysis
    ai_affected_hcp_count: int = 0
    ai_territory_reach: Optional[str] = None    # "3/12"
    ai_rx_risk: Optional[str] = None            # High / Medium / Low
    ai_icd10_codes_affected: List[ICD10Affected] = []
    ai_prescribing_drift_note: Optional[str] = None
    ai_detection_lead_weeks: Optional[float] = None

    # AI counter-script
    ai_counter_script: Optional[str] = None
    ai_supporting_materials: List[SupportingMaterial] = []

    # State flags
    is_acknowledged: bool = False
    is_dismissed: bool = False
    is_deployed: bool = False

    # Action buttons from DB (e.g. ["Deploy to Field", "View Affected HCPs", "Dismiss"])
    recommended_actions: List[str] = []

    # Computed by AI layer
    ai_is_detected: bool = True


class ActionCenterSummary(BaseModel):
    territory_id: str
    period: str
    last_refresh: str

    # KPI tiles
    ai_critical_count: int = 0             # AI DETECTED badge
    ai_high_priority_count: int = 0        # AI DETECTED badge
    ai_medium_priority_count: int = 0
    ai_hcp_drift_detected_count: int = 0   # ML MODEL badge
    ai_early_detection_weeks: float = 0.0  # e.g. 2.8 (vs 6-8 traditional)

    # Yellow banner
    ai_new_unread_count: int = 0
    ai_banner_message: Optional[str] = None


class AlertListResponse(BaseModel):
    summary: ActionCenterSummary
    alerts: List[AlertItem]
    total: int


# ──────────────────────────────────────────────────
# HCP Awareness
# ──────────────────────────────────────────────────

class HCPAwarenessItem(BaseModel):
    awareness_id: str
    hcp_id: str
    hcp_full_name: str
    specialty: Optional[str] = None
    territory_id: str
    period: Optional[str] = None

    # Raw metrics
    product_awareness_score: float = 0.0
    competitor_awareness_score: float = 0.0
    clinical_evidence_score: float = 0.0
    total_interactions: int = 0
    last_interaction_date: Optional[str] = None

    # AI output keys
    ai_awareness_score: float = 0.0
    ai_awareness_level: Literal["High", "Medium", "Low"]
    ai_key_messages_delivered: List[str] = []
    ai_knowledge_gaps: List[str] = []
    ai_recommended_action: Optional[str] = None

    ai_is_assessed: bool = True


class HCPAwarenessResponse(BaseModel):
    items: List[HCPAwarenessItem]
    total: int
    ai_high_awareness_count: int = 0
    ai_medium_awareness_count: int = 0
    ai_low_awareness_count: int = 0


# ──────────────────────────────────────────────────
# Competitive Intel
# ──────────────────────────────────────────────────

class CompetitiveIntelItem(BaseModel):
    intel_id: str
    competitor_name: str
    territory_id: str
    period: Optional[str] = None

    # Signal data
    message_theme: Optional[str] = None
    detection_date: Optional[str] = None
    affected_hcp_count: int = 0
    market_share_change_pct: float = 0.0
    icd10_focus: List[ICD10Affected] = []
    source_channel: Optional[str] = None

    # AI output keys
    ai_threat_score: float = 0.0
    ai_threat_level: Literal["High", "Medium", "Low"]
    ai_counter_strategy: Optional[str] = None
    ai_supporting_evidence: Optional[str] = None
    ai_detection_method: Optional[str] = None

    ai_is_analyzed: bool = True


class CompetitiveIntelResponse(BaseModel):
    items: List[CompetitiveIntelItem]
    total: int
    ai_high_threat_count: int = 0
    ai_medium_threat_count: int = 0
    ai_avg_threat_score: float = 0.0


# ──────────────────────────────────────────────────
# Payer Access
# ──────────────────────────────────────────────────

class PayerAccessItem(BaseModel):
    access_id: str
    payer_name: str
    territory_id: str
    period: Optional[str] = None

    # Formulary data
    product_tier_current: Optional[int] = None
    product_tier_previous: Optional[int] = None
    tier_change_date: Optional[str] = None
    formulary_status: Optional[str] = None     # PREFERRED / NON-PREFERRED / EXCLUDED / PA_REQUIRED
    covered_lives: int = 0
    affected_hcp_count: int = 0
    patient_assistance_available: bool = False

    # AI output keys
    ai_impact_score: float = 0.0
    ai_access_impact: Literal["High", "Medium", "Low"]
    ai_action_required: Optional[str] = None
    ai_patient_assistance_note: Optional[str] = None
    ai_tier_change_direction: Optional[str] = None    # UPGRADE / DOWNGRADE / UNCHANGED

    ai_is_flagged: bool = True


class PayerAccessResponse(BaseModel):
    items: List[PayerAccessItem]
    total: int
    ai_high_impact_count: int = 0
    ai_total_covered_lives_at_risk: int = 0
    ai_total_affected_hcps: int = 0
