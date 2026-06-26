"""Action Center — Launch & Market Defense router."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.auth import get_current_rep, RepIdentity
from app.models.active_alerts import ActiveAlert
from app.schemas.action_center import (
    AlertListResponse,
    HCPAwarenessResponse,
    CompetitiveIntelResponse,
    PayerAccessResponse,
)
from app.services.action_center.alert_engine import get_alerts
from app.services.action_center.alert_enricher import enrich_alert
from app.services.action_center.alert_pipeline import run_pipeline
from app.services.action_center.hcp_awareness_svc import get_hcp_awareness
from app.services.action_center.competitive_intel_svc import get_competitive_intel
from app.services.action_center.payer_access_svc import get_payer_access

router = APIRouter(prefix="/action-center", tags=["action-center"])


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="Active Alerts — full list or featured 3",
    description="""
Returns active ML-detected alerts for the rep's territory.

## Query Parameters
| Param | Type | Default | Description |
|---|---|---|---|
| `featured` | bool | `false` | `false` = all alerts · `true` = top 1 per severity (max 3 cards) |

## Response Fields
- **`total`** — alerts returned in this call (affected by `featured` flag)
- **`total_in_db`** — actual row count in `insight360_active_alerts` (always real DB count)
- **`summary`** — KPI tile values + yellow banner data
- **`alerts[]`** — alert cards sorted by severity (CRITICAL → HIGH → MEDIUM)

## Alert Types
| `alert_type` | UI Label | Detection |
|---|---|---|
| `COMPETITIVE` | Competitive threat | IsolationForest anomaly |
| `HCP_DRIFT` | HCP gradual drift | Linear Regression slope |
| `PAYER` | Formulary / payer change | Auto-detected |
| `FORMULARY` | Formulary review | Auto-detected |

## Detection Methods
| `ai_detection_method` | Badge shown | Source |
|---|---|---|
| `ANOMALY_DETECTION` | ANOMALY DETECTION (purple) | IsolationForest on Rx data |
| `ML_MODEL` | ML PREDICTION (blue) | Linear Regression on Rx trend |
| `AUTO_DETECTED` | AUTO-DETECTED | Pre-computed from DB |

## Note on `ai_territory_reach` and `ai_rx_risk`
For `alert_type = PAYER` or `FORMULARY`:
- `ai_territory_reach` → render as **Covered Lives** (not territory fraction)
- `ai_rx_risk` → render as **Access Impact** (not Rx risk)
""",
)
def active_alerts(
    featured: bool = False,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    return get_alerts(db, rep.territory_id, featured=featured)


@router.post("/detect")
def run_detection(
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """
    Run the full ML pipeline for the rep's territory:
      1. IsolationForest  → detects anomalous Rx HCPs
      2. LinearRegression → detects gradually drifting HCPs
      3. GPT-4o           → enriches each alert with counter-script + analysis
      4. Persists results to insight360_active_alerts
    """
    results = run_pipeline(db, rep.territory_id)
    return {
        "territory_id":    rep.territory_id,
        "alerts_generated": len(results),
        "alerts":           results,
    }


@router.post("/alerts/{alert_id}/enrich")
def enrich_alert_endpoint(
    alert_id: str,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """
    Trigger one GPT-4o call to generate all ai_* fields for a single alert.
    Use this when a raw alert row has no ai_* values yet.
    """
    alert = (
        db.query(ActiveAlert)
        .filter(
            ActiveAlert.alert_id == alert_id,
            ActiveAlert.territory_id == rep.territory_id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    result = enrich_alert(db, alert)
    return {"alert_id": alert_id, "status": "enriched", "ai_fields": result}


@router.get("/hcp-awareness", response_model=HCPAwarenessResponse)
def hcp_awareness(
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Return HCP awareness scores for the rep's territory."""
    return get_hcp_awareness(db, rep.territory_id)


@router.get("/competitive-intel", response_model=CompetitiveIntelResponse)
def competitive_intel(
    featured: bool = False,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """
    Return competitive intelligence signals for the rep's territory.
    Pass ?featured=true to get top 1 per threat tier (Critical/High, Medium, Low).
    """
    return get_competitive_intel(db, territory_id=rep.territory_id, featured=featured)


@router.get("/payer-access", response_model=PayerAccessResponse)
def payer_access(
    featured: bool = False,
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """
    Return payer formulary and access changes.
    Pass ?featured=true to get top 1 per status tier (AI_ALERT, STABLE high, STABLE low).
    """
    return get_payer_access(db, territory_id=rep.territory_id, featured=featured)
