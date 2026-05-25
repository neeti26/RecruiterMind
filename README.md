# RecruiterMind — AI Candidate Ranking System

> **Hack2Skill India Runs 2026 — Data & AI Challenge**

RecruiterMind ranks candidates the way a great recruiter would: not by keyword overlap, but by deeply understanding career trajectory, skill depth, behavioral signals, and role fit — then explaining every decision.

---

## Architecture Overview

```
Job Description
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 0 — JD Intelligence                                      │
│  LLM extracts: required skills, nice-to-have, seniority,        │
│  culture signals, implicit needs, deal-breakers                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1 — Candidate Profiling                                  │
│  Parse resume/profile → structured JSON:                        │
│  skills taxonomy, career velocity, tenure patterns,             │
│  seniority trajectory, domain depth, platform signals           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2 — Hybrid Retrieval (Recall Layer)                      │
│  Dense: nomic-embed-text-v1.5 + FAISS ANN search               │
│  Sparse: BM25 keyword retrieval                                 │
│  Fusion: Reciprocal Rank Fusion → top-K candidates             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 3 — Multi-Dimensional Scoring (Precision Layer)          │
│  7 independent scoring dimensions:                              │
│  1. Technical Skill Match (semantic + taxonomy)                 │
│  2. Career Trajectory Score (velocity + growth arc)             │
│  3. Domain Depth Score (years × breadth × recency)             │
│  4. Seniority Alignment (level fit, not over/under)             │
│  5. Behavioral Signal Score (platform activity, contributions)  │
│  6. Culture & Soft Skill Fit (LLM-inferred)                    │
│  7. Risk Penalty (job-hopping, gaps, red flags)                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4 — LLM Listwise Tournament Reranker                     │
│  Mini-tournaments of 5 candidates at a time                     │
│  LLM produces ranked permutations                               │
│  Plackett-Luce aggregation → final stable ranking               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 5 — Explainability & Bias Audit                          │
│  Per-candidate recruiter narrative                              │
│  Dimension breakdown radar chart                                │
│  Bias detection (gender/age/name neutralization)                │
│  Confidence intervals on scores                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
                  Ranked Output CSV + HTML Report
```

---

## Key Differentiators

| Feature | Toy Models | RecruiterMind |
|---|---|---|
| JD Understanding | Keyword extraction | LLM semantic decomposition with implicit needs |
| Candidate Scoring | Single cosine similarity | 7-dimensional weighted scoring |
| Ranking Method | Sort by score | LLM listwise tournament + Plackett-Luce |
| Explainability | Per-candidate recruiter narrative | ✅ |
| Bias Handling | None | Active neutralization + audit trail |
| Career Intelligence | None | Velocity, trajectory, tenure pattern analysis |
| Output | CSV | CSV + interactive HTML report |

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full pipeline
python main.py \
  --jd data/job_description.txt \
  --candidates data/candidates.csv \
  --output output/ranked_candidates.csv \
  --report output/report.html

# Or use the interactive demo
python demo.py
```

---

## Project Structure

```
recruiter_mind/
├── main.py                    # Entry point
├── demo.py                    # Interactive demo
├── config.py                  # Configuration & weights
├── pipeline/
│   ├── jd_intelligence.py     # Stage 0: JD parsing
│   ├── candidate_profiler.py  # Stage 1: Candidate parsing
│   ├── hybrid_retrieval.py    # Stage 2: FAISS + BM25 + RRF
│   ├── multi_dim_scorer.py    # Stage 3: 7-dimension scoring
│   ├── tournament_reranker.py # Stage 4: LLM tournament
│   └── explainer.py           # Stage 5: Explanations + bias
├── models/
│   ├── embedder.py            # nomic-embed-text-v1.5 wrapper
│   └── llm_client.py          # LLM API abstraction
├── utils/
│   ├── skill_taxonomy.py      # Skills ontology
│   ├── career_analyzer.py     # Career trajectory logic
│   └── report_generator.py    # HTML report
└── data/
    ├── sample_jd.txt
    └── sample_candidates.csv
```

---

## Evaluation

The system is evaluated on:
- **NDCG@10** — ranking quality vs. human expert labels
- **Precision@5** — top-5 shortlist accuracy
- **Spearman ρ** — rank correlation with ground truth
- **Bias Audit Score** — demographic parity check

---

## Tech Stack

- **Embeddings**: `nomic-embed-text-v1.5` (MTEB SOTA, open-source)
- **Vector Search**: FAISS (IVF + HNSW)
- **Sparse Retrieval**: rank-bm25
- **LLM**: OpenAI GPT-4o / Groq Llama-3.3-70B (configurable)
- **Scoring**: NumPy + SciPy
- **Visualization**: Plotly + Jinja2 HTML reports
