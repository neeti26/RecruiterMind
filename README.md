# RecruiterMind 🧠

> **Hack2Skill India Runs 2026 — Data & AI Challenge**  
> AI candidate ranking that thinks like a great recruiter — not a keyword filter.

**Live Demo:** https://recruitermind.vercel.app  
**GitHub:** https://github.com/neeti26/RecruiterMind

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RecruiterMind Pipeline                          │
│                                                                         │
│  Job Description                    Candidates CSV                      │
│       │                                   │                             │
│       ▼                                   ▼                             │
│  ┌─────────────┐               ┌──────────────────┐                    │
│  │ Stage 0     │               │ Stage 1           │                    │
│  │ JD Intel    │               │ Candidate         │                    │
│  │ LLM extracts│               │ Profiler          │                    │
│  │ implicit    │               │ + PII Masker      │                    │
│  │ needs,      │               │ + Timeline        │                    │
│  │ culture,    │               │   Validator       │                    │
│  │ deal-breakers│              └────────┬─────────┘                    │
│  └──────┬──────┘                        │                              │
│         │                               │                              │
│         └──────────────┬────────────────┘                              │
│                        ▼                                                │
│              ┌──────────────────┐                                       │
│              │ Stage 2          │                                       │
│              │ Semantic Embed   │  nomic-embed-text-v1.5 (768-dim)     │
│              │ + Disk Cache     │  Matryoshka embeddings               │
│              └────────┬─────────┘                                       │
│                       │                                                 │
│                       ▼                                                 │
│              ┌──────────────────┐                                       │
│              │ Stage 3          │  Dense:  FAISS IVF (cosine)          │
│              │ Hybrid Retrieval │  Sparse: BM25 (Okapi)                │
│              │ FAISS + BM25     │  Fusion: Reciprocal Rank Fusion      │
│              │ + RRF Fusion     │                                       │
│              └────────┬─────────┘                                       │
│                       │                                                 │
│                       ▼                                                 │
│              ┌──────────────────┐                                       │
│              │ Stage 4          │  ms-marco-MiniLM-L6-v2               │
│              │ Cross-Encoder    │  Full attention over (JD, Resume)    │
│              │ Reranking        │  Dramatically improves top-10 order  │
│              └────────┬─────────┘                                       │
│                       │                                                 │
│                       ▼                                                 │
│              ┌──────────────────┐                                       │
│              │ Stage 5          │  7 independent dimensions:           │
│              │ Multi-Dim        │  Skills · Career · Domain ·          │
│              │ Scoring          │  Seniority · Behavioral ·            │
│              │                  │  Culture · Risk Penalty              │
│              └────────┬─────────┘                                       │
│                       │                                                 │
│                       ▼                                                 │
│              ┌──────────────────┐                                       │
│              │ Stage 6          │  Mini-tournaments of 5 candidates    │
│              │ LLM Tournament   │  Plackett-Luce aggregation           │
│              │ (optional)       │  Requires GROQ_API_KEY               │
│              └────────┬─────────┘                                       │
│                       │                                                 │
│                       ▼                                                 │
│              ┌──────────────────┐                                       │
│              │ Stage 7          │  3-bullet fit verdicts               │
│              │ Explainability   │  Bias audit + variance check         │
│              │ + Bias Audit     │  Timeline discrepancy flags          │
│              └────────┬─────────┘                                       │
│                       │                                                 │
│                       ▼                                                 │
│         Ranked CSV + Interactive React Dashboard                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Differentiators

| Feature | Standard Approach | RecruiterMind |
|---|---|---|
| JD Understanding | Keyword extraction | LLM semantic decomposition — implicit needs, culture signals, deal-breakers |
| Retrieval | Single cosine similarity | Hybrid FAISS + BM25 + Reciprocal Rank Fusion |
| Ranking Precision | Sort by embedding score | Cross-encoder reranking (full attention over JD+Resume pairs) |
| Scoring | 1 number | 7 independent dimensions with configurable weights |
| LLM Ranking | None | Listwise tournament + Plackett-Luce aggregation |
| Explainability | None | 3-bullet fit verdict per candidate (Pros / Gaps / Culture) |
| Bias | None | PII masking, anonymous mode, demographic neutralization |
| Trust | None | Timeline discrepancy detection — flags experience inflation |
| UI | Static table | Interactive: weight sliders, shortlist, sort/filter, instant rerank |
| Output | Basic CSV | Rich CSV with 20+ columns including `primary_fit_reason` |

---

## Quick Start

### Option 1: Docker (recommended)

```bash
git clone https://github.com/neeti26/RecruiterMind.git
cd RecruiterMind

# Optional: add LLM key for tournament reranking
echo "GROQ_API_KEY=gsk_..." > .env

docker-compose up --build
# Open http://localhost:8000
```

### Option 2: Local

```bash
# Backend
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Frontend (separate terminal)
cd dashboard
npm install
npm run dev
# Open http://localhost:5173
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Optional | Enables LLM tournament reranking (free tier at console.groq.com) |
| `OPENAI_API_KEY` | Optional | Alternative LLM provider (GPT-4o) |
| `EMBEDDING_CACHE_DIR` | Optional | Path for embedding cache (default: `.cache/embeddings`) |

---

## Usage

1. Paste a job description (the more detail, the better)
2. Upload your candidates CSV (or use the built-in sample)
3. Toggle **Anonymous Mode** for bias-free ranking
4. Click **Run AI Pipeline** — watch the 8 stages execute live
5. Explore results: adjust weight sliders, shortlist candidates, export CSV

### CSV Format

```
id, name, current_title, years_experience, skills, location,
github_repos, github_stars, open_source_contributions,
publications, blog_posts, certifications, summary
```

---

## Output CSV Columns

| Column | Description |
|---|---|
| `rank` | Final ranking position |
| `final_score_pct` | Weighted composite score (0–100%) |
| `hire_recommendation` | strong_yes / yes / maybe / no |
| `confidence_pct` | Model confidence in the score |
| `trust_score_pct` | Timeline validation trust (100% = no discrepancies) |
| `has_discrepancy` | YES if timeline inconsistency detected |
| `tech_skills_pct` | Technical skill match score |
| `career_traj_pct` | Career trajectory score |
| `domain_depth_pct` | Domain depth score |
| `seniority_fit_pct` | Seniority alignment score |
| `behavioral_pct` | Behavioral signals score |
| `culture_fit_pct` | Culture fit score |
| `risk_penalty_pct` | Risk penalty |
| `cross_encoder_pct` | Cross-encoder precision score |
| `matched_skills` | Required skills the candidate has |
| `missing_skills` | Required skills the candidate lacks |
| `critical_gaps` | High-priority missing skills |
| `primary_fit_reason` | AI-generated one-line fit summary |
| `key_strength` | Single most compelling attribute |
| `key_concern` | Single biggest concern |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Embeddings | `nomic-embed-text-v1.5` (MTEB SOTA, 768-dim, Matryoshka) |
| Dense Search | FAISS (IndexFlatIP / IVF) |
| Sparse Search | BM25 Okapi (rank-bm25) |
| Fusion | Reciprocal Rank Fusion |
| Cross-Encoder | `cross-encoder/ms-marco-MiniLM-L6-v2` |
| LLM | Groq Llama-3.3-70B / OpenAI GPT-4o |
| Backend | FastAPI + WebSocket streaming |
| Frontend | React 19 + Vite + Tailwind v4 + Framer Motion + Recharts |
| Caching | Disk-backed SHA256 embedding cache |
| Deployment | Vercel (frontend) + Docker (backend) |

---

## Project Structure

```
RecruiterMind/
├── api.py                        # FastAPI backend, WebSocket pipeline
├── config.py                     # All tunable parameters
├── Dockerfile                    # Production container
├── docker-compose.yml            # One-command local setup
├── requirements.txt
├── pipeline/
│   ├── jd_intelligence.py        # Stage 0: LLM JD analysis
│   ├── candidate_profiler.py     # Stage 1: Profile parsing
│   ├── pii_masker.py             # Anonymous mode / PII redaction
│   ├── timeline_validator.py     # Discrepancy detection
│   ├── embedding_cache.py        # Disk-backed embedding cache
│   ├── hybrid_retrieval.py       # Stage 3: FAISS + BM25 + RRF
│   ├── multi_dim_scorer.py       # Stage 5: 7-dimension scoring
│   ├── tournament_reranker.py    # Stage 6: LLM tournament
│   └── explainer.py              # Stage 7: Fit verdicts + bias audit
├── models/
│   ├── embedder.py               # nomic-embed-text-v1.5 wrapper
│   ├── cross_encoder.py          # ms-marco cross-encoder
│   └── llm_client.py             # OpenAI / Groq abstraction
├── utils/
│   ├── skill_taxonomy.py         # Skills ontology + normalization
│   └── career_analyzer.py        # Career trajectory analysis
├── data/
│   ├── sample_jd.txt
│   └── sample_candidates.csv
└── dashboard/                    # React frontend
    ├── src/
    │   ├── App.jsx
    │   └── components/
    │       ├── ResultsDashboard.jsx
    │       ├── WeightSliders.jsx   # Dynamic weight adjustment
    │       ├── FitVerdict.jsx      # 3-bullet AI verdict
    │       ├── DiscrepancyBadge.jsx # Timeline flags
    │       ├── PipelineProgress.jsx
    │       ├── InputPanel.jsx
    │       ├── ScoreRadar.jsx
    │       ├── DimensionChart.jsx
    │       └── BiasAudit.jsx
    └── vercel.json
```
