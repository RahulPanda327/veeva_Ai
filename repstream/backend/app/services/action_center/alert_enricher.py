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
Given ML-detected alert data, return a JSON object with EXACTLY these 5 keys:

{
  "title": "<specific alert title — mention threat type, HCP count, and location/territory>",
  "description": "<2 sentence narrative — what happened, where, how many HCPs, date range>",
  "ai_prescribing_drift_note": "<1-2 sentences — what changed in prescribing behavior and why>",
  "ai_counter_script": "<3-4 sentences — actionable rep script citing specific Zenpep advantages>",
  "ai_supporting_materials": [
    {"title": "<material name>", "sku": "<sku or null>"}
  ]
}

Rules:
- title: be specific, e.g. "Creon gaining share — 11 HCPs affected in Midwest" not generic "Alert detected"
- description: mention competitor activity OR formulary change OR HCP detailing decline
- ai_counter_script: what the rep should say/do NOW — cite Zenpep microspheres, APEX trial, ZenConnect
- supporting materials: Zenpep-specific only (APEX Trial, ZenConnect, Competitive Positioning Guide, etc.)
- Return valid JSON only — no markdown, no explanation"""


def _build_prompt(alert) -> str:
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

    return f"""Severity         : {alert.severity}
Detection Method : {alert.detection_method}
Threat Type      : {threat}
Territory        : {territory}
Affected HCPs    : {alert.ai_affected_hcp_count}
Territory Reach  : {alert.ai_territory_reach}
Rx Risk          : {alert.ai_rx_risk}
Detected At      : {alert.detected_at}{extra}

Generate the 5 language fields as JSON."""


def enrich(alert) -> dict:
    """
    Returns 5 LLM-generated language fields for the alert.
    Cached per alert_id — GPT-4o called only once per process restart.
    """
    alert_id = alert.alert_id

    if alert_id in _CACHE:
        log.debug("Cache hit for %s", alert_id)
        return _CACHE[alert_id]

    result = _stub(alert) if settings.LLM_STUB_MODE else _call_gpt4o(alert)
    _CACHE[alert_id] = result
    return result


def _call_gpt4o(alert) -> dict:
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
            {"role": "user",   "content": _build_prompt(alert)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
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
