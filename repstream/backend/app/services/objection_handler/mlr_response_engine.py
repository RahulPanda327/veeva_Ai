"""MLR-approved responses and sample data for Objection Handler (Module 3).

Falls back to representative sample data when insight360_objection_handler is unavailable.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.objection_handler import ObjectionHandler

log = logging.getLogger(__name__)

FrequencyLabel = Literal["HIGH", "MEDIUM", "LOW"]

_FREQ_ORDER: Dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%b %d, %Y",
    "%b %d",
]


def _parse_objection_date(obj: Dict) -> datetime:
    """Parse call_date (ISO) or end-date from ai_date_range for sort key."""
    raw = obj.get("call_date", "")
    if raw:
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
    date_range = obj.get("ai_date_range", "")
    if date_range and " - " in date_range:
        end_part = date_range.split(" - ")[-1].strip()
        for fmt in ("%b %d, %Y", "%b %d"):
            try:
                dt = datetime.strptime(end_part, fmt)
                if fmt == "%b %d":
                    dt = dt.replace(year=datetime.now().year)
                return dt
            except ValueError:
                continue
    return datetime.min


def sort_objections(objections: List[Dict]) -> List[Dict]:
    """Sort all objections: HIGH → MEDIUM → LOW, then by date descending within each group."""
    return sorted(
        objections,
        key=lambda o: (
            _FREQ_ORDER.get(o.get("ai_frequency_label", "LOW").upper(), 2),
            -_parse_objection_date(o).timestamp(),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sample fallback data (matches UI screenshots exactly)
# ─────────────────────────────────────────────────────────────────────────────

_SAMPLE_OBJECTIONS: List[Dict] = [
    {
        "objection_id":          "OBJ001",
        "objection_type":        "Side Effect Profile",
        "objection_text":        '"I\'m concerned about the side effect profile"',
        "period":                "Mar 1 - Apr 26, 2026",
        "territory_id":          "TERR-001",
        "hcp_segment":           "Target A",
        "ai_call_count":         12,
        "call_date":             "2026-04-22",
        "ai_date_range":         "Mar 15 - Apr 22",
        "ai_success_rate":       0.67,
        "ai_frequency_label":    "HIGH",
        "ai_mlr_response": (
            "I understand that's an important consideration. The clinical trial data shows that "
            "the incidence of [specific side effect] was comparable to placebo at 3.2% vs 3.1%. "
            "Would you like to review the safety profile data from the Phase 3 trials together?"
        ),
        "response_source":       "MLR-v3.1",
        "ai_sku":                "SP-2024-01",
        "ai_supporting_materials": "Safety Profile Summary (SKU: SP-2024-01), Phase 3 Results Card",
    },
    {
        "objection_id":          "OBJ002",
        "objection_type":        "Dosing Complexity",
        "objection_text":        '"The dosing schedule is too complex"',
        "period":                "Mar 1 - Apr 26, 2026",
        "territory_id":          "TERR-001",
        "hcp_segment":           "Target A",
        "ai_call_count":         8,
        "call_date":             "2026-04-18",
        "ai_date_range":         "Mar 20 - Apr 18",
        "ai_success_rate":       0.75,
        "ai_frequency_label":    "MEDIUM",
        "ai_mlr_response": (
            "That's actually a common initial reaction. Most of our prescribers find that once patients "
            "get into the routine, adherence rates are actually higher than simpler regimens because of "
            "the built-in checkpoints. We have patient education materials that make it very straightforward. "
            "Would you be interested in reviewing how Dr. Davidson's practice implemented this successfully?"
        ),
        "response_source":       "MLR-v2.8",
        "ai_sku":                "DG-2024-01",
        "ai_supporting_materials": "Dosing Guide (SKU: DG-2024-01), Patient Education Kit",
    },
    {
        "objection_id":          "OBJ003",
        "objection_type":        "Insurance Coverage",
        "objection_text":        '"My patients can\'t afford it — insurance doesn\'t always cover it"',
        "period":                "Mar 1 - Apr 26, 2026",
        "territory_id":          "TERR-001",
        "hcp_segment":           "Target B",
        "ai_call_count":         6,
        "call_date":             "2026-04-14",
        "ai_date_range":         "Mar 10 - Apr 14",
        "ai_success_rate":       0.58,
        "ai_frequency_label":    "MEDIUM",
        "ai_mlr_response": (
            "We have a patient assistance program that covers most commercially insured patients at $0 copay, "
            "and for Medicare patients we have a bridge program. I can leave co-pay cards and have our "
            "reimbursement team contact your office coordinator directly to pre-qualify patients."
        ),
        "response_source":       "MLR-v3.0",
        "ai_sku":                "PA-2024-01",
        "ai_supporting_materials": "Copay Card (SKU: PA-2024-01), Prior Auth Support Guide",
    },
    {
        "objection_id":          "OBJ004",
        "objection_type":        "Efficacy Skepticism",
        "objection_text":        '"I\'m not sure it works better than generic pancrelipase"',
        "period":                "Mar 1 - Apr 26, 2026",
        "territory_id":          "TERR-001",
        "hcp_segment":           "Target B",
        "ai_call_count":         4,
        "call_date":             "2026-04-20",
        "ai_date_range":         "Apr 2 - Apr 20",
        "ai_success_rate":       0.50,
        "ai_frequency_label":    "LOW",
        "ai_mlr_response": (
            "That's a fair question. ZENPEP is the only pancrelipase with Phase 3 data showing consistent "
            "fat absorption across all three macronutrients. The PERT optimization data shows measurable "
            "difference in CFA outcomes at 6 and 12 weeks. Would you like to walk through the head-to-head data?"
        ),
        "response_source":       "MLR-v3.1",
        "ai_sku":                "CL-2024-01",
        "ai_supporting_materials": "Clinical Summary (SKU: CL-2024-01), Phase 3 Study Card",
    },
]


# ── NLP enrichment helpers ────────────────────────────────────────────────────

def _frequency_label(call_count: int) -> FrequencyLabel:
    if call_count > 10:
        return "HIGH"
    if call_count >= 5:
        return "MEDIUM"
    return "LOW"


def _combine_materials(mlr_response: Optional[str], sku: Optional[str]) -> Optional[str]:
    """ai_supporting_materials = the real MLR response + its SKU, combined.
    Both values come straight from insight360_objection_handler
    (MLR_Approved_Response + MLR_SKU_Code) — no hardcoded material names."""
    response = (mlr_response or "").strip()
    sku = (sku or "").strip()
    if response and sku:
        return f"{response} (SKU: {sku})"
    if response:
        return response
    if sku:
        return f"SKU: {sku}"
    return None


def _nlp_badges(row: Dict) -> List[str]:
    badges = ["DETECTED_BY_AI", "NLP_ANALYSIS"]
    if row.get("ai_success_rate", 0) > 0:
        badges.append("AI_OPTIMIZED")
    return badges


# ── DB loaders ────────────────────────────────────────────────────────────────

def load_all_objections(
    db: Session,
    territory_id: str,
    period: Optional[str] = None,
) -> List[Dict]:
    """Load objections from DB with AI enrichment. Falls back to sample data."""
    try:
        # insight360_objection_handler has no territory_id column (KPI 10 joins via call_transcripts)
        stmt = select(ObjectionHandler).order_by(ObjectionHandler.call_count_mentions.desc())
        rows = list(db.scalars(stmt).all())

        if rows:
            result = []
            for r in rows:
                sku = r.mlr_sku_code
                obj_type = r.objection_category
                raw_count = int(r.call_count_mentions or 0) if r.call_count_mentions else 0
                raw_rate_str = (r.conversion_rate_pct or "0").replace("%", "")
                raw_rate = float(raw_rate_str) / 100.0 if raw_rate_str else 0.0
                result.append({
                    "objection_id":          r.transcript_id,
                    "objection_type":        r.objection_category or "",
                    "objection_text":        r.objection_text or "",
                    "period":                r.detection_period or "",
                    "territory_id":          territory_id,
                    "hcp_segment":           None,
                    "call_date":             r.call_date or "",
                    "ai_call_count":         raw_count,
                    "ai_date_range":         r.detection_period or "",
                    "ai_success_rate":       raw_rate,
                    "ai_frequency_label":    (r.frequency_label or "").upper() or _frequency_label(raw_count),
                    "ai_mlr_response":       r.mlr_response or "",
                    "response_source":       "MLR-approved",
                    "ai_sku":                sku,
                    "ai_supporting_materials": _combine_materials(r.mlr_response, sku),
                })
            log.info("Loaded %d objections from DB.", len(result))
            return result
    except Exception as exc:
        log.warning("Objection DB load failed (%s), using sample data.", exc)

    # Fallback — filter sample by territory (always matches TERR-001 in dev)
    fallback = [dict(o) for o in _SAMPLE_OBJECTIONS]
    if territory_id and territory_id != "TERR-001":
        # Give generic data for other territories
        for o in fallback:
            o["territory_id"] = territory_id
    log.info("Using sample objection data.")
    return fallback


def get_best_mlr_response(db: Session, objection_id: str) -> Optional[Dict]:
    """Fetch a single objection response by ID. Falls back to sample."""
    try:
        stmt = select(ObjectionHandler).where(ObjectionHandler.transcript_id == objection_id)
        row = db.scalars(stmt).first()
        if row:
            sku = row.mlr_sku_code
            raw_rate_str = (row.conversion_rate_pct or "0").replace("%", "")
            raw_rate = float(raw_rate_str) / 100.0 if raw_rate_str else 0.0
            return {
                "objection_id":          row.transcript_id,
                "objection_type":        row.objection_category or "",
                "objection_text":        row.objection_text or "",
                "recommended_response":  row.mlr_response or "",
                "response_source":       "MLR-approved",
                "sku":                   sku,
                "success_rate":          raw_rate,
                "hcp_segment":           None,
                "ai_supporting_materials": _combine_materials(row.mlr_response, sku),
            }
    except Exception as exc:
        log.warning("MLR response DB lookup failed (%s).", exc)

    # Fallback to sample
    sample = next((o for o in _SAMPLE_OBJECTIONS if o["objection_id"] == objection_id), None)
    if sample:
        return {
            "objection_id":          sample["objection_id"],
            "objection_type":        sample["objection_type"],
            "objection_text":        sample["objection_text"],
            "recommended_response":  sample["ai_mlr_response"],
            "response_source":       sample["response_source"],
            "sku":                   sample["ai_sku"],
            "success_rate":          sample["ai_success_rate"],
            "hcp_segment":           sample["hcp_segment"],
            "ai_supporting_materials": sample["ai_supporting_materials"],
        }
    return None


def enrich_objection_list(objections: List[Dict]) -> List[Dict]:
    """Add NLP analysis badges and conversion score to each objection."""
    for obj in objections:
        obj["analysis_badges"]     = _nlp_badges(obj)
        obj["ai_conversion_score"] = round(float(obj.get("ai_success_rate", 0)) * 100, 1)
    return objections
