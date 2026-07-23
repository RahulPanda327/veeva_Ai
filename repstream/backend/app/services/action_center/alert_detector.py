"""
ML Detection Engine — Active Alerts

Full pipeline on real Azure Synapse Rx data:

  FEATURE ENGINEERING
    Per HCP per month:
      zenpep_rx     = SUM(Total_Rx_Count) where Brand_Name = 'ZENPEP'
      competitor_rx = SUM(Total_Rx_Count) where Brand_Name IN ('CREON','PANCREAZE')

    Derived features:
      rx_ratio         = recent_zenpep / baseline_zenpep  (sudden drop = < 1)
      comp_change      = recent_competitor - baseline_competitor  (competitor gaining)
      rx_change_pct    = % change in Zenpep Rx
      market_share_chg = recent_share - baseline_share

  TECHNIQUE 1 — IsolationForest
    Input : [rx_ratio, comp_change]  → StandardScaler normalized
    Output: HCPs where score < threshold = anomalous (sudden Rx shift)
    Alert : ANOMALY_DETECTION / COMPETITIVE

  TECHNIQUE 2 — Linear Regression (numpy.polyfit)
    Input : X = month index, Y = zenpep_rx per month
    Output: HCPs where slope < -1.0 AND R² > 0.3 = consistent gradual drift
    Alert : ML_MODEL / HCP_DRIFT

  ICD-10 from HCP Dimension Table
    Map Specialty_Group → relevant ICD-10 codes
    Scale counts to actual affected_hcp_count

Results cached 1 hour — avoids re-running on every API call.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

log = logging.getLogger(__name__)

# ── Model persistence paths ───────────────────────────────────────────────────
# Stored at: repstream/backend/models/
MODEL_DIR          = Path(__file__).resolve().parents[3] / "models"
ISO_MODEL_FILE     = MODEL_DIR / "isolation_forest.pkl"
SCALER_FILE        = MODEL_DIR / "scaler.pkl"
ALERTS_CACHE_FILE  = MODEL_DIR / "detected_alerts.pkl"

# ── Thresholds ────────────────────────────────────────────────────────────────
ANOMALY_CONTAMINATION = 0.10   # expect ~10% anomalous HCPs
TREND_MIN_MONTHS      = 3      # need at least 3 months of data per HCP
TREND_NEGATIVE_SLOPE  = -1.0   # Rx/month decline threshold
DRIFT_MIN_HCP_COUNT   = 2
TOTAL_TERRITORIES     = 12
CACHE_TTL_SECONDS     = 3600   # 1 hour

# ── In-memory cache ───────────────────────────────────────────────────────────
_ML_CACHE: Dict[str, Any] = {}   # key → {"ts": float, "data": list}


# ── Output structure ──────────────────────────────────────────────────────────
@dataclass
class DetectedAlert:
    alert_id:             str
    alert_type:           str     # COMPETITIVE | HCP_DRIFT
    severity:             str     # CRITICAL | HIGH | MEDIUM | LOW
    detection_method:     str     # ANOMALY_DETECTION | ML_MODEL
    territory_id:         str
    territory_name:       str
    detected_at:          str
    ai_affected_hcp_count: int
    ai_territory_reach:   str     # "3/12"
    ai_rx_risk:           str     # High | Medium | Low
    ai_icd10_codes_affected: List[dict]
    ai_detection_lead_weeks: float
    avg_rx_change_pct:    float
    avg_slope:            float = 0.0
    affected_hcp_ids:     List[int] = field(default_factory=list)


# ── Specialty → ICD-10 mapping ────────────────────────────────────────────────
_SPECIALTY_ICD10: Dict[str, List[tuple]] = {
    "GASTROENTEROLOGY": [
        ("K86.81", "Exocrine pancreatic insufficiency"),
        ("K86.1",  "Chronic pancreatitis"),
        ("K90.3",  "Pancreatic steatorrhea"),
    ],
    "MEDICAL ONCOLOGY": [
        ("C25.0",  "Malignant neoplasm of head of pancreas"),
        ("C25.9",  "Malignant neoplasm of pancreas, unspecified"),
        ("K86.81", "Exocrine pancreatic insufficiency"),
    ],
    "PEDIATRICS": [
        ("K86.81", "Exocrine pancreatic insufficiency"),
        ("K90.3",  "Pancreatic steatorrhea"),
        ("K86.1",  "Chronic pancreatitis"),
    ],
    "INTERNAL MEDICINE": [
        ("K86.81", "Exocrine pancreatic insufficiency"),
        ("K86.1",  "Chronic pancreatitis"),
    ],
    "SURGERY": [
        ("K86.81", "Exocrine pancreatic insufficiency"),
        ("C25.0",  "Malignant neoplasm of head of pancreas"),
    ],
}
_DEFAULT_ICD10 = [
    ("K86.81", "Exocrine pancreatic insufficiency"),
    ("K86.1",  "Chronic pancreatitis"),
    ("K90.3",  "Pancreatic steatorrhea"),
    ("C25.0",  "Malignant neoplasm of head of pancreas"),
    ("K86.0",  "Alcohol-induced chronic pancreatitis"),
]
_ICD10_FALLBACK_WEIGHTS = [0.45, 0.30, 0.15, 0.07, 0.03]


# ── SQL helpers ───────────────────────────────────────────────────────────────

def _load_pivot(engine) -> pd.DataFrame:
    """
    Aggregate 3.3M Rx rows into per-HCP per-month pivot.
    Returns columns: hcp_id, year, month, zenpep_rx, competitor_rx, territory_raw
    Only Zenpep prescribers in last 12 months.
    """
    sql = text("""
        SELECT
            s.HCP_Durable_Id                              AS hcp_id,
            YEAR(s.Month_Ending_Date)                     AS yr,
            MONTH(s.Month_Ending_Date)                    AS mo,
            SUM(CASE WHEN s.Brand_Name = 'ZENPEP'
                     THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) AS zenpep_rx,
            SUM(CASE WHEN s.Brand_Name IN ('CREON','PANCREAZE')
                     THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) AS competitor_rx,
            MAX(s.sf_terr_pk_gi)                          AS territory_raw
        FROM hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul s
        WHERE CAST(s.Month_Ending_Date AS DATE) >= CAST(DATEADD(MONTH, -12, GETDATE()) AS DATE)
          AND s.HCP_Durable_Id IS NOT NULL
        GROUP BY s.HCP_Durable_Id,
                 YEAR(s.Month_Ending_Date),
                 MONTH(s.Month_Ending_Date)
        HAVING SUM(CASE WHEN s.Brand_Name = 'ZENPEP'
                        THEN ISNULL(s.Total_Rx_Count, 0) ELSE 0 END) > 0
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    df["month_key"] = df["yr"].astype(str) + "-" + df["mo"].astype(str).str.zfill(2)
    df = df.sort_values(["hcp_id", "month_key"]).reset_index(drop=True)
    return df


def _load_hcp_info(engine, hcp_ids: List[int]) -> Dict[int, dict]:
    if not hcp_ids:
        return {}
    ids_str = ",".join(str(i) for i in hcp_ids[:1000])
    sql = text(f"""
        SELECT HCP_Durable_Id, Full_Name, Specialty_Description, Speciality_Group,
               City, State_Province, gi_territory_name
        FROM hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul
        WHERE HCP_Durable_Id IN ({ids_str})
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return {
        int(r[0]): {
            "full_name":       r[1],
            "specialty":       r[2],
            "specialty_group": (r[3] or "").upper(),
            "city":            r[4],
            "state":           r[5],
            "territory_name":  r[6],
        }
        for r in rows
    }


def _extract_territory_id(raw: str) -> str:
    """'Commercial_Sales_Field_Force|A0E000000013007' → 'A0E000000013007'"""
    if not raw:
        return "UNKNOWN"
    parts = str(raw).split("|")
    return parts[-1].strip()


# ── ICD-10 builder ────────────────────────────────────────────────────────────

def _build_icd10(hcp_info: Dict[int, dict], hcp_ids: List[int], total: int) -> List[dict]:
    code_counts: Dict[str, dict] = {}
    for hid in hcp_ids:
        info = hcp_info.get(hid, {})
        spec = info.get("specialty_group", "")
        codes = _SPECIALTY_ICD10.get(spec, _DEFAULT_ICD10)
        for code, label in codes[:2]:
            e = code_counts.setdefault(code, {"code": code, "label": label, "hcp_count": 0})
            e["hcp_count"] += 1

    if not code_counts:
        result, remaining = [], total
        for i, (code, label) in enumerate(_DEFAULT_ICD10):
            if remaining <= 0:
                break
            count = remaining if i == len(_DEFAULT_ICD10) - 1 \
                    else max(1, round(total * _ICD10_FALLBACK_WEIGHTS[i]))
            remaining -= count
            result.append({"code": code, "label": label, "hcp_count": count})
        return result

    top = sorted(code_counts.values(), key=lambda x: -x["hcp_count"])[:5]
    total_raw = sum(i["hcp_count"] for i in top) or 1
    for item in top:
        item["hcp_count"] = max(1, round(total * item["hcp_count"] / total_raw))
    return top


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _rx_risk(pct_change: float, hcp_count: int) -> str:
    if pct_change <= -20 or hcp_count >= 8:
        return "High"
    if pct_change <= -10 or hcp_count >= 4:
        return "Medium"
    return "Low"


def _severity(rx_risk: str, hcp_count: int) -> str:
    if rx_risk == "High" and hcp_count >= 6:
        return "CRITICAL"
    if rx_risk == "High" or hcp_count >= 5:
        return "HIGH"
    if rx_risk == "Medium" or hcp_count >= 3:
        return "MEDIUM"
    return "LOW"


def _alert_id(prefix: str, territory: str) -> str:
    key = f"{prefix}-{territory}-{datetime.now().strftime('%Y%m%d')}"
    return f"ML-{prefix[:4].upper()}-{hashlib.md5(key.encode()).hexdigest()[:8].upper()}"


def _territory_reach(n_territories: int) -> str:
    return f"{min(n_territories, TOTAL_TERRITORIES)}/{TOTAL_TERRITORIES}"


# ── Technique 1 — IsolationForest ─────────────────────────────────────────────

def _detect_anomalies(pivot: pd.DataFrame) -> pd.DataFrame:
    """
    FEATURE ENGINEERING per HCP:
      rx_ratio      = avg recent Zenpep / avg baseline Zenpep
      comp_change   = avg recent competitor - avg baseline competitor
      rx_change_pct = % Zenpep Rx change

    IsolationForest flags HCPs where these features are outliers.
    Returns only HCPs with actual Zenpep decline (rx_change_pct < 0).
    """
    records = []
    for hcp_id, grp in pivot.groupby("hcp_id"):
        grp = grp.sort_values("month_key")
        mid = max(1, len(grp) // 2)

        baseline_zen  = grp.iloc[:mid]["zenpep_rx"].mean() + 1e-6
        recent_zen    = grp.iloc[mid:]["zenpep_rx"].mean()
        baseline_comp = grp.iloc[:mid]["competitor_rx"].mean()
        recent_comp   = grp.iloc[mid:]["competitor_rx"].mean()

        rx_ratio      = recent_zen / baseline_zen
        comp_change   = recent_comp - baseline_comp
        rx_change_pct = (recent_zen - baseline_zen) / baseline_zen * 100

        # Market share change
        total_baseline = baseline_zen + (grp.iloc[:mid]["competitor_rx"].mean() + 1e-6)
        total_recent   = recent_zen   + (recent_comp + 1e-6)
        share_baseline = baseline_zen / total_baseline
        share_recent   = recent_zen   / total_recent
        share_change   = share_recent - share_baseline

        records.append({
            "hcp_id":        hcp_id,
            "rx_ratio":      rx_ratio,
            "comp_change":   comp_change,
            "share_change":  share_change,
            "rx_change_pct": rx_change_pct,
            "territory_raw": grp["territory_raw"].iloc[-1],
        })

    if len(records) < 10:
        return pd.DataFrame()

    feature_df = pd.DataFrame(records)
    X = feature_df[["rx_ratio", "comp_change", "share_change"]].values

    if ISO_MODEL_FILE.exists() and SCALER_FILE.exists():
        log.info("Loading IsolationForest + scaler from saved files")
        iso    = joblib.load(ISO_MODEL_FILE)
        scaler = joblib.load(SCALER_FILE)
        X_scaled = scaler.transform(X)
        preds    = iso.predict(X_scaled)
        scores   = iso.score_samples(X_scaled)
    else:
        log.info("Training IsolationForest for the first time — saving to %s", MODEL_DIR)
        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        iso = IsolationForest(
            contamination=ANOMALY_CONTAMINATION,
            random_state=42,
            n_estimators=100,
        )
        preds  = iso.fit_predict(X_scaled)
        scores = iso.score_samples(X_scaled)
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(iso,    ISO_MODEL_FILE)
        joblib.dump(scaler, SCALER_FILE)
        log.info("Saved: %s, %s", ISO_MODEL_FILE, SCALER_FILE)

    feature_df["is_anomaly"]    = preds == -1
    feature_df["anomaly_score"] = scores

    anomalies = feature_df[feature_df["is_anomaly"] & (feature_df["rx_change_pct"] < 0)]
    return anomalies.sort_values("anomaly_score")  # most anomalous first


# ── Technique 2 — Linear Regression ──────────────────────────────────────────

def _detect_drift(pivot: pd.DataFrame) -> pd.DataFrame:
    """
    FEATURE ENGINEERING per HCP:
      X = month index [0,1,2,...], Y = zenpep_rx
      slope  = LinearRegression coefficient (Rx/month rate of change)
      R²     = fit quality (filters noise)

    Only HCPs with slope < TREND_NEGATIVE_SLOPE AND R² > 0.3 are flagged.
    """
    records = []
    for hcp_id, grp in pivot.groupby("hcp_id"):
        grp = grp.sort_values("month_key").reset_index(drop=True)
        if len(grp) < TREND_MIN_MONTHS:
            continue

        x = np.arange(len(grp), dtype=float)
        y = grp["zenpep_rx"].values.astype(float)

        if y.std() < 1e-6:
            continue

        coeffs  = np.polyfit(x, y, deg=1)
        slope   = coeffs[0]

        y_pred  = np.polyval(coeffs, x)
        ss_res  = np.sum((y - y_pred) ** 2)
        ss_tot  = np.sum((y - y.mean()) ** 2)
        r2      = 1.0 - ss_res / (ss_tot + 1e-9)

        if slope < TREND_NEGATIVE_SLOPE and r2 > 0.3:
            records.append({
                "hcp_id":        hcp_id,
                "slope":         slope,
                "r_squared":     r2,
                "rx_change_pct": slope / (y.mean() + 1e-6) * 100,
                "territory_raw": grp["territory_raw"].iloc[-1],
            })

    return pd.DataFrame(records) if records else pd.DataFrame()


# ── Main detection ────────────────────────────────────────────────────────────

def detect_alerts(engine) -> List[DetectedAlert]:
    """
    Run full ML pipeline on real Rx data.
    First run: trains models, saves to models/*.pkl files.
    Subsequent runs: loads from saved files instantly.
    In-memory cache (1 hour) avoids even the file load on repeated calls.
    """
    cache_key = "ml_alerts"
    cached = _ML_CACHE.get(cache_key)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL_SECONDS:
        log.info("ML cache hit — returning %d cached alerts", len(cached["data"]))
        return cached["data"]

    # Load from saved .pkl file if it exists (skips DB query + retraining)
    if ALERTS_CACHE_FILE.exists():
        log.info("Loading detected alerts from %s", ALERTS_CACHE_FILE)
        alerts = joblib.load(ALERTS_CACHE_FILE)
        _ML_CACHE[cache_key] = {"ts": time.time(), "data": alerts}
        return alerts

    log.info("First run — training ML pipeline on Rx data...")

    try:
        pivot = _load_pivot(engine)
    except Exception as e:
        log.error("Failed to load Rx data: %s", e)
        return []

    if pivot.empty:
        log.warning("No Rx data found")
        return []

    log.info("Loaded %d HCP-month rows for %d HCPs", len(pivot), pivot["hcp_id"].nunique())

    alerts: List[DetectedAlert] = []
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    # ── Technique 1: IsolationForest — one alert per territory ───────────────
    anomaly_df = _detect_anomalies(pivot)
    if not anomaly_df.empty:
        all_hcp_ids = anomaly_df["hcp_id"].tolist()
        hcp_info    = _load_hcp_info(engine, all_hcp_ids)

        anomaly_df["territory_id"] = anomaly_df["territory_raw"].apply(_extract_territory_id)
        for territory_id, grp in anomaly_df.groupby("territory_id"):
            hcp_ids       = grp["hcp_id"].tolist()
            hcp_count     = len(hcp_ids)
            avg_rx_change = float(grp["rx_change_pct"].mean())
            rx_risk       = _rx_risk(avg_rx_change, hcp_count)
            sev           = _severity(rx_risk, hcp_count)
            territory_name = hcp_info.get(hcp_ids[0], {}).get("territory_name") or territory_id
            reach          = _territory_reach(anomaly_df["territory_id"].nunique())
            icd10          = _build_icd10(hcp_info, hcp_ids[:100], hcp_count)

            alerts.append(DetectedAlert(
                alert_id               = _alert_id("ANOM", territory_id),
                alert_type             = "COMPETITIVE",
                severity               = sev,
                detection_method       = "ANOMALY_DETECTION",
                territory_id           = territory_id,
                territory_name         = territory_name,
                detected_at            = now_str,
                ai_affected_hcp_count  = hcp_count,
                ai_territory_reach     = reach,
                ai_rx_risk             = rx_risk,
                ai_icd10_codes_affected= icd10,
                ai_detection_lead_weeks= round(abs(avg_rx_change) / 10, 1),
                avg_rx_change_pct      = avg_rx_change,
                affected_hcp_ids       = hcp_ids,
            ))
            log.info("IsolationForest [%s]: %d HCPs | rx_change=%.1f%% | severity=%s",
                     territory_id, hcp_count, avg_rx_change, sev)

    # ── Technique 2: Linear Regression — one alert per territory ─────────────
    drift_df = _detect_drift(pivot)
    if not drift_df.empty and len(drift_df) >= DRIFT_MIN_HCP_COUNT:
        all_hcp_ids = drift_df["hcp_id"].tolist()
        hcp_info    = _load_hcp_info(engine, all_hcp_ids)

        drift_df["territory_id"] = drift_df["territory_raw"].apply(_extract_territory_id)
        for territory_id, grp in drift_df.groupby("territory_id"):
            hcp_ids       = grp["hcp_id"].tolist()
            if len(hcp_ids) < DRIFT_MIN_HCP_COUNT:
                continue
            hcp_count     = len(hcp_ids)
            avg_slope     = float(grp["slope"].mean())
            avg_rx_change = float(grp["rx_change_pct"].mean())
            rx_risk       = _rx_risk(avg_rx_change, hcp_count)
            sev           = _severity(rx_risk, hcp_count)
            territory_name = hcp_info.get(hcp_ids[0], {}).get("territory_name") or territory_id
            reach          = _territory_reach(drift_df["territory_id"].nunique())
            icd10          = _build_icd10(hcp_info, hcp_ids[:100], hcp_count)

            alerts.append(DetectedAlert(
                alert_id               = _alert_id("DRFT", territory_id),
                alert_type             = "HCP_DRIFT",
                severity               = sev,
                detection_method       = "ML_MODEL",
                territory_id           = territory_id,
                territory_name         = territory_name,
                detected_at            = now_str,
                ai_affected_hcp_count  = hcp_count,
                ai_territory_reach     = reach,
                ai_rx_risk             = rx_risk,
                ai_icd10_codes_affected= icd10,
                ai_detection_lead_weeks= round(abs(avg_slope) / 2, 1),
                avg_rx_change_pct      = avg_rx_change,
                avg_slope              = avg_slope,
                affected_hcp_ids       = hcp_ids,
            ))
            log.info("LinearRegression [%s]: %d drifting HCPs | slope=%.2f | severity=%s",
                     territory_id, hcp_count, avg_slope, sev)

    # Save results to file — subsequent runs load instantly without retraining
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(alerts, ALERTS_CACHE_FILE)
    log.info("Saved detected alerts → %s", ALERTS_CACHE_FILE)

    _ML_CACHE[cache_key] = {"ts": time.time(), "data": alerts}
    log.info("ML pipeline complete — %d alerts detected", len(alerts))
    return alerts
