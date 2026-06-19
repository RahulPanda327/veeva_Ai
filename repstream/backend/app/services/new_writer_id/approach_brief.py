"""Generate warm approach brief via GPT-4o for Module 2."""
from datetime import datetime, timezone
from typing import Dict, Optional

from app.config import settings
from app.utils.llm_client import call_llm

_BRIEF_SYSTEM = (
    "You are a pharmaceutical sales training coach. "
    "Write warm, professional, compliant outreach briefs for sales reps. "
    "Never invent clinical data or make comparative efficacy claims."
)


def build_approach_brief_prompt(
    hcp_name: str,
    peer_name: Optional[str],
    competitor_brand: str,
    competitor_volume: float,
    matched_icd10_codes: list,
) -> str:
    peer_str = f"connected via {peer_name} who already prescribes our brand" if peer_name else "unconnected to current prescribers in the territory"
    icd_str = ", ".join(matched_icd10_codes) if matched_icd10_codes else "relevant diagnosis codes"
    return (
        f"Write a 2-sentence warm outreach brief for a pharma sales rep visiting Dr. {hcp_name}. "
        f"They are {peer_str}. "
        f"The doctor prescribes {competitor_brand or 'a competitor brand'} at {competitor_volume:.0f} Rx/qtr. "
        f"Relevant ICD-10 codes: {icd_str}. "
        "Tone: professional, specific. Do not fabricate clinical claims."
    )


def generate_approach_brief(hcp: Dict) -> str:
    """Return GPT-4o generated approach brief for a new-writer candidate."""
    prompt = build_approach_brief_prompt(
        hcp_name=hcp.get("name", "this physician"),
        peer_name=hcp.get("peer_name"),
        competitor_brand=hcp.get("competitor_brand", ""),
        competitor_volume=hcp.get("competitor_volume", 0.0),
        matched_icd10_codes=hcp.get("matched_icd10_codes", []),
    )
    return call_llm(
        prompt=prompt,
        system_message=_BRIEF_SYSTEM,
        cache_ttl=settings.CACHE_TTL_APPROACH_BRIEF,
        max_tokens=120,
        temperature=0.4,
    )


def build_approach_brief_response(hcp: Dict, brief_text: str) -> Dict:
    return {
        "hcp_id": hcp["hcp_id"],
        "brief_text": brief_text,
        "peer_name": hcp.get("peer_name"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }
