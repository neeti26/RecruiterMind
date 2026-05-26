"""
RecruiterMind Configuration
All tunable parameters in one place.
"""

from dataclasses import dataclass, field
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class EmbeddingConfig:
    model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    # Matryoshka dimension — 768 for max quality, 256 for speed
    embedding_dim: int = 768
    batch_size: int = 32
    max_seq_length: int = 2048
    # Instruction prefixes for nomic-embed
    query_prefix: str = "search_query: "
    document_prefix: str = "search_document: "


@dataclass
class RetrievalConfig:
    # How many candidates to retrieve before precision reranking
    top_k_retrieval: int = 50
    # BM25 vs dense weight in RRF fusion
    bm25_weight: float = 0.4
    dense_weight: float = 0.6
    # RRF constant (60 is standard)
    rrf_k: int = 60
    # FAISS index type: "flat" (exact), "ivf" (fast approx)
    faiss_index_type: str = "flat"


@dataclass
class ScoringWeights:
    """
    Weights for the 7 scoring dimensions.
    Must sum to 1.0. Tune these per role type if needed.
    """
    technical_skill_match: float = 0.28
    career_trajectory: float = 0.18
    domain_depth: float = 0.16
    seniority_alignment: float = 0.14
    behavioral_signals: float = 0.10
    culture_soft_fit: float = 0.08
    risk_penalty: float = 0.06  # subtracted

    def validate(self):
        total = (
            self.technical_skill_match
            + self.career_trajectory
            + self.domain_depth
            + self.seniority_alignment
            + self.behavioral_signals
            + self.culture_soft_fit
            + self.risk_penalty
        )
        assert abs(total - 1.0) < 1e-6, f"Weights must sum to 1.0, got {total}"


@dataclass
class TournamentConfig:
    """LLM Listwise Tournament settings."""
    # Candidates per mini-tournament
    tournament_size: int = 3
    # Number of tournament rounds (more = more stable)
    num_rounds: int = 1
    # Top-N to run through tournament (rest ranked by score)
    tournament_top_n: int = 10
    # Temperature for LLM ranking (lower = more deterministic)
    llm_temperature: float = 0.1


@dataclass
class LLMConfig:
    provider: str = "openai"  # "openai" | "groq" | "ollama"
    model: str = "gpt-4o"
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    groq_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    # Groq model for fast inference
    groq_model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 2048
    timeout: int = 60


@dataclass
class PipelineConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    scoring: ScoringWeights = field(default_factory=ScoringWeights)
    tournament: TournamentConfig = field(default_factory=TournamentConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Output settings
    output_top_n: int = 20
    generate_html_report: bool = True
    run_bias_audit: bool = True

    # Fallback: if no LLM key, skip tournament and use score-only ranking
    llm_fallback_to_score: bool = True


# Default config instance
DEFAULT_CONFIG = PipelineConfig()
