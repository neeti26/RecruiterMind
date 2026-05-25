"""
RecruiterMind Demo
Runs the full pipeline on sample data without requiring an LLM API key.
Shows the power of the multi-dimensional scoring system.
"""

import os
import sys
from pathlib import Path

# Ensure we can import from project root
sys.path.insert(0, str(Path(__file__).parent))


def run_demo():
    """Run demo with sample data."""
    from main import run_pipeline
    from config import PipelineConfig, EmbeddingConfig, RetrievalConfig, ScoringWeights, TournamentConfig, LLMConfig

    print("=" * 60)
    print("  RecruiterMind Demo")
    print("  Hack2Skill India Runs 2026")
    print("=" * 60)
    print()

    # Config for demo: no LLM required
    config = PipelineConfig(
        embedding=EmbeddingConfig(
            model_name="nomic-ai/nomic-embed-text-v1.5",
            embedding_dim=768,
        ),
        retrieval=RetrievalConfig(top_k_retrieval=20),
        scoring=ScoringWeights(),
        tournament=TournamentConfig(tournament_top_n=10),
        llm=LLMConfig(
            provider="openai",
            api_key=os.getenv("OPENAI_API_KEY"),
            groq_api_key=os.getenv("GROQ_API_KEY"),
        ),
        output_top_n=10,
        generate_html_report=True,
        run_bias_audit=True,
        llm_fallback_to_score=True,  # Use score-only if no LLM
    )

    os.makedirs("output", exist_ok=True)

    results = run_pipeline(
        jd_path="data/sample_jd.txt",
        candidates_path="data/sample_candidates.csv",
        output_path="output/ranked_candidates.csv",
        report_path="output/report.html",
        config=config,
    )

    print("\n" + "=" * 60)
    print("  Demo complete!")
    print("  Check output/ranked_candidates.csv and output/report.html")
    print("=" * 60)

    return results


if __name__ == "__main__":
    run_demo()
