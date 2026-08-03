"""
GPT-4o explanation of the ai_score — Territory Prioritization.

ai_score is a deterministic composite (see ai_score.py):
    score = trx_growth_norm x 0.60 + interaction_impact x 0.30 + decile_norm x 0.10

ai_score_reason explains WHY that particular number came out, in one or two
plain sentences, naming the components that actually moved it. The exact
point contribution of each component is computed here (not by the LLM) and
handed to GPT-4o so the text can never disagree with the arithmetic.

Mirrors llm_insight.py: separate on-disk cache, instant rule-based fallback in
the request path, real GPT-4o text produced by a background warmer.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from app.config import settings
from app.services.territory_prioritization.ai_score import WEIGHTS
from app.utils.cache_paths import cache_file

logger = logging.getLogger(__name__)

# Kept separate from insight_cache.json on purpose — the insight cache holds
# thousands of already-warmed GPT-4o insights, and sharing a key would throw
# them all away on the first deploy of this feature.
_REASON_CACHE: Dict[str, str] = {}
_CACHE_FILE = cache_file("score_reason_cache.json")   # backend/cache/score_reason_cache.json
_cache_io_lock = threading.Lock()


def _load_reason_cache() -> None:
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _REASON_CACHE.update(json.load(f))
        logger.info("Loaded %d cached score reasons from %s", len(_REASON_CACHE), _CACHE_FILE.name)
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load score reason cache (%s).", exc)


def _save_reason_cache() -> None:
    try:
        with _cache_io_lock:
            tmp = _CACHE_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_REASON_CACHE, f)
            os.replace(tmp, _CACHE_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save score reason cache (%s).", exc)


_load_reason_cache()


# ── Component breakdown (arithmetic, not LLM) ─────────────────────────────────

_MAX_POINTS = {k: round(v * 100, 1) for k, v in WEIGHTS.items()}   # 60.0 / 30.0 / 10.0


def _strength(norm: float) -> str:
    """Qualitative read of a component's normalized 0-100 value — this, not the raw
    point total, is what the LLM is asked to reason about."""
    if norm >= 70:
        return "strong"
    if norm >= 45:
        return "moderate"
    if norm >= 25:
        return "weak"
    return "very weak"


def _growth_strength(trend_pct: float) -> str:
    """Rx growth described the way a rep reads it, off the raw trend percentage."""
    if trend_pct >= 25:
        return "strong growth"
    if trend_pct >= 10:
        return "moderate growth"
    if trend_pct > -5:
        return "roughly flat"
    if trend_pct > -20:
        return "declining"
    return "sharply declining"


def _breakdown(hcp: Dict) -> List[Dict]:
    """Each scoring component's actual point contribution to the composite,
    strongest first. points = normalized_value x weight."""
    parts = [
        {
            "label":  "Rx growth",
            "norm":   float(hcp.get("ai_trx_growth_norm") or 0.0),
            "weight": WEIGHTS["trx_growth"],
            "detail": f"{hcp.get('rx_trend_pct', 0.0):+.1f}% quarter-over-quarter",
            # Described off the raw trend, not the normalized value: normalization
            # spans -50%..+150%, so +22% lands low on that scale even though no rep
            # would call +22% growth "weak".
            "strength": _growth_strength(float(hcp.get("rx_trend_pct") or 0.0)),
        },
        {
            "label":  "engagement",
            "norm":   float(hcp.get("ai_interaction_impact") or 0.0),
            "weight": WEIGHTS["interaction_impact"],
            "detail": _engagement_detail(hcp),
        },
        {
            "label":  "decile rank",
            "norm":   float(hcp.get("ai_decile_score_norm") or 0.0),
            "weight": WEIGHTS["decile_score"],
            "detail": (f"decile {hcp['decile_rank']}"
                       if hcp.get("decile_rank") else "no decile on file (neutral 50)"),
        },
    ]
    for p in parts:
        p["points"] = round(p["norm"] * p["weight"], 1)
        p["max"]    = round(p["weight"] * 100, 1)
        p.setdefault("strength", _strength(p["norm"]))
    return sorted(parts, key=lambda p: -p["points"])


def _engagement_detail(hcp: Dict) -> str:
    days  = hcp.get("days_since_last_call")
    calls = hcp.get("call_count_90d", 0)
    when  = f"last call {days}d ago" if days is not None else "no call on file"
    out   = hcp.get("last_call_outcome")
    tail  = f", outcome {out.lower()}" if out else ""
    return f"{when}, {calls} call(s) in 90d{tail}"


# ── Rule-based fallback (no API call) ─────────────────────────────────────────

def _rule_based_reason(hcp: Dict) -> str:
    """Instant, fully factual explanation built straight from the breakdown.
    Used in the request path and whenever the LLM is unavailable."""
    score = hcp.get("ai_priority_score", 0.0)
    tier  = hcp.get("ai_priority_tier", "LOW")
    parts = _breakdown(hcp)
    top, mid, low = parts[0], parts[1], parts[2]
    return (
        f"Scored {score:.2f}% ({tier}). "
        f"{top['label'].capitalize()} contributes the most at {top['points']:.1f} of {top['max']:.0f} points "
        f"({top['detail']}); {mid['label']} adds {mid['points']:.1f} of {mid['max']:.0f} ({mid['detail']}); "
        f"{low['label']} adds {low['points']:.1f} of {low['max']:.0f} ({low['detail']})."
    )


# ── GPT-4o call ───────────────────────────────────────────────────────────────

_SYSTEM = (
    "You explain how a pharmaceutical sales priority score was calculated. "
    "Use ONLY the numbers given to you — never invent or re-derive figures, and never "
    "round a component to a different value than the one supplied. "
    "Respond ONLY with valid JSON — no markdown, no extra text."
)

_PROMPT = """Explain in 1-2 sentences (25-45 words) why this HCP landed at an AI priority score of {score:.2f}% ({tier}).

The three scoring components, ALREADY RANKED by how much each moved this score:
{components}

Rules:
- Start with the PRIMARY component and say what about this HCP made it {tier_word}.
- Mention the SECONDARY component briefly. Only mention MINOR if it is notably strong or weak.
- Do NOT quote any point totals, weights, or percentages — describe the behaviour, not the arithmetic.
  ("decile 2" and "last call 12d ago" are facts about the HCP and are fine to reference.)
- Plain language for a pharma sales rep. No formulas, no bullet points.

Respond ONLY with this JSON:
{{"reason": "<1-2 sentence explanation of this score>"}}"""


def _build_prompt(hcp: Dict) -> str:
    ranks = ["PRIMARY", "SECONDARY", "MINOR"]
    lines = [
        f"- {rank} — {p['label']}: {p['strength']} ({p['detail']})"
        for rank, p in zip(ranks, _breakdown(hcp))
    ]
    tier = hcp.get("ai_priority_tier", "LOW")
    return _PROMPT.format(
        score=hcp.get("ai_priority_score", 0.0),
        tier=tier,
        tier_word="a priority" if tier == "HIGH" else "rank lower",
        components="\n".join(lines),
    )


def _reason_cache_key(hcp: Dict) -> str:
    # Score is part of the key so a re-scored HCP gets a fresh explanation.
    return f"reason_{hcp['hcp_id']}_{hcp.get('ai_priority_score', 0):.2f}"


def _call_gpt4o(hcp: Dict) -> str:
    cache_key = _reason_cache_key(hcp)
    cached = _REASON_CACHE.get(cache_key)
    if cached:
        return cached

    if settings.LLM_STUB_MODE:
        reason = _rule_based_reason(hcp)
        _REASON_CACHE[cache_key] = reason
        return reason

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
            temperature=0.2,
        )
        reason = str(json.loads(resp.choices[0].message.content).get("reason", "")).strip()
        if not reason:
            raise ValueError("empty reason in LLM response")
    except Exception as exc:  # noqa: BLE001
        logger.warning("GPT-4o score reason failed for %s: %s", hcp["hcp_id"], exc)
        reason = _rule_based_reason(hcp)

    _REASON_CACHE[cache_key] = reason
    return reason


# ── Public functions ──────────────────────────────────────────────────────────

def generate_score_reason(hcp: Dict) -> str:
    return _call_gpt4o(hcp)


def generate_score_reasons_for_list(hcps: List[Dict]) -> List[Dict]:
    """List view — READ ONLY, same contract as generate_insights_for_list().
    Serves warmed GPT-4o text when present, otherwise the instant rule-based
    explanation. Never calls the LLM inline."""
    for hcp in hcps:
        hcp["ai_score_reason"] = (
            _REASON_CACHE.get(_reason_cache_key(hcp)) or _rule_based_reason(hcp)
        )
    return hcps


def count_uncached_reasons(hcps: List[Dict]) -> int:
    return sum(1 for hcp in hcps if _reason_cache_key(hcp) not in _REASON_CACHE)


_WARM_MAX_WORKERS = 16
_WARM_SAVE_EVERY = 25


def warm_score_reasons(hcps: List[Dict]) -> int:
    """Background pre-generation for every HCP without a cached reason.
    Runs in a daemon thread, never in the request path."""
    pending = [hcp for hcp in hcps if _reason_cache_key(hcp) not in _REASON_CACHE]
    if not pending:
        return 0
    done = 0
    with ThreadPoolExecutor(max_workers=_WARM_MAX_WORKERS) as pool:
        futures = [pool.submit(_call_gpt4o, hcp) for hcp in pending]   # writes into _REASON_CACHE
        for future in as_completed(futures):
            future.result()
            done += 1
            if done % _WARM_SAVE_EVERY == 0:
                _save_reason_cache()
                logger.info("Score reason warm progress: %d/%d", done, len(pending))
    _save_reason_cache()
    logger.info("Warmed %d GPT-4o score reasons.", len(pending))
    return len(pending)


def regenerate_score_reason(hcp: Dict) -> str:
    """Force a fresh GPT-4o explanation, bypassing the cache."""
    _REASON_CACHE.pop(_reason_cache_key(hcp), None)
    reason = _call_gpt4o(hcp)
    _save_reason_cache()
    return reason
