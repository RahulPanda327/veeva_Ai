"""Warm approach brief generation for new writer candidates (Module 2).

List view: rule-based instant warm approach (no API calls).
On-demand: GPT-4o full brief via 'Generate Approach Brief' button.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

_BRIEF_CACHE: Dict[str, Dict] = {}

_SYSTEM = (
    "You are a pharmaceutical sales training coach for ZENPEP (pancrelipase). "
    "Write warm, professional, compliant outreach briefs for sales reps. "
    "Never invent clinical data or make comparative efficacy claims. "
    "Respond ONLY with valid JSON — no markdown, no extra text."
)

_PROMPT = """Generate a warm approach brief for a pharma rep visiting {hcp_name}.

Profile:
- Specialty: {specialty} at {hospital}
- Peer connection: {peer_str}
- Competitor Rx: {competitor_brand} at {competitor_volume:.0f} Rx/qtr
- ICD-10 matches: {icd_str}
- Total in-class Rx: {in_class_rx:.0f}/qtr

Respond ONLY with this JSON:
{{"brief": "<2-sentence warm outreach brief>", "highlight": "<4-6 word key phrase>"}}"""


# ── Rule-based warm approach (list view, instant) ─────────────────────────────

def _rule_based_warm_approach(hcp: Dict) -> Tuple[str, Optional[str]]:
    peer  = hcp.get("ai_peer_name") or hcp.get("peer_name")
    score = float(hcp.get("ai_peer_match_score", 0) or 0)
    comp  = hcp.get("competitor_brand", "a competitor brand")
    vol   = float(hcp.get("competitor_volume", 0) or 0)
    icd   = hcp.get("ai_icd10_matched_codes") or hcp.get("matched_icd10_codes", [])

    if peer and score >= 70:
        return (
            f"Connected to {peer}. Prescribing {comp} in same class at {int(vol)} Rx/qtr — strong conversion opportunity.",
            f"Connected to {peer}",
        )
    if icd:
        codes = " | ".join(icd[:2])
        return (
            f"ICD-10 overlap ({codes}) confirms in-class prescribing activity. Peer network shows {int(score)}% match affinity.",
            f"{int(score)}% match affinity",
        )
    if vol > 20:
        return (
            f"High in-class {comp} volume ({int(vol)} Rx/qtr) — no current ZENPEP Rx. First-visit conversion window open.",
            "conversion window open",
        )
    return (
        f"Non-writer prescribing {comp} in same class. Peer network confirms territory alignment.",
        "territory alignment confirmed",
    )


# ── Direct GPT-4o call (on-demand only) ───────────────────────────────────────

def _call_gpt4o(hcp: Dict) -> Tuple[str, Optional[str]]:
    cache_key = f"brief_{hcp['hcp_id']}"
    if cache_key in _BRIEF_CACHE:
        c = _BRIEF_CACHE[cache_key]
        return c["brief"], c["highlight"]

    if settings.LLM_STUB_MODE:
        brief, highlight = _rule_based_warm_approach(hcp)
        _BRIEF_CACHE[cache_key] = {"brief": brief, "highlight": highlight}
        return brief, highlight

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=settings.OPENAI_MAX_RETRIES,
            timeout=settings.OPENAI_TIMEOUT,
        )
        peer = hcp.get("ai_peer_name") or hcp.get("peer_name")
        peer_str = f"connected via {peer} (existing ZENPEP writer)" if peer else "no current peer connection identified"
        icd = hcp.get("ai_icd10_matched_codes") or hcp.get("matched_icd10_codes", [])
        icd_str = ", ".join(icd) if icd else "none matched"

        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _PROMPT.format(
                    hcp_name=hcp.get("name", "this physician"),
                    specialty=hcp.get("specialty", "unknown"),
                    hospital=hcp.get("affiliated_hospital", "unknown"),
                    peer_str=peer_str,
                    competitor_brand=hcp.get("competitor_brand", "a competitor brand"),
                    competitor_volume=float(hcp.get("competitor_volume", 0) or 0),
                    icd_str=icd_str,
                    in_class_rx=float(hcp.get("in_class_rx_q1", 0) or 0),
                )},
            ],
            max_tokens=150,
            temperature=0.4,
        )
        data = json.loads(resp.choices[0].message.content)
        brief     = str(data.get("brief", ""))
        highlight = data.get("highlight")
    except Exception as exc:
        logger.warning("GPT-4o approach brief failed for %s: %s", hcp.get("hcp_id"), exc)
        brief, highlight = _rule_based_warm_approach(hcp)

    _BRIEF_CACHE[cache_key] = {"brief": brief, "highlight": highlight}
    return brief, highlight


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_warm_approach_for_list(candidates: List[Dict]) -> List[Dict]:
    """Enrich all candidates with rule-based warm approach text (instant, no API calls)."""
    for hcp in candidates:
        text, highlight = _rule_based_warm_approach(hcp)
        hcp["ai_warm_approach_text"] = text
        hcp["ai_approach_highlight"] = highlight
    return candidates


def generate_approach_brief(hcp: Dict) -> str:
    """On-demand: GPT-4o full approach brief."""
    brief, _ = _call_gpt4o(hcp)
    return brief


def build_approach_brief_response(hcp: Dict, brief_text: str) -> Dict:
    cache_key = f"brief_{hcp['hcp_id']}"
    _BRIEF_CACHE.pop(cache_key, None)
    brief, highlight = _call_gpt4o(hcp)
    return {
        "hcp_id":      hcp["hcp_id"],
        "brief_text":  brief,
        "peer_name":   hcp.get("ai_peer_name") or hcp.get("peer_name"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached":      False,
    }
