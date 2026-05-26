"""
PII Masker — Anonymous Mode
Masks names, locations, gender signals, and demographic indicators
so candidates are ranked purely on merit.
"""

import re
import hashlib
import logging
from typing import List

logger = logging.getLogger(__name__)

# Gender-coded name patterns (very conservative — only obvious cases)
GENDER_TITLES = re.compile(
    r'\b(Mr\.?|Mrs\.?|Ms\.?|Miss|Dr\.?|Prof\.?)\s+', re.IGNORECASE
)

# Common location patterns
LOCATION_PATTERN = re.compile(
    r'\b(bangalore|mumbai|delhi|hyderabad|chennai|pune|kolkata|india|usa|uk|'
    r'london|new york|san francisco|seattle|remote|work from home)\b',
    re.IGNORECASE
)

# University name patterns that might signal demographics
UNIVERSITY_PATTERN = re.compile(
    r'\b(iit|iim|nit|bits|vit|srm|anna university|delhi university|'
    r'mumbai university|pune university)\b',
    re.IGNORECASE
)


def mask_candidate(candidate, anon_mode: bool = False):
    """
    Apply PII masking to a candidate profile.
    Returns a copy with masked fields when anon_mode=True.
    """
    if not anon_mode:
        return candidate

    # Generate a stable anonymous ID from the real name
    name_hash = hashlib.md5(candidate.name.encode()).hexdigest()[:6].upper()
    candidate.name = f"Candidate #{name_hash}"

    # Mask location
    candidate.location = _mask_location(candidate.location)

    # Mask summary text
    candidate.summary_text = _mask_text(candidate.summary_text)

    # Mask work history company names (keep titles for relevance)
    for job in candidate.work_history:
        if "company" in job:
            job["company"] = _anonymize_company(job["company"])

    return candidate


def _mask_location(location: str) -> str:
    if not location:
        return ""
    # Replace specific city/country with region
    loc_lower = location.lower()
    if any(c in loc_lower for c in ["india", "bangalore", "mumbai", "delhi", "hyderabad", "chennai", "pune"]):
        return "South Asia"
    if any(c in loc_lower for c in ["usa", "new york", "san francisco", "seattle", "boston"]):
        return "North America"
    if any(c in loc_lower for c in ["uk", "london", "manchester"]):
        return "Europe"
    return "Undisclosed"


def _mask_text(text: str) -> str:
    if not text:
        return text
    # Remove gender titles
    text = GENDER_TITLES.sub("", text)
    # Mask locations
    text = LOCATION_PATTERN.sub("[LOCATION]", text)
    return text


def _anonymize_company(company: str) -> str:
    """Replace company name with tier indicator."""
    from utils.career_analyzer import classify_company_tier
    tier = classify_company_tier(company)
    tier_labels = {1: "Tier-1 Company", 2: "Tier-2 Company", 3: "Growth-Stage Company", 4: "Company"}
    return tier_labels.get(tier, "Company")


def mask_candidates_batch(candidates: List, anon_mode: bool) -> List:
    """Apply masking to a list of candidates."""
    if not anon_mode:
        return candidates
    return [mask_candidate(c, anon_mode=True) for c in candidates]
