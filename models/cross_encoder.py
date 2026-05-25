"""
Cross-Encoder Reranker
Uses cross-encoder/ms-marco-MiniLM-L6-v2 to score (JD, candidate) pairs.

Unlike bi-encoders (which embed independently), cross-encoders read both
texts together via full self-attention — dramatically more accurate for
relevance scoring. Used as the final precision layer after bi-encoder retrieval.
"""

import numpy as np
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """
    Cross-encoder reranker for (query, document) pair scoring.
    Significantly more accurate than cosine similarity for final ranking.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2",
        device: Optional[str] = None,
        batch_size: int = 16,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None
        self._device = device
        self._available = False
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import CrossEncoder
            import torch

            device = self._device
            if device is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading cross-encoder {self.model_name} on {device}...")
            self._model = CrossEncoder(self.model_name, device=device, max_length=512)
            self._available = True
            logger.info("Cross-encoder loaded successfully")
        except Exception as e:
            logger.warning(f"Cross-encoder unavailable: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def rerank(
        self,
        query: str,
        candidates: List,  # List[CandidateProfile]
        top_k: int = None,
    ) -> List[Tuple]:
        """
        Rerank candidates using cross-encoder scores.

        Args:
            query: The JD text (or rich query string)
            candidates: List of CandidateProfile objects
            top_k: Return only top-K (None = all)

        Returns:
            List of (candidate, cross_encoder_score) sorted descending
        """
        if not self._available or not candidates:
            return [(c, 0.0) for c in candidates]

        # Build (query, candidate_text) pairs
        pairs = [
            (query[:512], c.to_embedding_text()[:512])
            for c in candidates
        ]

        # Score in batches
        all_scores = []
        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i:i + self.batch_size]
            try:
                scores = self._model.predict(batch, show_progress_bar=False)
                all_scores.extend(scores.tolist() if hasattr(scores, 'tolist') else list(scores))
            except Exception as e:
                logger.warning(f"Cross-encoder batch failed: {e}")
                all_scores.extend([0.0] * len(batch))

        # Normalize scores to 0-1 using sigmoid
        scores_arr = np.array(all_scores)
        normalized = 1.0 / (1.0 + np.exp(-scores_arr))  # sigmoid

        # Pair and sort
        scored = list(zip(candidates, normalized.tolist()))
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[:top_k] if top_k else scored

    def score_single(self, query: str, candidate_text: str) -> float:
        """Score a single (query, candidate) pair."""
        if not self._available:
            return 0.5
        try:
            score = self._model.predict([(query[:512], candidate_text[:512])])
            return float(1.0 / (1.0 + np.exp(-score[0])))
        except Exception:
            return 0.5
