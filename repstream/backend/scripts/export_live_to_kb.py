"""Turn RepStream's warm-up output into an embeddable knowledge-base file.

Reads the response cache the warm-up already writes - no DB access, no extra
endpoint calls - and renders each endpoint's JSON as sentences the chatbot can
retrieve against.

    warm-up  ->  cache/endpoint_response_cache.json  ->  THIS  ->  kb/repstream_live_data.txt
                                                                     |
                                              python -m scripts.ingest_to_pgvector

Why sentences rather than the raw JSON: retrieval compares the embedding of the
rep's question with the embedding of the chunk. `{"ai_priority_tier":"HIGH"}`
shares almost no vocabulary with "who are my high priority doctors?", so raw JSON
retrieves badly. The rendered text repeats the words a rep actually types.

Sections are separated by `===` dividers, which is what the chatbot's existing
context-file chunker splits on.

Usage
    python scripts/export_live_to_kb.py
    python scripts/export_live_to_kb.py --base-url http://localhost:8003
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("export_live_to_kb")

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = BACKEND_DIR / "cache" / "endpoint_response_cache.json"
DEFAULT_OUT = BACKEND_DIR / "ai_assistant" / "kb"
OUT_NAME = "repstream_live_data.txt"

DIVIDER = "=" * 60


def _fmt(value: Any, dash: str = "not recorded") -> str:
    return dash if value in (None, "", []) else str(value)


def _decode(entry: Dict[str, Any]) -> Any:
    """Cached bodies are base64-encoded JSON, not raw text."""
    body = entry.get("body") or ""
    try:
        return json.loads(base64.b64decode(body))
    except Exception:
        try:
            return json.loads(body)
        except Exception:
            return None


def _scope_label(cache_key: str, names: Dict[str, str]) -> str:
    """'GET:/path:[('territory_id', 'A0E...')]:shared' -> 'Pittsburgh North PA'.

    Left as-is, the raw key reaches the embedding as
    "[('territory_id', 'A0E000000013065')]", which no rep would ever type, so it
    could never match a question naming that territory.
    """
    try:
        scope = cache_key.split(":")[2]
    except IndexError:
        return "all territories"
    if scope in ("", "[]"):
        return "all territories"
    ids = re.findall(r"A0E[0-9A-Za-z]+", scope)
    if not ids:
        return scope
    return ", ".join(names.get(i, i) for i in ids)


def _territory_names(base_url: Optional[str]) -> Dict[str, str]:
    """id -> human name, from the filter tree the summary endpoint returns."""
    if not base_url:
        return {}
    try:
        import httpx

        data = httpx.get(f"{base_url}/api/v1/territory/summary", timeout=180).json()
        names: Dict[str, str] = {}
        for m in (data.get("filters") or {}).get("manager_id", []):
            for e in m.get("employee_id", []):
                for t in e.get("territory_id", []):
                    if t.get("territory_id"):
                        names[t["territory_id"]] = t.get("territory_name") or t["territory_id"]
        return names
    except Exception as exc:  # noqa: BLE001
        log.warning("  could not read territory names (%s)", exc)
        return {}


def _fetch_summaries(base_url: Optional[str], names: Dict[str, str]) -> List[str]:
    """The KPI tiles, which are NOT in the response cache.

    The cache middleware deliberately skips */summary so the tiles can follow a
    caller's remembered filter. That means the authoritative counts - total HCPs,
    HIGH/MEDIUM/LOW, weekly target - never reach the knowledge base from the cache
    alone, and the model ends up inferring them from the capped HCP list instead.
    """
    if not base_url:
        return []
    try:
        import httpx
    except Exception:
        return []

    sections: List[str] = []
    targets = [("all territories", {})] + [(nm, {"territory_id": tid}) for tid, nm in names.items()]
    for label, params in targets:
        try:
            s = httpx.get(f"{base_url}/api/v1/territory/summary", params=params, timeout=180).json()
        except Exception as exc:  # noqa: BLE001
            log.warning("  summary fetch failed for %s (%s)", label, exc)
            continue
        sections.append(
            f"Territory Prioritization KPI summary for {label}. "
            f"The territory has {_fmt(s.get('total_hcps'))} HCPs shown in the list. "
            f"Priority counts across the full ranked list: "
            f"{_fmt(s.get('high_priority_count'))} HIGH priority HCPs, "
            f"{_fmt(s.get('medium_priority_count'))} MEDIUM priority, and "
            f"{_fmt(s.get('low_priority_count'))} LOW priority. "
            f"The weekly visit target is {_fmt(s.get('weekly_target'))} HCPs. "
            f"Reporting period {_fmt(s.get('period'))}, "
            f"last refreshed {_fmt(s.get('last_refresh'))}."
        )
        log.info("  fetched KPI summary for %s", label)
    return sections


# ── renderers, one per endpoint ──────────────────────────────────────────────

def _trend_pct(rx_q1: Any, rx_q4: Any) -> str:
    """The API exposes rx_q1/rx_q4 but not the trend, so derive it rather than
    emit 'not recorded' for something a rep will certainly ask about."""
    try:
        q1, q4 = float(rx_q1), float(rx_q4)
    except (TypeError, ValueError):
        return "not available"
    if q4 == 0:
        return "no prior-quarter prescriptions to compare" if q1 else "no change"
    return f"{round((q1 - q4) / q4 * 100, 1)} percent"


def _r_hcp_list(rows: Any) -> str:
    rows = rows.get("items") if isinstance(rows, dict) else rows
    if not isinstance(rows, list) or not rows:
        return "No HCPs are currently listed for this territory selection."
    tiers: Dict[str, int] = {}
    for r in rows:
        t = r.get("ai_priority_tier") or "UNKNOWN"
        tiers[t] = tiers.get(t, 0) + 1
    out = [
        f"There are {len(rows)} HCPs in the territory priority list.",
        "Priority breakdown: " + ", ".join(f"{n} are {t} priority" for t, n in tiers.items()) + ".",
        "",
        "The HCPs to call first, highest priority first:",
    ]
    for r in rows[:40]:
        prof = r.get("view_profile") or {}     # city/state live on the nested object
        out.append(
            f"{_fmt(r.get('name'))} (HCP id {_fmt(r.get('hcp_id'))}) is a "
            f"{_fmt(r.get('specialty'))} in {_fmt(prof.get('city'))}, "
            f"{_fmt(prof.get('state'))}, segment {_fmt(r.get('segment'))}. "
            f"Priority tier {_fmt(r.get('ai_priority_tier'))}. "
            f"Prescriptions this quarter {_fmt(r.get('rx_q1'))} versus "
            f"{_fmt(r.get('rx_q4'))} last quarter, a change of "
            f"{_trend_pct(r.get('rx_q1'), r.get('rx_q4'))}. "
            f"Last prescription {_fmt(r.get('last_rx_date'))}, "
            f"last call {_fmt(r.get('last_call_date'))}. "
            f"{_fmt(r.get('ai_generated_insight'), '')}"
        )
    return "\n".join(out)


def _r_candidates(rows: Any) -> str:
    items = rows.get("items") if isinstance(rows, dict) else rows
    if not isinstance(items, list) or not items:
        return ("There are no new writer candidates for this selection. A new writer "
                "candidate is an HCP prescribing competitor in-class products but not our brand.")
    out = [f"There are {len(items)} new writer candidates - HCPs prescribing competitor "
           f"in-class products who have not yet written our brand.", ""]
    for c in items[:40]:
        out.append(
            f"{_fmt(c.get('name'))} (HCP id {_fmt(c.get('hcp_id'))}), "
            f"{_fmt(c.get('specialty'))} in {_fmt(c.get('city'))}, {_fmt(c.get('state'))}. "
            f"Peer match {_fmt(c.get('peer_match_pct'))} percent. In-class prescriptions "
            f"{_fmt(c.get('in_class_rx_q1'))}. Most recent new in-class prescription "
            f"{_fmt(c.get('last_nrx_date'))}. Main competitor {_fmt(c.get('competitor_brand'))}."
        )
    return "\n".join(out)


def _r_objections(rows: Any) -> str:
    items = rows.get("items") if isinstance(rows, dict) else rows
    if not isinstance(items, list) or not items:
        return "No objections are currently recorded."
    out = [f"There are {len(items)} objections recorded from sales call transcripts, "
           f"most frequent first.", ""]
    for o in items[:40]:
        out.append(
            f'Objection "{_fmt(o.get("objection_type"))}": heard in '
            f'{_fmt(o.get("ai_call_count"))} calls, {_fmt(o.get("ai_frequency_label"))} '
            f'frequency, during {_fmt(o.get("period"))} '
            f'(date range {_fmt(o.get("ai_date_range"))}). Conversion score '
            f'{_fmt(o.get("ai_conversion_score"))}. What the HCP says: '
            f'{_fmt(o.get("objection_text"))} Approved MLR response: '
            f'{_fmt(o.get("ai_mlr_response"))} Supporting materials: '
            f'{_fmt(o.get("ai_supporting_materials"), "none")}'
        )
    return "\n".join(out)


def _r_alerts(data: Any) -> str:
    groups = (data or {}).get("active_alerts", {}) if isinstance(data, dict) else {}
    if not groups:
        return "There are no active alerts."
    out = ["Active alerts currently raised for this territory selection.", ""]
    total = 0
    for group, items in groups.items():
        for item in (items or []):
            obj = list(item.values())[0] if isinstance(item, dict) and len(item) == 1 else item
            if not isinstance(obj, dict):
                continue
            total += 1
            out.append(
                f"[{group}] {_fmt(obj.get('title'))} (alert id {_fmt(obj.get('alert_id'))}). "
                f"Severity {_fmt(obj.get('ai_severity'))}, detected "
                f"{_fmt(obj.get('detected_at'))}, affecting "
                f"{_fmt(obj.get('ai_affected_hcp_count'))} HCPs. Rx risk "
                f"{_fmt(obj.get('ai_rx_risk'))}, territory reach "
                f"{_fmt(obj.get('ai_territory_reach'))}. "
                f"{_fmt(obj.get('ai_prescribing_drift_note'), '')}"
            )
    out.insert(1, f"There are {total} active alerts in total.")
    return "\n".join(out)


_RENDERERS = {
    "/territory/hcp-list":     ("TERRITORY PRIORITIZATION - HCP PRIORITY LIST", _r_hcp_list),
    "/new-writers/candidates": ("NEW WRITER IDENTIFICATION - CANDIDATES", _r_candidates),
    "/objections/list":        ("OBJECTION HANDLER - OBJECTIONS AND APPROVED RESPONSES", _r_objections),
    "/action-center/alerts":   ("ACTION CENTER - ACTIVE ALERTS", _r_alerts),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Render warm-up output as an embeddable KB file.")
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--base-url", default="http://localhost:8000",
                    help="Live server, for the KPI tiles and territory names "
                         "(the */summary endpoints are never response-cached).")
    args = ap.parse_args()

    cache_path = Path(args.cache)
    if not cache_path.exists():
        log.error("Response cache not found: %s", cache_path)
        log.error("Start the backend and let the warm-up finish, then re-run this.")
        return 2

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    log.info("Read %d cached endpoint response(s) from %s", len(cache), cache_path.name)

    names = _territory_names(args.base_url)
    if names:
        log.info("Territory names: %s", ", ".join(names.values()))

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections: List[str] = [
        DIVIDER,
        f"REPSTREAM LIVE APPLICATION DATA (captured {stamp})\n"
        f"Current data from the RepStream application: HCPs, priorities, "
        f"prescriptions, calls, new writers, objections and alerts.\n"
        f"Each section below states which territory it covers. A section for "
        f"'all territories' is the combined total for the whole team; a section "
        f"naming one territory covers only that territory.",
    ]

    # KPI tiles first — authoritative counts, and never cached.
    for block in _fetch_summaries(args.base_url, names):
        sections += [DIVIDER, block]

    used = 0
    for key, entry in cache.items():
        match = next((frag for frag in _RENDERERS if frag in key), None)
        if match is None:
            continue
        if entry.get("status_code") != 200:
            log.warning("  skipping %s (status %s)", key, entry.get("status_code"))
            continue
        payload = _decode(entry)
        if payload is None:
            log.warning("  skipping %s (body could not be decoded)", key)
            continue

        title, render = _RENDERERS[match]
        scope_label = _scope_label(key, names)

        # Title, scope and body go in ONE block with no divider between them. The
        # chunker splits on ===, so a divider here would strand the heading in its
        # own chunk and leave the numbers with no idea which territory they belong
        # to — which is how "36 HCPs" once got returned for a 68-HCP total.
        sections.append(
            f"{DIVIDER}\n{title}\nTerritory scope: {scope_label}.\n"
            f"All figures in this section are for {scope_label}.\n\n"
            + render(payload)
        )
        used += 1
        log.info("  rendered %s", match)

    if not used:
        log.error("No RepStream endpoints found in the cache - has the warm-up run?")
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / OUT_NAME
    out_file.write_text("\n".join(sections), encoding="utf-8")

    log.info("\nWrote %s (%.1f KB, %d section(s))", out_file, out_file.stat().st_size / 1024, used)
    log.info("\nNext - embed it:")
    log.info("  cd %s", out_dir.parent)
    log.info("  python -m scripts.ingest_to_pgvector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
