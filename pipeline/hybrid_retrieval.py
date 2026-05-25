"""
Stage 2 — Hybrid Retrieval (Recall Layer)
Combines dense semantic search (FAISS) with sparse BM25 retrieval,
fused via Reciprocal Rank Fusion (RRF).

Goal: high recall — don't miss any good candidate.
Precision is handled in Stage 3.
"""

import numpy as np
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Two-stage retrieval:
    1. Dense: nomic-embed-text-v1.5 + FAISS ANN
    2. Sparse: BM25 keyword matching
    3. Fusion: Reciprocal Rank Fusion
    """

    def __init__(self, config=None):
        from config import RetrievalConfig
        self.config = config or RetrievalConfig()
        self._faiss_index = None
        self._bm25_index = None
        self._candidate_ids: List[str] = []
        self._embeddings: Optional[np.ndarray] = None
        self._corpus: List[str] = []

    def index_candidates(
        self,
        candidate_ids: List[str],
        embeddings: np.ndarray,
        corpus_texts: List[str],
    ):
        """
        Build FAISS and BM25 indices from candidate embeddings and texts.

        Args:
            candidate_ids: List of candidate IDs (same order as embeddings)
            embeddings: (N, D) normalized embedding matrix
            corpus_texts: List of candidate text representations for BM25
        """
        self._candidate_ids = candidate_ids
        self._embeddings = embeddings
        self._corpus = corpus_texts

        self._build_faiss_index(embeddings)
        self._build_bm25_index(corpus_texts)
        logger.info(f"Indexed {len(candidate_ids)} candidates")

    def _build_faiss_index(self, embeddings: np.ndarray):
        """Build FAISS index for dense retrieval."""
        try:
            import faiss
            dim = embeddings.shape[1]

            if self.config.faiss_index_type == "flat" or len(embeddings) < 1000:
                # Exact search — best for small datasets
                self._faiss_index = faiss.IndexFlatIP(dim)  # Inner product = cosine for normalized
            else:
                # Approximate search for large datasets
                nlist = min(100, len(embeddings) // 10)
                quantizer = faiss.IndexFlatIP(dim)
                self._faiss_index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
                self._faiss_index.train(embeddings.astype(np.float32))

            self._faiss_index.add(embeddings.astype(np.float32))
            logger.info(f"FAISS index built: {self._faiss_index.ntotal} vectors, dim={dim}")

        except ImportError:
            logger.warning("FAISS not available, using numpy fallback for dense search")
            self._faiss_index = None

    def _build_bm25_index(self, corpus: List[str]):
        """Build BM25 index for sparse retrieval."""
        try:
            from rank_bm25 import BM25Okapi
            import re

            def tokenize(text: str) -> List[str]:
                text = text.lower()
                tokens = re.findall(r'\b[a-z][a-z0-9+#.]*\b', text)
                return tokens

            tokenized = [tokenize(doc) for doc in corpus]
            self._bm25_index = BM25Okapi(tokenized)
            self._tokenize_fn = tokenize
            logger.info("BM25 index built")

        except ImportError:
            logger.warning("rank-bm25 not available, skipping sparse retrieval")
            self._bm25_index = None

    def retrieve(
        self,
        query_embedding: np.ndarray,
        query_text: str,
        top_k: int = None,
    ) -> List[Tuple[str, float]]:
        """
        Retrieve top-K candidates using hybrid search.

        Returns:
            List of (candidate_id, fusion_score) sorted by score descending
        """
        top_k = top_k or self.config.top_k_retrieval

        dense_ranks = self._dense_retrieve(query_embedding, top_k * 2)
        sparse_ranks = self._sparse_retrieve(query_text, top_k * 2)

        fused = self._reciprocal_rank_fusion(
            dense_ranks, sparse_ranks,
            w1=self.config.dense_weight,
            w2=self.config.bm25_weight,
            k=self.config.rrf_k,
        )

        return fused[:top_k]

    def _dense_retrieve(
        self, query_embedding: np.ndarray, top_k: int
    ) -> List[Tuple[str, float]]:
        """FAISS dense retrieval."""
        if self._faiss_index is not None:
            try:
                import faiss
                query = query_embedding.astype(np.float32).reshape(1, -1)
                scores, indices = self._faiss_index.search(query, min(top_k, len(self._candidate_ids)))
                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if idx >= 0:
                        results.append((self._candidate_ids[idx], float(score)))
                return results
            except Exception as e:
                logger.warning(f"FAISS search failed: {e}, using numpy fallback")

        # Numpy fallback
        if self._embeddings is not None:
            scores = self._embeddings @ query_embedding
            top_indices = np.argsort(scores)[::-1][:top_k]
            return [(self._candidate_ids[i], float(scores[i])) for i in top_indices]

        return []

    def _sparse_retrieve(
        self, query_text: str, top_k: int
    ) -> List[Tuple[str, float]]:
        """BM25 sparse retrieval."""
        if self._bm25_index is None:
            return []

        try:
            tokens = self._tokenize_fn(query_text)
            scores = self._bm25_index.get_scores(tokens)
            top_indices = np.argsort(scores)[::-1][:top_k]
            return [
                (self._candidate_ids[i], float(scores[i]))
                for i in top_indices
                if scores[i] > 0
            ]
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        list1: List[Tuple[str, float]],
        list2: List[Tuple[str, float]],
        w1: float = 0.6,
        w2: float = 0.4,
        k: int = 60,
    ) -> List[Tuple[str, float]]:
        """
        Reciprocal Rank Fusion.
        RRF(d) = Σ w_i / (k + rank_i(d))
        """
        scores: Dict[str, float] = {}

        for rank, (cid, _) in enumerate(list1, 1):
            scores[cid] = scores.get(cid, 0.0) + w1 / (k + rank)

        for rank, (cid, _) in enumerate(list2, 1):
            scores[cid] = scores.get(cid, 0.0) + w2 / (k + rank)

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def get_all_candidates_ranked_by_similarity(
        self, query_embedding: np.ndarray
    ) -> List[Tuple[str, float]]:
        """
        When dataset is small enough, rank ALL candidates by similarity.
        Used when top_k >= total candidates.
        """
        if self._embeddings is not None:
            scores = self._embeddings @ query_embedding
            sorted_indices = np.argsort(scores)[::-1]
            return [(self._candidate_ids[i], float(scores[i])) for i in sorted_indices]
        return []
