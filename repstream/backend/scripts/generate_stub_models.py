"""
Stub model generator — no DB connection needed.

Run this to immediately create the .pkl files using sample data:
    cd repstream/backend
    python scripts/generate_stub_models.py

Use this when:
  - DB is not reachable
  - You just want to see the .pkl files
  - You are testing locally without Azure Synapse

For production (real DB), use: python scripts/train_ml_models.py
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
from dataclasses import dataclass, field
from typing import List

from app.services.action_center.alert_detector import (
    MODEL_DIR,
    ISO_MODEL_FILE,
    SCALER_FILE,
    ALERTS_CACHE_FILE,
    DetectedAlert,
)
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import numpy as np


def main():
    print("=" * 60)
    print("RepStream — Stub Model Generator (no DB needed)")
    print("=" * 60)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Generate and save IsolationForest + Scaler ──────────────
    print("\n[1/3] Generating IsolationForest + StandardScaler...")
    X_dummy = np.random.RandomState(42).randn(100, 3)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_dummy)
    iso = IsolationForest(contamination=0.10, random_state=42, n_estimators=100)
    iso.fit(X_scaled)

    joblib.dump(iso,    ISO_MODEL_FILE)
    joblib.dump(scaler, SCALER_FILE)
    print(f"    Saved: {ISO_MODEL_FILE.name}")
    print(f"    Saved: {SCALER_FILE.name}")

    # ── 2. Generate and save stub DetectedAlert results ────────────
    # One alert per territory per technique — matches real ML behavior
    print("\n[2/3] Generating stub DetectedAlert results (per territory)...")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    stub_alerts: List[DetectedAlert] = [
        # ── IsolationForest — 3 territories (COMPETITIVE) ──────────
        DetectedAlert(
            alert_id="ML-ANOM-STUB001", alert_type="COMPETITIVE", severity="CRITICAL",
            detection_method="ANOMALY_DETECTION", territory_id="T001", territory_name="Joliet, IL",
            detected_at=now_str, ai_affected_hcp_count=8, ai_territory_reach="3/12",
            ai_rx_risk="High",
            ai_icd10_codes_affected=[
                {"code": "K86.81", "label": "Exocrine pancreatic insufficiency", "hcp_count": 4},
                {"code": "K86.1",  "label": "Chronic pancreatitis",              "hcp_count": 2},
                {"code": "K90.3",  "label": "Pancreatic steatorrhea",            "hcp_count": 1},
                {"code": "C25.0",  "label": "Malignant neoplasm of pancreas",    "hcp_count": 1},
            ],
            ai_detection_lead_weeks=2.8, avg_rx_change_pct=-22.5,
        ),
        DetectedAlert(
            alert_id="ML-ANOM-STUB002", alert_type="COMPETITIVE", severity="CRITICAL",
            detection_method="ANOMALY_DETECTION", territory_id="T002", territory_name="Chicago North, IL",
            detected_at=now_str, ai_affected_hcp_count=11, ai_territory_reach="2/12",
            ai_rx_risk="High",
            ai_icd10_codes_affected=[
                {"code": "K86.81", "label": "Exocrine pancreatic insufficiency", "hcp_count": 7},
                {"code": "K86.1",  "label": "Chronic pancreatitis",              "hcp_count": 4},
            ],
            ai_detection_lead_weeks=3.1, avg_rx_change_pct=-18.2,
        ),
        DetectedAlert(
            alert_id="ML-ANOM-STUB003", alert_type="COMPETITIVE", severity="CRITICAL",
            detection_method="ANOMALY_DETECTION", territory_id="T003", territory_name="Springfield, IL",
            detected_at=now_str, ai_affected_hcp_count=15, ai_territory_reach="4/12",
            ai_rx_risk="High",
            ai_icd10_codes_affected=[
                {"code": "K86.81", "label": "Exocrine pancreatic insufficiency", "hcp_count": 9},
                {"code": "C25.0",  "label": "Malignant neoplasm of pancreas",    "hcp_count": 6},
            ],
            ai_detection_lead_weeks=2.5, avg_rx_change_pct=-25.0,
        ),
        # ── Linear Regression — 2 territories (HCP_DRIFT) ──────────
        DetectedAlert(
            alert_id="ML-DRFT-STUB004", alert_type="HCP_DRIFT", severity="HIGH",
            detection_method="ML_MODEL", territory_id="T001", territory_name="Joliet, IL",
            detected_at=now_str, ai_affected_hcp_count=6, ai_territory_reach="1/12",
            ai_rx_risk="Medium",
            ai_icd10_codes_affected=[
                {"code": "K86.81", "label": "Exocrine pancreatic insufficiency", "hcp_count": 4},
                {"code": "K86.1",  "label": "Chronic pancreatitis",              "hcp_count": 2},
            ],
            ai_detection_lead_weeks=2.8, avg_rx_change_pct=-14.2, avg_slope=-1.8,
        ),
        DetectedAlert(
            alert_id="ML-DRFT-STUB005", alert_type="HCP_DRIFT", severity="MEDIUM",
            detection_method="ML_MODEL", territory_id="T002", territory_name="Chicago North, IL",
            detected_at=now_str, ai_affected_hcp_count=3, ai_territory_reach="1/12",
            ai_rx_risk="Medium",
            ai_icd10_codes_affected=[],
            ai_detection_lead_weeks=None, avg_rx_change_pct=-8.5, avg_slope=-1.2,
        ),
    ]

    joblib.dump(stub_alerts, ALERTS_CACHE_FILE)
    print(f"    Saved: {ALERTS_CACHE_FILE.name}  ({len(stub_alerts)} alerts)")

    # ── 3. Print summary ───────────────────────────────────────────
    print("\n[3/3] Summary")
    print("=" * 60)
    print(f"Files saved to: {MODEL_DIR}")
    print()
    for f in [ISO_MODEL_FILE, SCALER_FILE, ALERTS_CACHE_FILE]:
        size = f"{f.stat().st_size / 1024:.1f} KB" if f.exists() else "MISSING"
        print(f"  {f.name:<30} {size}")

    print("\nDone. App will now load from these files on every startup.")
    print("To use real DB data run: python scripts/train_ml_models.py")


if __name__ == "__main__":
    main()
