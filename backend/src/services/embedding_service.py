"""Embedding service — compute text embeddings for search using sentence-transformers.

Lazily loads the model on first use. Reuses the same all-MiniLM-L6-v2 model
as the library's enrichment pipeline for consistent embedding space.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_MODEL = None
_MODEL_NAME = "all-MiniLM-L6-v2"
_EMBEDDING_DIM = 384


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer

            _MODEL = SentenceTransformer(_MODEL_NAME)
            logger.info("Loaded embedding model %s", _MODEL_NAME)
        except ImportError:
            logger.warning("sentence-transformers not available; embeddings disabled")
            return None
    return _MODEL


def compute_embedding(text: str) -> list[float] | None:
    """Compute a 384-dim embedding for the given text."""
    model = _get_model()
    if model is None or not text.strip():
        return None
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def compute_embeddings_batch(texts: list[str]) -> list[list[float] | None]:
    """Compute embeddings for a batch of texts."""
    model = _get_model()
    if model is None:
        return [None] * len(texts)
    results: list[list[float] | None] = []
    non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
    if not non_empty:
        return [None] * len(texts)

    indices, valid_texts = zip(*non_empty)
    vecs = model.encode(list(valid_texts), normalize_embeddings=True, batch_size=64)

    result_map: dict[int, list[float]] = {}
    for idx, vec in zip(indices, vecs):
        result_map[idx] = vec.tolist()

    for i in range(len(texts)):
        results.append(result_map.get(i))
    return results


def build_search_text(entity_type: str, data: dict) -> str:
    """Build a search-friendly text string from entity data for tsvector and embedding."""
    sem = data.get("semantic", {})
    prov_list = data.get("provenance", [])

    parts: list[str] = []

    # Name from provenance
    for prov in prov_list:
        if isinstance(prov, dict):
            name = prov.get("name", "")
            if name:
                parts.append(name)
            desc = prov.get("description", "")
            if desc:
                parts.append(desc[:200])

    # Type-specific fields
    if entity_type == "elements":
        if sem.get("data_type"):
            parts.append(sem["data_type"])
        if sem.get("unit"):
            parts.append(sem["unit"])
        if sem.get("description"):
            parts.append(sem["description"][:200])
    elif entity_type == "values":
        if sem.get("label"):
            parts.append(sem["label"])
    elif entity_type == "valuesets":
        if sem.get("name"):
            parts.append(sem["name"])
    elif entity_type == "schemas":
        if sem.get("description"):
            parts.append(sem["description"][:200])

    return " ".join(parts).strip()
