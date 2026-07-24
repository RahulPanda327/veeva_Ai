"""
Alert enricher — GPT-4o generates the 5 LANGUAGE keys per alert.
ML owns all numbers. LLM owns all language.

GPT-4o generates:
  1. title                    — specific, data-driven headline
  2. description              — 2-sentence narrative
  3. ai_prescribing_drift_note — why behavior changed
  4. ai_counter_script         — what rep should say right now
  5. ai_supporting_materials   — which Zenpep materials to deploy

ICD-10 codes are NOT generated here — they come from the real HCP
dimension table in alert_engine.py (_icd10_for_alert).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from openai import OpenAI

from app.config import settings

log = logging.getLogger(__name__)

_CACHE: Dict[str, Any] = {}

_SYSTEM = """You are a pharmaceutical sales intelligence AI for Zenpep (pancrelipase).
You are given ONE detected alert with its real data, including the actual affected HCPs
(names, specialties, segments, locations). Return a JSON object with EXACTLY these 5 keys:

{
  "title": "<specific alert headline>",
  "description": "<2 sentence narrative — what happened, where, how many HCPs, date range>",
  "ai_prescribing_drift_note": "<1-2 sentences — what changed in prescribing behavior and why>",
  "ai_counter_script": "<3-4 sentences — actionable rep script citing specific Zenpep advantages>",
  "ai_supporting_materials": [
    {"title": "<material name>", "sku": "<sku or null>"}
  ]
}

Rules:
- Ground EVERY field in this alert's own data: its HCP count, dates, territory, and the
  affected HCPs' dominant specialties, segments, and cities/states. Two different alerts
  must never produce the same or near-identical wording.
- title: cite the threat + the real HCP count + the real location(s).
- description: mention competitor activity OR formulary change OR detailing decline, tied
  to the actual specialties/locations affected.
- ai_counter_script: what the rep should say/do NOW for THESE HCPs (reference their
  specialty mix), citing Zenpep microspheres, APEX trial, or ZenConnect where relevant.
- supporting materials: Zenpep-specific only (APEX Trial, ZenConnect, Competitive
  Positioning Guide, etc.).
- Never fabricate clinical data or HCP names not provided.
- Return valid JSON only — no markdown, no explanation."""


def _hcp_block(affected_hcps) -> str:
    """Compact per-HCP lines so the model can ground its language in real details."""
    if not affected_hcps:
        return "No individual HCP details available."
    lines = []
    for h in affected_hcps[:20]:
        name  = (h.get("name") or "").strip()
        place = ", ".join(p for p in (h.get("city"), h.get("state")) if p)
        parts = [p for p in (h.get("specialty"), h.get("segment"), place) if p]
        lines.append(f"- {name} ({' | '.join(parts)})")
    if len(affected_hcps) > 20:
        lines.append(f"... and {len(affected_hcps) - 20} more")
    return "\n".join(lines)


def _build_prompt(alert, affected_hcps=None) -> str:
    method = (alert.detection_method or "").upper()
    threat = "HCP detailing frequency decline / gradual drift" if "ML" in method or "TREND" in method \
             else "competitive script shift or formulary change"

    # Works for both ActiveAlert (DB) and DetectedAlert (ML)
    territory = getattr(alert, "territory_name", None) or getattr(alert, "territory_id", "Unknown")
    rx_change = getattr(alert, "avg_rx_change_pct", None)
    slope     = getattr(alert, "avg_slope", None)

    extra = ""
    if rx_change is not None:
        extra += f"\nRx Change %      : {rx_change:+.1f}%"
    if slope and slope != 0:
        extra += f"\nMonthly Slope    : {slope:.2f} Rx/month"

    return f"""Alert Id         : {alert.alert_id}
Severity         : {alert.severity}
Detection Method : {alert.detection_method}
Threat Type      : {threat}
Territory        : {territory}
Affected HCPs    : {alert.ai_affected_hcp_count}
Territory Reach  : {alert.ai_territory_reach}
Rx Risk          : {alert.ai_rx_risk}
Detected At      : {alert.detected_at}{extra}

Affected HCP details:
{_hcp_block(affected_hcps)}

Generate the 5 language fields as JSON, grounded in the details above."""


def enrich(alert, affected_hcps=None) -> dict:
    """
    Returns 5 LLM-generated language fields for the alert, grounded in the
    alert's real data + its actual affected HCP details.
    Cached per alert_id — GPT-4o called only once per process restart.
    """
    alert_id = alert.alert_id

    if alert_id in _CACHE:
        log.debug("Cache hit for %s", alert_id)
        return _CACHE[alert_id]

    if settings.LLM_STUB_MODE:
        result = _stub(alert)
        _CACHE[alert_id] = result
        return result

    try:
        result = _call_gpt4o(alert, affected_hcps)
    except Exception as exc:  # noqa: BLE001
        # LLM unavailable (key expired / 429 / timeout): DON'T crash the endpoint.
        # Return empty LLM-generated fields so the alert's DB-sourced structure
        # still comes through (_build_alert_item falls back to the DB Alert_Title /
        # Counter_Strategy for the other fields). Deliberately NOT cached, so this
        # self-heals — the next request retries GPT-4o and fills the values in as
        # soon as OpenAI is reachable again, with no restart needed.
        log.warning("GPT-4o alert enrichment unavailable for %s (%s) — empty LLM fields.", alert_id, exc)
        return {"ai_prescribing_drift_note": "", "ai_supporting_materials": []}

    _CACHE[alert_id] = result
    return result


def _call_gpt4o(alert, affected_hcps=None) -> dict:
    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        max_retries=settings.OPENAI_MAX_RETRIES,
        timeout=settings.OPENAI_TIMEOUT,
    )
    log.info("GPT-4o enriching alert %s", alert.alert_id)

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _build_prompt(alert, affected_hcps)},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(response.choices[0].message.content)


def _stub(alert) -> dict:
    hcp = alert.ai_affected_hcp_count
    territory = alert.territory_name or alert.territory_id
    return {
        "title": f"Rx pattern shift — {hcp} HCPs affected in {territory}",
        "description": (
            f"Unusual prescribing pattern detected across {hcp} HCPs in {territory}. "
            f"Detected on {alert.detected_at}."
        ),
        "ai_prescribing_drift_note": (
            f"{hcp} HCPs showing Rx volume reduction correlated with increased competitor activity."
        ),
        "ai_counter_script": (
            "Reinforce Zenpep microsphere differentiation and flexible dosing advantages. "
            "Leverage ZenConnect co-pay program for cost-sensitive patients. "
            "Deploy APEX trial data to counter competitor efficacy claims."
        ),
        "ai_supporting_materials": [
            {"title": "Zenpep Competitive Positioning Guide", "sku": "ZPP-COMP-001"},
            {"title": "ZenConnect Enrollment Form",           "sku": "ZPP-ZENCONNECT"},
            {"title": "APEX Trial Summary",                   "sku": "ZPP-APEX-001"},
        ],
    }


def enrich_alert(db, alert) -> dict:
    return enrich(alert)
