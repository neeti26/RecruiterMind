"""
Career Trajectory Analyzer
Extracts deep career intelligence from work history:
- Career velocity (how fast someone is growing)
- Tenure patterns (job-hopping vs. loyalty)
- Domain depth (years in relevant domain)
- Seniority trajectory (upward, lateral, downward)
- Company prestige signals
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import re
import math


@dataclass
class WorkExperience:
    title: str
    company: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]  # None = current
    duration_months: float
    is_current: bool
    seniority_level: int  # 0-7
    domain_relevance: float  # 0-1, set externally
    company_tier: int  # 1=FAANG/top, 2=mid, 3=startup, 4=unknown


@dataclass
class CareerAnalysis:
    total_years: float
    relevant_years: float
    career_velocity: float          # 0-1: how fast seniority is growing
    trajectory_direction: str       # "upward", "lateral", "downward", "mixed"
    avg_tenure_months: float
    job_hop_penalty: float          # 0-1: penalty for frequent switching
    domain_depth_score: float       # 0-1
    seniority_progression_score: float  # 0-1
    recency_weighted_relevance: float   # 0-1: recent experience matters more
    company_quality_score: float    # 0-1
    gap_penalty: float              # 0-1: penalty for unexplained gaps
    raw_seniority_levels: List[int]
    num_promotions: int
    num_companies: int


# ─── Company Tier Heuristics ──────────────────────────────────────────────────
TIER_1_COMPANIES = {
    "google", "meta", "apple", "amazon", "microsoft", "netflix",
    "openai", "anthropic", "deepmind", "nvidia", "tesla",
    "stripe", "airbnb", "uber", "lyft", "twitter", "x",
    "salesforce", "oracle", "ibm", "intel", "amd",
    "goldman sachs", "morgan stanley", "jpmorgan", "mckinsey",
    "infosys", "tcs", "wipro", "hcl", "cognizant",
    "flipkart", "zomato", "swiggy", "paytm", "razorpay",
    "byju", "ola", "meesho", "cred", "zepto",
}

TIER_2_COMPANIES = {
    "accenture", "deloitte", "pwc", "kpmg", "ey",
    "thoughtworks", "capgemini", "mphasis", "hexaware",
    "freshworks", "zoho", "browserstack", "postman",
}


def classify_company_tier(company_name: str) -> int:
    """Classify company into tier 1, 2, 3, or 4."""
    name_lower = company_name.lower().strip()
    for tier1 in TIER_1_COMPANIES:
        if tier1 in name_lower:
            return 1
    for tier2 in TIER_2_COMPANIES:
        if tier2 in name_lower:
            return 2
    # Heuristic: if it has "startup", "labs", "ai" in name → tier 3
    if any(kw in name_lower for kw in ["startup", "labs", "ventures", "ai", "tech"]):
        return 3
    return 4


def extract_seniority_from_title(title: str) -> int:
    """Extract seniority level (0-7) from job title."""
    from utils.skill_taxonomy import SENIORITY_LEVELS
    title_lower = title.lower()

    # Check for explicit level indicators
    for keyword, level in sorted(SENIORITY_LEVELS.items(), key=lambda x: -x[1]):
        if keyword in title_lower:
            return level

    # Fallback heuristics
    if any(w in title_lower for w in ["i ", "i,", " 1", "entry", "junior", "jr"]):
        return 1
    if any(w in title_lower for w in ["ii ", "ii,", " 2", "mid"]):
        return 2
    if any(w in title_lower for w in ["iii", " 3", "senior", "sr"]):
        return 3
    return 2  # default to mid


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats."""
    if not date_str or date_str.lower() in ("present", "current", "now", ""):
        return None

    formats = [
        "%Y-%m", "%m/%Y", "%b %Y", "%B %Y",
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y",
        "%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    # Try extracting year
    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
    if year_match:
        return datetime(int(year_match.group()), 1, 1)

    return None


def compute_duration_months(start: Optional[datetime], end: Optional[datetime]) -> float:
    """Compute duration in months between two dates."""
    if start is None:
        return 0.0
    end_dt = end or datetime.now()
    delta = end_dt - start
    return max(0.0, delta.days / 30.44)


def analyze_career(
    work_history: List[Dict],
    relevant_domain_keywords: List[str] = None
) -> CareerAnalysis:
    """
    Full career analysis from work history.

    Args:
        work_history: List of dicts with keys:
            title, company, start_date, end_date (or "present")
        relevant_domain_keywords: Keywords that define the target domain

    Returns:
        CareerAnalysis with all computed signals
    """
    relevant_domain_keywords = relevant_domain_keywords or []
    domain_kw_lower = [k.lower() for k in relevant_domain_keywords]

    if not work_history:
        return CareerAnalysis(
            total_years=0, relevant_years=0, career_velocity=0,
            trajectory_direction="unknown", avg_tenure_months=0,
            job_hop_penalty=0, domain_depth_score=0,
            seniority_progression_score=0, recency_weighted_relevance=0,
            company_quality_score=0, gap_penalty=0,
            raw_seniority_levels=[], num_promotions=0, num_companies=0
        )

    # ── Parse work history ────────────────────────────────────────────────────
    experiences: List[WorkExperience] = []
    for job in work_history:
        title = job.get("title", "")
        company = job.get("company", "")
        start_str = str(job.get("start_date", ""))
        end_str = str(job.get("end_date", "present"))

        start_dt = parse_date(start_str)
        end_dt = parse_date(end_str)
        is_current = end_dt is None
        duration = compute_duration_months(start_dt, end_dt)

        seniority = extract_seniority_from_title(title)
        tier = classify_company_tier(company)

        # Domain relevance: does this role relate to target domain?
        combined_text = f"{title} {company}".lower()
        domain_relevance = 0.0
        if domain_kw_lower:
            matches = sum(1 for kw in domain_kw_lower if kw in combined_text)
            domain_relevance = min(1.0, matches / max(1, len(domain_kw_lower) * 0.3))
        else:
            domain_relevance = 0.5  # neutral if no domain specified

        experiences.append(WorkExperience(
            title=title, company=company,
            start_date=start_dt, end_date=end_dt,
            duration_months=duration, is_current=is_current,
            seniority_level=seniority, domain_relevance=domain_relevance,
            company_tier=tier
        ))

    # Sort by start date (oldest first)
    experiences.sort(key=lambda x: x.start_date or datetime(1900, 1, 1))

    # ── Total & relevant years ────────────────────────────────────────────────
    total_months = sum(e.duration_months for e in experiences)
    total_years = total_months / 12.0

    relevant_months = sum(
        e.duration_months * e.domain_relevance for e in experiences
    )
    relevant_years = relevant_months / 12.0

    # ── Career velocity ───────────────────────────────────────────────────────
    # How fast is seniority growing relative to time?
    seniority_levels = [e.seniority_level for e in experiences]
    if len(seniority_levels) >= 2:
        seniority_gain = seniority_levels[-1] - seniority_levels[0]
        # Normalize: gaining 3 levels in 5 years = excellent velocity
        velocity = min(1.0, max(0.0, seniority_gain / max(1, total_years / 2)))
    else:
        velocity = 0.5  # neutral

    # ── Trajectory direction ──────────────────────────────────────────────────
    if len(seniority_levels) >= 2:
        diffs = [seniority_levels[i+1] - seniority_levels[i]
                 for i in range(len(seniority_levels)-1)]
        up = sum(1 for d in diffs if d > 0)
        down = sum(1 for d in diffs if d < 0)
        if up > down * 2:
            trajectory = "upward"
        elif down > up * 2:
            trajectory = "downward"
        elif up > 0 and down > 0:
            trajectory = "mixed"
        else:
            trajectory = "lateral"
    else:
        trajectory = "lateral"

    # ── Tenure & job-hopping ──────────────────────────────────────────────────
    tenures = [e.duration_months for e in experiences if e.duration_months > 0]
    avg_tenure = sum(tenures) / len(tenures) if tenures else 0

    # Job-hopping penalty: < 12 months average = red flag
    short_stints = sum(1 for t in tenures if t < 12)
    hop_ratio = short_stints / max(1, len(tenures))
    job_hop_penalty = min(1.0, hop_ratio * 1.5)

    # ── Domain depth score ────────────────────────────────────────────────────
    # Weighted by recency: recent experience counts more
    now = datetime.now()
    recency_weighted_domain = 0.0
    total_weight = 0.0
    for exp in experiences:
        if exp.start_date:
            months_ago = (now - (exp.end_date or now)).days / 30.44
            recency_weight = math.exp(-0.05 * months_ago)  # decay over time
            recency_weighted_domain += exp.domain_relevance * exp.duration_months * recency_weight
            total_weight += exp.duration_months * recency_weight

    recency_weighted_relevance = recency_weighted_domain / max(1, total_weight)

    # Domain depth: relevant years normalized (10 years = max)
    domain_depth_score = min(1.0, relevant_years / 10.0)

    # ── Seniority progression ─────────────────────────────────────────────────
    if seniority_levels:
        max_level = max(seniority_levels)
        seniority_progression_score = min(1.0, max_level / 5.0)
    else:
        seniority_progression_score = 0.0

    # ── Company quality ───────────────────────────────────────────────────────
    tier_scores = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.3}
    company_scores = [tier_scores.get(e.company_tier, 0.3) for e in experiences]
    company_quality_score = sum(company_scores) / max(1, len(company_scores))

    # ── Gap penalty ───────────────────────────────────────────────────────────
    gap_penalty = _compute_gap_penalty(experiences)

    # ── Promotions ────────────────────────────────────────────────────────────
    num_promotions = sum(
        1 for i in range(1, len(seniority_levels))
        if seniority_levels[i] > seniority_levels[i-1]
    )

    return CareerAnalysis(
        total_years=total_years,
        relevant_years=relevant_years,
        career_velocity=velocity,
        trajectory_direction=trajectory,
        avg_tenure_months=avg_tenure,
        job_hop_penalty=job_hop_penalty,
        domain_depth_score=domain_depth_score,
        seniority_progression_score=seniority_progression_score,
        recency_weighted_relevance=recency_weighted_relevance,
        company_quality_score=company_quality_score,
        gap_penalty=gap_penalty,
        raw_seniority_levels=seniority_levels,
        num_promotions=num_promotions,
        num_companies=len(set(e.company for e in experiences)),
    )


def _compute_gap_penalty(experiences: List[WorkExperience]) -> float:
    """Compute penalty for unexplained employment gaps > 3 months."""
    if len(experiences) < 2:
        return 0.0

    total_gap_months = 0.0
    for i in range(1, len(experiences)):
        prev_end = experiences[i-1].end_date
        curr_start = experiences[i].start_date
        if prev_end and curr_start:
            gap = (curr_start - prev_end).days / 30.44
            if gap > 3:  # gaps under 3 months are normal
                total_gap_months += gap - 3

    # Normalize: 12 months of gaps = max penalty
    return min(1.0, total_gap_months / 12.0)


def compute_career_trajectory_score(analysis: CareerAnalysis) -> float:
    """
    Aggregate career trajectory into a single 0-1 score.
    Combines velocity, progression, domain depth, and company quality.
    """
    score = (
        0.30 * analysis.career_velocity
        + 0.25 * analysis.seniority_progression_score
        + 0.20 * analysis.recency_weighted_relevance
        + 0.15 * analysis.company_quality_score
        + 0.10 * min(1.0, analysis.num_promotions / 3.0)
        - 0.20 * analysis.job_hop_penalty
        - 0.10 * analysis.gap_penalty
    )
    return max(0.0, min(1.0, score))
