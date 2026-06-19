"""
Alert pipeline — orchestrates the full detection → enrichment → persist flow.

  Step 1: alert_detector.py  — ML (IsolationForest + LinearRegression)
  Step 2: alert_enricher.py  — one GPT-4o call per alert
  Step 3: persist            — write enriched alert to insight360_active_alerts
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.active_alerts import ActiveAlert
from app.services.action_center.alert_detector import DetectedAlert, detect_alerts
from app.services.action_center.alert_enricher import enrich_alert

log = logging.getLogger(__name__)


def _to_orm(d: DetectedAlert) -> ActiveAlert:
    """Convert a DetectedAlert dataclass into an ORM row (not yet committed)."""
    return ActiveAlert(
        alert_id         = d.alert_id,
        alert_type       = d.alert_type,
        severity         = d.severity,
        detection_method = d.detection_method,
        title            = d.title,
        description      = d.description,
        detected_at      = d.detected_at,
        territory_id     = d.territory_id,
        period           = d.period,
        ai_affected_hcp_count   = d.ai_affected_hcp_count,
        ai_territory_reach      = d.ai_territory_reach,
        ai_rx_risk              = d.ai_rx_risk,
        ai_icd10_codes_affected = d.ai_icd10_codes_affected,
        ai_detection_lead_weeks = d.ai_detection_lead_weeks,
        ai_counter_script       = d.ai_counter_script,
        ai_prescribing_drift_note = d.ai_prescribing_drift_note,
        ai_supporting_materials = d.ai_supporting_materials,
        is_acknowledged = False,
        is_dismissed    = False,
        is_deployed     = False,
    )


def run_pipeline(db: Session, territory_id: str) -> List[dict]:
    """
    Full pipeline for a territory:
      1. ML detection on prescriber sales data
      2. GPT-4o enrichment (one call per detected alert)
      3. Persist to insight360_active_alerts

    Returns summary of generated alerts.
    """
    log.info("Pipeline started for territory %s", territory_id)

    # ── Step 1: ML Detection ──────────────────────────────────────────────────
    detected: List[DetectedAlert] = detect_alerts(db, territory_id)

    if not detected:
        log.info("No alerts detected for %s", territory_id)
        return []

    log.info("%d alert(s) detected, starting enrichment", len(detected))

    results = []
    for d in detected:
        # ── Step 2: LLM Enrichment ────────────────────────────────────────────
        orm_alert = _to_orm(d)
        db.add(orm_alert)
        db.flush()   # get the row into DB so enricher can update it

        try:
            ai_fields = enrich_alert(db, orm_alert)
            log.info("Enriched alert %s", orm_alert.alert_id)
        except Exception as exc:
            log.error("Enrichment failed for %s: %s", orm_alert.alert_id, exc)
            ai_fields = {}

        # ── Step 3: Persist ───────────────────────────────────────────────────
        db.commit()

        results.append({
            "alert_id":        orm_alert.alert_id,
            "alert_type":      orm_alert.alert_type,
            "severity":        orm_alert.severity,
            "detection_method":orm_alert.detection_method,
            "ai_affected_hcp_count": orm_alert.ai_affected_hcp_count,
            "ai_rx_risk":      orm_alert.ai_rx_risk,
            "ai_counter_script_preview": (
                (orm_alert.ai_counter_script or "")[:100] + "..."
                if orm_alert.ai_counter_script else ""
            ),
        })

    log.info("Pipeline complete — %d alert(s) persisted", len(results))
    return results
