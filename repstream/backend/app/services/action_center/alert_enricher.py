"""
Alert enricher — one GPT-4o call per alert generates all 4 missing fields:
  - description           (full alert narrative)
  - ai_icd10_codes_affected
  - ai_prescribing_drift_note
  - ai_supporting_materials

Results cached in-memory (per process) to avoid repeated GPT-4o calls.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from openai import OpenAI

from app.config import settings

log = logging.getLogger(__name__)

# In-memory cache: alert_id → enriched fields dict
_CACHE: Dict[str, Any] = {}

_SYSTEM = """You are a pharmaceutical sales intelligence AI for Zenpep (pancrelipase).
Given a sales alert, return a JSON object with EXACTLY these 4 keys:

{
  "description": "<2 sentence narrative — what happened, where, how many HCPs, date range>",
  "ai_prescribing_drift_note": "<1-2 sentences — what changed in prescribing behavior and why>",
  "ai_icd10_codes_affected": [
    {"code": "<ICD-10 code>", "label": "<condition name>", "hcp_count": <int>}
  ],
  "ai_supporting_materials": [
    {"title": "<material name>", "sku": "<sku or null>"}
  ]
}

Rules:
- description must mention competitor activity OR formulary change OR HCP drift
- ICD-10 codes must be relevant to pancreatic conditions (K86.81, K86.1, K86.0, C25.0, C25.9, K90.3)
- supporting materials must be Zenpep-specific (APEX Trial, ZenConnect, Competitive Positioning Guide etc.)
- Return valid JSON only — no markdown, no explanation"""


def _build_prompt(alert) -> str:
    return f"""Severity       : {alert.severity}
Detection Type : {alert.detection_method}
Title          : {alert.title}
Territory      : {alert.territory_name or alert.territory_id}
Affected HCPs  : {alert.ai_affected_hcp_count}
Territory Reach: {alert.ai_territory_reach}
Rx Risk        : {alert.ai_rx_risk}
Counter Script : {alert.ai_counter_script}
Detected At    : {alert.detected_at}

Generate the 4 missing fields as JSON."""


def enrich(alert) -> dict:
    """
    Returns enriched fields for the alert.
    Uses in-memory cache — GPT-4o called only once per alert per process restart.
    """
    alert_id = alert.alert_id

    if alert_id in _CACHE:
        log.debug("Cache hit for %s", alert_id)
        return _CACHE[alert_id]

    if settings.LLM_STUB_MODE:
        result = _stub(alert)
    else:
        result = _call_gpt4o(alert)

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
    return {
        "description": (
            f"Unusual prescribing pattern detected across {alert.ai_affected_hcp_count} HCPs "
            f"in {alert.territory_name or alert.territory_id}. "
            f"Detected on {alert.detected_at}."
        ),
        "ai_prescribing_drift_note": (
            f"{alert.ai_affected_hcp_count} HCPs showing Rx volume reduction "
            "correlated with increased competitor activity in the territory."
        ),
        "ai_icd10_codes_affected": [
            {"code": "K86.81", "label": "Exocrine Pancreatic Insufficiency", "hcp_count": int(alert.ai_affected_hcp_count or 0)},
            {"code": "K86.1",  "label": "Chronic Pancreatitis",              "hcp_count": max(1, int(alert.ai_affected_hcp_count or 0) // 2)},
        ],
        "ai_supporting_materials": [
            {"title": "Zenpep Competitive Positioning Guide", "sku": "ZPP-COMP-001"},
            {"title": "ZenConnect Enrollment Form",           "sku": "ZPP-ZENCONNECT"},
        ],
    }


# Keep old signature for /enrich endpoint compatibility
def enrich_alert(db, alert) -> dict:
    return enrich(alert)
