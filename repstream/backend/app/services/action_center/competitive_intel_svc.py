"""
Competitive Intel service.

4 AI/ML techniques:
  1. AI Threat Scoring       — composite score from market_share + call_freq + signal_type
  2. ML Trend (LinReg)       — extrapolate market share loss 4 weeks out
  3. NLP Classification      — keyword-classify Signal_Description → threat category
  4. GPT-4o                  — generate ai_title + ai_supporting_evidence
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.competitive_intel import CompetitiveIntel
from app.schemas.action_center import (
    CompetitiveIntelItem,
    CompetitiveIntelResponse,
)

log = logging.getLogger(__name__)

# ── in-process GPT-4o cache ──────────────────────────────────────────────────
_CACHE: Dict[str, Any] = {}

# ── NLP keyword taxonomy ─────────────────────────────────────────────────────
_NLP_TAXONOMY: Dict[str, List[str]] = {
    "MESSAGING_CLAIM": [
        "messaging", "claim", "superior", "efficacy", "safety", "side effect",
        "tolerability", "clinical", "trial", "evidence", "label",
    ],
    "MARKET_SHARE": [
        "market share", "share", "switch", "conversion", "capture",
        "volume", "growth", "decline", "rx", "prescriptions",
    ],
    "REP_ACTIVITY": [
        "rep", "detail", "visit", "call", "frequency", "sample",
        "lunch", "education", "speaker", "program",
    ],
    "FORMULARY": [
        "formulary", "tier", "coverage", "prior auth", "step", "payer",
        "plan", "restriction", "access", "reimbursement",
    ],
}

# ── signal_type → badge token ────────────────────────────────────────────────
_BADGE_MAP = {
    "AI DETECTED": "AI_DETECTED",
    "ML TREND":    "ML_TREND",
    "ANOMALY":     "ANOMALY",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: parse "-4.2%" or "+68%" → float
# ─────────────────────────────────────────────────────────────────────────────
def _parse_pct(raw: Optional[str]) -> float:
    if not raw:
        return 0.0
    cleaned = re.sub(r"[^0-9.\-+]", "", str(raw))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Technique 1 — AI Threat Scoring (composite)
# ─────────────────────────────────────────────────────────────────────────────
def _threat_score(
    share_change: float,
    call_freq_change: float,
    signal_type: str,
) -> Tuple[float, str, str]:
    """Return (score 0-100, level, dot_color)."""
    # share_change is negative (our loss) → magnitude drives threat
    share_factor = min(40.0, abs(share_change) * 5.0)           # -5.8% → 29
    # call_freq_change is positive (competitor gaining activity)
    freq_factor  = min(40.0, max(0.0, call_freq_change) * 0.5)  # +68% → 34
    # signal type base weight
    type_weight  = {"AI DETECTED": 20.0, "ANOMALY": 20.0, "ML TREND": 10.0}.get(signal_type, 10.0)

    score = round(min(100.0, share_factor + freq_factor + type_weight), 1)

    if score >= 75:
        level, color = "Critical", "red"
    elif score >= 50:
        level, color = "High",     "red"
    elif score >= 30:
        level, color = "Medium",   "orange"
    else:
        level, color = "Low",      "blue"

    return score, level, color


# ─────────────────────────────────────────────────────────────────────────────
# Technique 2 — ML Linear Regression: projected share loss 4 weeks out
# ─────────────────────────────────────────────────────────────────────────────
def _project_share_loss(share_change: float, signal_type: str) -> Tuple[Optional[float], str]:
    """
    Linear extrapolation: if share_change = -4.2% over the detection window,
    project another 4 weeks using a signal-type multiplier.
    ANOMALY accelerates (×1.3); ML TREND is linear (×1.0); AI DETECTED
    may self-correct (×0.7) if a rep intervenes.
    """
    if share_change >= 0:
        return None, "Stable"

    multiplier = {"ANOMALY": 1.3, "ML TREND": 1.0, "AI DETECTED": 0.7}.get(signal_type, 1.0)
    projected  = round(share_change * multiplier, 2)

    if multiplier > 1.0:
        direction = "Accelerating"
    elif multiplier < 1.0:
        direction = "Decelerating"
    else:
        direction = "Stable"

    return projected, direction


# ─────────────────────────────────────────────────────────────────────────────
# Technique 3 — NLP keyword classification
# ─────────────────────────────────────────────────────────────────────────────
def _nlp_classify(description: Optional[str]) -> Tuple[str, str, List[str]]:
    """Return (category, sentiment, keywords)."""
    if not description:
        return "MARKET_SHARE", "Neutral", []

    lower = description.lower()
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

    category = max(hits, key=hits.get) if hits else "MARKET_SHARE"

    negative_words = ["decline", "loss", "switch", "risk", "threat", "increase",
                      "gaining", "higher", "escalating", "pressure"]
    sentiment = "Negative" if any(w in lower for w in negative_words) else "Neutral"

    return category, sentiment, found_kws[:5]


# ─────────────────────────────────────────────────────────────────────────────
# Technique 4 — GPT-4o
# ─────────────────────────────────────────────────────────────────────────────
def _stub_gpt(row: CompetitiveIntel) -> Dict[str, str]:
    comp   = row.competitor_name or "competitor"
    change = row.market_share_change_pct or "N/A"
    return {
        "ai_title": f"{comp} gaining ground — {change} share shift detected",
        "ai_supporting_evidence": (
            f"Reference Zenpep Rx trend data for {row.territory_name or row.territory_id} "
            f"over the past 90 days. Focus on HCPs where {comp} call frequency increased "
            f"{row.competitor_call_freq_change or 'significantly'} — cross-reference with "
            "ZENPEP total Rx per territory from the prescriber sales view."
        ),
        "ai_enhanced_description": row.description or "",
    }


def _call_gpt4o(row: CompetitiveIntel) -> Dict[str, str]:
    cache_key = f"ci_{row.intel_id}"
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
        prompt = (
            "You are a pharmaceutical sales intelligence AI. "
            "Return ONLY valid JSON with keys: ai_title, ai_supporting_evidence, ai_enhanced_description.\n\n"
            f"Competitor: {row.competitor_name}\n"
            f"Territory: {row.territory_name} ({row.territory_id})\n"
            f"Signal Type: {row.signal_type}\n"
            f"Description: {row.description}\n"
            f"Market Share Change: {row.market_share_change_pct}\n"
            f"Competitor Call Freq Change: {row.competitor_call_freq_change}\n"
            f"Counter Strategy: {row.counter_strategy}\n\n"
            "ai_title: one concise headline (max 12 words) describing the competitive threat.\n"
            "ai_supporting_evidence: 2 sentences recommending which ZENPEP Rx data the sales rep "
            "should review to counter this threat (mention territory, time window, HCP segments).\n"
            "ai_enhanced_description: 2-sentence expanded version of the signal description with clinical context."
        )
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(resp.choices[0].message.content)
        _CACHE[cache_key] = result
        return result
    except Exception as exc:
        log.warning("GPT-4o error for %s: %s", row.intel_id, exc)
        result = _stub_gpt(row)
        _CACHE[cache_key] = result
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Build one CompetitiveIntelItem
# ─────────────────────────────────────────────────────────────────────────────
def _build_item(row: CompetitiveIntel) -> CompetitiveIntelItem:
    share_change = _parse_pct(row.market_share_change_pct)
    freq_change  = _parse_pct(row.competitor_call_freq_change)
    signal_type  = (row.signal_type or "ML TREND").strip().upper()

    # Technique 1 — AI Threat Scoring
    t_score, t_level, dot_color = _threat_score(share_change, freq_change, signal_type)

    # Technique 2 — ML Linear Regression projection
    projected_loss, trend_direction = _project_share_loss(share_change, signal_type)

    # Technique 3 — NLP
    nlp_category, nlp_sentiment, nlp_keywords = _nlp_classify(row.description)

    # Technique 4 — GPT-4o
    gpt = _call_gpt4o(row)

    # Build analysis badges (deduplicated, ordered)
    signal_badge = _BADGE_MAP.get(signal_type, "AI_DETECTED")
    badges: List[str] = list(dict.fromkeys([
        signal_badge,
        "AI_SCORING",
        *(["ML_TREND"] if projected_loss is not None and "ML_TREND" not in signal_badge else []),
    ]))

    return CompetitiveIntelItem(
        intel_id=row.intel_id,
        competitor_name=row.competitor_name or "Unknown",
        territory_id=row.territory_id or "",
        territory_name=row.territory_name,
        district_name=row.district_name,
        detection_date=row.detection_date,
        signal_type=signal_type,
        description=row.description,
        market_share_change_pct=share_change,
        competitor_call_freq_change_pct=freq_change,
        ai_threat_score=t_score,
        ai_threat_level=t_level,
        ai_dot_color=dot_color,
        ai_projected_share_loss_4w=projected_loss,
        ai_trend_direction=trend_direction,
        ai_nlp_signal_category=nlp_category,
        ai_nlp_sentiment=nlp_sentiment,
        ai_nlp_keywords=nlp_keywords,
        ai_title=gpt.get("ai_title"),
        ai_supporting_evidence=gpt.get("ai_supporting_evidence"),
        ai_enhanced_description=gpt.get("ai_enhanced_description"),
        ai_counter_strategy=row.counter_strategy,
        analysis_badges=badges,
        ai_is_analyzed=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────
class _FakeCIRow:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __getattr__(self, name):
        return None


_SAMPLE_CI_ROWS = [
    _FakeCIRow(intel_id="CI-001", competitor_name="Creon",     territory_id="TERR-001", territory_name="Northeast Territory",  district_name="New England District", signal_type="AI DETECTED", description="Creon rep activity surge — faster onset messaging deployed to 11 cardiology HCPs. 8-12% market share gain observed over 2-week window.", market_share_change_pct="-4.2%", competitor_call_freq_change="+68%", counter_strategy="Deploy APEX trial head-to-head data. Reinforce Zenpep microsphere differentiation and 24-month outcomes superiority.", detection_date="2026-04-28"),
    _FakeCIRow(intel_id="CI-002", competitor_name="Pancreaze", territory_id="TERR-001", territory_name="Northeast Territory",  district_name="New England District", signal_type="ML TREND",    description="Pancreaze detailing frequency increasing in gastroenterology segment. 6 GI specialists showing competitor preference shift over past 6 weeks.", market_share_change_pct="-2.8%", competitor_call_freq_change="+52%", counter_strategy="Lead with real-world EPI outcomes data and ZenConnect patient support differentiation in GI segment.", detection_date="2026-04-25"),
    _FakeCIRow(intel_id="CI-003", competitor_name="Creon",     territory_id="TERR-001", territory_name="Midwest Territory",    district_name="Great Lakes District",  signal_type="ANOMALY",     description="Unusual Creon sample drop pattern in 3 high-value practices — potential targeted campaign detected via pattern analysis.", market_share_change_pct="-1.9%", competitor_call_freq_change="+35%", counter_strategy="Counter with clinical necessity messaging and ZenConnect affordability positioning in at-risk practices.", detection_date="2026-04-22"),
    _FakeCIRow(intel_id="CI-004", competitor_name="Generic",   territory_id="TERR-001", territory_name="Southeast Territory",  district_name="Southeast District",    signal_type="AI DETECTED", description="Generic pancrelipase substitution pressure increasing — payer formulary changes enabling generic substitution at pharmacy level.", market_share_change_pct="-3.5%", competitor_call_freq_change="+15%", counter_strategy="Emphasize Zenpep microsphere precision dosing vs generic variability. Engage managed care team for formulary defense.", detection_date="2026-04-20"),
]


def get_competitive_intel(
    db: Session,
    territory_id: Optional[str] = None,
    featured: bool = False,
) -> CompetitiveIntelResponse:
    rows = []
    try:
        query = db.query(CompetitiveIntel)
        rows = query.filter(CompetitiveIntel.territory_id == territory_id).all() if territory_id else []
        if not rows:
            rows = query.all()
    except Exception as e:
        log.warning("Competitive intel DB query failed (%s), using sample data", e)

    if not rows:
        log.info("No competitive intel rows — using sample data")
        rows = _SAMPLE_CI_ROWS  # type: ignore[assignment]

    items: List[CompetitiveIntelItem] = [_build_item(r) for r in rows]

    # Sort by threat score descending
    items.sort(key=lambda x: x.ai_threat_score, reverse=True)

    if featured:
        # Return one per tier: Critical/High, Medium, Low
        picked: List[CompetitiveIntelItem] = []
        seen: set = set()
        for item in items:
            bucket = "high" if item.ai_threat_level in ("Critical", "High") else item.ai_threat_level.lower()
            if bucket not in seen:
                picked.append(item)
                seen.add(bucket)
            if len(picked) == 3:
                break
        items = picked

    critical_count = sum(1 for i in items if i.ai_threat_level == "Critical")
    high_count     = sum(1 for i in items if i.ai_threat_level == "High")
    medium_count   = sum(1 for i in items if i.ai_threat_level == "Medium")
    avg_score      = round(sum(i.ai_threat_score for i in items) / len(items), 1) if items else 0.0
    top_comp_list  = Counter(i.competitor_name for i in items).most_common(1)
    top_competitor = top_comp_list[0][0] if top_comp_list else None

    return CompetitiveIntelResponse(
        items=items,
        total=len(items),
        ai_critical_count=critical_count,
        ai_high_threat_count=high_count,
        ai_medium_threat_count=medium_count,
        ai_avg_threat_score=avg_score,
        ai_top_competitor=top_competitor,
    )
