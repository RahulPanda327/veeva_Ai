"""Action Center — Launch & Market Defense router."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.auth import get_current_rep, RepIdentity
from app.models.active_alerts import ActiveAlert
from app.schemas.action_center import (
    ActiveAlertListResponse,
    ActionCenterSummary,
    HCPAwarenessResponse,
    CompetitiveIntelResponse,
    PayerAccessResponse,
)
from app.schemas.filters import OrgFilters
from app.services.action_center.alert_engine import get_alerts, get_alert_summary
from app.services.filters_service import (
    FilterSelection,
    filter_params,
    get_org_filters,
    resolve_territories,
    salesforce_of,
)
from app.services.action_center.alert_enricher import enrich_alert
from app.services.action_center.alert_pipeline import run_pipeline
from app.services.action_center.hcp_awareness_svc import get_hcp_awareness
from app.services.action_center.competitive_intel_svc import get_competitive_intel
from app.services.action_center.payer_access_svc import get_payer_access

router = APIRouter(prefix="/action-center", tags=["action-center"])


def _scoped_territory_ids(db, rep, sel: FilterSelection) -> Optional[list]:
    """Resolve a manager/employee/territory selection to the BARE Territory_Durable_Ids
    it covers (e.g. ['A0E000000013065', ...]) — the format the Action Center tables
    store in their Territory_Durable_Id column. Returns None when nothing is selected,
    so the services fall back to their default (all rows), unchanged."""
    terrs = resolve_territories(db, salesforce_of(rep.territory_id), sel)
    if not terrs:
        return None
    return [t.split("|")[-1] for t in terrs]


@router.get(
    "/alerts",
    response_model=ActiveAlertListResponse,
    summary="Active Alerts — full list or featured 3",
    description="""
Returns active ML-detected alerts for the rep's territory.

## Query Parameters
| Param | Type | Default | Description |
|---|---|---|---|
| `featured` | bool | `false` | `false` = all alerts · `true` = top 1 per severity (max 3 cards) |

## Response Fields
- **`total`** — alerts returned in this call (affected by `featured` flag)
- **`total_in_db`** — actual row count in `insight360_active_alerts_dul` (always real DB count)
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
    sel: FilterSelection = Depends(filter_params),
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    return get_alerts(db, _scoped_territory_ids(db, rep, sel), featured=featured)


@router.get(
    "/alerts/summary",
    response_model=ActionCenterSummary,
    summary="Active Alerts — KPI summary tiles only",
)
def alert_summary(
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """KPI summary tiles plus the manager → employee → territory `filters` tree.

    Always returns the rep's own tiles plus the `filters` tree for the dropdowns.
    Selection is applied on the data endpoints (e.g. /competitive-intel?territory_id=),
    not here."""
    sf = salesforce_of(rep.territory_id)
    summary = get_alert_summary(db, rep.territory_id)
    summary.filters = OrgFilters(**get_org_filters(db, sf))
    return summary


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
      4. Persists results to insight360_active_alerts_dul
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
    # Alert_Id is the primary key (globally unique) — no territory filter needed.
    # (The rep's territory_id is the piped "salesforce|durable_id" form anyway,
    # while the column stores the bare durable id, so an == check never matched.)
    alert = db.query(ActiveAlert).filter(ActiveAlert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    result = enrich_alert(db, alert)
    return {"alert_id": alert_id, "status": "enriched", "ai_fields": result}


@router.get("/hcp-awareness", response_model=HCPAwarenessResponse)
def hcp_awareness(
    sel: FilterSelection = Depends(filter_params),
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """Return HCP awareness scores for the rep's (or selected) territory,
    filtered on the table's Territory_Durable_Id column."""
    return get_hcp_awareness(db, territory_ids=_scoped_territory_ids(db, rep, sel))


@router.get("/competitive-intel", response_model=CompetitiveIntelResponse)
def competitive_intel(
    featured: bool = False,
    sel: FilterSelection = Depends(filter_params),
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """
    Return competitive intelligence signals for the rep's (or selected) territory.
    Pass ?featured=true to get top 1 per threat tier (Critical/High, Medium, Low).
    """
    return get_competitive_intel(
        db, territory_ids=_scoped_territory_ids(db, rep, sel), featured=featured
    )


@router.get("/payer-access", response_model=PayerAccessResponse)
def payer_access(
    featured: bool = False,
    sel: FilterSelection = Depends(filter_params),
    rep: RepIdentity = Depends(get_current_rep),
    db: Session = Depends(get_db),
):
    """
    Return payer formulary and access changes for the rep's (or selected) territory,
    filtered on the table's Territory_Durable_Id column.
    Pass ?featured=true to get top 1 per status tier (AI_ALERT, STABLE high/low).
    """
    return get_payer_access(
        db, territory_ids=_scoped_territory_ids(db, rep, sel), featured=featured
    )
