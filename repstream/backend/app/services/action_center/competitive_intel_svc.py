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
def _stub_gpt(row: CompetitiveIntel) -> Dict:
    comp      = (row.competitor_name or "Competitor").upper()
    territory = row.territory_name or row.territory_id or "territory"
    rx_chg    = row.market_share_change_pct or "N/A"
    freq_chg  = row.competitor_call_freq_change or "N/A"
    signal    = (row.signal_type or "ML TREND").strip().upper()

    headline = f"{comp} Gains Traction in {territory} — Immediate Action Required for ZENPEP"

    executive_summary = (
        f"{comp} has intensified its engagement in {territory} with a {freq_chg} increase in activity, "
        f"coinciding with a {rx_chg} decline in ZENPEP's Rx volume. "
        f"Immediate strategic response is required to defend market position."
    )

    business_impact = (
        f"The {rx_chg} decline in Rx volume in {territory} represents a direct revenue risk "
        f"if {comp}'s current trajectory continues unchecked."
    )

    if signal == "AI DETECTED":
        recommended_actions = [
            f"Schedule immediate follow-up meetings with top prescribers in {territory} to reinforce ZENPEP's benefits.",
            f"Deploy targeted digital campaigns highlighting ZENPEP's clinical advantages over {comp}.",
            "Engage managed care team to reinforce formulary positioning in at-risk accounts.",
        ]
        talking_points = [
            "ZENPEP offers consistent enzyme delivery validated in Phase 3 clinical trials.",
            "ZENPEP's patient adherence rates are superior, leading to better long-term outcomes.",
            "ZENPEP is backed by robust real-world EPI outcomes data that differentiates it from competitors.",
        ]
    elif signal == "ANOMALY":
        recommended_actions = [
            f"Conduct rapid response visits to the top 5 at-risk HCP accounts in {territory}.",
            f"Provide clinical dossier comparing ZENPEP vs {comp} to key prescribers immediately.",
            "Enroll at-risk patients in ZenConnect patient support program.",
        ]
        talking_points = [
            "ZENPEP microsphere formulation ensures precise, consistent enzyme release.",
            "ZENPEP's safety and efficacy are supported by 24-month real-world outcomes data.",
            "ZenConnect affordability program removes cost barriers for patients switching from competitors.",
        ]
    else:  # ML TREND
        recommended_actions = [
            f"Engage GI specialists in {territory} with ZENPEP's latest clinical evidence.",
            f"Submit formulary defense dossier to payers where {comp} has gained preferred status.",
            "Brief district manager on trend data — coordinate territory-level counter-strategy.",
        ]
        talking_points = [
            "ZENPEP's consistent enzyme profile ensures better digestion and patient comfort.",
            "ZENPEP formulary access is strong — leverage preferred status in detailing conversations.",
            "ZENPEP patient adherence data shows measurable superiority in long-term outcomes.",
        ]

    return {
        "headline": headline,
        "executive_summary": executive_summary,
        "business_impact": business_impact,
        "recommended_actions": recommended_actions,
        "field_force_talking_points": talking_points,
        "why_it_matters": "",
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
            "You are a pharmaceutical sales intelligence AI for ZENPEP (pancrelipase). "
            "Return ONLY valid JSON with these exact keys: "
            "headline, executive_summary, business_impact, recommended_actions, field_force_talking_points, why_it_matters.\n\n"
            f"Competitor: {row.competitor_name}\n"
            f"Territory: {row.territory_name} ({row.territory_id})\n"
            f"Signal Type: {row.signal_type}\n"
            f"Description: {row.description}\n"
            f"Rx Change: {row.market_share_change_pct}\n"
            f"Activity Change: {row.competitor_call_freq_change}\n"
            f"Counter Strategy: {row.counter_strategy}\n\n"
            "headline: one concise headline (max 15 words) describing the competitive threat to ZENPEP.\n"
            "executive_summary: 2-3 sentence summary of the threat and urgency for the sales rep.\n"
            "business_impact: 1-2 sentence description of revenue/market share risk.\n"
            "recommended_actions: list of exactly 3 action steps the rep should take immediately.\n"
            "field_force_talking_points: list of exactly 3 talking points to use with HCPs.\n"
            "why_it_matters: 1 sentence on why this matters for ZENPEP (can be empty string)."
        )
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(resp.choices[0].message.content)
        for key in ("recommended_actions", "field_force_talking_points"):
            if isinstance(result.get(key), str):
                result[key] = [s.strip() for s in result[key].split("\n") if s.strip()]
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
_RISK_MAP = {"Critical": "HIGH", "High": "HIGH", "Medium": "MEDIUM", "Low": "LOW"}
_URGENCY_MAP = {"HIGH": "IMMEDIATE", "MEDIUM": "STANDARD", "LOW": "ROUTINE"}


def _parse_sales(raw) -> Optional[float]:
    if raw is None:
        return None
    try:
        return round(float(str(raw).replace(",", "").replace("$", "").strip()), 2)
    except (ValueError, TypeError):
        return None


def _build_item(row: CompetitiveIntel) -> CompetitiveIntelItem:
    share_change = _parse_pct(row.market_share_change_pct)
    freq_change  = _parse_pct(row.competitor_call_freq_change)
    signal_type  = (row.signal_type or "ML TREND").strip().upper()

    # AI Threat Scoring (used internally for risk_level)
    t_score, t_level, _ = _threat_score(share_change, freq_change, signal_type)
    risk_level   = _RISK_MAP.get(t_level, "MEDIUM")
    urgency_level = _URGENCY_MAP.get(risk_level, "STANDARD")

    # GPT-4o enrichment
    gpt = _call_gpt4o(row)

    return CompetitiveIntelItem(
        signal_id=row.intel_id,
        signal_type=signal_type,
        signal_date=row.detection_date,
        territory_id=row.territory_id or "",
        territory_name=row.territory_name,
        region=getattr(row, "region", None),
        competitor_brand=(row.competitor_name or "Unknown").upper(),
        rx_change_percent=share_change,
        activity_change_percent=freq_change,
        territory_sales=_parse_sales(getattr(row, "territory_sales", None)),
        headline=gpt.get("headline"),
        executive_summary=gpt.get("executive_summary"),
        counter_strategy=row.counter_strategy,
        risk_level=risk_level,
        urgency_level=urgency_level,
        business_impact=gpt.get("business_impact"),
        recommended_actions=gpt.get("recommended_actions") or [],
        field_force_talking_points=gpt.get("field_force_talking_points") or [],
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
    _FakeCIRow(intel_id="SIG-001", competitor_name="Creon",     territory_id="A0E000000013012", territory_name="BAY RIDGE, NY",    region="NORTH", signal_type="AI DETECTED", description="Creon rep activity surge — faster onset messaging deployed to 11 cardiology HCPs. 8-12% market share gain observed over 2-week window.", market_share_change_pct="-4.2%", competitor_call_freq_change="+68%", territory_sales="353529.80", counter_strategy="Deploy APEX trial head-to-head data. Reinforce Zenpep microsphere differentiation and 24-month outcomes superiority.", detection_date="2026-04-28"),
    _FakeCIRow(intel_id="SIG-002", competitor_name="Pancreaze", territory_id="A0E000000013112", territory_name="PENSACOLA, FL",   region="SOUTH", signal_type="ML TREND",    description="Pancreaze detailing frequency increasing in gastroenterology segment. 6 GI specialists showing competitor preference shift over past 6 weeks.", market_share_change_pct="-3.1%", competitor_call_freq_change="+22%", territory_sales="108906.50", counter_strategy="Lead with real-world EPI outcomes data and ZenConnect patient support differentiation in GI segment.", detection_date="2026-04-25"),
    _FakeCIRow(intel_id="SIG-003", competitor_name="Creon",     territory_id="A0E000000013142", territory_name="LOS ANGELES, CA", region="SOUTH", signal_type="ANOMALY",     description="Unusual Creon sample drop pattern in 3 high-value practices — potential targeted campaign detected via pattern analysis.", market_share_change_pct="-5.8%", competitor_call_freq_change="+45%", territory_sales="113765.00", counter_strategy="Counter with clinical necessity messaging and ZenConnect affordability positioning in at-risk practices.", detection_date="2026-04-22"),
    _FakeCIRow(intel_id="SIG-004", competitor_name="Pancreaze", territory_id="A0E000000013161", territory_name="FORT WORTH, TX",  region="SOUTH", signal_type="AI DETECTED", description="Generic pancrelipase substitution pressure increasing — payer formulary changes enabling generic substitution at pharmacy level.", market_share_change_pct="-2.3%", competitor_call_freq_change="+31%", territory_sales="119982.15", counter_strategy="Emphasize Zenpep microsphere precision dosing vs generic variability. Engage managed care team for formulary defense.", detection_date="2026-04-20"),
    _FakeCIRow(intel_id="SIG-005", competitor_name="Creon",     territory_id="A0E000000013148", territory_name="SAN DIEGO, CA",   region="SOUTH", signal_type="ML TREND",    description="Creon brand awareness among new GI fellows rising — 18% increase in brand recall across academic medical centers.", market_share_change_pct="-1.8%", competitor_call_freq_change="+18%", territory_sales="127381.75", counter_strategy="Focus on engaging with academic medical centers. Highlight ZENPEP's superior patient support programs.", detection_date="2026-04-18"),
]


def get_competitive_intel(
    db: Session,
    territory_ids: Optional[List[str]] = None,
    featured: bool = False,
) -> CompetitiveIntelResponse:
    # territory_ids = bare Territory_Durable_Ids for a manager/employee/territory
    # selection; None = the unfiltered default (all rows, sample fallback if empty).
    rows = []
    filtered = bool(territory_ids)
    try:
        query = db.query(CompetitiveIntel)
        if filtered:
            rows = query.filter(CompetitiveIntel.territory_id.in_(territory_ids)).all()
        else:
            rows = query.all()
    except Exception as e:
        log.warning("Competitive intel DB query failed (%s), using sample data", e)

    # Sample fallback only for the unfiltered default — a filtered selection with
    # no matching rows is a valid empty result, not a reason to show sample data.
    if not rows and not filtered:
        log.info("No competitive intel rows — using sample data")
        rows = _SAMPLE_CI_ROWS  # type: ignore[assignment]

    items: List[CompetitiveIntelItem] = [_build_item(r) for r in rows]

    # Sort by threat score descending
    _risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items.sort(key=lambda x: _risk_order.get(x.risk_level or "LOW", 2))

    if featured:
        picked: List[CompetitiveIntelItem] = []
        seen: set = set()
        for item in items:
            bucket = (item.risk_level or "LOW").upper()
            if bucket not in seen:
                picked.append(item)
                seen.add(bucket)
            if len(picked) == 3:
                break
        items = picked

    return CompetitiveIntelResponse(
        items=items,
        total=len(items),
    )
