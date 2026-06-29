"""
One-time ML training script.

Run this once to generate the .pkl model files:
    cd repstream/backend
    python scripts/train_ml_models.py

Generated files (repstream/backend/models/):
    isolation_forest.pkl  — trained IsolationForest model
    scaler.pkl            — fitted StandardScaler
    detected_alerts.pkl   — final DetectedAlert results

After running this, the app will load from these files instantly
on every startup — no retraining, no DB query for ML.
"""
import sys
from pathlib import Path

# Allow imports from app/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.services.action_center.alert_detector import (
    MODEL_DIR,
    ISO_MODEL_FILE,
    SCALER_FILE,
    ALERTS_CACHE_FILE,
    detect_alerts,
)

def main():
    print("=" * 60)
    print("RepStream — ML Model Training")
    print("=" * 60)

    # Delete existing files to force fresh training
    for f in [ISO_MODEL_FILE, SCALER_FILE, ALERTS_CACHE_FILE]:
        if f.exists():
            f.unlink()
            print(f"Removed old file: {f.name}")

    print("\nConnecting to DB and loading Rx data...")
    print("Training IsolationForest + LinearRegression...\n")

    alerts = detect_alerts(engine)

    print("\n" + "=" * 60)
    print(f"Training complete — {len(alerts)} alerts detected")
    print("=" * 60)
    print(f"\nFiles saved to: {MODEL_DIR}/")
    for f in [ISO_MODEL_FILE, SCALER_FILE, ALERTS_CACHE_FILE]:
        size = f"{f.stat().st_size / 1024:.1f} KB" if f.exists() else "missing"
        print(f"  {f.name:<30} {size}")

    print("\nApp will now load from these files on every startup.")

if __name__ == "__main__":
    main()
