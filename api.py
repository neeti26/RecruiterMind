"""
RecruiterMind FastAPI Backend — Production Grade
8-stage pipeline: JD Intel → Profile → Embed → Hybrid Retrieval →
Cross-Encoder → 7-Dim Score → LLM Tournament → Explainability
"""
import asyncio, csv, io, json, logging, sys, time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("api")

app = FastAPI(title="RecruiterMind API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Singletons ────────────────────────────────────────────────────────────────
_embedder = _llm = _cross_encoder = None

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

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    logger.info("Pre-warming models...")
    await loop.run_in_executor(None, get_embedder)
    await loop.run_in_executor(None, get_llm)
    await loop.run_in_executor(None, get_cross_encoder)
    logger.info("All models ready.")

# ── Schemas ───────────────────────────────────────────────────────────────────
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
        await send("log", message=message, level=level, stage=stage, status=status,
                   time=datetime.now().strftime("%H:%M:%S"))

    async def keepalive():
        """Ping every 20s so WebSocket stays alive during long LLM calls."""
        while True:
            await asyncio.sleep(20)
            try:
                await ws.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break

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
        ka_task = asyncio.create_task(keepalive())

        try:
            # ── Stage 0: JD Intelligence ──────────────────────────────────
            await log("Analyzing job description...", stage="jd", status="running")
            from pipeline.jd_intelligence import JDIntelligence
            llm = get_llm()
            jd_intel = JDIntelligence(llm_client=llm if llm.is_available() else None)
            jd_analysis = await loop.run_in_executor(None, jd_intel.analyze, jd_text)
            await log(f"Role: {jd_analysis.role_title} ({jd_analysis.seniority_level})", stage="jd", status="done")
            await log(f"Skills: {len(jd_analysis.required_skills)} required, {len(jd_analysis.nice_to_have_skills)} nice-to-have", stage="jd")

            # ── Stage 1: Candidate Profiling + PII + Timeline ─────────────
            await log("Profiling candidates...", stage="profile", status="running")
            from pipeline.candidate_profiler import CandidateProfiler
            from pipeline.pii_masker import mask_candidates_batch
            from pipeline.timeline_validator import validate_candidate_timeline

            profiler = CandidateProfiler()
            if candidates_csv.strip():
                rows = list(csv.DictReader(io.StringIO(candidates_csv)))
            else:
                with open(Path(__file__).parent / "data" / "sample_candidates.csv", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))

            candidates = []
            for i, row in enumerate(rows):
                cid = str(row.get("id", row.get("candidate_id", f"C{i+1:04d}")))
                candidates.append(profiler.profile_from_csv_row(row, cid))

            if anon_mode:
                candidates = mask_candidates_batch(candidates, anon_mode=True)
                await log("Anonymous mode: PII masked", stage="profile")

            discrepancy_count = 0
            for c in candidates:
                v = validate_candidate_timeline(c)
                c.raw_data["_timeline_validation"] = v.to_dict()
                if v.has_discrepancy:
                    discrepancy_count += 1

            await log(f"Loaded {len(candidates)} candidates, {discrepancy_count} timeline flags", stage="profile", status="done")

            # ── Stage 2: Semantic Embeddings (cached) ─────────────────────
            await log("Computing semantic embeddings (cached)...", stage="embed", status="running")
            from pipeline.embedding_cache import embed_with_cache, cache_stats
            embedder = get_embedder()
            texts = [c.to_embedding_text() for c in candidates]
            t0 = time.time()
            embeddings = await loop.run_in_executor(None, lambda: embed_with_cache(embedder, texts))
            for i, c in enumerate(candidates):
                c.embedding = embeddings[i]
            jd_emb = await loop.run_in_executor(None, lambda: embed_with_cache(embedder, [jd_analysis.to_search_text()], is_query=True)[0])
            await log(f"Embedded {len(candidates)} candidates in {time.time()-t0:.1f}s (768-dim, cached)", stage="embed", status="done")

            # ── Stage 3: Hybrid Retrieval ─────────────────────────────────
            await log("Hybrid retrieval: FAISS + BM25 + RRF...", stage="retrieve", status="running")
            from pipeline.hybrid_retrieval import HybridRetriever
            retriever = HybridRetriever()
            retriever.index_candidates([c.candidate_id for c in candidates], embeddings, texts)
            retrieved = (retriever.get_all_candidates_ranked_by_similarity(jd_emb)
                         if len(candidates) <= 50
                         else retriever.retrieve(jd_emb, jd_analysis.to_search_text()))
            cand_map = {c.candidate_id: c for c in candidates}
            sim_map = {cid: s for cid, s in retrieved}
            pool = [cand_map[cid] for cid, _ in retrieved if cid in cand_map]
            await log(f"Retrieved {len(pool)} candidates via hybrid search", stage="retrieve", status="done")

            # ── Stage 4: Cross-Encoder Reranking ─────────────────────────
            await log("Cross-encoder reranking...", stage="score", status="running")
            ce = get_cross_encoder()
            ce_map: Dict[str, float] = {}
            if ce.is_available:
                ce_results = await loop.run_in_executor(None, lambda: ce.rerank(jd_analysis.to_search_text(), pool[:50]))
                ce_map = {c.candidate_id: s for c, s in ce_results}
                await log(f"Cross-encoder scored {len(ce_results)} candidates", stage="score")

            # ── Stage 5: 7-Dimension Scoring ─────────────────────────────
            from pipeline.multi_dim_scorer import MultiDimScorer
            from config import ScoringWeights
            weights = ScoringWeights(**{k: v for k, v in (custom_weights or {}).items() if hasattr(ScoringWeights, k)}) if custom_weights else ScoringWeights()
            scorer = MultiDimScorer(config=weights, llm_client=llm if llm.is_available() else None)
            for c in pool:
                sem = max(0.0, min(1.0, (sim_map.get(c.candidate_id, 0.0) + 1) / 2))
                ds = scorer.score_candidate(c, jd_analysis, sem, ce_map.get(c.candidate_id, 0.0))
                c.scores = ds.to_dict()
                c.final_score = scorer.compute_final_score(ds)
                c.confidence = scorer.compute_confidence(ds, c)
            pool.sort(key=lambda c: c.final_score, reverse=True)
            await log(f"Scored {len(pool)} candidates — top: {pool[0].name} ({pool[0].final_score:.1%})", stage="score", status="done")

            # ── Stage 6: LLM Tournament ───────────────────────────────────
            if llm.is_available():
                await log("LLM listwise tournament reranking...", stage="tournament", status="running")
                from pipeline.tournament_reranker import TournamentReranker
                pool = await loop.run_in_executor(None, TournamentReranker(llm_client=llm).rerank, pool, jd_analysis, 15)
                pool.sort(key=lambda c: c.final_score, reverse=True)
                await log("Tournament complete (Plackett-Luce aggregation)", stage="tournament", status="done")
            else:
                await log("No LLM key — skipping tournament", stage="tournament", status="done")

            # ── Stage 7: Explainability + Bias Audit ─────────────────────
            await log("Generating AI fit verdicts...", stage="explain", status="running")
            from pipeline.explainer import Explainer
            pool = Explainer(llm_client=llm if llm.is_available() else None).explain_candidates(pool, jd_analysis, top_n=20)
            from pipeline.explainer import Explainer
            bias = Explainer(llm_client=None).run_bias_audit(pool)
            for i, c in enumerate(pool):
                c.final_rank = i + 1
            await log("Fit verdicts generated", stage="explain", status="done")
            await log(f"Bias audit: {'✓ PASSED' if bias.audit_passed else '⚠ REVIEW'}", stage="explain",
                      level="success" if bias.audit_passed else "warn")

            # ── Serialize & send ──────────────────────────────────────────
            stats = cache_stats()
            out = []
            for c in pool[:20]:
                d = c.to_dict()
                d["scores"] = c.scores
                d["work_history"] = c.work_history[:4] if c.work_history else []
                d["confidence"] = round(c.confidence, 3)
                d["hire_recommendation"] = c.hire_recommendation
                d["why_hire"] = c.why_hire
                d["key_strength"] = c.key_strength
                d["key_concern"] = c.key_concern
                tv = c.raw_data.get("_timeline_validation", {})
                d["timeline_validation"] = tv
                d["has_discrepancy"] = tv.get("has_discrepancy", False)
                d["trust_score"] = tv.get("trust_score", 1.0)
                sg = c.raw_data.get("_skill_gap")
                d["matched_skills"] = sg.matched_required[:8] if sg else []
                d["missing_skills"] = sg.missing_required[:5] if sg else []
                d["critical_gaps"] = sg.critical_gaps[:3] if sg else []
                out.append(d)

            await send("result", data={
                "candidates": out,
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
                    "audit_passed": bias.audit_passed,
                    "bias_flags": bias.bias_flags,
                    "score_variance": bias.score_variance,
                    "dimension_variances": bias.dimension_variances,
                },
                "meta": {
                    "total_candidates": len(candidates),
                    "shortlisted": len(out),
                    "llm_used": llm.is_available(),
                    "cross_encoder_used": ce.is_available,
                    "anonymous_mode": anon_mode,
                    "cache_entries": stats["entries"],
                    "discrepancy_count": discrepancy_count,
                },
            })
            await log("Pipeline complete!", level="success")
            await asyncio.sleep(1)  # give client time to receive result before close

        finally:
            ka_task.cancel()

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.exception("Pipeline error")
        try:
            await send("error", message=str(e))
        except Exception:
            pass

# ── REST: instant rerank with new weights ─────────────────────────────────────
@app.post("/api/rerank")
async def rerank_with_weights(req: RerankRequest):
    from config import ScoringWeights
    from pipeline.multi_dim_scorer import MultiDimScorer, DimensionScores
    w = req.weights
    scorer = MultiDimScorer(config=ScoringWeights(
        technical_skill_match=w.technical_skill_match, career_trajectory=w.career_trajectory,
        domain_depth=w.domain_depth, seniority_alignment=w.seniority_alignment,
        behavioral_signals=w.behavioral_signals, culture_soft_fit=w.culture_soft_fit,
        risk_penalty=w.risk_penalty,
    ))
    reranked = []
    for c in req.candidates:
        s = c.get("scores", {})
        score = scorer.compute_final_score(DimensionScores(
            technical_skill_match=s.get("technical_skill_match", 0),
            career_trajectory=s.get("career_trajectory", 0),
            domain_depth=s.get("domain_depth", 0),
            seniority_alignment=s.get("seniority_alignment", 0),
            behavioral_signals=s.get("behavioral_signals", 0),
            culture_soft_fit=s.get("culture_soft_fit", 0),
            risk_penalty=s.get("risk_penalty", 0),
            cross_encoder_score=s.get("cross_encoder_score", 0),
        ))
        reranked.append({**c, "final_score": round(score, 4)})
    reranked.sort(key=lambda x: x["final_score"], reverse=True)
    for i, c in enumerate(reranked):
        c["final_rank"] = i + 1
    return {"candidates": reranked}

@app.get("/api/sample-csv")
async def sample_csv():
    return FileResponse(str(Path(__file__).parent / "data" / "sample_candidates.csv"), media_type="text/csv")

@app.get("/api/health")
async def health():
    from pipeline.embedding_cache import cache_stats
    return {"status": "ok", "llm_available": get_llm().is_available(),
            "cross_encoder_available": get_cross_encoder().is_available, "cache": cache_stats()}

# ── Serve React build ─────────────────────────────────────────────────────────
dist = Path(__file__).parent / "dashboard" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")
    @app.get("/")
    async def idx(): return FileResponse(str(dist / "index.html"))
    @app.get("/{path:path}")
    async def spa(path: str):
        f = dist / path
        return FileResponse(str(f)) if f.exists() and f.is_file() else FileResponse(str(dist / "index.html"))
