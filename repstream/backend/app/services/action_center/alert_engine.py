"""
Active Alerts engine — full pipeline:

  STEP 1 — DB READ
    Read alert rows from hub_insight360.insight360_active_alerts

  STEP 2 — ML / DATA (numbers & classifications)
    ai_severity          ← DB Alert_Priority (pre-computed by upstream ML)
    ai_detection_method  ← DB Alert_Type → mapped to enum
    alert_type           ← derived from detection_method
    ai_affected_hcp_count← DB Affected_HCP_Count
    ai_territory_reach   ← DB Territory_Reach → formatted "X/12"
    ai_rx_risk           ← DB Rx_Risk_Level
    ai_icd10_codes_affected ← HCP dimension table (real ICD-10) → rule-based fallback
    ai_detection_lead_weeks ← LinearRegression slope (None for DB-sourced alerts)
    recommended_actions  ← rule-based on severity (not DB string)

  STEP 3 — LLM (language keys)
    title                ← GPT-4o (specific, data-driven)
    description          ← GPT-4o (2-sentence narrative)
    ai_prescribing_drift_note ← GPT-4o
    ai_counter_script    ← GPT-4o (actionable rep script)
    ai_supporting_materials   ← GPT-4o

  STEP 4 — STATE FLAGS (Python defaults)
    is_acknowledged / is_dismissed / is_deployed → False
    ai_is_detected → True
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

_DATE_FORMATS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%b %d, %Y at %I:%M %p",
    "%b %d, %Y at %I:%M%p",
]

def _parse_detected_at(val: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(val.strip(), fmt)
        except ValueError:
            continue
    return datetime.min

from sqlalchemy import case, text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

from app.models.active_alerts import ActiveAlert
from app.models.territory_prioritization import HealthcarePractitioner
from app.services.action_center.alert_enricher import enrich
from app.services.action_center.alert_detector import DetectedAlert, detect_alerts
from app.database import engine as db_engine
from app.schemas.action_center import (
    ActionCenterSummary,
    ActiveAlertListResponse,
    AlertGroups,
    AlertItem,
    AlertListResponse,
    CompetitiveAlertItem,
    HCPAlertItem,
    PayerAlertItem,
    ICD10Affected,
    SupportingMaterial,
)

# ── Sample fallback data — matches UI screenshot exactly ─────────────────────
# Used when both ML pipeline and DB return no rows (firewalled views / empty table).

_SAMPLE_ALERT_ITEMS: List[AlertItem] = [
    # ─── 3 CRITICAL ───────────────────────────────────────────────────────────
    AlertItem(
        alert_id="ALERT-001",
        alert_type="COMPETITIVE",
        title="Competitive script shift in cardiology segment",
        description=(
            'Competitor X launched new messaging around "faster onset" claims. '
            "Detected in 8 HCP interactions across 3 territories between Apr 26-28, 2026."
        ),
        detected_at="Apr 28, 2026 at 8:15 AM",
        period="Q1 2026 (Jan - Mar)",
        ai_severity="CRITICAL",
        ai_detection_method="ANOMALY_DETECTION",
        ai_affected_hcp_count=23,
        ai_territory_reach="3/12",
        ai_rx_risk="High",
        ai_icd10_codes_affected=[
            ICD10Affected(code="I50.9",  label="Heart Failure",     hcp_count=12),
            ICD10Affected(code="I25.10", label="CAD",               hcp_count=8),
            ICD10Affected(code="I11.0",  label="Hypertensive HD",   hcp_count=3),
        ],
        ai_prescribing_drift_note=(
            "Prescribing drift detected: 4 HCPs showing 15-20% reduction in Rx volume Apr 14-28, 2026."
        ),
        ai_detection_lead_weeks=2.8,
        ai_counter_script=(
            "While onset time is one factor, our clinical data shows sustained efficacy over 24 months "
            "with significantly lower adverse events. The APEX trial demonstrates that long-term patient "
            "outcomes are superior with our mechanism of action."
        ),
        ai_supporting_materials=[
            SupportingMaterial(title="APEX Trial Summary",           sku="APEX-2024-01"),
            SupportingMaterial(title="Competitive Positioning Guide", sku=None),
        ],
        is_acknowledged=False, is_dismissed=False, is_deployed=False, ai_is_detected=True,
        recommended_actions=["Deploy to Field", "View Affected HCPs", "Dismiss"],
    ),
    AlertItem(
        alert_id="ALERT-002",
        alert_type="COMPETITIVE",
        title="Creon gaining share — 11 HCPs increasing competitor volume",
        description=(
            "Creon detailing surge detected across 2 territories. 11 HCPs shifted >10% Rx volume "
            "to competitor over Apr 18-28, 2026. IsolationForest anomaly score: high confidence."
        ),
        detected_at="Apr 27, 2026 at 6:45 PM",
        period="Q1 2026 (Jan - Mar)",
        ai_severity="CRITICAL",
        ai_detection_method="ANOMALY_DETECTION",
        ai_affected_hcp_count=11,
        ai_territory_reach="2/12",
        ai_rx_risk="High",
        ai_icd10_codes_affected=[
            ICD10Affected(code="K86.81", label="Exocrine pancreatic insufficiency", hcp_count=7),
            ICD10Affected(code="K86.1",  label="Chronic pancreatitis",              hcp_count=4),
        ],
        ai_prescribing_drift_note=(
            "Creon rep call frequency increased +68% in affected territory. Market share down 4.2 points."
        ),
        ai_detection_lead_weeks=3.1,
        ai_counter_script=(
            "Reinforce Zenpep's microsphere technology — unlike Creon's beads, microspheres are sized "
            "for optimal duodenal release. Deploy the APEX comparative outcomes data showing superior "
            "CFA response at 12 weeks. ZenConnect co-pay card available for cost-sensitive patients."
        ),
        ai_supporting_materials=[
            SupportingMaterial(title="APEX Trial Summary",    sku="APEX-2024-01"),
            SupportingMaterial(title="ZenConnect Enrollment", sku="ZPP-ZENCONNECT"),
        ],
        is_acknowledged=False, is_dismissed=False, is_deployed=False, ai_is_detected=True,
        recommended_actions=["Deploy to Field", "View Affected HCPs", "Dismiss"],
    ),
    AlertItem(
        alert_id="ALERT-003",
        alert_type="COMPETITIVE",
        title="Rx volume decline across 15 HCPs — 18% drop last 2 weeks",
        description=(
            "IsolationForest flagged 15 HCPs with simultaneous Zenpep volume reduction and "
            "competitor Rx increase across 4 territories. Detection window: Apr 14-28, 2026."
        ),
        detected_at="Apr 26, 2026 at 9:00 AM",
        period="Q1 2026 (Jan - Mar)",
        ai_severity="CRITICAL",
        ai_detection_method="ANOMALY_DETECTION",
        ai_affected_hcp_count=15,
        ai_territory_reach="4/12",
        ai_rx_risk="High",
        ai_icd10_codes_affected=[
            ICD10Affected(code="K86.81", label="Exocrine pancreatic insufficiency", hcp_count=9),
            ICD10Affected(code="C25.0",  label="Malignant neoplasm of pancreas",    hcp_count=6),
        ],
        ai_prescribing_drift_note=(
            "15-20% Rx volume reduction correlated with increased competitor detailing frequency "
            "in the same period. Urgently deploy counter-messaging."
        ),
        ai_detection_lead_weeks=2.5,
        ai_counter_script=(
            "Reference real-world evidence showing Zenpep EPI management outcomes. Highlight "
            "ZenConnect patient support services and the clinical necessity advantage in patients "
            "with documented pancreatic enzyme deficiency. Offer a lunch-and-learn to the practice."
        ),
        ai_supporting_materials=[
            SupportingMaterial(title="Zenpep Real-World Evidence Summary", sku="RWE-2024-01"),
            SupportingMaterial(title="ZenConnect Patient Support",         sku="ZPP-ZENCONNECT"),
        ],
        is_acknowledged=False, is_dismissed=False, is_deployed=False, ai_is_detected=True,
        recommended_actions=["Deploy to Field", "View Affected HCPs", "Dismiss"],
    ),
    # ─── 3 HIGH ───────────────────────────────────────────────────────────────
    AlertItem(
        alert_id="ALERT-004",
        alert_type="PAYER",
        title="Payer formulary update — Tier change",
        description=(
            "BlueCross Northeast moved our product from Tier 2 to Tier 3 effective Apr 25, 2026. "
            "Affects approximately 340 covered lives in your territory."
        ),
        detected_at="Apr 28, 2026 at 4:30 AM",
        period="Q1 2026 (Jan - Mar)",
        ai_severity="HIGH",
        ai_detection_method="AUTO_DETECTED",
        ai_affected_hcp_count=47,
        ai_territory_reach="340",   # covered lives for PAYER type (UI shows "Covered Lives" label)
        ai_rx_risk="Medium",        # shown as "Access Impact" for PAYER type
        ai_icd10_codes_affected=[],
        ai_prescribing_drift_note=(
            "Action needed: Patient assistance program enrollment may be required for cost-sensitive patients."
        ),
        ai_detection_lead_weeks=None,
        ai_counter_script=None,
        ai_supporting_materials=[],
        is_acknowledged=False, is_dismissed=False, is_deployed=False, ai_is_detected=True,
        recommended_actions=["View HCP List", "Access Resources", "Acknowledge"],
    ),
    AlertItem(
        alert_id="ALERT-005",
        alert_type="COMPETITIVE",
        title="Pancreaze detailing surge — 8 gastroenterology HCPs affected",
        description=(
            "Pancreaze rep activity increased +52% in gastroenterology segment. "
            "8 top-decile HCPs showing reduced Zenpep call access over Apr 20-28, 2026."
        ),
        detected_at="Apr 27, 2026 at 11:15 AM",
        period="Q1 2026 (Jan - Mar)",
        ai_severity="HIGH",
        ai_detection_method="AUTO_DETECTED",
        ai_affected_hcp_count=8,
        ai_territory_reach="2/12",
        ai_rx_risk="Medium",
        ai_icd10_codes_affected=[
            ICD10Affected(code="K86.81", label="Exocrine pancreatic insufficiency", hcp_count=5),
            ICD10Affected(code="K86.1",  label="Chronic pancreatitis",              hcp_count=3),
        ],
        ai_prescribing_drift_note="8 HCPs showing reduced rep engagement — schedule urgent calls.",
        ai_detection_lead_weeks=1.9,
        ai_counter_script=(
            "Pancreaze does not have Phase 3 data showing consistent fat absorption across all three "
            "macronutrients. Lead with the APEX trial head-to-head data and reinforce Zenpep's EPI "
            "management superiority at 6 and 12 weeks. Offer gastro-focused patient cases."
        ),
        ai_supporting_materials=[
            SupportingMaterial(title="Pancreaze vs Zenpep Comparison", sku="COMP-PANC-001"),
            SupportingMaterial(title="APEX Trial Summary",              sku="APEX-2024-01"),
        ],
        is_acknowledged=False, is_dismissed=False, is_deployed=False, ai_is_detected=True,
        recommended_actions=["Deploy to Field", "View Affected HCPs", "Dismiss"],
    ),
    AlertItem(
        alert_id="ALERT-006",
        alert_type="HCP_DRIFT",
        title="HCP engagement declining — 6 prescribers showing gradual drift",
        description=(
            "Linear regression model detected consistent downward Zenpep Rx slope across 6 HCPs. "
            "Average decline: -1.8 Rx/month over past 4 months. ML confidence: high (R² > 0.7)."
        ),
        detected_at="Apr 28, 2026 at 7:00 AM",
        period="Q1 2026 (Jan - Mar)",
        ai_severity="HIGH",
        ai_detection_method="ML_MODEL",
        ai_affected_hcp_count=6,
        ai_territory_reach="1/12",
        ai_rx_risk="Medium",
        ai_icd10_codes_affected=[
            ICD10Affected(code="K86.81", label="Exocrine pancreatic insufficiency", hcp_count=4),
            ICD10Affected(code="K86.1",  label="Chronic pancreatitis",              hcp_count=2),
        ],
        ai_prescribing_drift_note=(
            "Gradual Rx drift detected 2.8 weeks earlier than traditional call-based reporting. "
            "Intervention now could recover 60-80% of at-risk volume."
        ),
        ai_detection_lead_weeks=2.8,
        ai_counter_script=(
            "Prioritize re-engagement calls with these 6 HCPs this week. Lead with updated EPI "
            "outcomes data and ZenConnect patient support. Request peer discussion with a high-volume "
            "Zenpep writer from their hospital network."
        ),
        ai_supporting_materials=[
            SupportingMaterial(title="Zenpep EPI Outcomes Data", sku="EPI-2024-01"),
            SupportingMaterial(title="ZenConnect Program Guide",  sku="ZPP-ZENCONNECT"),
        ],
        is_acknowledged=False, is_dismissed=False, is_deployed=False, ai_is_detected=True,
        recommended_actions=["Deploy to Field", "View Affected HCPs", "Dismiss"],
    ),
    # ─── 2 MEDIUM ─────────────────────────────────────────────────────────────
    AlertItem(
        alert_id="ALERT-007",
        alert_type="FORMULARY",
        title="Formulary review cycle — Aetna Tier 1 renewal pending Q3",
        description=(
            "Aetna Commercial formulary review scheduled for Q3 2026. Current Tier 1 status at risk "
            "if clinical dossier not submitted by Jun 30. Affects ~280 covered lives."
        ),
        detected_at="Apr 25, 2026 at 3:00 PM",
        period="Q1 2026 (Jan - Mar)",
        ai_severity="MEDIUM",
        ai_detection_method="AUTO_DETECTED",
        ai_affected_hcp_count=12,
        ai_territory_reach="280",   # covered lives
        ai_rx_risk="Low",           # shown as "Access Impact"
        ai_icd10_codes_affected=[],
        ai_prescribing_drift_note="Submit updated clinical dossier before Jun 30, 2026 to maintain Tier 1 status.",
        ai_detection_lead_weeks=None,
        ai_counter_script=None,
        ai_supporting_materials=[
            SupportingMaterial(title="Formulary Dossier Template", sku=None),
        ],
        is_acknowledged=False, is_dismissed=False, is_deployed=False, ai_is_detected=True,
        recommended_actions=["View HCP List", "Access Resources", "Acknowledge"],
    ),
    AlertItem(
        alert_id="ALERT-008",
        alert_type="HCP_DRIFT",
        title="HCP awareness score decline in endocrinology",
        description=(
            "3 HCPs showing decreased awareness of key product benefits between Apr 6-27, 2026. "
            "May indicate need for re-education."
        ),
        detected_at="Apr 27, 2026 at 2:15 PM",
        period="Q1 2026 (Jan - Mar)",
        ai_severity="MEDIUM",
        ai_detection_method="ML_MODEL",
        ai_affected_hcp_count=3,
        ai_territory_reach=None,
        ai_rx_risk=None,
        ai_icd10_codes_affected=[],
        ai_prescribing_drift_note=None,
        ai_detection_lead_weeks=None,
        ai_counter_script=None,
        ai_supporting_materials=[],
        is_acknowledged=False, is_dismissed=False, is_deployed=False, ai_is_detected=True,
        recommended_actions=["Schedule Calls", "Review Later"],
    ),
]

# ── Severity sort ─────────────────────────────────────────────────────────────

_SEVERITY_RANK = case(
    (ActiveAlert.severity == "CRITICAL", 0),
    (ActiveAlert.severity == "HIGH",     1),
    (ActiveAlert.severity == "MEDIUM",   2),
    else_=3,
)

# ── Detection method mapping ──────────────────────────────────────────────────

_DETECTION_MAP = {
    "ANOMALY DETECTION": "ANOMALY_DETECTION",
    "ML TREND":          "ML_MODEL",
    "ANOMALY":           "ANOMALY_DETECTION",
}

# ── Known Zenpep ICD-10 codes (pancreatic enzyme conditions) ──────────────────

_ZENPEP_ICD10 = [
    ("K86.81", "Exocrine pancreatic insufficiency"),
    ("K86.1",  "Chronic pancreatitis"),
    ("K90.3",  "Pancreatic steatorrhea"),
    ("C25.0",  "Malignant neoplasm of head of pancreas"),
    ("K86.0",  "Alcohol-induced chronic pancreatitis"),
]

# Proportional weights for fallback — EPI most common, then chronic pancreatitis
_ICD10_WEIGHTS = [0.45, 0.30, 0.15, 0.07, 0.03]

_RX_RISK_SCORE: Dict[str, int] = {"High": 3, "Medium": 2, "Low": 1}


# ── STEP 1 helper: territory reach formatter ──────────────────────────────────

def _format_reach(raw: str | None) -> str:
    if not raw:
        return "—"
    parts = raw.split(" of ")
    if len(parts) == 2:
        num   = parts[0].strip()
        denom = parts[1].replace("territories", "").replace("territory", "").strip()
        return f"{num}/{denom}"
    return raw


# ── STEP 2a: ICD-10 from HCP dimension table (ML/data layer) ─────────────────

def _icd10_for_alert(db: Session, row: ActiveAlert) -> List[ICD10Affected]:
    """
    Pull real ICD-10 codes from vw_tdim_healthcarepractitioner_zenpep_reporting
    for HCPs in this alert's territory.  Counts are scaled to ai_affected_hcp_count.
    Falls back to proportional rule-based split if the view is empty.
    """
    total = int(row.ai_affected_hcp_count or 0)
    if total == 0:
        return []

    try:
        hcps = (
            db.query(HealthcarePractitioner)
            .filter(
                HealthcarePractitioner.territory_id == row.territory_id,
                HealthcarePractitioner.icd10_codes.isnot(None),
            )
            .limit(200)
            .all()
        )

        if hcps:
            code_counts: Dict[str, dict] = {}
            for hcp in hcps:
                for raw_code in (hcp.icd10_codes or "").split(","):
                    code = raw_code.strip()
                    if not code:
                        continue
                    known = next((c for c in _ZENPEP_ICD10 if c[0] == code), None)
                    label = known[1] if known else code
                    entry = code_counts.setdefault(code, {"code": code, "label": label, "hcp_count": 0})
                    entry["hcp_count"] += 1

            if code_counts:
                # Top 5 codes, counts scaled proportionally to actual affected HCP count
                top = sorted(code_counts.values(), key=lambda x: -x["hcp_count"])[:5]
                total_raw = sum(i["hcp_count"] for i in top) or 1
                result = []
                for item in top:
                    scaled = max(1, round(total * item["hcp_count"] / total_raw))
                    result.append(ICD10Affected(
                        code=item["code"],
                        label=item["label"],
                        hcp_count=scaled,
                    ))
                return result
    except Exception:
        pass  # view not available — use fallback

    # Fallback: proportional split across known Zenpep ICD-10 codes
    result = []
    remaining = total
    for i, (code, label) in enumerate(_ZENPEP_ICD10):
        if remaining <= 0:
            break
        if i == len(_ZENPEP_ICD10) - 1:
            count = remaining
        else:
            count = max(1, round(total * _ICD10_WEIGHTS[i]))
            remaining -= count
        result.append(ICD10Affected(code=code, label=label, hcp_count=count))
    return result


# ── STEP 2b: recommended actions — rule-based on severity ────────────────────

def _recommended_actions(severity: str, alert_type: str = "COMPETITIVE") -> List[str]:
    if alert_type in ("PAYER", "FORMULARY"):
        return ["View HCP List", "Access Resources", "Acknowledge"]
    if alert_type == "HCP_DRIFT":
        return ["Schedule Calls", "Review Later"]
    if severity in ("CRITICAL", "HIGH"):
        return ["Deploy to Field", "View Affected HCPs", "Dismiss"]
    if severity == "MEDIUM":
        return ["Monitor", "View Affected HCPs", "Dismiss"]
    return ["Monitor", "Dismiss"]


# ── STEP 4: impact score for featured ranking ─────────────────────────────────

def _impact_score(alert: AlertItem) -> tuple:
    """
    Composite rank within a severity bucket.
    Priority: most HCPs affected → widest territory reach → highest Rx risk → most recent.
    """
    hcp = alert.ai_affected_hcp_count

    reach_num = 0
    if alert.ai_territory_reach and "/" in alert.ai_territory_reach:
        try:
            reach_num = int(alert.ai_territory_reach.split("/")[0])
        except ValueError:
            pass

    rx = _RX_RISK_SCORE.get(alert.ai_rx_risk or "", 0)
    return (hcp, reach_num, rx, alert.detected_at)


# ── ML alert builder (DetectedAlert → AlertItem) ─────────────────────────────

def _build_ml_alert_item(ml: DetectedAlert, ai: dict) -> AlertItem:
    """Builds AlertItem from ML-detected alert + GPT-4o language fields."""
    return AlertItem(
        alert_id                  = ml.alert_id,
        alert_type                = ml.alert_type,
        title                     = ai.get("title") or f"{ml.detection_method} — {ml.ai_affected_hcp_count} HCPs affected",
        description               = ai.get("description") or "",
        detected_at               = ml.detected_at,
        period                    = "",
        ai_severity               = ml.severity,
        ai_detection_method       = ml.detection_method,
        ai_affected_hcp_count     = ml.ai_affected_hcp_count,
        ai_territory_reach        = ml.ai_territory_reach,
        ai_rx_risk                = ml.ai_rx_risk,
        ai_icd10_codes_affected   = [ICD10Affected(**i) for i in ml.ai_icd10_codes_affected],
        ai_prescribing_drift_note = ai.get("ai_prescribing_drift_note"),
        ai_detection_lead_weeks   = ml.ai_detection_lead_weeks,
        ai_counter_script         = ai.get("ai_counter_script"),
        ai_supporting_materials   = [SupportingMaterial(**m) for m in ai.get("ai_supporting_materials", [])],
        is_acknowledged           = False,
        is_dismissed              = False,
        is_deployed               = False,
        ai_is_detected            = True,
        recommended_actions       = _recommended_actions(ml.severity, ml.alert_type),
    )


# ── DB alert builder (ActiveAlert → AlertItem) ────────────────────────────────

def _build_alert_item(
    row: ActiveAlert,
    ai: dict,
    icd10: List[ICD10Affected],
) -> AlertItem:
    # STEP 2 — numbers from DB (pre-computed by upstream ML pipeline)
    severity_raw = (row.severity or "MEDIUM").upper()
    ai_severity  = severity_raw if severity_raw in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} else "MEDIUM"

    raw_method       = (row.detection_method or "").strip().upper()
    ai_detect_method = _DETECTION_MAP.get(raw_method, "AUTO_DETECTED")
    alert_type       = _classify_alert_type(row.title or "", raw_method)

    # STEP 3 — language from GPT-4o
    title         = ai.get("title") or row.title or ""
    description   = ai.get("description") or row.territory_name or ""
    drift_note    = ai.get("ai_prescribing_drift_note")
    counter_script= ai.get("ai_counter_script") or row.ai_counter_script
    materials     = [SupportingMaterial(**m) for m in ai.get("ai_supporting_materials", [])]

    return AlertItem(
        alert_id                  = row.alert_id,
        alert_type                = alert_type,
        title                     = title,
        description               = description,
        detected_at               = row.detected_at or "",
        period                    = "",
        ai_severity               = ai_severity,
        ai_detection_method       = ai_detect_method,
        ai_affected_hcp_count     = int(row.ai_affected_hcp_count or 0),
        ai_territory_reach        = _format_reach(row.ai_territory_reach),
        ai_rx_risk                = row.ai_rx_risk,
        ai_icd10_codes_affected   = icd10,           # STEP 2 — HCP dim table / rule-based
        ai_prescribing_drift_note = drift_note,       # STEP 3 — LLM
        ai_detection_lead_weeks   = None,
        ai_counter_script         = counter_script,   # STEP 3 — LLM
        ai_supporting_materials   = materials,        # STEP 3 — LLM
        is_acknowledged           = False,
        is_dismissed              = False,
        is_deployed               = False,
        ai_is_detected            = True,
        recommended_actions       = _recommended_actions(ai_severity, alert_type),  # STEP 2 — rule-based
    )


# ── Alert type NLP classifier ─────────────────────────────────────────────────

_PAYER_KEYWORDS    = ["payer", "formulary", "tier", "coverage", "insurance", "pa required", "prior auth"]
_HCP_DRIFT_KEYWORDS = ["awareness", "detailing frequency", "engagement", "drift", "re-education", "decline"]

def _classify_alert_type(title: str, raw_method: str) -> str:
    lower = title.lower()
    if any(k in lower for k in _PAYER_KEYWORDS):
        return "PAYER"
    if any(k in lower for k in _HCP_DRIFT_KEYWORDS):
        return "HCP_DRIFT"
    if raw_method == "ML TREND":
        return "HCP_DRIFT"
    return "COMPETITIVE"


# ── Build synthetic PAYER AlertItem from payer_access table ──────────────────

def _payer_alerts_from_db(db: Session) -> List[AlertItem]:
    """Pull ALL AI-flagged payer rows from DB — dynamic, changes as DB updates."""
    try:
        from app.models.payer_access import PayerAccess
        rows = (
            db.query(PayerAccess)
            .filter(PayerAccess.ai_alert_flag == "Yes")
            .all()
        )
        if not rows:
            rows = db.query(PayerAccess).limit(5).all()
        if not rows:
            return []

        result = []
        for row in rows:
            lives  = row.covered_lives or "0"
            hcps   = int(row.affected_hcp_count or 0) if row.affected_hcp_count else 0
            tier_c = row.tier_current or "Unknown"
            tier_p = row.tier_previous or "Unknown"
            payer  = row.payer_name or "Payer"
                # Map impact_level from DB → severity
            impact    = (row.impact_level or "").upper()
            sev_map   = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}
            ai_sev    = sev_map.get(impact, "MEDIUM")
            # recommended_actions from DB column (pipe-separated) or empty
            rec_actions = [r.strip() for r in (row.recommended_action or "").split("|") if r.strip()] or []

            result.append(AlertItem(
                alert_id              = f"PAYER-{row.plan_id}",
                alert_type            = "PAYER",
                title                 = f"Payer formulary update — {payer} Tier change" if payer else "",
                description           = (
                    f"{payer} moved our product from {tier_p} to {tier_c} effective {row.change_date}. "
                    f"Affects approximately {lives} covered lives in your territory."
                ) if row.change_date else "",
                detected_at           = row.change_date or "",
                period                = "",
                ai_severity           = ai_sev,
                ai_detection_method   = "AUTO_DETECTED",
                ai_affected_hcp_count = hcps,
                ai_territory_reach    = str(lives) if lives else "",
                ai_rx_risk            = row.impact_level or "",
                ai_icd10_codes_affected   = [],
                ai_prescribing_drift_note = row.recommended_action or "",
                ai_detection_lead_weeks   = None,
                ai_counter_script         = None,
                ai_supporting_materials   = [],
                is_acknowledged = False,
                is_dismissed    = False,
                is_deployed     = False,
                ai_is_detected  = True,
                recommended_actions = rec_actions,
            ))
        return result
    except Exception as exc:
        log.warning("Could not build payer alerts from DB: %s", exc)
        return []
        return None


def _affected_hcps_by_alert(db: Session) -> Dict[str, List[dict]]:
    """Alert_Id → affected HCP details.

    insight360_active_alerts_details is the alert→HCP bridge table
    (Alert_Id, HCP_Durable_Id); joined to the HCP dimension view for details.
    One query for all alerts, grouped in Python (only ~60 bridge rows).
    """
    try:
        sql = text("""
            SELECT
                b.Alert_Id              AS alert_id,
                b.HCP_Durable_Id        AS hcp_id,
                c.Formatted_Name        AS name,
                c.Specialty_Description AS specialty,
                c.Segment_Description   AS segment,
                c.City                  AS city,
                c.State_Province        AS state
            FROM hub_insight360.insight360_active_alerts_details b
            INNER JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting c
                ON b.HCP_Durable_Id = c.HCP_Durable_Id
        """)
        result: Dict[str, List[dict]] = {}
        for row in db.execute(sql).mappings():
            r = dict(row)
            result.setdefault(r.pop("alert_id"), []).append(r)
        return result
    except Exception as exc:
        log.warning("Affected HCP lookup failed (%s).", exc)
        return {}


def _deploy_reps_by_alert(db: Session) -> Dict[str, List[dict]]:
    """Alert_Id → field reps to deploy the alert to, with their affected HCPs.

    Chain: insight360_active_alerts_details (alert→HCP)
         → vw_account_territory_zenpep_reporting (HCP→territory, Commercial_Sales_Field_Force)
         → vw_tdim_employee_zenpep_reporting (territory→rep).
    One query for all alerts, grouped per alert per rep in Python.
    """
    try:
        sql = text("""
            SELECT
                d.Alert_Id               AS alert_id,
                c.Formatted_Name         AS hcp_name,
                at2.Territory_Durable_Id AS territory_id,
                e.Name                   AS rep_name,
                e.Email                  AS rep_email
            FROM hub_insight360.insight360_active_alerts_details d
            JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting c
              ON c.HCP_Durable_Id = d.HCP_Durable_Id
            LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting at2
              ON at2.HCP_Durable_Id = d.HCP_Durable_Id
             AND at2.sales_force = 'Commercial_Sales_Field_Force'
            LEFT JOIN hub_insight360.vw_tdim_employee_zenpep_reporting e
              ON e.Territory_Durable_Id = at2.Territory_Durable_Id
        """)
        grouped: Dict[str, Dict[tuple, dict]] = {}
        for row in db.execute(sql).mappings():
            if not row["rep_name"]:
                continue   # HCP has no assigned rep in this sales force — nothing to deploy to
            reps = grouped.setdefault(row["alert_id"], {})
            key  = (row["rep_name"], row["rep_email"], row["territory_id"])
            entry = reps.setdefault(key, {
                "rep_name":      row["rep_name"].strip(),
                "rep_email":     row["rep_email"],
                "territory_id":  row["territory_id"],
                "affected_hcps": [],
            })
            hcp_name = (row["hcp_name"] or "").strip()
            if hcp_name and hcp_name not in entry["affected_hcps"]:
                entry["affected_hcps"].append(hcp_name)
        return {aid: list(reps.values()) for aid, reps in grouped.items()}
    except Exception as exc:
        log.warning("Deploy-to-field rep lookup failed (%s).", exc)
        return {}


def _affected_hcps_by_plan(db: Session) -> Dict[str, List[dict]]:
    """Plan_Durable_Id → affected HCP details.

    insight360_payer_access_details is the payer-plan→HCP bridge table
    (Plan_Durable_Id, HCP_Durable_Id); joined to the HCP dimension view.
    """
    try:
        sql = text("""
            SELECT
                b.Plan_Durable_Id       AS plan_id,
                b.HCP_Durable_Id        AS hcp_id,
                c.Formatted_Name        AS name,
                c.Specialty_Description AS specialty,
                c.Segment_Description   AS segment,
                c.City                  AS city,
                c.State_Province        AS state
            FROM hub_insight360.insight360_payer_access_details b
            INNER JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting c
                ON b.HCP_Durable_Id = c.HCP_Durable_Id
        """)
        result: Dict[str, List[dict]] = {}
        for row in db.execute(sql).mappings():
            r = dict(row)
            result.setdefault(r.pop("plan_id"), []).append(r)
        return result
    except Exception as exc:
        log.warning("Payer affected HCP lookup failed (%s).", exc)
        return {}


# ── Public API ────────────────────────────────────────────────────────────────

def get_alerts(db: Session, territory_id: str, featured: bool = False) -> AlertListResponse:
    # ── Always get real DB count first (regardless of ML/featured path) ───────
    total_in_db = 0
    try:
        total_in_db = db.query(ActiveAlert).count()
    except Exception as e:
        log.warning("Could not count DB alerts: %s", e)

    # Alert_Id → affected HCP details (insight360_active_alerts_details bridge).
    # Built up-front: also fed into the GPT-4o enricher so each alert's language
    # is grounded in its own HCPs' specialties/segments/locations.
    affected_hcp_map = _affected_hcps_by_alert(db)

    # ── STEP 1: Pre-computed DB alerts (insight360_active_alerts) — primary.
    # Their Alert_Ids (AL-xxx) are what insight360_active_alerts_details maps
    # to HCPs, powering view_affected_hcp. ML detection is fallback only.
    rows: List[ActiveAlert] = []
    try:
        rows = (
            db.query(ActiveAlert)
            .order_by(_SEVERITY_RANK, ActiveAlert.detected_at)
            .all()
        )
    except Exception as e:
        log.warning("DB query for alerts failed (%s), trying ML pipeline", e)

    if rows:
        log.info("Using %d DB alerts", len(rows))
        alerts = [
            _build_alert_item(
                r,
                enrich(r, affected_hcp_map.get(r.alert_id, [])),
                _icd10_for_alert(db, r),
            )
            for r in rows
        ]
    else:
        # ── STEP 2: Fall back to ML pipeline (IsolationForest + LinearRegression)
        log.info("No DB alerts — running ML detection")
        ml_detected: List[DetectedAlert] = []
        try:
            ml_detected = detect_alerts(db_engine)
        except Exception as e:
            log.warning("ML pipeline failed: %s", e)
        alerts = [_build_ml_alert_item(ml, enrich(ml)) for ml in ml_detected]

    # No data → return empty sections
    if not alerts:
        log.info("No alerts from ML or DB — returning empty")

    # ── Sort: severity ascending, then detected_at descending within each group
    alerts.sort(key=lambda a: (
        _SEVERITY_ORDER.get(a.ai_severity, 4),
        -_parse_detected_at(a.detected_at).timestamp(),
    ))

    # KPI counts over ALL alerts before featured filter
    all_alerts = alerts
    critical = sum(1 for a in all_alerts if a.ai_severity == "CRITICAL")
    high     = sum(1 for a in all_alerts if a.ai_severity == "HIGH")
    medium   = sum(1 for a in all_alerts if a.ai_severity == "MEDIUM")
    drift    = sum(a.ai_affected_hcp_count for a in all_alerts if a.alert_type == "HCP_DRIFT")
    unread   = len(all_alerts)

    # Group alerts by module type
    competitive_alerts: List[CompetitiveAlertItem] = [
        CompetitiveAlertItem(
            alert_id                  = a.alert_id,
            ai_severity               = a.ai_severity,
            ai_detection_method       = a.ai_detection_method,
            detected_at               = a.detected_at,
            title                     = a.title,
            description               = a.description,
            ai_affected_hcp_count     = a.ai_affected_hcp_count,
            ai_territory_reach        = a.ai_territory_reach,
            ai_rx_risk                = a.ai_rx_risk,
            ai_icd10_codes_affected   = a.ai_icd10_codes_affected,
            ai_prescribing_drift_note = a.ai_prescribing_drift_note,
            ai_counter_script         = a.ai_counter_script,
            ai_supporting_materials   = a.ai_supporting_materials,
            recommended_actions       = a.recommended_actions,
        )
        for a in alerts if a.alert_type == "COMPETITIVE"
    ]
    payer_alerts: List[PayerAlertItem] = [
        PayerAlertItem(
            alert_id                  = a.alert_id,
            ai_severity               = a.ai_severity,
            ai_detection_method       = a.ai_detection_method,
            detected_at               = a.detected_at,
            title                     = a.title,
            description               = a.description,
            ai_affected_hcp_count     = a.ai_affected_hcp_count,
            ai_territory_reach        = a.ai_territory_reach,
            ai_rx_risk                = a.ai_rx_risk,
            ai_prescribing_drift_note = a.ai_prescribing_drift_note,
            recommended_actions       = a.recommended_actions,
        )
        for a in alerts if a.alert_type in ("PAYER", "FORMULARY")
    ]
    hcp_awareness_alerts: List[HCPAlertItem] = [
        HCPAlertItem(
            alert_id            = a.alert_id,
            ai_severity         = a.ai_severity,
            ai_detection_method = a.ai_detection_method,
            detected_at         = a.detected_at,
            title               = a.title,
            description         = a.description,
            recommended_actions = a.recommended_actions,
        )
        for a in alerts if a.alert_type == "HCP_DRIFT"
    ]

    # Payer alerts — directly from DB only, no sample fallback
    if not payer_alerts:
        payer_alerts = [
            PayerAlertItem(
                alert_id                  = a.alert_id,
                ai_severity               = a.ai_severity,
                ai_detection_method       = a.ai_detection_method,
                detected_at               = a.detected_at,
                title                     = a.title,
                description               = a.description,
                ai_affected_hcp_count     = a.ai_affected_hcp_count,
                ai_territory_reach        = a.ai_territory_reach,
                ai_rx_risk                = a.ai_rx_risk,
                ai_prescribing_drift_note = a.ai_prescribing_drift_note,
                recommended_actions       = a.recommended_actions,
            )
            for a in _payer_alerts_from_db(db)
        ]

    if featured:
        competitive_alerts   = competitive_alerts[:1]
        hcp_awareness_alerts = hcp_awareness_alerts[:1]
        payer_alerts         = payer_alerts[:1]

    # Plan_Durable_Id → affected HCP details (insight360_payer_access_details bridge)
    plan_hcp_map = _affected_hcps_by_plan(db)
    # Alert_Id → reps to deploy to (HCP → territory → rep chain)
    deploy_map = _deploy_reps_by_alert(db)

    def _payer_hcps(alert_id: str) -> List[dict]:
        """Payer alerts come from two sources with different id shapes:
        'PAYER-{plan_id}' (from insight360_payer_access) → plan bridge;
        'AL-xxx' (payer-classified insight360_active_alerts) → alerts bridge."""
        if alert_id.startswith("PAYER-"):
            return plan_hcp_map.get(alert_id[len("PAYER-"):], [])
        return affected_hcp_map.get(alert_id, [])

    # Build 3 sectioned lists, each numbered independently from alert_1
    def _build_competitive(items):
        return [
            {f"alert_{i+1}": {
                "alert_type":               "competitive",
                "alert_id":                 a.alert_id,
                "ai_severity":              a.ai_severity,
                "ai_detection_method":      a.ai_detection_method,
                "detected_at":              a.detected_at,
                "title":                    a.title,
                "description":              a.description,
                "ai_affected_hcp_count":    a.ai_affected_hcp_count,
                "ai_territory_reach":       a.ai_territory_reach,
                "ai_rx_risk":               a.ai_rx_risk,
                "ai_icd10_codes_affected":  [x.model_dump() for x in a.ai_icd10_codes_affected],
                "ai_prescribing_drift_note": a.ai_prescribing_drift_note,
                "ai_counter_script":        a.ai_counter_script,
                "ai_supporting_materials":  [m.model_dump() for m in a.ai_supporting_materials],
                "recommended_actions":      a.recommended_actions,
                "view_affected_hcp":        affected_hcp_map.get(a.alert_id, []),
                "deploy_to_field":          deploy_map.get(a.alert_id, []),
            }}
            for i, a in enumerate(items)
        ]

    def _build_payer(items):
        return [
            {f"alert_{i+1}": {
                "alert_type":               "payer",
                "alert_id":                 a.alert_id,
                "ai_severity":              a.ai_severity,
                "ai_detection_method":      a.ai_detection_method,
                "detected_at":              a.detected_at,
                "title":                    a.title,
                "description":              a.description,
                "ai_affected_hcp_count":    a.ai_affected_hcp_count,
                "ai_territory_reach":       a.ai_territory_reach,
                "ai_rx_risk":               a.ai_rx_risk,
                "ai_prescribing_drift_note": a.ai_prescribing_drift_note,
                "recommended_actions":      a.recommended_actions,
                "view_hcp_list":            [{"name": h["name"].strip()} for h in _payer_hcps(a.alert_id)],
            }}
            for i, a in enumerate(items)
        ]

    def _build_hcp(items):
        return [
            {f"alert_{i+1}": {
                "alert_type":          "hcp_awareness",
                "alert_id":            a.alert_id,
                "ai_severity":         a.ai_severity,
                "ai_detection_method": a.ai_detection_method,
                "detected_at":         a.detected_at,
                "title":               a.title,
                "description":         a.description,
                "recommended_actions": a.recommended_actions,
            }}
            for i, a in enumerate(items)
        ]

    from app.schemas.action_center import ActiveAlertSection
    return ActiveAlertListResponse(
        active_alerts=ActiveAlertSection(
            competitive_alerts   = _build_competitive(competitive_alerts),
            payer_alerts         = _build_payer(payer_alerts),
            hcp_awareness_alerts = _build_hcp(hcp_awareness_alerts),
        )
    )


def get_alert_summary(db: Session, territory_id: str) -> ActionCenterSummary:
    """Separate endpoint — returns only the KPI summary tiles, no alert cards."""
    # DB alerts primary, ML fallback — must match get_alerts so KPIs agree with the list
    alerts: List[AlertItem] = []
    try:
        affected_hcp_map = _affected_hcps_by_alert(db)
        rows = (
            db.query(ActiveAlert)
            .order_by(_SEVERITY_RANK, ActiveAlert.detected_at)
            .all()
        )
        alerts = [
            _build_alert_item(
                r,
                enrich(r, affected_hcp_map.get(r.alert_id, [])),
                _icd10_for_alert(db, r),
            )
            for r in rows
        ]
    except Exception as e:
        log.warning("DB query failed in summary: %s", e)

    if not alerts:
        try:
            ml_detected = detect_alerts(db_engine)
            if ml_detected:
                alerts = [_build_ml_alert_item(ml, enrich(ml)) for ml in ml_detected]
        except Exception as e:
            log.warning("ML pipeline failed in summary: %s", e)

    critical       = sum(1 for a in alerts if a.ai_severity == "CRITICAL")
    high           = sum(1 for a in alerts if a.ai_severity == "HIGH")
    medium         = sum(1 for a in alerts if a.ai_severity == "MEDIUM")
    drift          = sum(a.ai_affected_hcp_count for a in alerts if a.alert_type == "HCP_DRIFT")
    unread         = len(alerts)
    now_str        = datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p")

    # ai_early_detection_weeks — avg of ML-detected lead weeks, 0.0 if none
    lead_weeks_vals = [
        a.ai_detection_lead_weeks for a in alerts
        if getattr(a, "ai_detection_lead_weeks", None) is not None
    ]
    early_detection = round(sum(lead_weeks_vals) / len(lead_weeks_vals), 1) if lead_weeks_vals else 0.0

    return ActionCenterSummary(
        territory_id                = territory_id,
        period                      = "",
        last_refresh                = now_str,
        ai_critical_count           = critical,
        ai_high_priority_count      = high,
        ai_medium_priority_count    = medium,
        ai_hcp_drift_detected_count = drift,
        ai_early_detection_weeks    = early_detection,
        ai_new_unread_count         = unread,
        ai_banner_message           = "Competitive script shifts detected in your territory" if critical > 0 else "",
    )
