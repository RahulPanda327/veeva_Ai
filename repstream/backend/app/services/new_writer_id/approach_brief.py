"""Warm approach generation for new writer candidates (Module 2).

List view: GPT-4o warm approach per HCP from their real data — background-warmed,
persisted to disk. DB Warm_Approach_Text (insight360_peer_match_dul) wins when present.
On-demand: GPT-4o full brief via 'Generate Approach Brief' button.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

_BRIEF_CACHE: Dict[str, Dict] = {}

# ── GPT-4o warm approach cache (persisted, same pattern as territory insights) ─
_WARM_CACHE: Dict[str, Dict] = {}
_WARM_CACHE_FILE = Path(__file__).resolve().parents[3] / ".warm_approach_cache.json"
_warm_io_lock = threading.Lock()
_WARM_MAX_WORKERS = 16
_WARM_SAVE_EVERY = 25


def _load_warm_cache() -> None:
    try:
        with open(_WARM_CACHE_FILE, encoding="utf-8") as f:
            _WARM_CACHE.update(json.load(f))
        logger.info("Loaded %d cached warm approaches from %s", len(_WARM_CACHE), _WARM_CACHE_FILE.name)
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load warm approach cache (%s).", exc)


def _save_warm_cache() -> None:
    try:
        with _warm_io_lock:
            tmp = _WARM_CACHE_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_WARM_CACHE, f)
            os.replace(tmp, _WARM_CACHE_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save warm approach cache (%s).", exc)


_load_warm_cache()


def _warm_key(hcp: Dict) -> str:
    return f"warm_{hcp['hcp_id']}_{int(float(hcp.get('in_class_rx_q1') or 0))}"


_WARM_SYSTEM = (
    "You are a pharmaceutical sales intelligence assistant for ZENPEP (pancrelipase). "
    "Write short, warm, compliant approach lines for sales reps visiting HCPs. "
    "Never invent clinical data, peer names, or comparative efficacy claims. "
    "Respond ONLY with valid JSON — no markdown, no extra text."
)

_WARM_PROMPT = """Write a 1-2 sentence warm approach line (max 30 words) for a pharma rep's first visit
to this non-writer HCP. Cite THIS HCP's own real numbers (Rx counts, brands, dates) — not generic advice.
Do NOT address the HCP by name and never use placeholders like [Name] or [Last Name] —
write it as guidance the rep can act on (e.g. "Acknowledge their 8 CREON Rx this quarter...").

HCP profile:
- Specialty: {specialty} | Location: {city_state} | Segment: {segment}
- Currently prescribing in-class: {top_brands} (total {in_class:.0f} Rx/qtr)
- Our brand (ZENPEP) this quarter: 0 Rx | Prior quarter: {brand_q4:.0f} Rx
- Most recent new in-class Rx: {nbrx}
- Peer connection: {peer_str}

Respond ONLY with this JSON:
{{"warm_approach": "<1-2 sentence approach line citing this HCP's numbers>", "highlight": "<3-6 word key phrase>"}}"""


def _build_warm_prompt(hcp: Dict) -> str:
    city_state = ", ".join(p for p in (hcp.get("city"), hcp.get("state")) if p) or "unknown"
    top5 = hcp.get("top_5_in_class_rx") or []
    top_brands = ", ".join(f"{b['brand']} {b['rx']} Rx" for b in top5) or (hcp.get("competitor_brand") or "unknown")
    peer = hcp.get("ai_peer_name") or hcp.get("peer_name")
    score = float(hcp.get("ai_peer_match_score") or 0)
    peer_str = f"{peer} (peer match {score:.0f}%)" if peer else "none identified"
    return _WARM_PROMPT.format(
        specialty=hcp.get("specialty") or "unknown",
        city_state=city_state,
        segment=hcp.get("segment") or "unclassified",
        top_brands=top_brands,
        in_class=float(hcp.get("in_class_rx_q1") or 0),
        brand_q4=float(hcp.get("brand_rx_q4") or 0),
        nbrx=hcp.get("last_nrx_date") or "none recorded",
        peer_str=peer_str,
    )


def _call_gpt4o_warm(hcp: Dict) -> Optional[Dict]:
    """One GPT-4o call → {"warm_approach", "highlight"}. Caches on success only."""
    key = _warm_key(hcp)
    cached = _WARM_CACHE.get(key)
    if cached:
        return cached
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
                {"role": "system", "content": _WARM_SYSTEM},
                {"role": "user",   "content": _build_warm_prompt(hcp)},
            ],
            max_tokens=120,
            temperature=0.3,
        )
        data = json.loads(resp.choices[0].message.content)
        text = str(data.get("warm_approach", ""))
        if not text:
            raise ValueError("empty warm_approach in GPT-4o response")
        result = {"warm_approach": text, "highlight": data.get("highlight")}
        _WARM_CACHE[key] = result
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("GPT-4o warm approach failed for %s: %s", hcp.get("hcp_id"), exc)
        return None   # not cached — retried on next warm cycle


# ── GPT-4o email-style approach brief (embedded per candidate) ────────────────

_EMAIL_CACHE: Dict[str, Dict] = {}
_EMAIL_CACHE_FILE = Path(__file__).resolve().parents[3] / ".approach_email_cache.json"


def _normalize_email_entry(v: Dict) -> Dict:
    """Migrate flat cached entries to the nested {email: {subject, email_body}} shape."""
    if "email" in v:
        return v
    return {
        "email": {
            "subject":    v.get("subject", ""),
            "email_body": v.get("email_body", ""),
        },
        "key_discussion_points": v.get("key_discussion_points") or [],
    }


def _load_email_cache() -> None:
    try:
        with open(_EMAIL_CACHE_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        _EMAIL_CACHE.update({k: _normalize_email_entry(v) for k, v in raw.items()})
        logger.info("Loaded %d cached approach briefs from %s", len(_EMAIL_CACHE), _EMAIL_CACHE_FILE.name)
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load approach brief cache (%s).", exc)


def _save_email_cache() -> None:
    try:
        with _warm_io_lock:
            tmp = _EMAIL_CACHE_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_EMAIL_CACHE, f)
            os.replace(tmp, _EMAIL_CACHE_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save approach brief cache (%s).", exc)


_load_email_cache()


def _email_key(hcp: Dict) -> str:
    return f"email_{hcp['hcp_id']}"


_EMAIL_SYSTEM = (
    "You are a pharmaceutical sales communication assistant for ZENPEP (pancrelipase). "
    "Write professional, compliant outreach emails for sales reps to send to HCPs. "
    "Only use the product advantages provided — never invent clinical data, statistics, "
    "or comparative efficacy claims. Warm, respectful, concise tone. "
    "Respond ONLY with valid JSON — no markdown, no extra text."
)

_EMAIL_PROMPT = """Write an approach email for this HCP.

HCP profile (real data):
- Name: {name} | Specialty: {specialty} | {city_state}
- Currently prescribing in-class: {top_brands}
- ZENPEP history: {brand_q4:.0f} Rx last quarter
- Most recent new in-class Rx: {nbrx}
- Peer connection: {peer_str}

Approved ZENPEP advantages (use ONLY these):
- Non-enteric-coated microsphere formulation
- 5 strengths (3K-40K lipase units) for flexible titration
- ZenConnect co-pay program ($0/month for most commercial patients)
- APEX trial data available on request

Respond ONLY with this JSON:
{{"subject": "<email subject line>",
  "email_body": "<3-4 short paragraphs: personal opener referencing their practice, key discussion points citing their real Rx context, ZENPEP advantages vs what they currently prescribe, soft call-to-action>",
  "key_discussion_points": ["<point 1>", "<point 2>", "<point 3>"]}}"""


def _build_email_prompt(hcp: Dict) -> str:
    city_state = ", ".join(p for p in (hcp.get("city"), hcp.get("state")) if p) or "unknown"
    top5 = hcp.get("top_5_in_class_rx") or []
    top_brands = ", ".join(f"{b['brand']} {b['rx']} Rx" for b in top5) or (hcp.get("competitor_brand") or "none recorded")
    peer = hcp.get("ai_peer_name") or hcp.get("peer_name")
    score = float(hcp.get("ai_peer_match_score") or 0)
    warm = hcp.get("ai_warm_approach_text") or ""
    peer_str = f"{peer} ({score:.0f}% match) — {warm}" if peer else "none identified"
    return _EMAIL_PROMPT.format(
        name=(hcp.get("name") or "").replace(",", " ").strip(),
        specialty=hcp.get("specialty") or "unknown",
        city_state=city_state,
        top_brands=top_brands,
        brand_q4=float(hcp.get("brand_rx_q4") or 0),
        nbrx=hcp.get("last_nrx_date") or "none recorded",
        peer_str=peer_str,
    )


def _call_gpt4o_email(hcp: Dict) -> Optional[Dict]:
    """One GPT-4o call → {"subject", "email_body", "key_discussion_points"}. Caches on success only."""
    key = _email_key(hcp)
    cached = _EMAIL_CACHE.get(key)
    if cached:
        return cached
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
                {"role": "system", "content": _EMAIL_SYSTEM},
                {"role": "user",   "content": _build_email_prompt(hcp)},
            ],
            max_tokens=500,
            temperature=0.4,
        )
        data = json.loads(resp.choices[0].message.content)
        if not data.get("email_body"):
            raise ValueError("empty email_body in GPT-4o response")
        result = {
            "email": {
                "subject":    str(data.get("subject", "")),
                "email_body": str(data.get("email_body", "")),
            },
            "key_discussion_points": data.get("key_discussion_points") or [],
        }
        _EMAIL_CACHE[key] = result
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("GPT-4o approach brief failed for %s: %s", hcp.get("hcp_id"), exc)
        return None   # not cached — retried on next warm cycle


def attach_approach_briefs(candidates: List[Dict]) -> List[Dict]:
    """READ-ONLY: fill approach_brief from the cache; null until warmed.
    Injects the HCP's real email address (dim view Email_1) as email.to."""
    for c in candidates:
        cached = _EMAIL_CACHE.get(_email_key(c))
        if cached:
            c["approach_brief"] = {
                **cached,
                "email": {
                    "to":      c.get("email"),
                    "to_name": (c.get("name") or "").replace(",", " ").strip(),
                    **cached.get("email", {}),
                },
            }
        else:
            c["approach_brief"] = None
    return candidates


def warm_approach_briefs(candidates: List[Dict]) -> int:
    """Background: GPT-4o email brief for every candidate not cached yet."""
    pending = [c for c in candidates if _email_key(c) not in _EMAIL_CACHE]
    if not pending:
        return 0
    with ThreadPoolExecutor(max_workers=_WARM_MAX_WORKERS) as pool:
        list(pool.map(_call_gpt4o_email, pending))
    _save_email_cache()
    logger.info("Warmed %d GPT-4o approach briefs.", len(pending))
    return len(pending)


def attach_warm_approaches(candidates: List[Dict]) -> List[Dict]:
    """READ-ONLY: fill ai_warm_approach_text from the cache. DB value (peer match)
    already set by the router wins; uncached HCPs stay null until warmed."""
    for c in candidates:
        if c.get("ai_warm_approach_text"):
            continue   # real DB Warm_Approach_Text present
        cached = _WARM_CACHE.get(_warm_key(c))
        if cached:
            c["ai_warm_approach_text"] = cached["warm_approach"]
            c["ai_approach_highlight"] = cached.get("highlight")
    return candidates


def count_unwarmed(candidates: List[Dict]) -> int:
    return sum(
        1 for c in candidates
        if not c.get("ai_warm_approach_text") and _warm_key(c) not in _WARM_CACHE
    )


def warm_approaches(candidates: List[Dict]) -> int:
    """Background: GPT-4o warm approach for every candidate that has neither a DB
    value nor a cached generation. Parallel; saves to disk every N completions."""
    pending = [
        c for c in candidates
        if not c.get("ai_warm_approach_text") and _warm_key(c) not in _WARM_CACHE
    ]
    if not pending:
        return 0
    done = 0
    with ThreadPoolExecutor(max_workers=_WARM_MAX_WORKERS) as pool:
        futures = [pool.submit(_call_gpt4o_warm, c) for c in pending]
        for future in as_completed(futures):
            future.result()
            done += 1
            if done % _WARM_SAVE_EVERY == 0:
                _save_warm_cache()
                logger.info("Warm approach progress: %d/%d", done, len(pending))
    _save_warm_cache()
    logger.info("Warmed %d GPT-4o warm approaches.", len(pending))
    return len(pending)

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
