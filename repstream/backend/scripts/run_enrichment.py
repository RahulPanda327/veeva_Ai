"""
Standalone enrichment runner — no PostgreSQL needed, uses SQLite.

What it does:
  1. Creates a local SQLite DB with your 8 alert rows
  2. Calls GPT-4o once per alert to generate all ai_* fields
  3. Prints the full enriched response as JSON

Usage:
    cd backend
    python scripts/run_enrichment.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override DATABASE_URL to SQLite before loading app modules
os.environ["DATABASE_URL"] = "sqlite:///./enrichment_test.db"
os.environ["HUB_SCHEMA"]   = ""   # SQLite has no schema prefix

from dotenv import load_dotenv
load_dotenv(override=False)   # .env values don't override what we set above

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, Text, DateTime
)
from sqlalchemy.orm import declarative_base, Session
from datetime import datetime, timezone

from app.config import settings
from app.services.action_center.alert_enricher import enrich_alert

# ── Build a standalone SQLite model (no schema prefix) ───────────────────────

Base = declarative_base()

class AlertRow(Base):
    __tablename__ = "insight360_active_alerts_dul"

    alert_id                  = Column(String(80), primary_key=True)
    alert_type                = Column(String(50))
    severity                  = Column(String(20))
    detection_method          = Column(String(50))
    title                     = Column(String(200))
    description               = Column(Text)
    detected_at               = Column(DateTime(timezone=True))
    territory_id              = Column(String(50))
    period                    = Column(String(20))
    ai_affected_hcp_count     = Column(Integer, default=0)
    ai_territory_reach        = Column(String(20))
    ai_rx_risk                = Column(String(20))
    ai_icd10_codes_affected   = Column(Text)
    ai_prescribing_drift_note = Column(Text)
    ai_detection_lead_weeks   = Column(Float)
    ai_counter_script         = Column(Text)
    ai_supporting_materials   = Column(Text)
    is_acknowledged           = Column(Boolean, default=False)
    is_dismissed              = Column(Boolean, default=False)
    is_deployed               = Column(Boolean, default=False)


# ── Your 8 alert rows ─────────────────────────────────────────────────────────

ALERTS = [
    dict(alert_id="AL-001", alert_type="COMPETITIVE",  severity="CRITICAL", detection_method="ANOMALY_DETECTION",
         title="Competitive script shift in cardiology segment",
         description="Competitor Creon launched new messaging around faster onset claims. Detected in 8 HCP interactions across 3 territories between Apr 26-28, 2026. Territory: JOLIET, IL.",
         territory_id="TERR-001", period="Q1 2026", ai_affected_hcp_count=8, ai_territory_reach="3/12",
         detected_at=datetime(2026, 4, 28, 8, 15, 0, tzinfo=timezone.utc)),

    dict(alert_id="AL-002", alert_type="COMPETITIVE",  severity="CRITICAL", detection_method="ANOMALY_DETECTION",
         title="Rapid Creon market share gain in Midwest district",
         description="Rapid Creon market share gain detected in ROCKFORD, IL. 11 HCPs impacted across 2 territories. Creon gained 3.2% market share in 14-day window Apr 13-27, 2026.",
         territory_id="TERR-001", period="Q1 2026", ai_affected_hcp_count=11, ai_territory_reach="2/12",
         detected_at=datetime(2026, 4, 27, 14, 30, 0, tzinfo=timezone.utc)),

    dict(alert_id="AL-003", alert_type="HCP_DRIFT",    severity="CRITICAL", detection_method="ML_MODEL",
         title="HCP detailing frequency decline correlated with Rx drop",
         description="ML trend model detected detailing frequency decline correlated with Rx drop in GARDEN GROVE, CA. 6 HCPs showing consistent reduction over 60-day rolling window.",
         territory_id="TERR-001", period="Q1 2026", ai_affected_hcp_count=6, ai_territory_reach="1/12",
         detected_at=datetime(2026, 4, 26, 9, 45, 0, tzinfo=timezone.utc)),

    dict(alert_id="AL-004", alert_type="COMPETITIVE",  severity="HIGH",     detection_method="ML_MODEL",
         title="Pancreaze rep activity spike detected in Southwest",
         description="Pancreaze rep activity spike detected in E. PHILADELPHIA, PA territory. 9 HCPs impacted. ML model detected unusual call frequency increase correlated with Rx share shifts.",
         territory_id="TERR-001", period="Q1 2026", ai_affected_hcp_count=9, ai_territory_reach="2/12",
         detected_at=datetime(2026, 4, 25, 11, 0, 0, tzinfo=timezone.utc)),

    dict(alert_id="AL-005", alert_type="COMPETITIVE",  severity="HIGH",     detection_method="ANOMALY_DETECTION",
         title="New HCP entrants prescribing generic PERT at high volume",
         description="New prescribers detected in LOUISVILLE, KY territory writing generic PERT at high volume. 5 HCPs identified across 1 territory. Potential early market share loss.",
         territory_id="TERR-001", period="Q1 2026", ai_affected_hcp_count=5, ai_territory_reach="1/12",
         detected_at=datetime(2026, 4, 24, 16, 20, 0, tzinfo=timezone.utc)),

    dict(alert_id="AL-006", alert_type="PAYER",        severity="HIGH",     detection_method="ANOMALY_DETECTION",
         title="Post-formulary change Rx erosion — Aetna plans",
         description="BlueCross Northeast moved Zenpep from Tier 2 to Tier 3 effective Apr 23, 2026. 14 HCPs impacted across 4 territories.",
         territory_id="TERR-001", period="Q1 2026", ai_affected_hcp_count=14, ai_territory_reach="4/12",
         detected_at=datetime(2026, 4, 23, 10, 10, 0, tzinfo=timezone.utc)),

    dict(alert_id="AL-007", alert_type="HCP_DRIFT",    severity="MEDIUM",   detection_method="ML_MODEL",
         title="Gradual awareness score decline in key HCP segment",
         description="ML model detected gradual awareness score decline in key HCP segment in SACRAMENTO, CA. 4 HCPs showing downward trend over 90 days.",
         territory_id="TERR-001", period="Q1 2026", ai_affected_hcp_count=4, ai_territory_reach="1/12",
         detected_at=datetime(2026, 4, 22, 13, 45, 0, tzinfo=timezone.utc)),

    dict(alert_id="AL-008", alert_type="COMPETITIVE",  severity="MEDIUM",   detection_method="ANOMALY_DETECTION",
         title="Unusual prescription timing pattern — potential competitor promotion",
         description="Unusual prescription timing pattern detected in MORGANTOWN, WV. 3 HCPs showing atypical Rx spikes mid-week consistent with competitor lunch promotion activity.",
         territory_id="TERR-001", period="Q1 2026", ai_affected_hcp_count=3, ai_territory_reach="1/12",
         detected_at=datetime(2026, 4, 21, 9, 30, 0, tzinfo=timezone.utc)),
]


def main():
    # ── Setup SQLite ──────────────────────────────────────────────────────────
    engine = create_engine("sqlite:///./enrichment_test.db", echo=False)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = Session(engine)

    for a in ALERTS:
        db.add(AlertRow(
            is_acknowledged=False,
            is_dismissed=False,
            is_deployed=False,
            **a,
        ))
    db.commit()

    print(f"\nLoaded {len(ALERTS)} alerts into SQLite")
    print(f"LLM_STUB_MODE : {settings.LLM_STUB_MODE}")
    print(f"OPENAI_MODEL  : {settings.OPENAI_MODEL}")
    print("=" * 70)

    alerts = db.query(AlertRow).order_by(AlertRow.alert_id).all()
    all_results = []

    for alert in alerts:
        print(f"\n[{alert.alert_id}]  {alert.severity}  |  {alert.detection_method}")
        print(f"  {alert.title}")
        print(f"  Calling GPT-4o...", end=" ", flush=True)

        ai = enrich_alert(db, alert)

        print("done")
        print(f"  ai_rx_risk               : {alert.ai_rx_risk}")
        print(f"  ai_detection_lead_weeks  : {alert.ai_detection_lead_weeks}")
        print(f"  ai_prescribing_drift_note: {alert.ai_prescribing_drift_note}")
        print(f"  ai_counter_script        : {alert.ai_counter_script}")
        print(f"  ai_icd10_codes_affected  : {json.loads(alert.ai_icd10_codes_affected or '[]')}")
        print(f"  ai_supporting_materials  : {json.loads(alert.ai_supporting_materials or '[]')}")
        print("-" * 70)

        all_results.append({
            "alert_id":                  alert.alert_id,
            "alert_type":                alert.alert_type,
            "severity":                  alert.severity,
            "detection_method":          alert.detection_method,
            "title":                     alert.title,
            "ai_rx_risk":                alert.ai_rx_risk,
            "ai_affected_hcp_count":     alert.ai_affected_hcp_count,
            "ai_territory_reach":        alert.ai_territory_reach,
            "ai_detection_lead_weeks":   alert.ai_detection_lead_weeks,
            "ai_prescribing_drift_note": alert.ai_prescribing_drift_note,
            "ai_counter_script":         alert.ai_counter_script,
            "ai_icd10_codes_affected":   json.loads(alert.ai_icd10_codes_affected or "[]"),
            "ai_supporting_materials":   json.loads(alert.ai_supporting_materials or "[]"),
        })

    db.close()

    print("\n\n=== FULL JSON RESPONSE ===\n")
    print(json.dumps(all_results, indent=2))
    print(f"\nDone — {len(all_results)} alerts enriched.")


if __name__ == "__main__":
    main()
