"""
Timeline Discrepancy Validator
Detects when claimed experience doesn't match actual work history timeline.
Flags hallucinations like "5 years React" when timeline only spans 2 years.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DiscrepancyFlag:
    flag_type: str          # "timeline_gap", "experience_inflation", "overlap", "date_inconsistency"
    severity: str           # "high", "medium", "low"
    description: str
    evidence: str


@dataclass
class ValidationResult:
    flags: List[DiscrepancyFlag] = field(default_factory=list)
    timeline_years: float = 0.0
    claimed_years: float = 0.0
    inflation_ratio: float = 0.0   # claimed / actual (>1.3 = suspicious)
    has_discrepancy: bool = False
    trust_score: float = 1.0       # 0-1, lower = less trustworthy

    def to_dict(self) -> Dict:
        return {
            "has_discrepancy": self.has_discrepancy,
            "trust_score": round(self.trust_score, 3),
            "timeline_years": round(self.timeline_years, 1),
            "claimed_years": round(self.claimed_years, 1),
            "inflation_ratio": round(self.inflation_ratio, 2),
            "flags": [
                {"type": f.flag_type, "severity": f.severity,
                 "description": f.description, "evidence": f.evidence}
                for f in self.flags
            ],
        }


def validate_candidate_timeline(candidate) -> ValidationResult:
    """
    Run timeline validation on a candidate profile.
    Checks for experience inflation, date inconsistencies, and suspicious gaps.
    """
    result = ValidationResult()
    result.claimed_years = candidate.total_years_experience

    # ── Compute actual timeline span ──────────────────────────────────────────
    if candidate.work_history:
        result.timeline_years = _compute_timeline_span(candidate.work_history)
    else:
        # No work history to validate against
        return result

    # ── Check experience inflation ────────────────────────────────────────────
    if result.timeline_years > 0 and result.claimed_years > 0:
        result.inflation_ratio = result.claimed_years / max(result.timeline_years, 0.5)

        if result.inflation_ratio > 2.0:
            result.flags.append(DiscrepancyFlag(
                flag_type="experience_inflation",
                severity="high",
                description=f"Claims {result.claimed_years:.0f}y but timeline only spans {result.timeline_years:.1f}y",
                evidence=f"Inflation ratio: {result.inflation_ratio:.1f}x"
            ))
        elif result.inflation_ratio > 1.4:
            result.flags.append(DiscrepancyFlag(
                flag_type="experience_inflation",
                severity="medium",
                description=f"Claimed experience ({result.claimed_years:.0f}y) exceeds timeline ({result.timeline_years:.1f}y)",
                evidence=f"Inflation ratio: {result.inflation_ratio:.1f}x"
            ))

    # ── Check for overlapping jobs (impossible timeline) ──────────────────────
    overlaps = _detect_overlaps(candidate.work_history)
    for overlap in overlaps:
        result.flags.append(DiscrepancyFlag(
            flag_type="overlap",
            severity="low",
            description="Overlapping employment periods detected",
            evidence=overlap
        ))

    # ── Check for suspiciously short stints ──────────────────────────────────
    short_stints = _detect_short_stints(candidate.work_history)
    if len(short_stints) >= 3:
        result.flags.append(DiscrepancyFlag(
            flag_type="timeline_gap",
            severity="medium",
            description=f"{len(short_stints)} roles under 6 months — pattern of instability",
            evidence=", ".join(short_stints[:3])
        ))

    # ── Compute trust score ───────────────────────────────────────────────────
    penalty = 0.0
    for flag in result.flags:
        if flag.severity == "high":
            penalty += 0.25
        elif flag.severity == "medium":
            penalty += 0.12
        else:
            penalty += 0.05

    result.trust_score = max(0.3, 1.0 - penalty)
    result.has_discrepancy = len(result.flags) > 0

    return result


def _compute_timeline_span(work_history: List[Dict]) -> float:
    """Compute total career span in years from work history."""
    from utils.career_analyzer import parse_date, compute_duration_months

    dates = []
    for job in work_history:
        start = parse_date(str(job.get("start_date", "")))
        end_str = str(job.get("end_date", "present"))
        end = parse_date(end_str) if end_str.lower() not in ("present", "current", "now", "") else datetime.now()
        if start:
            dates.append(start)
        if end:
            dates.append(end)

    if len(dates) < 2:
        return 0.0

    span_days = (max(dates) - min(dates)).days
    return max(0.0, span_days / 365.25)


def _detect_overlaps(work_history: List[Dict]) -> List[str]:
    """Detect jobs with overlapping date ranges."""
    from utils.career_analyzer import parse_date

    parsed = []
    for job in work_history:
        start = parse_date(str(job.get("start_date", "")))
        end_str = str(job.get("end_date", "present"))
        end = parse_date(end_str) if end_str.lower() not in ("present", "current", "now", "") else datetime.now()
        if start and end:
            parsed.append((start, end, job.get("title", "Unknown")))

    overlaps = []
    for i in range(len(parsed)):
        for j in range(i + 1, len(parsed)):
            s1, e1, t1 = parsed[i]
            s2, e2, t2 = parsed[j]
            # Check overlap: max(starts) < min(ends)
            overlap_start = max(s1, s2)
            overlap_end = min(e1, e2)
            if overlap_start < overlap_end:
                overlap_months = (overlap_end - overlap_start).days / 30.44
                if overlap_months > 2:  # ignore tiny overlaps (transition periods)
                    overlaps.append(f"{t1} ↔ {t2} ({overlap_months:.0f}mo overlap)")

    return overlaps


def _detect_short_stints(work_history: List[Dict]) -> List[str]:
    """Find roles shorter than 6 months."""
    from utils.career_analyzer import parse_date, compute_duration_months

    short = []
    for job in work_history:
        start = parse_date(str(job.get("start_date", "")))
        end_str = str(job.get("end_date", "present"))
        end = parse_date(end_str) if end_str.lower() not in ("present", "current", "now", "") else None
        duration = compute_duration_months(start, end)
        if 0 < duration < 6:
            short.append(f"{job.get('title', 'Unknown')} ({duration:.0f}mo)")

    return short
