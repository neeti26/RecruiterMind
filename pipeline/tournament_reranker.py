"""
Stage 4 — LLM Listwise Tournament Reranker
The secret weapon: instead of sorting by a single score,
we run mini-tournaments where an LLM compares groups of candidates
and produces ranked permutations. These are aggregated using the
Plackett-Luce model for a statistically robust final ranking.

Based on: "Agentic AI for Human Resources" (arXiv:2603.26710)
"""

import logging
import random
import math
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

TOURNAMENT_SYSTEM_PROMPT = """You are a world-class technical recruiter with deep expertise in evaluating candidates.
You will be given a job description and a group of candidate profiles.
Your task is to rank these candidates from BEST FIT to WORST FIT for the role.

Be a great recruiter — look at the full picture:
- Who has the right skills AND the right trajectory?
- Who has grown consistently vs. stagnated?
- Who shows genuine passion for the domain?
- Who is the right seniority level (not over/under-qualified)?

Respond with JSON only."""

TOURNAMENT_USER_TEMPLATE = """Rank these {n} candidates for the following role.

ROLE: {role_title} ({seniority_level})
REQUIRED SKILLS: {required_skills}
ROLE SUMMARY: {role_summary}

CANDIDATES:
{candidates_text}

Return JSON with this exact format:
{{
  "ranking": [1, 3, 2, 5, 4],
  "reasoning": "Brief explanation of your top 2-3 choices and why they stand out"
}}

Where the array contains candidate numbers (1-{n}) ordered from BEST to WORST fit.
Every candidate number must appear exactly once."""


def _format_candidate_for_tournament(candidate, rank: int) -> str:
    """Format a candidate profile for LLM tournament input."""
    analysis = candidate.raw_data.get("_career_analysis")
    trajectory = analysis.trajectory_direction if analysis else "unknown"
    total_years = analysis.total_years if analysis else candidate.total_years_experience

    lines = [
        f"CANDIDATE {rank}:",
        f"  Title: {candidate.current_title}",
        f"  Experience: {candidate.total_years_experience:.0f} years",
        f"  Skills: {', '.join(candidate.skills[:12])}",
        f"  Career trajectory: {trajectory}",
    ]

    if candidate.work_history:
        recent = candidate.work_history[:2]
        companies = [f"{j.get('title', '')} @ {j.get('company', '')}" for j in recent]
        lines.append(f"  Recent roles: {'; '.join(companies)}")

    if candidate.certifications:
        lines.append(f"  Certifications: {', '.join(candidate.certifications[:3])}")

    # Platform signals
    ps = candidate.platform_signals
    signals = []
    if ps.github_repos > 0:
        signals.append(f"{ps.github_repos} GitHub repos")
    if ps.open_source_contributions:
        signals.append("OSS contributor")
    if ps.publications > 0:
        signals.append(f"{ps.publications} publications")
    if ps.kaggle_rank:
        signals.append(f"Kaggle: {ps.kaggle_rank}")
    if signals:
        lines.append(f"  Platform: {', '.join(signals)}")

    lines.append(f"  Score breakdown: skill={candidate.scores.get('technical_skill_match', 0):.2f}, "
                 f"trajectory={candidate.scores.get('career_trajectory', 0):.2f}, "
                 f"seniority={candidate.scores.get('seniority_alignment', 0):.2f}")

    return "\n".join(lines)


class PlackettLuceAggregator:
    """
    Aggregates multiple ranked permutations using the Plackett-Luce model.
    Converts listwise rankings into stable global scores.

    The PL model assigns each item a "strength" parameter such that
    the probability of a ranking is proportional to the product of
    strengths at each position.

    We use a simple approximation: assign position-based scores
    and aggregate across rounds.
    """

    def __init__(self, n_items: int):
        self.n_items = n_items
        self.scores = defaultdict(float)
        self.appearances = defaultdict(int)

    def add_ranking(self, ranking: List[str], weight: float = 1.0):
        """
        Add a ranked list of candidate IDs.
        Position 0 = best, position n-1 = worst.
        """
        n = len(ranking)
        for position, cid in enumerate(ranking):
            # PL-inspired score: 1/(position+1) weighted by list length
            pl_score = weight * (1.0 / (position + 1)) * math.log(n + 1)
            self.scores[cid] += pl_score
            self.appearances[cid] += 1

    def get_final_ranking(self) -> List[Tuple[str, float]]:
        """Return candidates sorted by aggregated PL score."""
        # Normalize by appearances to handle unequal tournament participation
        normalized = {
            cid: score / max(1, self.appearances[cid])
            for cid, score in self.scores.items()
        }
        return sorted(normalized.items(), key=lambda x: x[1], reverse=True)


class TournamentReranker:
    """
    LLM Listwise Tournament Reranker.

    Runs multiple rounds of mini-tournaments where the LLM ranks
    small groups of candidates. Results are aggregated via Plackett-Luce.
    """

    def __init__(self, config=None, llm_client=None):
        from config import TournamentConfig
        self.config = config or TournamentConfig()
        self.llm = llm_client

    def rerank(
        self,
        candidates: List,  # List[CandidateProfile]
        jd_analysis,       # JDAnalysis
        top_n: int = None,
    ) -> List:
        """
        Rerank candidates using LLM tournaments.

        Args:
            candidates: Pre-scored candidates (sorted by score)
            jd_analysis: JD analysis for context
            top_n: Only tournament the top N candidates

        Returns:
            Reranked list of candidates
        """
        top_n = top_n or self.config.tournament_top_n

        if not self.llm or not self.llm.is_available():
            logger.info("LLM not available, skipping tournament reranking")
            return candidates

        # Split: tournament top-N, keep rest as-is
        tournament_pool = candidates[:top_n]
        rest = candidates[top_n:]

        if len(tournament_pool) < 2:
            return candidates

        logger.info(
            f"Running {self.config.num_rounds} tournament rounds "
            f"on top {len(tournament_pool)} candidates..."
        )

        aggregator = PlackettLuceAggregator(len(tournament_pool))

        for round_num in range(self.config.num_rounds):
            # Shuffle to avoid position bias
            pool_copy = list(tournament_pool)
            random.shuffle(pool_copy)

            # Run mini-tournaments
            for i in range(0, len(pool_copy), self.config.tournament_size):
                group = pool_copy[i:i + self.config.tournament_size]
                if len(group) < 2:
                    continue

                ranking = self._run_tournament(group, jd_analysis)
                if ranking:
                    aggregator.add_ranking(ranking, weight=1.0)

        # Get final PL ranking
        pl_ranking = aggregator.get_final_ranking()
        pl_scores = {cid: score for cid, score in pl_ranking}

        # Sort tournament pool by PL score
        tournament_pool.sort(
            key=lambda c: pl_scores.get(c.candidate_id, 0.0),
            reverse=True
        )

        # Update final scores with PL-adjusted values
        for i, candidate in enumerate(tournament_pool):
            pl_score = pl_scores.get(candidate.candidate_id, 0.0)
            # Blend original score with PL rank signal
            candidate.final_score = 0.6 * candidate.final_score + 0.4 * (
                pl_score / max(1, max(pl_scores.values()))
            )

        logger.info("Tournament reranking complete")
        return tournament_pool + rest

    def _run_tournament(
        self,
        group: List,  # List[CandidateProfile]
        jd_analysis,
    ) -> Optional[List[str]]:
        """
        Run a single mini-tournament for a group of candidates.
        Returns list of candidate IDs in ranked order (best first).
        """
        n = len(group)
        candidates_text = "\n\n".join(
            _format_candidate_for_tournament(c, i+1)
            for i, c in enumerate(group)
        )

        user_prompt = TOURNAMENT_USER_TEMPLATE.format(
            n=n,
            role_title=jd_analysis.role_title,
            seniority_level=jd_analysis.seniority_level,
            required_skills=", ".join(jd_analysis.required_skills[:10]),
            role_summary=jd_analysis.role_summary[:300],
            candidates_text=candidates_text,
        )

        try:
            result = self.llm.complete_json(
                TOURNAMENT_SYSTEM_PROMPT,
                user_prompt,
                temperature=self.config.llm_temperature,
            )

            ranking_indices = result.get("ranking", [])

            # Validate: must be a permutation of 1..n
            if (
                len(ranking_indices) == n
                and set(ranking_indices) == set(range(1, n+1))
            ):
                # Convert 1-indexed positions to candidate IDs
                return [group[idx-1].candidate_id for idx in ranking_indices]
            else:
                logger.warning(f"Invalid tournament ranking: {ranking_indices}")
                return None

        except Exception as e:
            logger.warning(f"Tournament round failed: {e}")
            return None
