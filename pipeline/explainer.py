"""
Stage 5 — Explainability & Bias Audit
Generates per-candidate recruiter narratives, why-hire one-liners,
hire recommendations, and a bias audit.
"""

import logging
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

EXPLANATION_SYSTEM_PROMPT = """You are a senior technical recruiter writing concise, evidence-based candidate assessments.
Be specific. Reference actual skills, companies, years. No fluff.
Respond with JSON only."""

EXPLANATION_USER_TEMPLATE = """Write a recruiter assessment for this candidate.

ROLE: {role_title} ({seniority_level})
CANDIDATE: {name} — {title} ({years}y exp)
RANK: #{rank} of {total} · SCORE: {final_score:.0%} · CONFIDENCE: {confidence:.0%}

SCORES:
  Tech Skills: {skill_score:.0%} | Career: {trajectory_score:.0%} | Domain: {domain_score:.0%}
  Seniority: {seniority_score:.0%} | Behavioral: {behavioral_score:.0%} | Culture: {culture_score:.0%}
  Risk: {risk_score:.0%} | Cross-Encoder: {ce_score:.0%}

MATCHED SKILLS: {matched_skills}
MISSING SKILLS: {missing_skills}
CRITICAL GAPS: {critical_gaps}
STRENGTHS: {strengths}

Return JSON:
{{
  "why_hire": "One punchy sentence a recruiter would say to a hiring manager. Be specific.",
  "recruiter_note": "2-3 sentence assessment. Evidence-based. What makes them stand out or fall short.",
  "hire_recommendation": "strong_yes|yes|maybe|no",
  "key_strength": "Single most compelling thing. Be specific.",
  "key_concern": "Single biggest concern. Be specific. 'None' if no concerns."
}}"""


@dataclass
class BiasAuditResult:
    gender_correlation: float = 0.0
    name_origin_variance: float = 0.0
    bias_detected: bool = False
    bias_flags: List[str] = field(default_factory=list)
    audit_passed: bool = True
    score_variance: float = 0.0
    dimension_variances: Dict[str, float] = field(default_factory=dict)


class Explainer:
    def __init__(self, llm_client=None):
        self.llm = llm_client

    def explain_candidates(self, candidates: List, jd_analysis, top_n: int = 20) -> List:
        total = len(candidates)
        for i, candidate in enumerate(candidates[:top_n]):
            try:
                self._explain_one(candidate, jd_analysis, rank=i+1, total=total)
            except Exception as e:
                logger.warning(f"Explanation failed for {candidate.candidate_id}: {e}")
                self._fallback_explain(candidate, i+1)
        return candidates

    def _explain_one(self, candidate, jd_analysis, rank: int, total: int):
        scores = candidate.scores
        gap = candidate.raw_data.get("_skill_gap")
        strengths = self._identify_strengths(candidate, jd_analysis, scores)

        if self.llm and self.llm.is_available():
            try:
                self._llm_explain(candidate, jd_analysis, rank, total, scores, gap, strengths)
                return
            except Exception as e:
                logger.warning(f"LLM explanation failed: {e}")

        self._rule_based_explain(candidate, jd_analysis, rank, scores, gap, strengths)

    def _llm_explain(self, candidate, jd_analysis, rank, total, scores, gap, strengths):
        user_prompt = EXPLANATION_USER_TEMPLATE.format(
            role_title=jd_analysis.role_title,
            seniority_level=jd_analysis.seniority_level,
            name=candidate.name,
            title=candidate.current_title,
            years=candidate.total_years_experience,
            rank=rank, total=total,
            final_score=candidate.final_score,
            confidence=candidate.confidence,
            skill_score=scores.get("technical_skill_match", 0),
            trajectory_score=scores.get("career_trajectory", 0),
            domain_score=scores.get("domain_depth", 0),
            seniority_score=scores.get("seniority_alignment", 0),
            behavioral_score=scores.get("behavioral_signals", 0),
            culture_score=scores.get("culture_soft_fit", 0),
            risk_score=scores.get("risk_penalty", 0),
            ce_score=scores.get("cross_encoder_score", 0),
            matched_skills=", ".join(gap.matched_required[:6]) if gap else "N/A",
            missing_skills=", ".join(gap.missing_required[:4]) if gap else "N/A",
            critical_gaps=", ".join(gap.critical_gaps[:3]) if gap else "None",
            strengths="; ".join(strengths[:3]) if strengths else "N/A",
        )
        result = self.llm.complete_json(EXPLANATION_SYSTEM_PROMPT, user_prompt)
        candidate.why_hire = result.get("why_hire", "")
        candidate.explanation = result.get("recruiter_note", "")
        candidate.hire_recommendation = result.get("hire_recommendation", "maybe")
        candidate.key_strength = result.get("key_strength", "")
        candidate.key_concern = result.get("key_concern", "")

    def _rule_based_explain(self, candidate, jd_analysis, rank, scores, gap, strengths):
        skill_score = scores.get("technical_skill_match", 0)
        seniority_score = scores.get("seniority_alignment", 0)
        trajectory_score = scores.get("career_trajectory", 0)

        # why_hire one-liner
        if skill_score >= 0.75 and seniority_score >= 0.8:
            candidate.why_hire = (
                f"{candidate.name} brings {candidate.total_years_experience:.0f} years of "
                f"directly relevant experience with strong coverage of required skills."
            )
        elif skill_score >= 0.6:
            candidate.why_hire = (
                f"{candidate.name} has solid technical foundations with "
                f"{int(skill_score*100)}% skill coverage for this role."
            )
        else:
            candidate.why_hire = (
                f"{candidate.name} shows potential but has skill gaps that need evaluation."
            )

        # Explanation
        parts = []
        if skill_score >= 0.75:
            parts.append(f"Strong technical match ({skill_score:.0%} skill coverage)")
        elif skill_score >= 0.55:
            parts.append(f"Good technical match ({skill_score:.0%} skill coverage)")
        else:
            parts.append(f"Partial technical match ({skill_score:.0%} skill coverage)")

        if trajectory_score >= 0.6:
            parts.append("upward career trajectory")
        if seniority_score < 0.6:
            parts.append("seniority level may not align")
        if gap and gap.missing_required:
            parts.append(f"missing: {', '.join(gap.missing_required[:2])}")

        candidate.explanation = ". ".join(parts).capitalize() + "."

        # Recommendation
        score = candidate.final_score
        if score >= 0.65:
            candidate.hire_recommendation = "strong_yes"
        elif score >= 0.50:
            candidate.hire_recommendation = "yes"
        elif score >= 0.38:
            candidate.hire_recommendation = "maybe"
        else:
            candidate.hire_recommendation = "no"

        candidate.key_strength = strengths[0] if strengths else "Relevant experience"
        if gap and gap.missing_required:
            candidate.key_concern = f"Missing: {', '.join(gap.missing_required[:2])}"
        elif seniority_score < 0.6:
            candidate.key_concern = "Seniority mismatch"
        else:
            candidate.key_concern = "None identified"

    def _fallback_explain(self, candidate, rank: int):
        candidate.explanation = f"Ranked #{rank} · Score: {candidate.final_score:.1%}"
        candidate.why_hire = candidate.explanation
        candidate.hire_recommendation = "maybe"
        candidate.key_strength = ""
        candidate.key_concern = ""

    def _identify_strengths(self, candidate, jd_analysis, scores) -> List[str]:
        strengths = []
        if scores.get("technical_skill_match", 0) >= 0.7:
            gap = candidate.raw_data.get("_skill_gap")
            if gap and gap.matched_required:
                strengths.append(f"Covers {len(gap.matched_required)} required skills: {', '.join(gap.matched_required[:3])}")
        analysis = candidate.raw_data.get("_career_analysis")
        if analysis:
            if analysis.trajectory_direction == "upward":
                strengths.append(f"Upward trajectory, {analysis.num_promotions} promotions")
            if analysis.company_quality_score >= 0.7:
                strengths.append("Top-tier company experience")
        ps = candidate.platform_signals
        if ps.open_source_contributions:
            strengths.append("Active OSS contributor")
        if ps.publications > 0:
            strengths.append(f"{ps.publications} publications")
        if ps.github_stars > 50:
            strengths.append(f"{ps.github_stars} GitHub stars")
        if scores.get("seniority_alignment", 0) >= 0.9:
            strengths.append("Perfect seniority match")
        return strengths

    # ── Bias Audit ────────────────────────────────────────────────────────────

    def run_bias_audit(self, candidates: List) -> BiasAuditResult:
        result = BiasAuditResult()
        if len(candidates) < 5:
            return result
        try:
            import numpy as np
            scores = [c.final_score for c in candidates]
            result.score_variance = float(np.var(scores))

            # Check dimension variances — low variance = not discriminating
            dims = ["technical_skill_match", "career_trajectory", "seniority_alignment"]
            for dim in dims:
                vals = [c.scores.get(dim, 0) for c in candidates]
                var = float(np.var(vals))
                result.dimension_variances[dim] = round(var, 4)
                if var < 0.001:
                    result.bias_flags.append(
                        f"'{dim}' has near-zero variance — may not be discriminating"
                    )

            # Check score gap
            if len(scores) >= 10:
                top5 = np.mean(scores[:5])
                bot5 = np.mean(scores[-5:])
                if top5 - bot5 > 0.55:
                    result.bias_flags.append(
                        "Large score gap between top and bottom — manual review recommended"
                    )

            result.bias_detected = len(result.bias_flags) > 0
            result.audit_passed = not result.bias_detected
        except Exception as e:
            logger.warning(f"Bias audit error: {e}")
        return result
