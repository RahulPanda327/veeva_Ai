"""Match HCP ICD-10 diagnosis codes against target codes for Module 2."""
from typing import Dict, List

from app.config import settings


def match_icd10_codes(icd10_raw: str, target_codes: List[str] = None) -> List[str]:
    """Return list of target ICD-10 codes found in the HCP's comma-separated icd10_codes field."""
    if target_codes is None:
        target_codes = settings.TARGET_ICD10_CODES

    if not icd10_raw:
        return []

    hcp_codes = {code.strip().upper() for code in icd10_raw.split(",")}
    target_set = {code.upper() for code in target_codes}
    return sorted(hcp_codes & target_set)


def enrich_with_icd10(candidates: List[Dict]) -> List[Dict]:
    """Add matched_icd10_codes to each candidate dict in place."""
    for candidate in candidates:
        candidate["matched_icd10_codes"] = match_icd10_codes(
            candidate.get("icd10_codes_raw", "")
        )
    return candidates
