"""
Embedding Cache
Disk-backed cache for candidate embeddings.
Prevents re-embedding the same candidate text on repeated runs.
Cache key = SHA256 of (model_name + text).
"""

import hashlib
import logging
import os
import pickle
from pathlib import Path
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("EMBEDDING_CACHE_DIR", ".cache/embeddings"))


def _cache_key(model_name: str, text: str) -> str:
    content = f"{model_name}::{text}"
    return hashlib.sha256(content.encode()).hexdigest()


def get_cached_embedding(model_name: str, text: str) -> Optional[np.ndarray]:
    """Return cached embedding or None."""
    try:
        key = _cache_key(model_name, text)
        path = CACHE_DIR / f"{key}.pkl"
        if path.exists():
            with open(path, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        logger.debug(f"Cache read failed: {e}")
    return None


def set_cached_embedding(model_name: str, text: str, embedding: np.ndarray):
    """Store embedding in cache."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        key = _cache_key(model_name, text)
        path = CACHE_DIR / f"{key}.pkl"
        with open(path, "wb") as f:
            pickle.dump(embedding, f)
    except Exception as e:
        logger.debug(f"Cache write failed: {e}")


def embed_with_cache(embedder, texts: list, is_query: bool = False) -> np.ndarray:
    """
    Embed a list of texts, using cache for documents.
    Queries are never cached (they change per run).
    """
    if is_query:
        return embedder.embed_queries(texts)

    model_name = embedder.model_name
    results = []
    uncached_indices = []
    uncached_texts = []

    # Check cache for each text
    for i, text in enumerate(texts):
        cached = get_cached_embedding(model_name, text)
        if cached is not None:
            results.append((i, cached))
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    # Embed uncached texts in batch
    if uncached_texts:
        new_embeddings = embedder.embed_documents(uncached_texts)
        for idx, (orig_i, text) in enumerate(zip(uncached_indices, uncached_texts)):
            emb = new_embeddings[idx]
            set_cached_embedding(model_name, text, emb)
            results.append((orig_i, emb))

    # Sort by original index and stack
    results.sort(key=lambda x: x[0])
    return np.vstack([emb for _, emb in results])


def cache_stats() -> dict:
    """Return cache statistics."""
    try:
        files = list(CACHE_DIR.glob("*.pkl"))
        total_size = sum(f.stat().st_size for f in files)
        return {"entries": len(files), "size_mb": round(total_size / 1e6, 2)}
    except Exception:
        return {"entries": 0, "size_mb": 0}
