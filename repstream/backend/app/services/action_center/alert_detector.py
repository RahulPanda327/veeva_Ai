"""
ML detection engine for Active Alerts.

Two techniques:
  1. IsolationForest — detects sudden Rx anomalies  → ANOMALY_DETECTION alerts
  2. Linear regression slope — detects gradual drift → ML_MODEL alerts

Reads from (read-only):
  vw_tfact_prescribersales_zenpep_reporting
  vw_tdim_healthcarepractitioner_zenpep_reporting

Returns list of DetectedAlert dicts — caller decides whether to persist them.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from app.models.territory_prioritization import HealthcarePractitioner, PrescriberSales

log = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

ANOMALY_CONTAMINATION   = 0.15   # expect ~15% of HCPs to have anomalous Rx
TREND_MIN_MONTHS        = 3      # need at least 3 months to fit a trend line
TREND_NEGATIVE_SLOPE    = -2.0   # monthly Rx decline per month triggers HCP_DRIFT
DRIFT_MIN_HCP_COUNT     = 2      # ignore single-HCP micro-trends
TOTAL_TERRITORIES       = 12     # denominator for territory reach display


# ── Output structure ──────────────────────────────────────────────────────────

@dataclass
class DetectedAlert:
    alert_id:          str
    alert_type:        str          # COMPETITIVE | HCP_DRIFT
    severity:          str          # CRITICAL | HIGH | MEDIUM | LOW
    detection_method:  str          # ANOMALY_DETECTION | ML_MODEL
    title:             str
    description:       str
    detected_at:       datetime
    territory_id:      str
    period:            str
    ai_affected_hcp_count: int
    ai_territory_reach:    str      # "3/12"
    ai_rx_risk:            str      # High | Medium | Low
    ai_icd10_codes_affected: str    # JSON
    # ai_counter_script / ai_prescribing_drift_note filled by enricher
    ai_counter_script:        str = ""
    ai_prescribing_drift_note:str = ""
    ai_detection_lead_weeks:  float = 2.8
    ai_supporting_materials:  str = "[]"
    affected_hcp_ids: List[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _severity(rx_risk: str, hcp_count: int) -> str:
    if rx_risk == "High" and hcp_count >= 6:
        return "CRITICAL"
    if rx_risk == "High" or hcp_count >= 5:
        return "HIGH"
    if rx_risk == "Medium" or hcp_count >= 3:
        return "MEDIUM"
    return "LOW"


def _rx_risk(pct_change: float, hcp_count: int) -> str:
    if pct_change <= -20 or hcp_count >= 8:
        return "High"
    if pct_change <= -10 or hcp_count >= 4:
        return "Medium"
    return "Low"


def _territory_reach(affected_territories: int) -> str:
    return f"{affected_territories}/{TOTAL_TERRITORIES}"


def _icd10_from_hcps(hcps: List[HealthcarePractitioner], hcp_ids: List[str]) -> str:
    """Extract ICD-10 codes from the HCP dimension for affected HCPs."""
    hcp_map = {h.hcp_id: h for h in hcps}
    code_counts: dict[str, dict] = {}
    for hid in hcp_ids:
        hcp = hcp_map.get(hid)
        if not hcp or not hcp.icd10_codes:
            continue
        for code in hcp.icd10_codes.split(","):
            code = code.strip()
            if code:
                entry = code_counts.setdefault(code, {"code": code, "label": code, "hcp_count": 0})
                entry["hcp_count"] += 1
    return json.dumps(list(code_counts.values())[:5])  # top 5 codes


def _current_period() -> str:
    now = datetime.now()
    q = (now.month - 1) // 3 + 1
    return f"Q{q} {now.year}"


# ── Technique 1 — IsolationForest anomaly detection ──────────────────────────

def _detect_anomalies(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Per HCP, compute recent vs baseline Rx ratio.
    IsolationForest on [rx_ratio, competitor_rx_change] flags anomalous HCPs.

    Returns dataframe of anomalous HCP rows with added columns:
      anomaly_score, rx_change_pct
    """
    if sales_df.empty or len(sales_df) < 4:
        return pd.DataFrame()

    sales_df = sales_df.sort_values(["hcp_id", "period_date"])

    # Per HCP: split into baseline (older half) vs recent (newer half)
    records = []
    for hcp_id, grp in sales_df.groupby("hcp_id"):
        grp = grp.sort_values("period_date")
        mid = len(grp) // 2
        baseline_rx  = grp.iloc[:mid]["total_rx"].mean() or 0.0
        recent_rx    = grp.iloc[mid:]["total_rx"].mean() or 0.0
        baseline_comp = grp.iloc[:mid]["competitor_rx"].mean() or 0.0
        recent_comp   = grp.iloc[mid:]["competitor_rx"].mean() or 0.0

        rx_ratio      = recent_rx / (baseline_rx + 1e-6)
        comp_change   = recent_comp - baseline_comp
        rx_change_pct = (recent_rx - baseline_rx) / (baseline_rx + 1e-6) * 100

        records.append({
            "hcp_id":       hcp_id,
            "rx_ratio":     rx_ratio,
            "comp_change":  comp_change,
            "rx_change_pct":rx_change_pct,
            "recent_rx":    recent_rx,
        })

    if not records:
        return pd.DataFrame()

    feature_df = pd.DataFrame(records)
    features = feature_df[["rx_ratio", "comp_change"]].values

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    iso = IsolationForest(
        contamination=ANOMALY_CONTAMINATION,
        random_state=42,
        n_estimators=100,
    )
    predictions = iso.fit_predict(X_scaled)   # -1 = anomaly, 1 = normal
    scores      = iso.score_samples(X_scaled) # lower = more anomalous

    feature_df["is_anomaly"]     = predictions == -1
    feature_df["anomaly_score"]  = scores
    return feature_df[feature_df["is_anomaly"]]


# ── Technique 2 — Linear regression slope for gradual drift ──────────────────

def _detect_drift(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each HCP with >= TREND_MIN_MONTHS data points, fit a linear regression
    on total_rx over time. A significantly negative slope signals HCP_DRIFT.

    Returns dataframe of drifting HCP rows with added columns:
      slope, r_squared
    """
    if sales_df.empty:
        return pd.DataFrame()

    sales_df = sales_df.sort_values(["hcp_id", "period_date"])
    records  = []

    for hcp_id, grp in sales_df.groupby("hcp_id"):
        grp = grp.sort_values("period_date").reset_index(drop=True)
        if len(grp) < TREND_MIN_MONTHS:
            continue

        # X = months index (0,1,2,...), Y = total_rx
        x = np.arange(len(grp), dtype=float)
        y = grp["total_rx"].values.astype(float)

        if y.std() < 1e-6:   # flat line — no trend
            continue

        coeffs  = np.polyfit(x, y, deg=1)
        slope   = coeffs[0]

        # R² to filter out noisy fits
        y_pred  = np.polyval(coeffs, x)
        ss_res  = np.sum((y - y_pred) ** 2)
        ss_tot  = np.sum((y - y.mean()) ** 2)
        r2      = 1 - ss_res / (ss_tot + 1e-9)

        if slope < TREND_NEGATIVE_SLOPE and r2 > 0.3:
            records.append({
                "hcp_id":    hcp_id,
                "slope":     slope,
                "r_squared": r2,
                "rx_change_pct": slope / (y.mean() + 1e-6) * 100,
            })

    return pd.DataFrame(records) if records else pd.DataFrame()


# ── Main detection function ───────────────────────────────────────────────────

def detect_alerts(db: Session, territory_id: str) -> List[DetectedAlert]:
    """
    Run both ML techniques on prescriber sales for the territory.
    Returns a list of DetectedAlert objects (not yet persisted).
    """
    # ── Load data ──
    sales_rows = (
        db.query(PrescriberSales)
        .filter(PrescriberSales.territory_id == territory_id)
        .all()
    )
    hcp_rows = (
        db.query(HealthcarePractitioner)
        .filter(HealthcarePractitioner.territory_id == territory_id)
        .all()
    )

    if not sales_rows:
        log.warning("No sales data for territory %s", territory_id)
        return []

    sales_df = pd.DataFrame([{
        "hcp_id":        r.hcp_id,
        "period_date":   r.period_date,
        "total_rx":      r.total_rx or 0.0,
        "competitor_rx": r.competitor_rx or 0.0,
        "market_share":  r.market_share or 0.0,
    } for r in sales_rows])

    alerts:  List[DetectedAlert] = []
    now      = datetime.now(timezone.utc)
    period   = _current_period()

    # ── Technique 1: Anomaly Detection ──
    anomaly_df = _detect_anomalies(sales_df)
    if not anomaly_df.empty:
        affected_hcp_ids  = anomaly_df["hcp_id"].tolist()
        avg_rx_change_pct = anomaly_df["rx_change_pct"].mean()
        hcp_count         = len(affected_hcp_ids)
        rx_risk           = _rx_risk(avg_rx_change_pct, hcp_count)
        severity          = _severity(rx_risk, hcp_count)
        reach             = _territory_reach(max(1, hcp_count // 3))

        alerts.append(DetectedAlert(
            alert_id         = f"ML-ANOM-{uuid.uuid4().hex[:8].upper()}",
            alert_type       = "COMPETITIVE",
            severity         = severity,
            detection_method = "ANOMALY_DETECTION",
            title            = f"Anomalous Rx pattern detected — {hcp_count} HCPs affected",
            description      = (
                f"IsolationForest detected unusual prescribing patterns across "
                f"{hcp_count} HCPs in territory {territory_id}. "
                f"Average Rx change: {avg_rx_change_pct:+.1f}% vs baseline."
            ),
            detected_at           = now,
            territory_id          = territory_id,
            period                = period,
            ai_affected_hcp_count = hcp_count,
            ai_territory_reach    = reach,
            ai_rx_risk            = rx_risk,
            ai_icd10_codes_affected = _icd10_from_hcps(hcp_rows, affected_hcp_ids),
            ai_detection_lead_weeks = round(abs(avg_rx_change_pct) / 10, 1),
            affected_hcp_ids      = affected_hcp_ids,
        ))
        log.info("ANOMALY_DETECTION: %d HCPs flagged, rx_risk=%s, severity=%s",
                 hcp_count, rx_risk, severity)

    # ── Technique 2: Trend / Drift Detection ──
    drift_df = _detect_drift(sales_df)
    if not drift_df.empty and len(drift_df) >= DRIFT_MIN_HCP_COUNT:
        affected_hcp_ids  = drift_df["hcp_id"].tolist()
        avg_slope         = drift_df["slope"].mean()
        avg_rx_change_pct = drift_df["rx_change_pct"].mean()
        hcp_count         = len(affected_hcp_ids)
        rx_risk           = _rx_risk(avg_rx_change_pct, hcp_count)
        severity          = _severity(rx_risk, hcp_count)
        reach             = _territory_reach(max(1, hcp_count // 3))

        alerts.append(DetectedAlert(
            alert_id         = f"ML-DRIFT-{uuid.uuid4().hex[:8].upper()}",
            alert_type       = "HCP_DRIFT",
            severity         = severity,
            detection_method = "ML_MODEL",
            title            = f"Gradual Rx decline detected — {hcp_count} HCPs drifting",
            description      = (
                f"Linear regression on rolling Rx window detected a consistent decline "
                f"across {hcp_count} HCPs in territory {territory_id}. "
                f"Average monthly slope: {avg_slope:.2f} Rx/month."
            ),
            detected_at           = now,
            territory_id          = territory_id,
            period                = period,
            ai_affected_hcp_count = hcp_count,
            ai_territory_reach    = reach,
            ai_rx_risk            = rx_risk,
            ai_icd10_codes_affected = _icd10_from_hcps(hcp_rows, affected_hcp_ids),
            ai_detection_lead_weeks = round(abs(avg_slope) / 2, 1),
            affected_hcp_ids      = affected_hcp_ids,
        ))
        log.info("ML_MODEL (drift): %d HCPs flagged, slope=%.2f, severity=%s",
                 hcp_count, avg_slope, severity)

    return alerts
