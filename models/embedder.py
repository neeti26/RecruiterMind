"""
Embedding Model Wrapper
Uses nomic-embed-text-v1.5 — MTEB SOTA open-source model.
Supports Matryoshka embeddings (variable dimension).
Falls back to sentence-transformers/all-mpnet-base-v2 if nomic unavailable.
"""

import numpy as np
from typing import List, Union, Optional
import logging

logger = logging.getLogger(__name__)


class Embedder:
    """
    Wraps nomic-embed-text-v1.5 for high-quality semantic embeddings.

    Key features:
    - Instruction-tuned: prepend "search_query:" or "search_document:"
    - Matryoshka: supports 64, 128, 256, 512, 768 dimensions
    - Long context: up to 8192 tokens
    """

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-text-v1.5",
        embedding_dim: int = 768,
        batch_size: int = 32,
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self.batch_size = batch_size
        self._model = None
        self._device = device
        self._load_model()

    def _load_model(self):
        """Load the embedding model with fallback."""
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            device = self._device
            if device is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading {self.model_name} on {device}...")
            self._model = SentenceTransformer(
                self.model_name,
                trust_remote_code=True,  # required for nomic
                device=device,
            )
            self._model.max_seq_length = 2048
            logger.info(f"Model loaded. Embedding dim: {self.embedding_dim}")

        except Exception as e:
            logger.warning(f"Failed to load {self.model_name}: {e}")
            logger.warning("Falling back to all-mpnet-base-v2")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
                self.embedding_dim = 768
                self.model_name = "sentence-transformers/all-mpnet-base-v2"
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                raise RuntimeError("Could not load any embedding model") from e2

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a search query (with instruction prefix)."""
        return self.embed_queries([text])[0]

    def embed_document(self, text: str) -> np.ndarray:
        """Embed a document (candidate profile) with instruction prefix."""
        return self.embed_documents([text])[0]

    def embed_queries(self, texts: List[str]) -> np.ndarray:
        """Batch embed queries."""
        # nomic uses instruction prefixes
        if "nomic" in self.model_name:
            prefixed = [f"search_query: {t}" for t in texts]
        else:
            prefixed = texts
        return self._encode(prefixed)

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """Batch embed documents."""
        if "nomic" in self.model_name:
            prefixed = [f"search_document: {t}" for t in texts]
        else:
            prefixed = texts
        return self._encode(prefixed)

    def _encode(self, texts: List[str]) -> np.ndarray:
        """Core encoding with batching and normalization."""
        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embeddings = self._model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

            # Matryoshka truncation if needed
            if self.embedding_dim < embeddings.shape[1]:
                embeddings = embeddings[:, :self.embedding_dim]
                # Re-normalize after truncation
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                embeddings = embeddings / np.maximum(norms, 1e-8)

            all_embeddings.append(embeddings)

        return np.vstack(all_embeddings)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two normalized embeddings."""
        return float(np.dot(a, b))

    def batch_similarity(
        self, query: np.ndarray, documents: np.ndarray
    ) -> np.ndarray:
        """Cosine similarity of query against all documents."""
        return documents @ query
