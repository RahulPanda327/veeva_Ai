"""Build the manager → employee → territory filter tree for the summary endpoints.

Source: hub_insight360.vw_tdim_employee_zenpep_reporting_dul — one denormalized
row per (employee, territory) with Manager_*, Employee_* and Territory_* columns.
Scoped to the caller's sales force (parsed from the piped territory id).

Cached in-process (small, slow-changing: ~1 manager / 3 employees / 8 territories
for the Commercial field force) with a short TTL.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.config import settings

log = logging.getLogger(__name__)

DEFAULT_SALESFORCE = "Commercial_Sales_Field_Force"


@dataclass
class FilterSelection:
    """A manager/employee/territory selection, always by id.

    The UI renders the human-readable names from the `filters` tree (which carries
    both id and name for every level) but sends back the *ids* — the backend filters
    on ids only, so nothing breaks if names change in the DB."""
    manager_id: Optional[str] = None
    employee_id: Optional[str] = None
    territory_id: Optional[str] = None

    def is_empty(self) -> bool:
        return not any((self.manager_id, self.employee_id, self.territory_id))


def filter_params(
    manager_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    territory_id: Optional[str] = None,
) -> FilterSelection:
    """FastAPI dependency — collects the id filter query params into one object.

    Use as `sel: FilterSelection = Depends(filter_params)` so every module endpoint
    exposes the same manager/employee/territory id filter without repeating the list."""
    return FilterSelection(manager_id=manager_id, employee_id=employee_id, territory_id=territory_id)

_CACHE: dict[str, dict] = {}
_CACHE_TS: dict[str, float] = {}
_TTL = 3600
_lock = threading.Lock()

_FILTER_SQL = text(f"""
    SELECT DISTINCT
        Manager_Employee_Durable_Id AS manager_id,
        Manager_Name                AS manager_name,
        Employee_Durable_Id         AS employee_id,
        Employee_Name               AS employee_name,
        Territory_Durable_Id        AS territory_id,
        Territory_Name              AS territory_name
    FROM {settings.HUB_SCHEMA}.vw_tdim_employee_zenpep_reporting_dul
    WHERE salesforce = :sf
      AND Manager_Employee_Durable_Id IS NOT NULL
      AND Employee_Durable_Id IS NOT NULL
      AND Territory_Durable_Id IS NOT NULL
""")


def salesforce_of(territory_id: Optional[str]) -> str:
    """Sales force prefix of a piped territory id (Commercial_Sales_Field_Force|A0E...)."""
    if territory_id and "|" in territory_id:
        return territory_id.split("|", 1)[0]
    return DEFAULT_SALESFORCE


def normalize_territory_id(territory_id: Optional[str], salesforce: str) -> Optional[str]:
    """Filter dropdowns hand back a bare Territory_Durable_Id (A0E...). The data
    queries key on the piped `salesforce|durable_id` form (sf_terr_pk_gi), so
    prepend the sales force when it isn't already piped."""
    if not territory_id:
        return territory_id
    if "|" in territory_id:
        return territory_id
    return f"{salesforce}|{territory_id}"


def resolve_territories(
    db: Session,
    salesforce: str,
    sel: Optional[FilterSelection] = None,
) -> Optional[list[str]]:
    """Resolve a manager/employee/territory selection (by id) to the piped territory
    ids it covers. Most specific wins: a territory id narrows to that territory; an
    employee id → all their territories; a manager id → all territories under them.

    Fast path: a bare territory_id with no other constraint is returned directly, so
    it works even for a territory that isn't in the org tree (e.g. the rep's own).

    Returns a de-duplicated list of `salesforce|durable_id` strings, or None when
    nothing was selected.
    """
    sel = sel or FilterSelection()
    if sel.is_empty():
        return None

    if sel.territory_id and not sel.manager_id and not sel.employee_id:
        return [normalize_territory_id(sel.territory_id, salesforce)]

    tree = get_org_filters(db, salesforce)
    out: list[str] = []
    seen: set[str] = set()
    for m in tree.get("manager_id", []):
        if sel.manager_id and m["manager_id"] != sel.manager_id:
            continue
        for e in m["employee_id"]:
            if sel.employee_id and e["employee_id"] != sel.employee_id:
                continue
            for t in e["territory_id"]:
                if sel.territory_id and t["territory_id"] != sel.territory_id:
                    continue
                piped = normalize_territory_id(t["territory_id"], salesforce)
                if piped not in seen:
                    seen.add(piped)
                    out.append(piped)
    return out or None


def hcps_for_territories(db: Session, territories: Optional[list[str]]) -> set[str]:
    """Resolve piped territory ids (salesforce|durable_id) to the real HCP_Durable_Ids
    assigned to them, via the account-territory bridge table.

    This is the table that actually links reps' territories to their live HCP
    population (11k+ rows) — distinct from the tiny, unscoped New Writer ID
    candidate list (insight360_peer_match_dul, ~10 rows DB-wide, not territory-
    mapped). Used to derive a real per-territory candidate pool for New Writer ID
    when a manager/employee/territory filter is applied.
    """
    if not territories:
        return set()
    bare_ids = sorted({t.split("|")[-1] for t in territories if t})
    if not bare_ids:
        return set()
    sql = text(f"""
        SELECT DISTINCT HCP_Durable_Id
        FROM {settings.HUB_SCHEMA}.vw_account_territory_zenpep_reporting_dul
        WHERE sales_force = 'Commercial_Sales_Field_Force'
          AND Territory_Durable_Id IN :terr_ids
    """).bindparams(bindparam("terr_ids", expanding=True))
    try:
        rows = db.execute(sql, {"terr_ids": bare_ids}).fetchall()
        return {r[0] for r in rows if r[0]}
    except Exception as exc:  # noqa: BLE001
        log.warning("HCP-for-territory lookup failed (%s).", exc)
        return set()


def get_org_filters(db: Session, salesforce: str = DEFAULT_SALESFORCE) -> dict:
    """Return the nested {manager_id:[...]} tree for the given sales force.

    Never raises — returns an empty tree if the DB is unavailable so the
    summary endpoints keep working."""
    now = time.time()
    with _lock:
        if salesforce in _CACHE and now - _CACHE_TS.get(salesforce, 0.0) < _TTL:
            return _CACHE[salesforce]

    try:
        rows = db.execute(_FILTER_SQL, {"sf": salesforce}).mappings().all()
    except Exception as exc:  # noqa: BLE001
        log.warning("Org filter tree load failed (%s). Returning empty filters.", exc)
        return {"manager_id": []}

    managers: dict[str, dict] = {}
    for r in rows:
        mid, eid, tid = r["manager_id"], r["employee_id"], r["territory_id"]
        m = managers.setdefault(mid, {"manager_id": mid, "manager_name": r["manager_name"], "_emps": {}})
        e = m["_emps"].setdefault(eid, {"employee_id": eid, "employee_name": r["employee_name"], "_terrs": {}})
        e["_terrs"].setdefault(tid, {"territory_id": tid, "territory_name": r["territory_name"]})

    tree = {
        "manager_id": [
            {
                "manager_id": m["manager_id"],
                "manager_name": m["manager_name"],
                "employee_id": [
                    {
                        "employee_id": e["employee_id"],
                        "employee_name": e["employee_name"],
                        "territory_id": sorted(
                            e["_terrs"].values(), key=lambda t: (t["territory_id"] or "")
                        ),
                    }
                    for e in sorted(m["_emps"].values(), key=lambda x: (x["employee_name"] or ""))
                ],
            }
            for m in sorted(managers.values(), key=lambda x: (x["manager_name"] or ""))
        ]
    }

    with _lock:
        _CACHE[salesforce] = tree
        _CACHE_TS[salesforce] = now
    return tree
