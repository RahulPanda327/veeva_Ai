"""Pydantic v2 schemas for Action Center — Launch & Market Defense."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


# ──────────────────────────────────────────────────
# Shared sub-objects
# ──────────────────────────────────────────────────

class ICD10Affected(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"code": "K86.81", "label": "Exocrine pancreatic insufficiency", "hcp_count": 9}
    })
    code:      str = Field(description="ICD-10 diagnosis code", examples=["K86.81", "I50.9", "C25.0"])
    label:     str = Field(description="Human-readable diagnosis label", examples=["Exocrine pancreatic insufficiency"])
    hcp_count: int = Field(description="Number of affected HCPs with this diagnosis", examples=[9])


class SupportingMaterial(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"title": "APEX Trial Summary", "sku": "APEX-2024-01"}
    })
    title: str            = Field(description="Name of the Zenpep material to deploy", examples=["APEX Trial Summary"])
    sku:   Optional[str]  = Field(default=None, description="Material SKU code (null if no SKU)", examples=["APEX-2024-01"])


# ──────────────────────────────────────────────────
# Active Alerts
# ──────────────────────────────────────────────────

class AlertItem(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "alert_id":                 "ALERT-001",
        "alert_type":               "COMPETITIVE",
        "title":                    "Competitive script shift in cardiology segment",
        "description":              "Competitor X launched new messaging around 'faster onset' claims. Detected in 8 HCP interactions across 3 territories between Apr 26-28, 2026.",
        "detected_at":              "Apr 28, 2026 at 8:15 AM",
        "period":                   "Q1 2026 (Jan - Mar)",
        "ai_severity":              "CRITICAL",
        "ai_detection_method":      "ANOMALY_DETECTION",
        "ai_affected_hcp_count":    23,
        "ai_territory_reach":       "3/12",
        "ai_rx_risk":               "High",
        "ai_icd10_codes_affected": [
            {"code": "I50.9",  "label": "Heart Failure",    "hcp_count": 12},
            {"code": "I25.10", "label": "CAD",              "hcp_count": 8},
            {"code": "I11.0",  "label": "Hypertensive HD",  "hcp_count": 3}
        ],
        "ai_prescribing_drift_note": "Prescribing drift detected: 4 HCPs showing 15-20% reduction in Rx volume Apr 14-28, 2026.",
        "ai_detection_lead_weeks":   2.8,
        "ai_counter_script":         "While onset time is one factor, our clinical data shows sustained efficacy over 24 months with significantly lower adverse events. The APEX trial demonstrates that long-term patient outcomes are superior with our mechanism of action.",
        "ai_supporting_materials": [
            {"title": "APEX Trial Summary",            "sku": "APEX-2024-01"},
            {"title": "Competitive Positioning Guide", "sku": None}
        ],
        "is_acknowledged":    False,
        "is_dismissed":       False,
        "is_deployed":        False,
        "recommended_actions": ["Deploy to Field", "View Affected HCPs", "Dismiss"],
        "ai_is_detected":     True
    }})

    # ── Identity ──────────────────────────────────────────────────────────────
    alert_id:     str = Field(description="Unique alert identifier", examples=["ALERT-001", "ML-ANOM-A3F2B1C4"])
    alert_type:   str = Field(description="Alert category", examples=["COMPETITIVE", "PAYER", "HCP_DRIFT", "FORMULARY"])
    title:        str = Field(description="GPT-4o generated alert headline")
    description:  str = Field(description="GPT-4o generated 2-sentence narrative (what happened, where, when)")
    detected_at:  str = Field(description="Detection timestamp shown on card", examples=["Apr 28, 2026 at 8:15 AM"])
    period:       Optional[str] = Field(default=None, description="Data period", examples=["Q1 2026 (Jan - Mar)"])

    # ── AI Detection Metadata ─────────────────────────────────────────────────
    ai_severity:         Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        description="Severity level — drives badge color (CRITICAL=red, HIGH=orange, MEDIUM=teal)"
    )
    ai_detection_method: Literal["ANOMALY_DETECTION", "AUTO_DETECTED", "ML_MODEL"] = Field(
        description="How the alert was detected — drives method badge on card"
    )

    # ── AI Impact Analysis ────────────────────────────────────────────────────
    ai_affected_hcp_count:   int           = Field(default=0,   description="Number of HCPs impacted — shown in Impact Analysis section", examples=[23])
    ai_territory_reach:      Optional[str] = Field(default=None, description="Territories affected as fraction. For PAYER type shows covered lives count instead", examples=["3/12", "340"])
    ai_rx_risk:              Optional[str] = Field(default=None, description="Rx risk level. For PAYER type shown as Access Impact", examples=["High", "Medium", "Low"])
    ai_icd10_codes_affected: List[ICD10Affected] = Field(default=[], description="ICD-10 codes affected — shown as tags under Target ICD-10 section. Empty for PAYER/FORMULARY types")
    ai_prescribing_drift_note: Optional[str] = Field(default=None, description="GPT-4o: why prescribing behavior changed — shown below ICD-10 tags")
    ai_detection_lead_weeks:   Optional[float] = Field(default=None, description="Weeks ahead of traditional reporting this was detected. Null for PAYER/FORMULARY types", examples=[2.8])

    # ── AI Counter Script ─────────────────────────────────────────────────────
    ai_counter_script:        Optional[str]          = Field(default=None, description="GPT-4o: what rep should say right now — shown in Recommended Counter-Script section")
    ai_supporting_materials:  List[SupportingMaterial] = Field(default=[], description="GPT-4o: Zenpep materials to deploy — shown below counter script")

    # ── Payer tier change ─────────────────────────────────────────────────────
    tier_current:  Optional[str] = Field(default=None, description="insight360_payer_access.Formulary_Tier. Only populated for payer alerts sourced from that table; null otherwise")
    tier_previous: Optional[str] = Field(default=None, description="insight360_payer_access.Previous_Tier. Only populated for payer alerts sourced from that table; null otherwise")

    # ── State Flags ───────────────────────────────────────────────────────────
    is_acknowledged: bool = Field(default=False, description="Rep has acknowledged this alert")
    is_dismissed:    bool = Field(default=False, description="Rep has dismissed this alert")
    is_deployed:     bool = Field(default=False, description="Alert has been deployed to field")

    # ── Action Buttons ────────────────────────────────────────────────────────
    recommended_actions: List[str] = Field(
        default=[],
        description="Action buttons to render on card. CRITICAL/HIGH: ['Deploy to Field','View Affected HCPs','Dismiss']. MEDIUM: ['Monitor','View Affected HCPs','Dismiss']. PAYER: ['View HCP List','Access Resources','Acknowledge']",
        examples=[["Deploy to Field", "View Affected HCPs", "Dismiss"]]
    )
    ai_is_detected: bool = Field(default=True, description="Always true — confirms this alert was AI-generated")


class ActionCenterSummary(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "territory_id":                 "A0E000000013007",
        "period":                       "Q1 2026 (Jan - Mar)",
        "last_refresh":                 "Jun 24, 2026 10:30 AM",
        "ai_critical_count":            3,
        "ai_high_priority_count":       3,
        "ai_medium_priority_count":     2,
        "ai_hcp_drift_detected_count":  12,
        "ai_early_detection_weeks":     2.8,
        "ai_new_unread_count":          8,
        "ai_banner_message":            "Competitive script shifts detected in your territory"
    }})

    territory_id: str = Field(description="Rep's territory identifier")
    period:       str = Field(description="Data reference period shown top-right", examples=["Q1 2026 (Jan - Mar)"])
    last_refresh: str = Field(description="Timestamp of last data refresh shown top-right", examples=["Jun 24, 2026 10:30 AM"])

    # KPI tiles
    ai_critical_count:            int   = Field(default=0,   description="Critical Alerts KPI tile — shows AI DETECTED badge", examples=[3])
    ai_high_priority_count:       int   = Field(default=0,   description="High Priority KPI tile — shows AI DETECTED badge", examples=[3])
    ai_medium_priority_count:     int   = Field(default=0,   description="Medium Priority KPI tile", examples=[2])
    ai_hcp_drift_detected_count:  int   = Field(default=0,   description="HCP Drift Detected KPI tile — shows ML MODEL badge", examples=[12])
    ai_early_detection_weeks:     float = Field(default=0.0, description="Early Detection KPI tile — weeks ahead of traditional reporting", examples=[2.8])

    # Yellow banner
    ai_new_unread_count: int          = Field(default=0,    description="Badge count on yellow banner showing unread alerts", examples=[8])
    ai_banner_message:   Optional[str]= Field(default=None, description="Yellow banner message text. Null if no critical alerts", examples=["Competitive script shifts detected in your territory"])


class CompetitiveAlertItem(BaseModel):
    alert_id:                 str
    ai_severity:              Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    ai_detection_method:      Literal["ANOMALY_DETECTION", "AUTO_DETECTED", "ML_MODEL"]
    detected_at:              str
    title:                    str
    description:              str
    ai_affected_hcp_count:    int                  = 0
    ai_territory_reach:       Optional[str]        = None
    ai_rx_risk:               Optional[str]        = None
    ai_icd10_codes_affected:  List[ICD10Affected]  = []
    ai_prescribing_drift_note: Optional[str]       = None
    ai_counter_script:        Optional[str]        = None
    ai_supporting_materials:  List[SupportingMaterial] = []
    recommended_actions:      List[str]            = []


class HCPAlertItem(BaseModel):
    alert_id:             str
    ai_severity:          Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    ai_detection_method:  Literal["ANOMALY_DETECTION", "AUTO_DETECTED", "ML_MODEL"]
    detected_at:          str
    title:                str
    description:          str
    recommended_actions:  List[str] = []


class PayerAlertItem(BaseModel):
    alert_id:                 str
    ai_severity:              Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    ai_detection_method:      Literal["ANOMALY_DETECTION", "AUTO_DETECTED", "ML_MODEL"]
    detected_at:              str
    title:                    str
    description:              str
    ai_affected_hcp_count:    int           = 0
    ai_territory_reach:       Optional[str] = None   # shows as "Covered Lives" for payer
    ai_rx_risk:               Optional[str] = None   # shows as "Access Impact" for payer
    ai_prescribing_drift_note: Optional[str] = None
    recommended_actions:      List[str]     = []
    tier_current:              Optional[str] = Field(default=None, description="insight360_payer_access.Formulary_Tier. Only populated for payer alerts sourced from that table; null otherwise")
    tier_previous:             Optional[str] = Field(default=None, description="insight360_payer_access.Previous_Tier. Only populated for payer alerts sourced from that table; null otherwise")


class AlertGroups(BaseModel):
    competitive:   List[CompetitiveAlertItem] = Field(default=[], description="All COMPETITIVE alert cards")
    payer:         List[PayerAlertItem]       = Field(default=[], description="All PAYER alert cards")
    hcp_awareness: List[HCPAlertItem]         = Field(default=[], description="All HCP_DRIFT / awareness alert cards")


class AlertListResponse(BaseModel):
    summary:     ActionCenterSummary = Field(description="KPI summary tiles + banner data for the top section")
    alerts:      AlertGroups         = Field(description="Alerts grouped by module type")
    total:       int                 = Field(description="Total alerts returned across all groups", examples=[8])
    total_in_db: int                 = Field(default=0, description="Actual row count in insight360_active_alerts", examples=[8])


class ActiveAlertSection(BaseModel):
    competitive_alerts:   List[Dict[str, Any]] = []
    payer_alerts:         List[Dict[str, Any]] = []
    hcp_awareness_alerts: List[Dict[str, Any]] = []


class ActiveAlertListResponse(BaseModel):
    active_alerts: ActiveAlertSection


# ──────────────────────────────────────────────────
# HCP Awareness
# ──────────────────────────────────────────────────

class ICD10Pattern(BaseModel):
    code: str
    label: str
    pct: float                      # e.g. 42.0 (%)


class TrendPoint(BaseModel):
    period: str                     # "Jan 29", "Feb 26", etc.
    avg_score: float


class HCPAwarenessItem(BaseModel):
    hcp_full_name: str
    specialty: Optional[str] = None
    institution: Optional[str] = None
    ai_awareness_score: float = 0.0
    ai_awareness_level: Literal["High", "Medium", "Low"] = "Medium"
    ai_trend_direction: Optional[str] = None
    ai_score_change_pct: Optional[float] = None
    ai_change_from_period: Optional[str] = None
    analysis_badges: List[str] = []
    ai_icd10_prescribing_patterns: List[ICD10Pattern] = []
    ai_aim_xr_activity: Optional[str] = None


class HCPAwarenessResponse(BaseModel):
    awareness_trend: List[TrendPoint] = []
    ai_declining_period: Optional[str] = None
    items: List[HCPAwarenessItem]


# ──────────────────────────────────────────────────
# Competitive Intel
# ──────────────────────────────────────────────────

class CompetitiveIntelItem(BaseModel):
    signal_id: str
    signal_type: str                          # "AI DETECTED" / "ML TREND" / "ANOMALY"
    signal_date: Optional[str] = None
    territory_id: str
    territory_name: Optional[str] = None
    region: Optional[str] = None
    competitor_brand: str
    rx_change_percent: float = 0.0
    activity_change_percent: float = 0.0
    territory_sales: Optional[float] = None

    # ── GPT-4o enrichment ────────────────────────────────────────────────────
    headline: Optional[str] = None
    executive_summary: Optional[str] = None
    counter_strategy: Optional[str] = None   # DB Counter_Strategy
    risk_level: Optional[str] = None         # "HIGH" / "MEDIUM" / "LOW"
    urgency_level: Optional[str] = None      # "IMMEDIATE" / "STANDARD" / "ROUTINE"
    business_impact: Optional[str] = None
    recommended_actions: List[str] = []
    field_force_talking_points: List[str] = []


class CompetitiveIntelResponse(BaseModel):
    items: List[CompetitiveIntelItem]
    total: int


# ──────────────────────────────────────────────────
# Payer Access
# ──────────────────────────────────────────────────

class PayerAccessItem(BaseModel):
    plan_id: str
    payer_name: str
    mco_org_name: Optional[str] = None
    channel_name: Optional[str] = None          # Commercial / Medicare / Medicaid

    # Raw formulary data
    tier_current: Optional[str] = None          # "Tier 1" / "Tier 2" / "Non-Formulary"
    tier_previous: Optional[str] = None
    change_date: Optional[str] = None
    pa_required: Optional[str] = None        # "Yes" / "No"
    covered_lives: int = 0
    affected_hcp_count: int = 0

    # UI display labels (computed)
    tier_label_current: Optional[str] = None    # "Preferred" / "Standard" / "Non-preferred"
    status_badge: str = "STABLE"                # "AI_ALERT" / "STABLE"
    change_badge: Optional[str] = None          # "CHANGE_DETECTED" or None

    # ── ML: AI Impact Scoring (AI_SCORING badge) ─────────────────────────────
    ai_impact_score: float = 0.0                # 0-100 composite
    ai_impact_level: Literal["High", "Medium", "Low"] = "Low"
    ai_tier_change_direction: Optional[str] = None   # UPGRADE / DOWNGRADE / UNCHANGED
    # ── ML: Predictive Analytics (PREDICTIVE_ANALYTICS badge) ────────────────
    ai_abandonment_risk_pct: Optional[float] = None  # % patients likely to abandon Rx
    ai_projected_patient_impact: Optional[int] = None  # estimated patients impacted

    # ── NLP: Recommended_Action classification (NLP_ANALYSIS badge) ──────────
    ai_nlp_action_category: Optional[str] = None   # FORMULARY_CHANGE / PA_REQUIREMENT / ACCESS_WIN / MONITORING
    ai_nlp_urgency: Optional[str] = None            # Immediate / Standard / Routine
    ai_nlp_keywords: List[str] = []

    # ── GPT-4o ────────────────────────────────────────────────────────────────
    ai_impact_summary: Optional[str] = None         # 1-sentence business impact
    ai_action_plan: Union[str, List[str]] = []       # List[str] when AI-flagged, str when DB fallback
    ai_pa_bridge_note: Optional[str] = None         # PA bridge language (if PA required)

    # "View Action Plan" — insight360_payer_access.Recommended_Action
    view_action_plan: Optional[str] = None

    # Badges
    analysis_badges: List[str] = []

    ai_is_flagged: bool = True


class PayerAccessResponse(BaseModel):
    items: List[PayerAccessItem]
    total: int
    ai_alert_count: int = 0
    ai_stable_count: int = 0
    ai_tier_downgrade_count: int = 0
    ai_high_impact_count: int = 0
    ai_total_covered_lives_at_risk: int = 0
    ai_total_affected_hcps: int = 0
