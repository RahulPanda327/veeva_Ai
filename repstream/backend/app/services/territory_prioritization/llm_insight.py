"""GPT-4o insight generation for Territory Prioritization."""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# In-process cache of generated insights, persisted to disk so warmed GPT-4o
# text survives uvicorn --reload restarts (no Redis in this deployment).
_INSIGHT_CACHE: Dict[str, Any] = {}
_CACHE_FILE = Path(__file__).resolve().parents[3] / ".insight_cache.json"   # backend/.insight_cache.json
_cache_io_lock = threading.Lock()


def _load_insight_cache() -> None:
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _INSIGHT_CACHE.update(json.load(f))
        logger.info("Loaded %d cached insights from %s", len(_INSIGHT_CACHE), _CACHE_FILE.name)
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load insight cache (%s).", exc)


def _save_insight_cache() -> None:
    try:
        with _cache_io_lock:
            tmp = _CACHE_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_INSIGHT_CACHE, f)
            os.replace(tmp, _CACHE_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save insight cache (%s).", exc)


_load_insight_cache()

_SYSTEM = (
    "You are a pharmaceutical sales intelligence assistant for ZENPEP (pancrelipase). "
    "Write concise, actionable insights for pharma sales reps. "
    "Never fabricate drug names, indications, or patient data. "
    "Respond ONLY with valid JSON — no markdown, no extra text."
)

_PROMPT = """Generate a 3-4 sentence (60-100 words) AI insight for a pharma rep visiting this HCP.
Cite this HCP's OWN numbers (trend %, Rx counts, dates, specialty) so the insight is clearly specific to them — not generic advice.
Cover, across the 3-4 sentences: (1) their current Rx trend/volume this quarter vs prior quarter, (2) competitor activity/share if relevant, (3) call/engagement history context, (4) a specific, actionable recommendation for this visit.
If you address the HCP by name, use their REAL name exactly as given below ("{hcp_name}") — never a placeholder like [HCP Name] or [Last Name].

HCP profile:
- Name: {hcp_name}
- Specialty: {specialty} | Location: {city_state}
- Rx trend this quarter: {rx_trend_pct:+.1f}% ({trend_direction})
- Current-quarter Rx: {rx_q1:.0f} | Prior-quarter: {rx_q4:.0f}
- Most recent Rx: {last_rx_date}
- Competitor brand share: {competitor_brand_share:.0%} (competitor: {competitor_brand})
- Predicted next-quarter Rx: {predicted_q}
- Last call: {last_call_str} | Outcome: {last_call_outcome}
- AI priority score: {ai_priority_score:.0f}/100 | Tier: {tier}
- Engagement category: {engagement_category} | Urgency: {urgency}
- HCP segment: {segment}
- Peer intro hint: {peer_hint}

Respond ONLY with this JSON:
{{"insight": "<3-4 sentence insight citing this HCP's specific numbers/dates>", "highlight": "<3-8 word key phrase to show in green>"}}"""


# ── Rule-based fallback (no API call) ─────────────────────────────────────────

def _rule_based_insight(hcp: Dict) -> Tuple[str, Optional[str]]:
    trend  = hcp.get("ai_rx_trend_direction", "Stable")
    cat    = hcp.get("ai_engagement_category", "STABLE")
    comp   = hcp.get("competitor_brand_share", 0.0)
    peer   = hcp.get("ai_peer_match_hint")
    rx_q1  = hcp.get("rx_q1", 0)
    rx_q4  = hcp.get("rx_q4", 0)
    days   = hcp.get("days_since_last_call")
    specialty = hcp.get("specialty") or "this specialty"
    call_str  = f"Last contacted {days} days ago." if days is not None else "No recent call activity on file."

    if cat == "NEW_WRITER":
        intro = f" {peer}." if peer else ""
        return (
            f"New to territory as a {specialty} prescriber — no established Rx history yet.{intro} "
            f"Peer network signals suggest strong affinity for ZENPEP based on similar prescribers. "
            f"{call_str} Prioritize an introductory visit this week to establish the relationship.",
            peer or "new writer opportunity",
        )
    if cat == "LAPSED_RECOVERABLE":
        return (
            f"Lapsed prescriber with {rx_q4:.0f} Rx in the prior quarter but only {rx_q1:.0f} this quarter. "
            f"Historical volume suggests recoverable prescribing behavior rather than permanent attrition. "
            f"{call_str} Re-engagement this week could recover lost volume before the quarter closes.",
            "re-engagement this week",
        )
    if cat == "AT_RISK":
        pct = round(comp * 100)
        return (
            f"Rx volume has moved from {rx_q4:.0f} to {rx_q1:.0f} this quarter, a {trend.lower()} trend. "
            f"Competitor brand share is at {pct}% and rising, putting this account at risk. "
            f"{call_str} Immediate counter-detailing is needed to protect remaining volume.",
            "immediate counter-detailing",
        )
    if cat == "ACTIVE_HIGH_VALUE" and trend == "Improving":
        return (
            f"Rx volume is trending upward this quarter, from {rx_q4:.0f} to {rx_q1:.0f}. "
            f"Competitor brand share is declining, indicating growing preference for ZENPEP among this {specialty} prescriber. "
            f"{call_str} High conversion potential — consider expanding the conversation to additional patient segments.",
            "High conversion potential",
        )
    if trend == "Declining":
        return (
            f"Rx volume is declining this quarter, from {rx_q4:.0f} to {rx_q1:.0f}. "
            f"This {specialty} prescriber may be shifting share to a competitor or reducing overall prescribing. "
            f"{call_str} Schedule a maintenance call before end of month to understand the cause and re-engage.",
            "schedule maintenance call",
        )
    return (
        f"Stable prescriber with consistent Rx activity this quarter ({rx_q1:.0f} Rx, prior quarter {rx_q4:.0f}). "
        f"No significant competitor pressure detected for this {specialty} account. "
        f"{call_str} Consider a routine maintenance call this month to reinforce the relationship.",
        "consistent Rx activity",
    )


# ── Direct GPT-4o call (bypasses Redis, uses in-memory cache) ─────────────────

def _build_prompt(hcp: Dict) -> str:
    last_call_str = str(hcp.get("last_call_date")) if hcp.get("last_call_date") else "no recent call"
    pred_q = hcp.get("ai_predicted_next_q_rx")
    city_state = ", ".join(p for p in (hcp.get("city"), hcp.get("state")) if p) or "unknown"
    return _PROMPT.format(
        hcp_name=(hcp.get("name") or "").strip() or "this HCP",
        specialty=hcp.get("specialty") or "unknown",
        city_state=city_state,
        rx_trend_pct=hcp.get("rx_trend_pct", 0.0),
        trend_direction=hcp.get("ai_rx_trend_direction", "Stable"),
        competitor_brand_share=hcp.get("competitor_brand_share", 0.0),
        competitor_brand=hcp.get("competitor_brand") or "unknown",
        rx_q1=hcp.get("rx_q1", 0.0),
        rx_q4=hcp.get("rx_q4", 0.0),
        last_rx_date=hcp.get("last_rx_date") or "none recorded",
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
            max_tokens=220,
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


_WARM_MAX_WORKERS = 16
_WARM_SAVE_EVERY = 25   # persist to disk every N generated insights


def _insight_cache_key(hcp: Dict) -> str:
    return f"insight_{hcp['hcp_id']}_{round(hcp.get('ai_priority_score', 0))}"


def generate_insights_for_list(hcps: List[Dict]) -> List[Dict]:
    """
    List view — READ ONLY. Never calls the LLM inline (that would block the
    request and could take minutes for a large territory). For each HCP:
      • if the background warmer has already produced a real GPT-4o insight for
        this HCP at its current priority score, serve that from cache;
      • otherwise fall back to the instant rule-based template.
    Real insights fill in progressively as warm_insights() completes in the
    background — subsequent page loads show more genuine GPT-4o text.
    """
    for hcp in hcps:
        cached = _INSIGHT_CACHE.get(_insight_cache_key(hcp))
        if cached:
            hcp["ai_generated_insight"] = cached["insight"]
            hcp["ai_insight_highlight"] = cached["highlight"]
        else:
            insight, highlight = _rule_based_insight(hcp)
            hcp["ai_generated_insight"] = insight
            hcp["ai_insight_highlight"] = highlight

        if hcp.get("ai_generated_insight") and "AI_INSIGHT" not in hcp.get("analysis_badges", []):
            hcp.setdefault("analysis_badges", []).append("AI_INSIGHT")

    return hcps


def count_uncached_insights(hcps: List[Dict]) -> int:
    """How many HCPs still need a real GPT-4o insight generated."""
    return sum(1 for hcp in hcps if _insight_cache_key(hcp) not in _INSIGHT_CACHE)


def warm_insights(hcps: List[Dict]) -> int:
    """
    Background pre-generation: produce a real GPT-4o insight for every HCP that
    isn't cached yet, in parallel, writing results into _INSIGHT_CACHE. Intended
    to run in a daemon thread (see the router's warmer), NOT in the request path.
    _call_gpt4o handles its own caching and falls back to the template on error.
    Returns the number of HCPs generated.
    """
    pending = [hcp for hcp in hcps if _insight_cache_key(hcp) not in _INSIGHT_CACHE]
    if not pending:
        return 0
    done = 0
    with ThreadPoolExecutor(max_workers=_WARM_MAX_WORKERS) as pool:
        futures = [pool.submit(_call_gpt4o, hcp) for hcp in pending]   # writes into _INSIGHT_CACHE
        for future in as_completed(futures):
            future.result()
            done += 1
            if done % _WARM_SAVE_EVERY == 0:
                _save_insight_cache()   # survive a mid-warm restart
                logger.info("Insight warm progress: %d/%d", done, len(pending))
    _save_insight_cache()
    logger.info("Warmed %d GPT-4o insights.", len(pending))
    return len(pending)


def regenerate_single_hcp_insight(hcp: Dict) -> Dict:
    # Clear cache to force fresh generation
    cache_key = f"insight_{hcp['hcp_id']}_{round(hcp.get('ai_priority_score', 0))}"
    _INSIGHT_CACHE.pop(cache_key, None)
    insight, highlight = _call_gpt4o(hcp)
    _save_insight_cache()
    return {
        "hcp_id":               hcp["hcp_id"],
        "ai_generated_insight": insight,
        "ai_insight_highlight": highlight,
        "generated_at":         datetime.now(timezone.utc).isoformat(),
        "cached":               False,
    }
