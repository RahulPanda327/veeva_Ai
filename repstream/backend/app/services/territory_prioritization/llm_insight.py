"""GPT-4o insight generation for Territory Prioritization."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# In-process cache — survives across requests in the same worker process
_INSIGHT_CACHE: Dict[str, Any] = {}

_SYSTEM = (
    "You are a pharmaceutical sales intelligence assistant for ZENPEP (pancrelipase). "
    "Write concise, actionable insights for pharma sales reps. "
    "Never fabricate drug names, indications, or patient data. "
    "Respond ONLY with valid JSON — no markdown, no extra text."
)

_PROMPT = """Generate a single-sentence (max 25 words) AI insight for a pharma rep visiting this HCP.

HCP profile:
- Rx trend this quarter: {rx_trend_pct:+.1f}% ({trend_direction})
- Competitor brand share: {competitor_brand_share:.0%} (competitor: {competitor_brand})
- Current-quarter Rx: {rx_q1:.0f} | Prior-quarter: {rx_q4:.0f}
- Predicted next-quarter Rx: {predicted_q}
- Last call: {last_call_str} | Outcome: {last_call_outcome}
- AI priority score: {ai_priority_score:.0f}/100 | Tier: {tier}
- Engagement category: {engagement_category} | Urgency: {urgency}
- HCP segment: {segment}
- Peer intro hint: {peer_hint}

Respond ONLY with this JSON:
{{"insight": "<your 1-sentence actionable insight>", "highlight": "<3-8 word key phrase to show in green>"}}"""


# ── Rule-based fallback (no API call) ─────────────────────────────────────────

def _rule_based_insight(hcp: Dict) -> Tuple[str, Optional[str]]:
    trend  = hcp.get("ai_rx_trend_direction", "Stable")
    cat    = hcp.get("ai_engagement_category", "STABLE")
    comp   = hcp.get("competitor_brand_share", 0.0)
    peer   = hcp.get("ai_peer_match_hint")
    rx_q1  = hcp.get("rx_q1", 0)
    days   = hcp.get("days_since_last_call")

    if cat == "NEW_WRITER":
        intro = f" {peer}." if peer else ""
        return (f"New to territory — peer network shows affinity for ZENPEP.{intro} Priority this week.",
                peer or "new writer opportunity")
    if cat == "LAPSED_RECOVERABLE":
        return ("Lapsed prescriber showing historical Rx volume — re-engagement this week could recover volume.",
                "re-engagement this week")
    if cat == "AT_RISK":
        pct = round(comp * 100)
        return (f"Competitor brand share at {pct}% with declining Zenpep Rx — immediate counter-detailing needed.",
                "immediate counter-detailing")
    if cat == "ACTIVE_HIGH_VALUE" and trend == "Improving":
        return ("Rx volume trending upward this quarter. Competitor brand share declining. High conversion potential.",
                "High conversion potential")
    if trend == "Declining":
        return ("Rx volume declining this quarter — schedule maintenance call before end of month.",
                "schedule maintenance call")
    return ("Stable prescriber with consistent Rx activity. Consider maintenance call this month.",
            "consistent Rx activity")


# ── Direct GPT-4o call (bypasses Redis, uses in-memory cache) ─────────────────

def _build_prompt(hcp: Dict) -> str:
    last_call_str = str(hcp.get("last_call_date")) if hcp.get("last_call_date") else "no recent call"
    pred_q = hcp.get("ai_predicted_next_q_rx")
    return _PROMPT.format(
        rx_trend_pct=hcp.get("rx_trend_pct", 0.0),
        trend_direction=hcp.get("ai_rx_trend_direction", "Stable"),
        competitor_brand_share=hcp.get("competitor_brand_share", 0.0),
        competitor_brand=hcp.get("competitor_brand") or "unknown",
        rx_q1=hcp.get("rx_q1", 0.0),
        rx_q4=hcp.get("rx_q4", 0.0),
        predicted_q=f"{pred_q:.0f} Rx" if pred_q is not None else "N/A",
        last_call_str=last_call_str,
        last_call_outcome=hcp.get("last_call_outcome") or "unknown",
        ai_priority_score=hcp.get("ai_priority_score", 0.0),
        tier=hcp.get("ai_priority_tier", "LOW"),
        engagement_category=hcp.get("ai_engagement_category") or "STABLE",
        urgency=hcp.get("ai_engagement_urgency") or "This Month",
        segment=hcp.get("segment") or "unclassified",
        peer_hint=hcp.get("ai_peer_match_hint") or "none",
    )


def _call_gpt4o(hcp: Dict) -> Tuple[str, Optional[str]]:
    """Direct OpenAI call with in-memory cache — no Redis dependency."""
    cache_key = f"insight_{hcp['hcp_id']}_{round(hcp.get('ai_priority_score', 0))}"
    if cache_key in _INSIGHT_CACHE:
        c = _INSIGHT_CACHE[cache_key]
        return c["insight"], c["highlight"]

    if settings.LLM_STUB_MODE:
        insight, highlight = _rule_based_insight(hcp)
        _INSIGHT_CACHE[cache_key] = {"insight": insight, "highlight": highlight}
        return insight, highlight

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=settings.OPENAI_MAX_RETRIES,
            timeout=settings.OPENAI_TIMEOUT,
        )
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": _build_prompt(hcp)},
            ],
            max_tokens=120,
            temperature=0.3,
        )
        data = json.loads(resp.choices[0].message.content)
        insight   = str(data.get("insight", ""))
        highlight = data.get("highlight")
    except Exception as exc:
        logger.warning("GPT-4o insight failed for %s: %s", hcp["hcp_id"], exc)
        insight, highlight = _rule_based_insight(hcp)

    _INSIGHT_CACHE[cache_key] = {"insight": insight, "highlight": highlight}
    return insight, highlight


# ── Public functions ──────────────────────────────────────────────────────────

def generate_hcp_insight(hcp: Dict) -> Tuple[str, Optional[str]]:
    return _call_gpt4o(hcp)


def generate_insights_for_list(hcps: List[Dict]) -> List[Dict]:
    """
    List view: use rule-based insights only (instant, no API call).
    GPT-4o insights are generated on-demand via /hcp/{id}/insight endpoint.
    """
    for hcp in hcps:
        cache_key = f"insight_{hcp['hcp_id']}_{round(hcp.get('ai_priority_score', 0))}"
        if cache_key in _INSIGHT_CACHE:
            c = _INSIGHT_CACHE[cache_key]
            hcp["ai_generated_insight"] = c["insight"]
            hcp["ai_insight_highlight"] = c["highlight"]
        else:
            insight, highlight = _rule_based_insight(hcp)
            hcp["ai_generated_insight"] = insight
            hcp["ai_insight_highlight"] = highlight
            _INSIGHT_CACHE[cache_key] = {"insight": insight, "highlight": highlight}

        if hcp.get("ai_generated_insight") and "AI_INSIGHT" not in hcp.get("analysis_badges", []):
            hcp.setdefault("analysis_badges", []).append("AI_INSIGHT")

    return hcps


def regenerate_single_hcp_insight(hcp: Dict) -> Dict:
    # Clear cache to force fresh generation
    cache_key = f"insight_{hcp['hcp_id']}_{round(hcp.get('ai_priority_score', 0))}"
    _INSIGHT_CACHE.pop(cache_key, None)
    insight, highlight = _call_gpt4o(hcp)
    return {
        "hcp_id":               hcp["hcp_id"],
        "ai_generated_insight": insight,
        "ai_insight_highlight": highlight,
        "generated_at":         datetime.now(timezone.utc).isoformat(),
        "cached":               False,
    }
