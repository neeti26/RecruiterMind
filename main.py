"""
RecruiterMind — Main Pipeline Entry Point
Hack2Skill India Runs 2026 — Data & AI Challenge

Usage:
  python main.py --jd data/job_description.txt --candidates data/candidates.csv
  python main.py --jd data/job_description.txt --candidates data/candidates.csv \
                 --output output/ranked.csv --report output/report.html
"""

import os
import sys
import csv
import logging
import argparse
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

# ── Setup ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("recruiter_mind")
console = Console()


def run_pipeline(
    jd_path: str,
    candidates_path: str,
    output_path: str = "output/ranked_candidates.csv",
    report_path: Optional[str] = "output/report.html",
    config=None,
) -> List:
    """
    Run the full RecruiterMind pipeline.

    Returns:
        List of ranked CandidateProfile objects
    """
    from config import PipelineConfig, DEFAULT_CONFIG
    from models.embedder import Embedder
    from models.llm_client import LLMClient
    from pipeline.jd_intelligence import JDIntelligence
    from pipeline.candidate_profiler import CandidateProfiler
    from pipeline.hybrid_retrieval import HybridRetriever
    from pipeline.multi_dim_scorer import MultiDimScorer
    from pipeline.tournament_reranker import TournamentReranker
    from pipeline.explainer import Explainer
    from utils.report_generator import generate_html_report

    config = config or DEFAULT_CONFIG
    start_time = time.time()

    console.print(Panel.fit(
        "[bold blue]🧠 RecruiterMind[/bold blue]\n"
        "[dim]AI Candidate Ranking — Hack2Skill India Runs 2026[/dim]",
        border_style="blue"
    ))

    # ── Initialize components ─────────────────────────────────────────────────
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:

        task = progress.add_task("Loading embedding model...", total=None)
        embedder = Embedder(
            model_name=config.embedding.model_name,
            embedding_dim=config.embedding.embedding_dim,
            batch_size=config.embedding.batch_size,
        )
        progress.update(task, description="✅ Embedding model loaded")

        task2 = progress.add_task("Initializing LLM client...", total=None)
        llm = LLMClient(config.llm)
        if llm.is_available():
            progress.update(task2, description="✅ LLM client ready")
        else:
            progress.update(task2, description="⚠️  No LLM — using rule-based fallback")

    # ── Stage 0: JD Intelligence ──────────────────────────────────────────────
    console.print("\n[bold cyan]Stage 0:[/bold cyan] Analyzing job description...")
    jd_text = Path(jd_path).read_text(encoding="utf-8")
    jd_intel = JDIntelligence(llm_client=llm)
    jd_analysis = jd_intel.analyze(jd_text)

    console.print(f"  Role: [bold]{jd_analysis.role_title}[/bold] ({jd_analysis.seniority_level})")
    console.print(f"  Required skills: {', '.join(jd_analysis.required_skills[:8])}")
    console.print(f"  Domain: {', '.join(jd_analysis.domain_keywords[:5])}")

    # ── Stage 1: Candidate Profiling ──────────────────────────────────────────
    console.print("\n[bold cyan]Stage 1:[/bold cyan] Profiling candidates...")
    profiler = CandidateProfiler(llm_client=None)  # Rule-based for speed at scale
    candidates = _load_candidates(candidates_path, profiler)
    console.print(f"  Loaded [bold]{len(candidates)}[/bold] candidates")

    # ── Embed all candidates ──────────────────────────────────────────────────
    console.print("\n[bold cyan]Embedding:[/bold cyan] Computing semantic embeddings...")
    candidate_texts = [c.to_embedding_text() for c in candidates]

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), console=console) as progress:
        task = progress.add_task(f"Embedding {len(candidates)} candidates...", total=len(candidates))
        embeddings = embedder.embed_documents(candidate_texts)
        progress.update(task, completed=len(candidates))

    for i, candidate in enumerate(candidates):
        candidate.embedding = embeddings[i]

    # Embed JD query
    jd_embedding = embedder.embed_query(jd_analysis.to_search_text())

    # ── Stage 2: Hybrid Retrieval ─────────────────────────────────────────────
    console.print("\n[bold cyan]Stage 2:[/bold cyan] Hybrid retrieval (FAISS + BM25)...")
    retriever = HybridRetriever(config.retrieval)
    retriever.index_candidates(
        candidate_ids=[c.candidate_id for c in candidates],
        embeddings=embeddings,
        corpus_texts=candidate_texts,
    )

    # If dataset is small, rank all; otherwise retrieve top-K
    if len(candidates) <= config.retrieval.top_k_retrieval:
        retrieved = retriever.get_all_candidates_ranked_by_similarity(jd_embedding)
    else:
        retrieved = retriever.retrieve(
            jd_embedding,
            jd_analysis.to_search_text(),
            top_k=config.retrieval.top_k_retrieval,
        )

    # Build candidate lookup
    cand_map = {c.candidate_id: c for c in candidates}
    # Compute semantic similarity for each retrieved candidate
    sim_map = {cid: score for cid, score in retrieved}

    retrieved_candidates = [
        cand_map[cid] for cid, _ in retrieved if cid in cand_map
    ]
    console.print(f"  Retrieved [bold]{len(retrieved_candidates)}[/bold] candidates for scoring")

    # ── Stage 3: Multi-Dimensional Scoring ───────────────────────────────────
    console.print("\n[bold cyan]Stage 3:[/bold cyan] Multi-dimensional scoring (7 dimensions)...")
    scorer = MultiDimScorer(config.scoring, llm_client=llm, embedder=embedder)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), console=console) as progress:
        task = progress.add_task("Scoring candidates...", total=len(retrieved_candidates))
        for candidate in retrieved_candidates:
            sem_sim = sim_map.get(candidate.candidate_id, 0.0)
            # Normalize similarity to 0-1 range
            sem_sim = max(0.0, min(1.0, (sem_sim + 1) / 2))

            dim_scores = scorer.score_candidate(candidate, jd_analysis, sem_sim)
            candidate.scores = dim_scores.to_dict()
            candidate.final_score = scorer.compute_final_score(dim_scores)
            progress.advance(task)

    # Sort by final score
    retrieved_candidates.sort(key=lambda c: c.final_score, reverse=True)

    # ── Stage 4: LLM Tournament Reranking ────────────────────────────────────
    if llm.is_available() and not config.llm_fallback_to_score:
        console.print("\n[bold cyan]Stage 4:[/bold cyan] LLM tournament reranking...")
        reranker = TournamentReranker(config.tournament, llm_client=llm)
        retrieved_candidates = reranker.rerank(
            retrieved_candidates, jd_analysis,
            top_n=config.tournament.tournament_top_n
        )
        # Re-sort after tournament
        retrieved_candidates.sort(key=lambda c: c.final_score, reverse=True)
    elif llm.is_available():
        console.print("\n[bold cyan]Stage 4:[/bold cyan] LLM tournament reranking...")
        reranker = TournamentReranker(config.tournament, llm_client=llm)
        retrieved_candidates = reranker.rerank(
            retrieved_candidates, jd_analysis,
            top_n=config.tournament.tournament_top_n
        )
        retrieved_candidates.sort(key=lambda c: c.final_score, reverse=True)
    else:
        console.print("\n[dim]Stage 4: Skipped (no LLM available)[/dim]")

    # Assign final ranks
    for i, candidate in enumerate(retrieved_candidates):
        candidate.final_rank = i + 1

    # ── Stage 5: Explainability & Bias Audit ─────────────────────────────────
    console.print("\n[bold cyan]Stage 5:[/bold cyan] Generating explanations & bias audit...")
    explainer = Explainer(llm_client=llm)
    retrieved_candidates = explainer.explain_candidates(
        retrieved_candidates, jd_analysis, top_n=config.output_top_n
    )

    bias_audit = None
    if config.run_bias_audit:
        bias_audit = explainer.run_bias_audit(retrieved_candidates)
        status = "✅ PASSED" if bias_audit.audit_passed else "⚠️  REVIEW NEEDED"
        console.print(f"  Bias audit: {status}")

    # ── Output ────────────────────────────────────────────────────────────────
    console.print("\n[bold cyan]Output:[/bold cyan] Saving results...")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    _save_csv(retrieved_candidates[:config.output_top_n], output_path)
    console.print(f"  CSV saved: [bold]{output_path}[/bold]")

    if report_path and config.generate_html_report:
        os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
        generate_html_report(
            retrieved_candidates, jd_analysis, bias_audit,
            report_path, top_n=config.output_top_n
        )
        console.print(f"  HTML report: [bold]{report_path}[/bold]")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    _print_summary(retrieved_candidates[:10], elapsed)

    return retrieved_candidates


def _load_candidates(path: str, profiler) -> List:
    """Load candidates from CSV file."""
    candidates = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            cid = str(row.get("id", row.get("candidate_id", f"C{i+1:04d}")))
            candidate = profiler.profile_from_csv_row(row, cid)
            candidates.append(candidate)
    return candidates


def _save_csv(candidates: List, output_path: str):
    """Save ranked candidates to CSV."""
    if not candidates:
        return

    fieldnames = list(candidates[0].to_dict().keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(candidate.to_dict())


def _print_summary(top_candidates: List, elapsed: float):
    """Print a rich summary table."""
    console.print(f"\n[bold green]✅ Pipeline complete in {elapsed:.1f}s[/bold green]\n")

    table = Table(title="🏆 Top 10 Candidates", border_style="blue")
    table.add_column("Rank", style="bold yellow", width=6)
    table.add_column("Name", style="bold white", width=25)
    table.add_column("Title", style="dim", width=30)
    table.add_column("Score", style="bold cyan", width=8)
    table.add_column("Skills", style="green", width=8)
    table.add_column("Trajectory", style="blue", width=10)
    table.add_column("Seniority", style="magenta", width=10)

    for c in top_candidates:
        scores = c.scores
        table.add_row(
            f"#{c.final_rank}",
            c.name[:24],
            (c.current_title or "N/A")[:29],
            f"{c.final_score:.1%}",
            f"{scores.get('technical_skill_match', 0):.0%}",
            f"{scores.get('career_trajectory', 0):.0%}",
            f"{scores.get('seniority_alignment', 0):.0%}",
        )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="RecruiterMind — AI Candidate Ranking System"
    )
    parser.add_argument("--jd", required=True, help="Path to job description file")
    parser.add_argument("--candidates", required=True, help="Path to candidates CSV")
    parser.add_argument("--output", default="output/ranked_candidates.csv",
                        help="Output CSV path")
    parser.add_argument("--report", default="output/report.html",
                        help="Output HTML report path (set to 'none' to skip)")
    parser.add_argument("--top-n", type=int, default=20,
                        help="Number of candidates to output")
    parser.add_argument("--no-tournament", action="store_true",
                        help="Skip LLM tournament reranking")
    parser.add_argument("--no-report", action="store_true",
                        help="Skip HTML report generation")

    args = parser.parse_args()

    from config import DEFAULT_CONFIG
    config = DEFAULT_CONFIG
    config.output_top_n = args.top_n
    config.generate_html_report = not args.no_report
    if args.no_tournament:
        config.llm_fallback_to_score = True

    report_path = None if args.no_report or args.report == "none" else args.report

    run_pipeline(
        jd_path=args.jd,
        candidates_path=args.candidates,
        output_path=args.output,
        report_path=report_path,
        config=config,
    )


if __name__ == "__main__":
    main()
