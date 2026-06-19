"""Active Alerts service — reads hub_insight360.insight360_active_alerts from Azure Synapse."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.active_alerts import ActiveAlert
from app.services.action_center.alert_enricher import enrich
from app.schemas.action_center import (
    ActionCenterSummary,
    AlertItem,
    AlertListResponse,
    ICD10Affected,
    SupportingMaterial,
)

# Severity sort: CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3
_SEVERITY_RANK = case(
    (ActiveAlert.severity == "CRITICAL", 0),
    (ActiveAlert.severity == "HIGH",     1),
    (ActiveAlert.severity == "MEDIUM",   2),
    else_=3,
)

_RX_RISK_SCORE: Dict[str, int] = {"High": 3, "Medium": 2, "Low": 1}


def _impact_score(alert: AlertItem) -> tuple:
    """
    Composite rank within a severity bucket — higher tuple = more urgent.
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

    # detected_at is a string "2026-04-28 08:15" — lexicographic sort works fine
    return (hcp, reach_num, rx, alert.detected_at)

# Map live DB values → frontend enum values
_DETECTION_MAP = {
    "ANOMALY DETECTION": "ANOMALY_DETECTION",
    "ML TREND":          "ML_MODEL",
    "ANOMALY":           "ANOMALY_DETECTION",
}

# Map "3 of 12 territories" → "3/12"
def _format_reach(raw: str | None) -> str:
    if not raw:
        return "—"
    # "3 of 12 territories" → "3/12"
    parts = raw.split(" of ")
    if len(parts) == 2:
        num  = parts[0].strip()
        denom = parts[1].replace("territories", "").replace("territory", "").strip()
        return f"{num}/{denom}"
    return raw


def _build_alert_item(row: ActiveAlert, ai: dict) -> AlertItem:
    severity_raw = (row.severity or "MEDIUM").upper()
    valid_sev    = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    ai_severity  = severity_raw if severity_raw in valid_sev else "MEDIUM"

    raw_method      = (row.detection_method or "").strip().upper()
    ai_detect_method = _DETECTION_MAP.get(raw_method, "AUTO_DETECTED")

    # alert_type derived from detection_method for UI routing
    alert_type = "HCP_DRIFT" if raw_method == "ML TREND" else "COMPETITIVE"

    # action buttons come from Recommended_Actions column ("A | B | C")
    action_buttons = [b.strip() for b in (row.recommended_actions or "").split("|") if b.strip()]

    return AlertItem(
        alert_id              = row.alert_id,
        alert_type            = alert_type,
        title                 = row.title or "",
        description           = ai.get("description") or row.territory_name or "",
        detected_at           = row.detected_at or "",
        period                = "Q1 2026",
        ai_severity           = ai_severity,
        ai_detection_method   = ai_detect_method,
        ai_affected_hcp_count = int(row.ai_affected_hcp_count or 0),
        ai_territory_reach    = _format_reach(row.ai_territory_reach),
        ai_rx_risk            = row.ai_rx_risk,
        ai_icd10_codes_affected   = [ICD10Affected(**i) for i in ai.get("ai_icd10_codes_affected", [])],
        ai_prescribing_drift_note = ai.get("ai_prescribing_drift_note"),
        ai_detection_lead_weeks   = None,
        ai_counter_script         = row.ai_counter_script,
        ai_supporting_materials   = [SupportingMaterial(**m) for m in ai.get("ai_supporting_materials", [])],
        is_acknowledged           = False,
        is_dismissed              = False,
        is_deployed               = False,
        ai_is_detected            = True,
        recommended_actions       = action_buttons,
    )


def get_alerts(db: Session, territory_id: str, featured: bool = False) -> AlertListResponse:
    rows: List[ActiveAlert] = (
        db.query(ActiveAlert)
        .order_by(_SEVERITY_RANK, ActiveAlert.detected_at)
        .all()
    )

    alerts = [_build_alert_item(r, enrich(r)) for r in rows]

    if featured:
        # Within each severity bucket, pick the single most impactful alert:
        #   rank by (hcp_count DESC, territory_reach DESC, rx_risk DESC, detected_at DESC)
        buckets: Dict[str, List[AlertItem]] = {}
        for a in alerts:
            buckets.setdefault(a.ai_severity, []).append(a)

        featured_alerts = []
        for sev in ("CRITICAL", "HIGH", "MEDIUM"):
            group = buckets.get(sev, [])
            if group:
                best = max(group, key=_impact_score)
                featured_alerts.append(best)
        alerts = featured_alerts

    critical = sum(1 for a in alerts if a.ai_severity == "CRITICAL")
    high     = sum(1 for a in alerts if a.ai_severity == "HIGH")
    medium   = sum(1 for a in alerts if a.ai_severity == "MEDIUM")
    drift    = sum(a.ai_affected_hcp_count for a in alerts if a.alert_type == "HCP_DRIFT")
    unread   = len(alerts)

    now_str = datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p")

    summary = ActionCenterSummary(
        territory_id          = territory_id,
        period                = "Q1 2026 (Jan - Mar)",
        last_refresh          = now_str,
        ai_critical_count     = critical,
        ai_high_priority_count= high,
        ai_medium_priority_count = medium,
        ai_hcp_drift_detected_count = drift,
        ai_early_detection_weeks = 2.8,
        ai_new_unread_count   = unread,
        ai_banner_message     = "Competitive script shifts detected in your territory" if critical > 0 else None,
    )

    return AlertListResponse(summary=summary, alerts=alerts, total=len(alerts))
