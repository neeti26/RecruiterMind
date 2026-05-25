"""
RecruiterMind FastAPI Backend
Serves the React dashboard and runs the pipeline via WebSocket streaming.
"""

import asyncio
import csv
import io
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="RecruiterMind API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Lazy-load heavy components once ──────────────────────────────────────────
_embedder = None
_llm = None

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


# ── WebSocket pipeline endpoint ───────────────────────────────────────────────
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
        jd_text = payload.get("jd_text", "")
        candidates_csv = payload.get("candidates_csv", "")

        if not jd_text.strip():
            await send("error", message="Job description is required")
            return

        # ── Stage 0: JD Intelligence ──────────────────────────────────────
        await log("Analyzing job description...", stage="jd", status="running")
        await asyncio.sleep(0.05)

        from pipeline.jd_intelligence import JDIntelligence
        llm = get_llm()
        jd_intel = JDIntelligence(llm_client=llm if llm.is_available() else None)
        jd_analysis = await asyncio.get_event_loop().run_in_executor(
            None, jd_intel.analyze, jd_text
        )
        await log(f"Role: {jd_analysis.role_title} ({jd_analysis.seniority_level})", stage="jd", status="done")
        await log(f"Required skills: {', '.join(jd_analysis.required_skills[:6])}", stage="jd")

        # ── Stage 1: Candidate Profiling ──────────────────────────────────
        await log("Profiling candidates...", stage="profile", status="running")

        from pipeline.candidate_profiler import CandidateProfiler
        profiler = CandidateProfiler()

        if candidates_csv.strip():
            reader = csv.DictReader(io.StringIO(candidates_csv))
            rows = list(reader)
        else:
            # Use built-in sample
            sample_path = Path(__file__).parent / "data" / "sample_candidates.csv"
            with open(sample_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

        candidates = []
        for i, row in enumerate(rows):
            cid = str(row.get("id", row.get("candidate_id", f"C{i+1:04d}")))
            c = profiler.profile_from_csv_row(row, cid)
            candidates.append(c)

        await log(f"Loaded {len(candidates)} candidates", stage="profile", status="done")

        # ── Stage 2: Embeddings ───────────────────────────────────────────
        await log("Computing semantic embeddings (nomic-embed-text-v1.5)...", stage="embed", status="running")

        embedder = get_embedder()
        texts = [c.to_embedding_text() for c in candidates]

        embeddings = await asyncio.get_event_loop().run_in_executor(
            None, embedder.embed_documents, texts
        )
        for i, c in enumerate(candidates):
            c.embedding = embeddings[i]

        jd_embedding = await asyncio.get_event_loop().run_in_executor(
            None, embedder.embed_query, jd_analysis.to_search_text()
        )
        await log(f"Embedded {len(candidates)} candidates (768-dim)", stage="embed", status="done")

        # ── Stage 3: Hybrid Retrieval ─────────────────────────────────────
        await log("Running hybrid retrieval (FAISS + BM25 + RRF)...", stage="retrieve", status="running")

        from pipeline.hybrid_retrieval import HybridRetriever
        import numpy as np
        retriever = HybridRetriever()
        retriever.index_candidates(
            [c.candidate_id for c in candidates],
            embeddings,
            texts,
        )

        if len(candidates) <= 50:
            retrieved = retriever.get_all_candidates_ranked_by_similarity(jd_embedding)
        else:
            retrieved = retriever.retrieve(jd_embedding, jd_analysis.to_search_text())

        cand_map = {c.candidate_id: c for c in candidates}
        sim_map = {cid: score for cid, score in retrieved}
        retrieved_candidates = [cand_map[cid] for cid, _ in retrieved if cid in cand_map]

        await log(f"Retrieved {len(retrieved_candidates)} candidates via hybrid search", stage="retrieve", status="done")

        # ── Stage 4: Multi-Dimensional Scoring ───────────────────────────
        await log("Scoring across 7 dimensions...", stage="score", status="running")

        from pipeline.multi_dim_scorer import MultiDimScorer
        scorer = MultiDimScorer(llm_client=llm if llm.is_available() else None)

        for c in retrieved_candidates:
            sem_sim = sim_map.get(c.candidate_id, 0.0)
            sem_sim = max(0.0, min(1.0, (sem_sim + 1) / 2))
            dim_scores = scorer.score_candidate(c, jd_analysis, sem_sim)
            c.scores = dim_scores.to_dict()
            c.final_score = scorer.compute_final_score(dim_scores)
            c.confidence = scorer.compute_confidence(dim_scores, c)

        retrieved_candidates.sort(key=lambda c: c.final_score, reverse=True)
        await log(f"Scored {len(retrieved_candidates)} candidates", stage="score", status="done")
        await log(f"Top candidate: {retrieved_candidates[0].name} ({retrieved_candidates[0].final_score:.1%})", stage="score")

        # ── Stage 5: LLM Tournament (if available) ────────────────────────
        if llm.is_available():
            await log("Running LLM listwise tournament...", stage="tournament", status="running")
            from pipeline.tournament_reranker import TournamentReranker
            reranker = TournamentReranker(llm_client=llm)
            retrieved_candidates = await asyncio.get_event_loop().run_in_executor(
                None, reranker.rerank, retrieved_candidates, jd_analysis, 15
            )
            retrieved_candidates.sort(key=lambda c: c.final_score, reverse=True)
            await log("Tournament reranking complete (Plackett-Luce aggregation)", stage="tournament", status="done")
        else:
            await log("LLM not configured — using score-based ranking", stage="tournament", status="done")

        # ── Stage 6: Explainability ───────────────────────────────────────
        await log("Generating recruiter explanations...", stage="explain", status="running")

        from pipeline.explainer import Explainer
        explainer = Explainer(llm_client=llm if llm.is_available() else None)
        retrieved_candidates = explainer.explain_candidates(retrieved_candidates, jd_analysis, top_n=20)
        bias_audit = explainer.run_bias_audit(retrieved_candidates)

        for i, c in enumerate(retrieved_candidates):
            c.final_rank = i + 1

        await log("Explanations generated", stage="explain", status="done")
        await log(f"Bias audit: {'PASSED' if bias_audit.audit_passed else 'REVIEW NEEDED'}", stage="explain",
                  level="success" if bias_audit.audit_passed else "warn")

        # ── Serialize results ─────────────────────────────────────────────
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
            candidates_out.append(d)

        result_payload = {
            "candidates": candidates_out,
            "jd_analysis": {
                "role_title": jd_analysis.role_title,
                "seniority_level": jd_analysis.seniority_level,
                "required_skills": jd_analysis.required_skills,
                "nice_to_have_skills": jd_analysis.nice_to_have_skills,
                "role_summary": jd_analysis.role_summary,
            },
            "bias_audit": {
                "audit_passed": bias_audit.audit_passed,
                "bias_flags": bias_audit.bias_flags,
            },
            "meta": {
                "total_candidates": len(candidates),
                "shortlisted": len(candidates_out),
                "llm_used": llm.is_available(),
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


# ── REST endpoints ────────────────────────────────────────────────────────────
@app.get("/api/sample-csv")
async def sample_csv():
    path = Path(__file__).parent / "data" / "sample_candidates.csv"
    return FileResponse(path, media_type="text/csv")


@app.get("/api/health")
async def health():
    return {"status": "ok", "llm_available": get_llm().is_available()}


# ── Serve React build ─────────────────────────────────────────────────────────
dist_path = Path(__file__).parent / "dashboard" / "dist"
if dist_path.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(dist_path / "index.html"))

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file = dist_path / path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(dist_path / "index.html"))
