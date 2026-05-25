"""
Stage 3 — Multi-Dimensional Scorer (Precision Layer)
7 independent dimensions + cross-encoder reranking + skill gap analysis.

Dimensions:
1. Technical Skill Match — taxonomy overlap + semantic + cross-encoder
2. Career Trajectory    — velocity, growth arc, company quality
3. Domain Depth         — years × breadth × recency in target domain
4. Seniority Alignment  — level fit (penalizes over/under-qualification)
5. Behavioral Signals   — platform activity, OSS, publications
6. Culture & Soft Fit   — LLM-inferred or heuristic
7. Risk Penalty         — job-hopping, gaps, red flags
"""

import numpy as np
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CULTURE_FIT_SYSTEM_PROMPT = """You are an expert recruiter evaluating candidate-role cultural fit.
Assess how well the candidate's background aligns with the role's culture signals.
Score from 0.0 to 1.0. Respond with JSON only."""

CULTURE_FIT_USER_TEMPLATE = """Rate the cultural and soft skill fit.

ROLE CULTURE SIGNALS: {culture_signals}
ROLE SOFT SKILLS: {soft_skills}
CANDIDATE: {title}, {years} years, trajectory={trajectory}
SKILLS: {skills}
SUMMARY: {summary}

Return JSON: {{"culture_fit_score": 0.0, "soft_skill_score": 0.0, "reasoning": "..."}}"""


@dataclass
class SkillGapAnalysis:
    """Detailed skill gap breakdown for a candidate."""
    matched_required: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    matched_nice: List[str] = field(default_factory=list)
    missing_nice: List[str] = field(default_factory=list)
    required_coverage: float = 0.0
    nice_coverage: float = 0.0
    # Criticality: which missing skills are most important
    critical_gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "matched_required": self.matched_required,
            "missing_required": self.missing_required,
            "matched_nice": self.matched_nice,
            "missing_nice": self.missing_nice,
            "required_coverage": round(self.required_coverage, 3),
            "nice_coverage": round(self.nice_coverage, 3),
            "critical_gaps": self.critical_gaps,
        }


@dataclass
class DimensionScores:
    technical_skill_match: float = 0.0
    career_trajectory: float = 0.0
    domain_depth: float = 0.0
    seniority_alignment: float = 0.0
    behavioral_signals: float = 0.0
    culture_soft_fit: float = 0.0
    risk_penalty: float = 0.0
    cross_encoder_score: float = 0.0   # bonus precision signal
    skill_gap: Optional[SkillGapAnalysis] = field(default=None)

    def weighted_total(self, weights) -> float:
        base = (
            weights.technical_skill_match * self.technical_skill_match
            + weights.career_trajectory    * self.career_trajectory
            + weights.domain_depth         * self.domain_depth
            + weights.seniority_alignment  * self.seniority_alignment
            + weights.behavioral_signals   * self.behavioral_signals
            + weights.culture_soft_fit     * self.culture_soft_fit
            - weights.risk_penalty         * self.risk_penalty
        )
        # Cross-encoder blended in as a 15% signal when available
        if self.cross_encoder_score > 0:
            base = 0.85 * base + 0.15 * self.cross_encoder_score
        return max(0.0, min(1.0, base))

    def to_dict(self) -> Dict:
        return {
            "technical_skill_match": round(self.technical_skill_match, 4),
            "career_trajectory":     round(self.career_trajectory, 4),
            "domain_depth":          round(self.domain_depth, 4),
            "seniority_alignment":   round(self.seniority_alignment, 4),
            "behavioral_signals":    round(self.behavioral_signals, 4),
            "culture_soft_fit":      round(self.culture_soft_fit, 4),
            "risk_penalty":          round(self.risk_penalty, 4),
            "cross_encoder_score":   round(self.cross_encoder_score, 4),
        }


class MultiDimScorer:
    def __init__(self, config=None, llm_client=None, embedder=None, cross_encoder=None):
        from config import ScoringWeights
        self.weights = config or ScoringWeights()
        self.llm = llm_client
        self.embedder = embedder
        self.cross_encoder = cross_encoder

    def score_candidate(
        self,
        candidate,
        jd_analysis,
        semantic_similarity: float = 0.0,
        cross_encoder_score: float = 0.0,
    ) -> DimensionScores:
        scores = DimensionScores()

        # 1. Technical Skill Match (taxonomy + semantic + cross-encoder)
        skill_gap, skill_score = self._score_technical_skills(
            candidate, jd_analysis, semantic_similarity
        )
        scores.technical_skill_match = skill_score
        scores.skill_gap = skill_gap

        # Store gap on candidate for UI
        candidate.raw_data["_skill_gap"] = skill_gap

        # 2. Career Trajectory
        scores.career_trajectory = self._score_career_trajectory(candidate, jd_analysis)

        # 3. Domain Depth
        scores.domain_depth = self._score_domain_depth(candidate, jd_analysis)

        # 4. Seniority Alignment
        scores.seniority_alignment = self._score_seniority_alignment(candidate, jd_analysis)

        # 5. Behavioral Signals
        scores.behavioral_signals = self._score_behavioral_signals(candidate)

        # 6. Culture & Soft Skill Fit
        scores.culture_soft_fit = self._score_culture_fit(candidate, jd_analysis)

        # 7. Risk Penalty
        scores.risk_penalty = self._score_risk_penalty(candidate)

        # 8. Cross-encoder precision signal
        scores.cross_encoder_score = cross_encoder_score

        return scores

    # ── Dimension 1 ──────────────────────────────────────────────────────────

    def _score_technical_skills(self, candidate, jd_analysis, semantic_similarity):
        from utils.skill_taxonomy import compute_skill_overlap, SKILL_CATEGORIES

        overlap = compute_skill_overlap(
            candidate.skills,
            jd_analysis.required_skills,
            jd_analysis.nice_to_have_skills,
        )

        # Build skill gap analysis
        gap = SkillGapAnalysis(
            matched_required=overlap["matched_required"],
            missing_required=overlap["missing_required"],
            matched_nice=overlap.get("matched_nice", []),
            missing_nice=overlap.get("missing_nice", []),
            required_coverage=overlap["required_coverage"],
            nice_coverage=overlap.get("nice_coverage", 0.0),
        )

        # Identify critical gaps: missing required skills that appear in
        # high-priority categories (ml_ai_core, programming_languages)
        critical_cats = {"ml_ai_core", "programming_languages", "ml_frameworks"}
        gap.critical_gaps = [
            s for s in gap.missing_required
            if any(s in SKILL_CATEGORIES.get(cat, []) for cat in critical_cats)
        ][:3]

        taxonomy_score = overlap["total_score"]
        blended = 0.55 * taxonomy_score + 0.45 * semantic_similarity

        if overlap["required_coverage"] >= 0.9:
            blended = min(1.0, blended * 1.08)

        return gap, min(1.0, blended)

    # ── Dimension 2 ──────────────────────────────────────────────────────────

    def _score_career_trajectory(self, candidate, jd_analysis) -> float:
        from utils.career_analyzer import analyze_career, compute_career_trajectory_score

        analysis = analyze_career(
            candidate.work_history,
            relevant_domain_keywords=jd_analysis.domain_keywords,
        )
        candidate.raw_data["_career_analysis"] = analysis
        traj_score = compute_career_trajectory_score(analysis)

        # If no work history dates available, fall back to years-of-experience
        # heuristic so the score isn't always 0.
        if not candidate.work_history or analysis.total_years == 0:
            yrs = candidate.total_years_experience
            # Normalise: 0y→0, 3y→0.35, 6y→0.55, 10y→0.70, 15y→0.80
            import math
            traj_score = min(0.80, 0.80 * (1 - math.exp(-yrs / 10)))

        return traj_score

    # ── Dimension 3 ──────────────────────────────────────────────────────────

    def _score_domain_depth(self, candidate, jd_analysis) -> float:
        from utils.career_analyzer import analyze_career
        analysis = candidate.raw_data.get("_career_analysis")
        if analysis is None:
            analysis = analyze_career(
                candidate.work_history,
                relevant_domain_keywords=jd_analysis.domain_keywords,
            )

        depth_score = analysis.domain_depth_score

        # Skill-based domain coverage (works even without work history dates)
        domain_kw_lower = [k.lower() for k in jd_analysis.domain_keywords]
        if domain_kw_lower:
            skill_domain_overlap = sum(
                1 for s in candidate.skills
                if any(kw in s.lower() for kw in domain_kw_lower)
            )
            skill_domain_ratio = min(1.0, skill_domain_overlap / max(1, len(domain_kw_lower) * 0.5))
        else:
            skill_domain_ratio = 0.5

        # If no work history, rely more on skill overlap
        if not candidate.work_history or analysis.total_years == 0:
            return skill_domain_ratio

        return 0.55 * depth_score + 0.45 * skill_domain_ratio

    # ── Dimension 4 ──────────────────────────────────────────────────────────

    def _score_seniority_alignment(self, candidate, jd_analysis) -> float:
        from utils.skill_taxonomy import SENIORITY_LEVELS, years_to_seniority_level
        title_lower = candidate.current_title.lower()
        candidate_level = 2
        for kw, level in sorted(SENIORITY_LEVELS.items(), key=lambda x: -x[1]):
            if kw in title_lower:
                candidate_level = level
                break
        years_level = years_to_seniority_level(candidate.total_years_experience)
        candidate_level = max(candidate_level, years_level)
        target_level = SENIORITY_LEVELS.get(jd_analysis.seniority_level.lower(), 2)
        diff = abs(candidate_level - target_level)
        return [1.0, 0.80, 0.50, 0.25, 0.05][min(diff, 4)]

    # ── Dimension 5 ──────────────────────────────────────────────────────────

    def _score_behavioral_signals(self, candidate) -> float:
        return candidate.platform_signals.compute_score()

    # ── Dimension 6 ──────────────────────────────────────────────────────────

    def _score_culture_fit(self, candidate, jd_analysis) -> float:
        if self.llm and self.llm.is_available() and (
            jd_analysis.culture_signals or jd_analysis.soft_skills_required
        ):
            try:
                return self._llm_culture_fit(candidate, jd_analysis)
            except Exception as e:
                logger.warning(f"LLM culture fit failed: {e}")
        return self._heuristic_culture_fit(candidate, jd_analysis)

    def _llm_culture_fit(self, candidate, jd_analysis) -> float:
        analysis = candidate.raw_data.get("_career_analysis")
        trajectory = analysis.trajectory_direction if analysis else "unknown"
        user_prompt = CULTURE_FIT_USER_TEMPLATE.format(
            culture_signals=", ".join(jd_analysis.culture_signals[:5]),
            soft_skills=", ".join(jd_analysis.soft_skills_required[:5]),
            title=candidate.current_title,
            years=candidate.total_years_experience,
            trajectory=trajectory,
            skills=", ".join(candidate.skills[:15]),
            summary=candidate.summary_text[:300],
        )
        result = self.llm.complete_json(CULTURE_FIT_SYSTEM_PROMPT, user_prompt)
        return 0.5 * float(result.get("culture_fit_score", 0.5)) + \
               0.5 * float(result.get("soft_skill_score", 0.5))

    def _heuristic_culture_fit(self, candidate, jd_analysis) -> float:
        score = 0.5
        if jd_analysis.soft_skills_required:
            text = " ".join(candidate.skills + [candidate.summary_text]).lower()
            matches = sum(1 for s in jd_analysis.soft_skills_required if s.lower() in text)
            score = 0.4 + 0.6 * (matches / len(jd_analysis.soft_skills_required))
        return min(1.0, score)

    # ── Dimension 7 ──────────────────────────────────────────────────────────

    def _score_risk_penalty(self, candidate) -> float:
        analysis = candidate.raw_data.get("_career_analysis")
        if analysis is None:
            return 0.0
        penalty = (
            0.4 * analysis.job_hop_penalty
            + 0.3 * analysis.gap_penalty
            + (0.3 if analysis.trajectory_direction == "downward" else 0.0)
        )
        return min(1.0, penalty)

    def compute_final_score(self, scores: DimensionScores) -> float:
        return max(0.0, min(1.0, scores.weighted_total(self.weights)))

    def compute_confidence(self, scores: DimensionScores, candidate) -> float:
        """
        Confidence in the score: higher when multiple signals agree.
        Low confidence = signals are contradictory (e.g. high skills, low trajectory).
        """
        signal_scores = [
            scores.technical_skill_match,
            scores.career_trajectory,
            scores.domain_depth,
            scores.seniority_alignment,
        ]
        # Confidence = 1 - normalized std dev of key signals
        std = float(np.std(signal_scores))
        confidence = max(0.4, 1.0 - std)
        # Boost confidence if cross-encoder agrees with taxonomy
        if scores.cross_encoder_score > 0:
            agreement = 1.0 - abs(scores.cross_encoder_score - scores.technical_skill_match)
            confidence = 0.7 * confidence + 0.3 * agreement
        return round(min(1.0, confidence), 3)
