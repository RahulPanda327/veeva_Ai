"""Generate per-HCP AI insight text + highlight phrase via GPT-4o for Module 1."""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from app.config import settings
from app.utils.llm_client import call_llm

logger = logging.getLogger(__name__)

_INSIGHT_SYSTEM = (
    "You are a pharmaceutical sales intelligence assistant. "
    "Write concise, actionable insights for pharma sales reps. "
    "Never fabricate drug names, indications, or patient data. "
    "Always respond with valid JSON only — no markdown, no extra text."
)

_INSIGHT_PROMPT_TEMPLATE = """Given this HCP profile, write a single-sentence (max 25 words) actionable insight for a pharma sales rep.

HCP data:
- Rx trend this quarter: {rx_trend_pct:+.1f}%
- Competitor brand share: {competitor_brand_share:.0%} (competitor: {competitor_brand})
- Current-quarter Rx: {rx_q1:.0f}
- Last call date: {last_call_str}
- Last call outcome: {last_call_outcome}
- AI priority score: {ai_priority_score:.0f}/100
- HCP segment: {segment}

Respond ONLY with this JSON (no markdown):
{{
  "insight": "<your 1-sentence insight here>",
  "highlight": "<3-8 word key phrase from the insight to emphasize in green>"
}}"""


def _build_prompt(hcp: Dict) -> str:
    last_call_str = str(hcp["last_call_date"]) if hcp.get("last_call_date") else "no recent call on record"
    return _INSIGHT_PROMPT_TEMPLATE.format(
        rx_trend_pct=hcp.get("rx_trend_pct", 0.0),
        competitor_brand_share=hcp.get("competitor_brand_share", 0.0),
        competitor_brand=hcp.get("competitor_brand") or "unknown",
        rx_q1=hcp.get("rx_q1", 0.0),
        last_call_str=last_call_str,
        last_call_outcome=hcp.get("last_call_outcome") or "unknown",
        ai_priority_score=hcp.get("ai_priority_score", 0.0),
        segment=hcp.get("segment") or "unclassified",
    )


def _parse_insight_response(raw: str) -> Tuple[str, Optional[str]]:
    """Parse JSON response from LLM. Returns (insight_text, highlight_phrase)."""
    try:
        data = json.loads(raw)
        return str(data.get("insight", raw)), data.get("highlight")
    except (json.JSONDecodeError, ValueError):
        # Fallback: treat the whole response as plain insight text
        return raw.strip(), None


def generate_hcp_insight(hcp: Dict) -> Tuple[str, Optional[str]]:
    """Return (insight_text, highlight_phrase) for a single HCP feature dict."""
    raw = call_llm(
        prompt=_build_prompt(hcp),
        system_message=_INSIGHT_SYSTEM,
        cache_ttl=settings.CACHE_TTL_INSIGHT,
        max_tokens=120,
        temperature=0.3,
    )
    return _parse_insight_response(raw)


def generate_insights_for_list(hcps: list[Dict]) -> list[Dict]:
    """Add ai_generated_insight + ai_insight_highlight to each HCP dict."""
    for hcp in hcps:
        try:
            insight, highlight = generate_hcp_insight(hcp)
            hcp["ai_generated_insight"] = insight
            hcp["ai_insight_highlight"] = highlight
        except Exception as exc:
            logger.warning("LLM insight failed for hcp %s: %s", hcp["hcp_id"], exc)
            hcp["ai_generated_insight"] = None
            hcp["ai_insight_highlight"] = None
    return hcps


def regenerate_single_hcp_insight(hcp: Dict) -> Dict:
    insight, highlight = generate_hcp_insight(hcp)
    return {
        "hcp_id": hcp["hcp_id"],
        "ai_generated_insight": insight,
        "ai_insight_highlight": highlight,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }
