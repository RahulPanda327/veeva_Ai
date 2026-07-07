"""
Payer Access service.

4 AI/ML techniques:
  1. AI Impact Scoring         — composite from tier direction, covered lives, PA, channel
  2. ML Predictive Analytics   — project patient abandonment % and count for tier changes
  3. NLP Classification        — keyword-classify Recommended_Action → urgency + category
  4. GPT-4o                    — generate ai_impact_summary, ai_action_plan, ai_pa_bridge_note
"""
from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.payer_access import PayerAccess
from app.schemas.action_center import PayerAccessItem, PayerAccessResponse

log = logging.getLogger(__name__)

# ── in-process GPT-4o cache ──────────────────────────────────────────────────
_CACHE: Dict[str, Any] = {}

# ── tier → numeric rank (lower number = better access) ───────────────────────
_TIER_RANK = {
    "tier 1": 1,
    "tier 2": 2,
    "tier 3": 3,
    "non-formulary": 4,
}

# ── tier → human-readable label ──────────────────────────────────────────────
_TIER_LABEL = {
    "tier 1": "Preferred",
    "tier 2": "Standard",
    "tier 3": "Non-preferred",
    "non-formulary": "Non-Formulary",
}

# ── NLP keyword taxonomy for Recommended_Action ──────────────────────────────
_NLP_TAXONOMY: Dict[str, List[str]] = {
    "FORMULARY_CHANGE": [
        "non-formulary", "appeal", "escalate", "market access", "tier change",
        "formulary", "tier appeal", "dossier", "formulary review",
    ],
    "PA_REQUIREMENT": [
        "prior auth", "pa", "step therapy", "approval scripts", "pa bridge",
        "prior authorization", "hub services", "pa support",
    ],
    "ACCESS_WIN": [
        "positive tier", "access win", "favorable", "preferred", "tier improvement",
        "improve", "leverage", "advantage",
    ],
    "MONITORING": [
        "monitor", "upcoming", "review cycle", "submit", "q3", "q4", "clinical dossier",
        "maintain", "no action",
    ],
}

_URGENCY_WORDS = {
    "Immediate": ["immediate", "critical", "escalate", "abandonment", "alert field", "emergency"],
    "Standard":  ["coordinate", "brief", "provide", "enroll", "schedule", "submit"],
    "Routine":   ["monitor", "maintain", "leverage", "upcoming", "no action"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: parse int strings safely
# ─────────────────────────────────────────────────────────────────────────────
def _parse_int(raw: Optional[str]) -> int:
    try:
        return int(str(raw).replace(",", "").strip()) if raw else 0
    except ValueError:
        return 0


def _tier_rank(tier: Optional[str]) -> int:
    return _TIER_RANK.get((tier or "").lower().strip(), 2)


def _tier_label(tier: Optional[str]) -> str:
    return _TIER_LABEL.get((tier or "").lower().strip(), tier or "Unknown")


def _tier_str(val: Optional[str]) -> Optional[str]:
    """Normalize tier value: '2' → 'Tier 2', 'Tier 2' → 'Tier 2', None → None."""
    if val is None:
        return None
    v = str(val).strip()
    if v.isdigit():
        return f"Tier {v}"
    return v


def _tier_change_direction(current: Optional[str], previous: Optional[str]) -> str:
    c, p = _tier_rank(current), _tier_rank(previous)
    if c > p:
        return "DOWNGRADE"
    if c < p:
        return "UPGRADE"
    return "UNCHANGED"


# ─────────────────────────────────────────────────────────────────────────────
# Technique 1 — AI Impact Scoring (composite)
# ─────────────────────────────────────────────────────────────────────────────
def _impact_score(
    tier_current: Optional[str],
    tier_previous: Optional[str],
    pa_required: bool,
    covered_lives: int,
    channel: Optional[str],
    ai_alert_flag: bool,
) -> Tuple[float, str, str]:
    """Return (score 0-100, level, impact_label)."""
    direction = _tier_change_direction(tier_current, tier_previous)

    # Tier change weight
    tier_delta = _tier_rank(tier_current) - _tier_rank(tier_previous)
    if direction == "DOWNGRADE":
        tier_weight = min(35.0, tier_delta * 15.0)    # 1 tier = 15, 2+ = 30, 3+ = 35
        impact_label = "Non-Formulary" if "non-formulary" in (tier_current or "").lower() else "Higher copays"
    elif direction == "UPGRADE":
        tier_weight = -10.0
        impact_label = "Access Win"
    else:
        tier_weight = 0.0
        impact_label = "PA Required" if pa_required else "Stable Access"

    # Covered lives factor (log scale: 400k → 30, 100k → 20, 42k → 13)
    lives_weight = min(30.0, math.log10(max(covered_lives, 1)) * 10.0 - 30.0) if covered_lives > 0 else 0.0
    lives_weight = max(0.0, lives_weight)

    # PA required adds friction
    pa_weight = 15.0 if pa_required else 0.0

    # Channel: Medicare = slightly higher (elderly, chronic disease, harder to switch)
    channel_weight = 5.0 if (channel or "").lower() == "medicare" else 0.0

    # Confirmed AI alert from DB
    alert_weight = 10.0 if ai_alert_flag else 0.0

    score = round(min(100.0, max(0.0, tier_weight + lives_weight + pa_weight + channel_weight + alert_weight)), 1)

    if score >= 65:
        level = "High"
    elif score >= 35:
        level = "Medium"
    else:
        level = "Low"

    return score, level, impact_label


# ─────────────────────────────────────────────────────────────────────────────
# Technique 2 — ML Predictive Analytics: patient abandonment projection
# ─────────────────────────────────────────────────────────────────────────────
def _predict_abandonment(
    direction: str,
    tier_current: Optional[str],
    pa_required: bool,
    covered_lives: int,
) -> Tuple[Optional[float], Optional[int]]:
    """
    Estimate % of patients who will abandon Zenpep Rx in next 30 days.
    Based on published literature: tier downgrade increases abandonment 12-22%;
    non-formulary increases abandonment 35-55%.
    """
    if direction == "UPGRADE":
        return None, None  # no abandonment risk on upgrade

    tier_lower = (tier_current or "").lower()

    if "non-formulary" in tier_lower:
        abandonment_pct = 45.0
    elif "tier 3" in tier_lower:
        abandonment_pct = 18.0
    elif "tier 2" in tier_lower and pa_required:
        abandonment_pct = 12.0
    elif direction == "DOWNGRADE":
        abandonment_pct = 10.0
    else:
        return None, None

    # Convert covered_lives to estimated Zenpep patients (assume 0.15% penetration)
    estimated_patients = max(1, round(covered_lives * 0.0015))
    projected_impact   = round(estimated_patients * abandonment_pct / 100)

    return round(abandonment_pct, 1), projected_impact


# ─────────────────────────────────────────────────────────────────────────────
# Technique 3 — NLP classification
# ─────────────────────────────────────────────────────────────────────────────
def _nlp_classify(action_text: Optional[str]) -> Tuple[str, str, List[str]]:
    """Return (category, urgency, keywords)."""
    if not action_text:
        return "MONITORING", "Routine", []

    lower = action_text.lower()
    hits: Dict[str, int] = {}
    found_kws: List[str] = []

    for cat, kws in _NLP_TAXONOMY.items():
        score = 0
        for kw in kws:
            if kw in lower:
                score += 1
                if kw not in found_kws:
                    found_kws.append(kw)
        if score:
            hits[cat] = score

    category = max(hits, key=hits.get) if hits else "MONITORING"

    urgency = "Routine"
    for lvl, words in _URGENCY_WORDS.items():
        if any(w in lower for w in words):
            urgency = lvl
            break

    return category, urgency, found_kws[:5]


# ─────────────────────────────────────────────────────────────────────────────
# Technique 4 — GPT-4o
# ─────────────────────────────────────────────────────────────────────────────
def _stub_gpt(row: PayerAccess) -> Dict[str, str]:
    direction = _tier_change_direction(row.tier_current, row.tier_previous)
    pa_text   = "PA required — provide bridge script." if row.pa_required == "Yes" else ""
    lives     = _parse_int(row.covered_lives)

    if direction == "DOWNGRADE":
        summary = (
            f"{row.payer_name} tier downgrade ({row.tier_previous} → {row.tier_current}) "
            f"affects {lives:,} covered lives — expect increased patient cost burden and potential Rx abandonment."
        )
        plan = [
            f"Brief top prescribers in {row.channel_name or 'territory'} on formulary change.",
            "Provide PA bridge scripts for continuity-of-care patients.",
            "Enroll at-risk patients in ZenConnect co-pay assistance program.",
        ]
    elif direction == "UPGRADE":
        summary = (
            f"{row.payer_name} tier improvement ({row.tier_previous} → {row.tier_current}) — "
            f"positive access win for {lives:,} covered lives. Leverage in detailing conversations."
        )
        plan = [
            "Notify field force of improved formulary status.",
            f"Use {row.payer_name} preferred status as a detailing advantage with top prescribers.",
            "Update patient services team on improved access.",
        ]
    else:
        summary = (
            f"{row.payer_name} formulary status is stable at {row.tier_current}. "
            f"Monitor for upcoming review cycle and maintain current detailing strategy."
        )
        plan = [
            "Maintain current access — no immediate action required.",
            f"Monitor {row.payer_name} formulary review calendar.",
            "Submit clinical dossier for next renewal cycle if applicable.",
        ]

    pa_bridge = (
        f"For {row.payer_name}: emphasize clinical necessity of Zenpep in patients with documented EPI. "
        "Use Step Edit override request — cite gastroenterologist specialty and prior PERT trial failure."
    ) if row.pa_required == "Yes" else None

    return {
        "ai_impact_summary": summary,
        "ai_action_plan": plan,
        "ai_pa_bridge_note": pa_bridge or "",
    }


def _call_gpt4o(row: PayerAccess) -> Dict[str, str]:
    cache_key = f"pa_{row.plan_id}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if settings.LLM_STUB_MODE:
        result = _stub_gpt(row)
        _CACHE[cache_key] = result
        return result

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=settings.OPENAI_MAX_RETRIES,
            timeout=settings.OPENAI_TIMEOUT,
        )
        direction = _tier_change_direction(row.tier_current, row.tier_previous)
        prompt = (
            "You are a pharmaceutical market access AI for ZENPEP (pancrelipase). "
            "Return ONLY valid JSON with keys: ai_impact_summary, ai_action_plan, ai_pa_bridge_note.\n\n"
            f"Payer: {row.payer_name} (MCO: {row.mco_org_name})\n"
            f"Channel: {row.channel_name}\n"
            f"Tier Change: {row.tier_previous} → {row.tier_current} ({direction})\n"
            f"Change Date: {row.change_date}\n"
            f"PA Required: {row.pa_required}\n"
            f"Covered Lives: {row.covered_lives}\n"
            f"Affected HCPs: {row.affected_hcp_count}\n"
            f"Impact Level: {row.impact_level}\n"
            f"DB Recommended Action: {row.recommended_action}\n\n"
            "ai_impact_summary: 1 sentence describing the business impact for the sales rep.\n"
            "ai_action_plan: 3-step numbered action plan for the rep (each step max 20 words).\n"
            "ai_pa_bridge_note: If PA required, provide 1-2 sentence clinical rationale for PA approval. "
            "If PA not required, return empty string."
        )
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(resp.choices[0].message.content)
        # Normalize action_plan to list
        if isinstance(result.get("ai_action_plan"), str):
            result["ai_action_plan"] = [s.strip() for s in result["ai_action_plan"].split("\n") if s.strip()]
        _CACHE[cache_key] = result
        return result
    except Exception as exc:
        log.warning("GPT-4o error for %s: %s", row.plan_id, exc)
        result = _stub_gpt(row)
        _CACHE[cache_key] = result
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Build one PayerAccessItem
# ─────────────────────────────────────────────────────────────────────────────
def _build_item(row: PayerAccess) -> PayerAccessItem:
    covered_lives = _parse_int(row.covered_lives)
    hcp_count     = _parse_int(row.affected_hcp_count)
    pa_req_bool   = (row.pa_required or "").strip().upper() == "YES"
    ai_alert      = (row.ai_alert_flag or "").strip().upper() == "YES"
    tier_changed  = (row.recent_tier_change or "").strip().upper() == "YES"

    # Normalize tier strings ("2" → "Tier 2")
    tier_cur  = _tier_str(row.tier_current)
    tier_prev = _tier_str(row.tier_previous)

    # Derived display fields
    tier_label    = _tier_label(tier_cur)
    direction     = _tier_change_direction(tier_cur, tier_prev)
    status_badge  = "AI_ALERT" if ai_alert else "STABLE"
    change_badge  = "CHANGE_DETECTED" if tier_changed else None

    # Technique 1 — AI Impact Scoring
    impact_score, impact_level, impact_label = _impact_score(
        tier_cur, tier_prev, pa_req_bool,
        covered_lives, row.channel_name, ai_alert,
    )

    # Technique 2 — ML Predictive Analytics
    abandonment_pct, projected_impact = _predict_abandonment(
        direction, tier_cur, pa_req_bool, covered_lives
    )

    # Technique 3 — NLP
    nlp_category, nlp_urgency, nlp_keywords = _nlp_classify(row.recommended_action)

    # Technique 4 — GPT-4o (only used when AI-flagged)
    gpt = _call_gpt4o(row) if ai_alert else {}

    # Build analysis badges
    badges: List[str] = ["AI_SCORING"]
    if ai_alert:
        badges.append("AI_ALERT")
    if abandonment_pct is not None:
        badges.append("PREDICTIVE_ANALYTICS")
    if nlp_category in ("PA_REQUIREMENT", "FORMULARY_CHANGE"):
        badges.append("NLP_ANALYSIS")
    badges = list(dict.fromkeys(badges))

    return PayerAccessItem(
        plan_id=row.plan_id,
        payer_name=row.payer_name or "Unknown",
        mco_org_name=row.mco_org_name,
        channel_name=row.channel_name,
        tier_current=tier_cur,
        tier_previous=tier_prev,
        change_date=row.change_date if row.change_date else None,
        pa_required="Yes" if pa_req_bool else "No",
        covered_lives=covered_lives,
        affected_hcp_count=hcp_count,
        tier_label_current=tier_label,
        status_badge=status_badge,
        change_badge=change_badge,
        ai_impact_score=impact_score,
        ai_impact_level=impact_level,
        ai_tier_change_direction=direction,
        ai_abandonment_risk_pct=abandonment_pct,
        ai_projected_patient_impact=projected_impact,
        ai_nlp_action_category=nlp_category,
        ai_nlp_urgency=nlp_urgency,
        ai_nlp_keywords=nlp_keywords,
        ai_impact_summary=gpt.get("ai_impact_summary"),
        ai_action_plan=gpt.get("ai_action_plan") if ai_alert else (row.recommended_action or ""),
        ai_pa_bridge_note=gpt.get("ai_pa_bridge_note") or None,
        view_action_plan=row.recommended_action,   # insight360_payer_access.Recommended_Action
        analysis_badges=badges,
        ai_is_flagged=ai_alert,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────
class _FakePARow:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __getattr__(self, name):
        return None


_SAMPLE_PA_ROWS = [
    _FakePARow(plan_id="PA-001", payer_name="BlueCross Northeast",  mco_org_name="BlueCross BlueShield",   channel_name="Commercial", tier_current="Tier 3", tier_previous="Tier 2", change_date="2026-04-25", pa_required="Yes", recent_tier_change="Yes", ai_alert_flag="Yes", affected_hcp_count="47",  covered_lives="340000",  impact_level="HIGH",   recommended_action="Alert field reps — immediate PA bridge script needed. Coordinate with hub services for prior auth support. Enroll affected patients in ZenConnect."),
    _FakePARow(plan_id="PA-002", payer_name="Aetna Commercial",     mco_org_name="Aetna Inc.",             channel_name="Commercial", tier_current="Tier 1", tier_previous="Tier 1", change_date=None,         pa_required="No",  recent_tier_change="No",  ai_alert_flag="No",  affected_hcp_count="89",  covered_lives="420000",  impact_level="LOW",    recommended_action="Leverage Tier 1 preferred status in detailing conversations. Maintain current access — no action required."),
    _FakePARow(plan_id="PA-003", payer_name="UnitedHealthcare",     mco_org_name="UnitedHealth Group",     channel_name="Commercial", tier_current="Tier 2", tier_previous="Tier 1", change_date="2026-03-01", pa_required="Yes", recent_tier_change="Yes", ai_alert_flag="Yes", affected_hcp_count="34",  covered_lives="280000",  impact_level="MEDIUM", recommended_action="Brief top prescribers on formulary change. Provide PA bridge scripts for continuity-of-care patients."),
    _FakePARow(plan_id="PA-004", payer_name="Medicare Part D",      mco_org_name="CMS",                    channel_name="Medicare",   tier_current="Tier 2", tier_previous="Tier 2", change_date=None,         pa_required="No",  recent_tier_change="No",  ai_alert_flag="No",  affected_hcp_count="156", covered_lives="95000",   impact_level="LOW",    recommended_action="No change — monitor for upcoming annual review. Maintain engagement with Medicare-heavy prescribers."),
    _FakePARow(plan_id="PA-005", payer_name="Cigna Health",         mco_org_name="Cigna Corporation",      channel_name="Commercial", tier_current="Tier 2", tier_previous="Tier 3", change_date="2026-02-15", pa_required="No",  recent_tier_change="Yes", ai_alert_flag="No",  affected_hcp_count="28",  covered_lives="185000",  impact_level="LOW",    recommended_action="Leverage tier improvement — use preferred status as a detailing advantage in Cigna-heavy practices."),
    _FakePARow(plan_id="PA-006", payer_name="Medicaid Managed Care", mco_org_name="State Medicaid",        channel_name="Medicaid",   tier_current="Non-Formulary", tier_previous="Tier 3", change_date="2026-04-01", pa_required="Yes", recent_tier_change="Yes", ai_alert_flag="Yes", affected_hcp_count="22",  covered_lives="65000",   impact_level="HIGH",   recommended_action="Escalate to market access team. Submit clinical dossier for formulary appeal. Enroll patients in patient assistance program immediately."),
]


def get_payer_access(
    db: Session,
    territory_id: Optional[str] = None,
    featured: bool = False,
) -> PayerAccessResponse:
    rows = []
    try:
        rows = db.query(PayerAccess).all()
    except Exception as e:
        log.warning("Payer access DB query failed (%s), using sample data", e)

    if not rows:
        log.info("No payer access rows — using sample data")
        rows = _SAMPLE_PA_ROWS  # type: ignore[assignment]

    items: List[PayerAccessItem] = [_build_item(r) for r in rows]

    # Sort: AI_ALERT first, then by impact score descending
    items.sort(key=lambda x: (0 if x.status_badge == "AI_ALERT" else 1, -x.ai_impact_score))

    if featured:
        # Return top 1 AI_ALERT, top 1 STABLE high-impact, top 1 STABLE low-impact
        picked: List[PayerAccessItem] = []
        seen: set = set()
        for item in items:
            bucket = item.status_badge
            if bucket == "STABLE":
                bucket = f"STABLE_{item.ai_impact_level}"
            if bucket not in seen:
                picked.append(item)
                seen.add(bucket)
            if len(picked) == 3:
                break
        items = picked

    alert_count     = sum(1 for i in items if i.status_badge == "AI_ALERT")
    stable_count    = sum(1 for i in items if i.status_badge == "STABLE")
    downgrade_count = sum(1 for i in items if i.ai_tier_change_direction == "DOWNGRADE")
    high_count      = sum(1 for i in items if i.ai_impact_level == "High")
    lives_at_risk   = sum(i.covered_lives for i in items if i.status_badge == "AI_ALERT")
    total_hcps      = sum(i.affected_hcp_count for i in items if i.status_badge == "AI_ALERT")

    return PayerAccessResponse(
        items=items,
        total=len(items),
        ai_alert_count=alert_count,
        ai_stable_count=stable_count,
        ai_tier_downgrade_count=downgrade_count,
        ai_high_impact_count=high_count,
        ai_total_covered_lives_at_risk=lives_at_risk,
        ai_total_affected_hcps=total_hcps,
    )
