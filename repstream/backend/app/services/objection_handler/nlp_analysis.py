"""NLP pattern extraction per segment from call transcripts for Module 3.

Uses spaCy for fast pattern matching and OpenAI embeddings for semantic clustering.
"""
import json
import logging
from collections import Counter
from typing import Dict, List, Optional

from app.models.objection_handler import CallTranscript

logger = logging.getLogger(__name__)

# Common pharma objection categories for pattern matching
OBJECTION_PATTERNS: Dict[str, List[str]] = {
    "COVERAGE": ["insurance", "coverage", "formulary", "prior auth", "not covered", "denied"],
    "EFFICACY": ["doesn't work", "not effective", "no evidence", "side effects", "tolerability"],
    "COST": ["expensive", "afford", "cost", "copay", "out of pocket", "price"],
    "HABIT": ["already prescribing", "happy with", "switching", "loyal", "comfortable with"],
    "AWARENESS": ["never heard", "don't know", "unfamiliar", "haven't tried", "tell me more"],
    "COMPETITOR": ["creon", "pancreaze", "pertzye", "viokace", "competitor", "other brand"],
}


def detect_objection_types(transcript_text: str) -> List[str]:
    """Return list of matched objection category keys found in transcript text."""
    text_lower = transcript_text.lower()
    detected = []
    for objection_type, keywords in OBJECTION_PATTERNS.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(objection_type)
    return detected


def extract_objection_frequencies(
    transcripts: List[CallTranscript],
) -> Dict[str, Dict]:
    """Count how many distinct calls each objection type appears in.

    Returns dict: objection_type → {call_count, calls_with_resolution, calls_with_rx_30d}
    """
    counts: Counter = Counter()
    resolved: Counter = Counter()
    rx_30d: Counter = Counter()

    for t in transcripts:
        if not t.has_objection:
            continue
        try:
            obj_types: List[str] = json.loads(t.objection_types) if t.objection_types else []
        except (json.JSONDecodeError, TypeError):
            obj_types = detect_objection_types(t.transcript_text or "")

        for ot in obj_types:
            counts[ot] += 1
            if t.objection_resolved:
                resolved[ot] += 1
            if t.rx_within_30_days:
                rx_30d[ot] += 1

    return {
        ot: {
            "call_count": cnt,
            "calls_with_resolution": resolved[ot],
            "calls_with_rx_30d": rx_30d[ot],
        }
        for ot, cnt in counts.items()
    }
