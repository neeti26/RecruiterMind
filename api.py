"""
RecruiterMind FastAPI Backend — Production Grade
Features:
  - WebSocket streaming pipeline with 8 stages
  - Cross-encoder reranking (ms-marco-MiniLM-L6-v2)
  - Disk-backed embedding cache (no re-embedding on repeat runs)
  - PII masking / Anonymous Mode
  - Timeline discrepancy detection
  - Dynamic weight adjustment endpoint
  - Batch processing with rate-limit protection
  - Structured JSON outputs throughout
"""

import asyncio
import csv
import io
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("api")

app = FastAPI(title="RecruiterMind API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singleton heavy models (loaded once, reused) ──────────────────────────────
_embedder = None
_llm = None
_cross_encoder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        from models.embedder import Embedder
        _embedder = Embedder()
    return _embedder


def get_llm():
    global _llm
    if _llm is None:
        from models.llm_client import LLMClient
        _llm = LLMClient()
    return _llm


def get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from models.cross_encoder import CrossEncoderReranker
        _cross_encoder = CrossEncoderReranker()
    return _cross_encoder


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class WeightAdjustRequest(BaseModel):
    technical_skill_match: float = Field(0.28, ge=0, le=1)
    career_trajectory:     float = Field(0.18, ge=0, le=1)
    domain_depth:          float = Field(0.16, ge=0, le=1)
    seniority_alignment:   float = Field(0.14, ge=0, le=1)
    behavioral_signals:    float = Field(0.10, ge=0, le=1)
    culture_soft_fit:      float = Field(0.08, ge=0, le=1)
    risk_penalty:          float = Field(0.06, ge=0, le=1)


class RerankRequest(BaseModel):
    candidates: list
    weights: WeightAdjustRequest
    jd_analysis: dict


# ── WebSocket pipeline ────────────────────────────────────────────────────────

@app.websocket("/ws/pipeline")
async def pipeline_ws(ws: WebSocket):
    await ws.accept()

    async def send(msg_type: str, **kwargs):
        await ws.send_text(json.dumps({"type": msg_type, **kwargs}))

    async def log(message: str, level: str = "info", stage: str = "", status: str = ""):
        t = datetime.now().strftime("%H:%M:%S")
        await send("log", message=message, level=level, stage=stage, status=status, time=t)

    try:
        raw = await ws.receive_text()
        payload = json.loads(raw)
        jd_text: str = payload.get("jd_text", "")
        candidates_csv: str = payload.get("candidates_csv", "")
        anon_mode: bool = payload.get("anonymous_mode", False)
        custom_weights: Optional[Dict] = payload.get("weights", None)

        if not jd_text.strip():
            await send("error", message="Job description is required")
            return

        loop = asyncio.get_event_loop()

        # ── Stage 0: JD Intelligence ──────────────────────────────────────
        await log("Analyzing job description...", stage="jd", status="running")
        from pipeline.jd_intelligence import JDIntelligence
        llm = get_llm()
        jd_intel = JDIntelligence(llm_client=llm if llm.is_available() else None)
        jd_analysis = await loop.run_in_executor(None, jd_intel.analyze, jd_text)
        await log(f"Role: {jd_analysis.role_title} ({jd_analysis.seniority_level})", stage="jd", status="done")
        await log(f"Skills extracted: {len(jd_analysis.required_skills)} required, {len(jd_analysis.nice_to_have_skills)} nice-to-have", stage="jd")

        # ── Stage 1: Candidate Profiling ──────────────────────────────────
        await log("Profiling candidates...", stage="profile", status="running")
        from pipeline.candidate_profiler import CandidateProfiler
        from pipeline.pii_masker import mask_candidates_batch

        profiler = CandidateProfiler()
        if candidates_csv.strip():
            reader = csv.DictReader(io.StringIO(candidates_csv))
            rows = list(reader)
        else:
            sample_path = Path(__file__).parent / "data" / "sample_candidates.csv"
            with open(sample_path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

        candidates = []
        for i, row in enumerate(rows):
            cid = str(row.get("id", row.get("candidate_id", f"C{i+1:04d}")))
            c = profiler.profile_from_csv_row(row, cid)
            candidates.append(c)

        # Apply PII masking if anonymous mode
        if anon_mode:
            candidates = mask_candidates_batch(candidates, anon_mode=True)
            await log("Anonymous mode: PII masked", stage="profile")

        await log(f"Loaded {len(candidates)} candidates", stage="profile", status="done")

        # ── Stage 2: Timeline Validation ──────────────────────────────────
        await log("Validating candidate timelines...", stage="profile")
        from pipeline.timeline_validator import validate_candidate_timeline
        discrepancy_count = 0
        for c in candidates:
            validation = validate_candidate_timeline(c)
            c.raw_data["_timeline_validation"] = validation.to_dict()
            if validation.has_discrepancy:
                discrepancy_count += 1
        if discrepancy_count:
            await log(f"⚠ {discrepancy_count} timeline discrepancies detected", stage="profile", level="warn")

        # ── Stage 3: Semantic Embeddings (with cache) ─────────────────────
        await log("Computing semantic embeddings (cached)...", stage="embed", status="running")
        from pipeline.embedding_cache import embed_with_cache

        embedder = get_embedder()
        texts = [c.to_embedding_text() for c in candidates]

        t0 = time.time()
        embeddings = await loop.run_in_executor(
            None, lambda: embed_with_cache(embedder, texts, is_query=False)
        )
        embed_time = time.time() - t0

        for i, c in enumerate(candidates):
            c.embedding = embeddings[i]

        jd_embedding = await loop.run_in_executor(
            None, lambda: embed_with_cache(embedder, [jd_analysis.to_search_text()], is_query=True)[0]
        )
        await log(f"Embedded {len(candidates)} candidates in {embed_time:.1f}s (768-dim, cached)", stage="embed", status="done")

        # ── Stage 4: Hybrid Retrieval (FAISS + BM25 + RRF) ───────────────
        await log("Hybrid retrieval: FAISS dense + BM25 sparse + RRF fusion...", stage="retrieve", status="running")
        from pipeline.hybrid_retrieval import HybridRetriever
        import numpy as np

        retriever = HybridRetriever()
        retriever.index_candidates([c.candidate_id for c in candidates], embeddings, texts)

        if len(candidates) <= 50:
            retrieved = retriever.get_all_candidates_ranked_by_similarity(jd_embedding)
        else:
            retrieved = retriever.retrieve(jd_embedding, jd_analysis.to_search_text())

        cand_map = {c.candidate_id: c for c in candidates}
        sim_map = {cid: score for cid, score in retrieved}
        retrieved_candidates = [cand_map[cid] for cid, _ in retrieved if cid in cand_map]
        await log(f"Retrieved {len(retrieved_candidates)} candidates via hybrid search", stage="retrieve", status="done")

        # ── Stage 5: Cross-Encoder Reranking ─────────────────────────────
        await log("Cross-encoder reranking top candidates...", stage="score", status="running")
        ce = get_cross_encoder()
        ce_score_map: Dict[str, float] = {}

        if ce.is_available:
            top_for_ce = retrieved_candidates[:50]
            jd_query = jd_analysis.to_search_text()
            ce_results = await loop.run_in_executor(
                None, lambda: ce.rerank(jd_query, top_for_ce)
            )
            ce_score_map = {c.candidate_id: score for c, score in ce_results}
            await log(f"Cross-encoder scored {len(ce_results)} candidates", stage="score")
        else:
            await log("Cross-encoder not available — using bi-encoder scores only", stage="score")

        # ── Stage 6: Multi-Dimensional Scoring ───────────────────────────
        from pipeline.multi_dim_scorer import MultiDimScorer
        from config import ScoringWeights

        # Apply custom weights if provided
        if custom_weights:
            weights = ScoringWeights(**{k: v for k, v in custom_weights.items()
                                        if hasattr(ScoringWeights, k)})
        else:
            weights = ScoringWeights()

        scorer = MultiDimScorer(config=weights, llm_client=llm if llm.is_available() else None)

        for c in retrieved_candidates:
            sem_sim = sim_map.get(c.candidate_id, 0.0)
            sem_sim = max(0.0, min(1.0, (sem_sim + 1) / 2))
            ce_score = ce_score_map.get(c.candidate_id, 0.0)
            dim_scores = scorer.score_candidate(c, jd_analysis, sem_sim, ce_score)
            c.scores = dim_scores.to_dict()
            c.final_score = scorer.compute_final_score(dim_scores)
            c.confidence = scorer.compute_confidence(dim_scores, c)

        retrieved_candidates.sort(key=lambda c: c.final_score, reverse=True)
        await log(f"Scored {len(retrieved_candidates)} candidates across 7 dimensions + cross-encoder", stage="score", status="done")
        await log(f"Top: {retrieved_candidates[0].name} ({retrieved_candidates[0].final_score:.1%})", stage="score")

        # ── Stage 7: LLM Tournament ───────────────────────────────────────
        if llm.is_available():
            await log("LLM listwise tournament reranking...", stage="tournament", status="running")
            from pipeline.tournament_reranker import TournamentReranker
            reranker = TournamentReranker(llm_client=llm)
            retrieved_candidates = await loop.run_in_executor(
                None, reranker.rerank, retrieved_candidates, jd_analysis, 15
            )
            retrieved_candidates.sort(key=lambda c: c.final_score, reverse=True)
            await log("Tournament complete (Plackett-Luce aggregation)", stage="tournament", status="done")
        else:
            await log("No LLM key — skipping tournament (add GROQ_API_KEY to .env)", stage="tournament", status="done")

        # ── Stage 8: Explainability + Bias Audit ─────────────────────────
        await log("Generating AI fit verdicts and bias audit...", stage="explain", status="running")
        from pipeline.explainer import Explainer
        explainer = Explainer(llm_client=llm if llm.is_available() else None)
        retrieved_candidates = explainer.explain_candidates(retrieved_candidates, jd_analysis, top_n=20)
        bias_audit = explainer.run_bias_audit(retrieved_candidates)

        for i, c in enumerate(retrieved_candidates):
            c.final_rank = i + 1

        await log("Fit verdicts generated", stage="explain", status="done")
        await log(f"Bias audit: {'✓ PASSED' if bias_audit.audit_passed else '⚠ REVIEW NEEDED'}", stage="explain",
                  level="success" if bias_audit.audit_passed else "warn")

        # ── Serialize ─────────────────────────────────────────────────────
        from pipeline.embedding_cache import cache_stats
        stats = cache_stats()

        candidates_out = []
        for c in retrieved_candidates[:20]:
            d = c.to_dict()
            d["scores"] = c.scores
            d["work_history"] = c.work_history[:4] if c.work_history else []
            d["confidence"] = round(c.confidence, 3)
            d["hire_recommendation"] = c.hire_recommendation
            d["why_hire"] = c.why_hire
            d["key_strength"] = c.key_strength
            d["key_concern"] = c.key_concern
            # Timeline validation
            tv = c.raw_data.get("_timeline_validation", {})
            d["timeline_validation"] = tv
            d["has_discrepancy"] = tv.get("has_discrepancy", False)
            d["trust_score"] = tv.get("trust_score", 1.0)
            # Skill gap detail
            sg = c.raw_data.get("_skill_gap")
            d["matched_skills"] = sg.matched_required[:8] if sg else []
            d["missing_skills"] = sg.missing_required[:5] if sg else []
            d["critical_gaps"] = sg.critical_gaps[:3] if sg else []
            candidates_out.append(d)

        result_payload = {
            "candidates": candidates_out,
            "jd_analysis": {
                "role_title": jd_analysis.role_title,
                "seniority_level": jd_analysis.seniority_level,
                "required_skills": jd_analysis.required_skills,
                "nice_to_have_skills": jd_analysis.nice_to_have_skills,
                "role_summary": jd_analysis.role_summary,
                "implicit_requirements": jd_analysis.implicit_requirements,
                "culture_signals": jd_analysis.culture_signals,
            },
            "bias_audit": {
                "audit_passed": bias_audit.audit_passed,
                "bias_flags": bias_audit.bias_flags,
                "score_variance": bias_audit.score_variance,
                "dimension_variances": bias_audit.dimension_variances,
            },
            "meta": {
                "total_candidates": len(candidates),
                "shortlisted": len(candidates_out),
                "llm_used": llm.is_available(),
                "cross_encoder_used": ce.is_available,
                "anonymous_mode": anon_mode,
                "cache_entries": stats["entries"],
                "discrepancy_count": discrepancy_count,
            },
        }

        await send("result", data=result_payload)
        await log("Pipeline complete!", level="success")

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.exception("Pipeline error")
        try:
            await send("error", message=str(e))
        except Exception:
            pass


# ── REST: Dynamic weight reranking (instant, no re-embedding) ─────────────────

@app.post("/api/rerank")
async def rerank_with_weights(req: RerankRequest):
    """
    Re-score candidates with new weights without re-running the full pipeline.
    Called by the UI weight sliders for instant re-ranking.
    """
    from config import ScoringWeights
    from pipeline.multi_dim_scorer import MultiDimScorer, DimensionScores

    weights = ScoringWeights(
        technical_skill_match=req.weights.technical_skill_match,
        career_trajectory=req.weights.career_trajectory,
        domain_depth=req.weights.domain_depth,
        seniority_alignment=req.weights.seniority_alignment,
        behavioral_signals=req.weights.behavioral_signals,
        culture_soft_fit=req.weights.culture_soft_fit,
        risk_penalty=req.weights.risk_penalty,
    )
    scorer = MultiDimScorer(config=weights)

    reranked = []
    for c in req.candidates:
        scores = c.get("scores", {})
        dim = DimensionScores(
            technical_skill_match=scores.get("technical_skill_match", 0),
            career_trajectory=scores.get("career_trajectory", 0),
            domain_depth=scores.get("domain_depth", 0),
            seniority_alignment=scores.get("seniority_alignment", 0),
            behavioral_signals=scores.get("behavioral_signals", 0),
            culture_soft_fit=scores.get("culture_soft_fit", 0),
            risk_penalty=scores.get("risk_penalty", 0),
            cross_encoder_score=scores.get("cross_encoder_score", 0),
        )
        new_score = scorer.compute_final_score(dim)
        reranked.append({**c, "final_score": round(new_score, 4)})

    reranked.sort(key=lambda x: x["final_score"], reverse=True)
    for i, c in enumerate(reranked):
        c["final_rank"] = i + 1

    return {"candidates": reranked}


# ── REST: Misc ────────────────────────────────────────────────────────────────

@app.get("/api/sample-csv")
async def sample_csv():
    path = Path(__file__).parent / "data" / "sample_candidates.csv"
    return FileResponse(path, media_type="text/csv")


@app.get("/api/health")
async def health():
    from pipeline.embedding_cache import cache_stats
    llm = get_llm()
    ce = get_cross_encoder()
    return {
        "status": "ok",
        "llm_available": llm.is_available(),
        "cross_encoder_available": ce.is_available,
        "cache": cache_stats(),
    }


# ── Serve React build ─────────────────────────────────────────────────────────
dist_path = Path(__file__).parent / "dashboard" / "dist"
if dist_path.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(dist_path / "index.html"))

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        f = dist_path / path
        if f.exists() and f.is_file():
            return FileResponse(str(f))
        return FileResponse(str(dist_path / "index.html"))
