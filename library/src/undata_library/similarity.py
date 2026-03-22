"""Semantic similarity scoring between data elements."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .embeddings import EmbeddingStore


def semantic_embedding_similarity(
    uri_a: str,
    uri_b: str,
    store: EmbeddingStore | None,
    elem_a: dict | None = None,
    elem_b: dict | None = None,
) -> float:
    """Compute semantic similarity using precomputed embeddings.

    Falls back to difflib name similarity if store is unavailable or URIs not found.
    """
    if store is not None:
        from .embeddings import cosine_similarity

        vec_a = store.get_vector(uri_a)
        vec_b = store.get_vector(uri_b)
        if vec_a is not None and vec_b is not None:
            return max(0.0, min(1.0, cosine_similarity(vec_a, vec_b)))

    # Fallback: difflib on element names
    name_a = _extract_name(elem_a) if elem_a else ""
    name_b = _extract_name(elem_b) if elem_b else ""
    if name_a and name_b:
        return _difflib_similarity(name_a, name_b)
    return 0.0


def name_similarity(name_a: str, name_b: str) -> float:
    """Compute name similarity using difflib (legacy, kept for backward compat)."""
    return _difflib_similarity(name_a, name_b)


def _difflib_similarity(a: str, b: str) -> float:
    """Fallback similarity using SequenceMatcher."""
    a_clean = a.lower().replace("_", " ").strip()
    b_clean = b.lower().replace("_", " ").strip()
    return difflib.SequenceMatcher(None, a_clean, b_clean).ratio()


def _extract_name(elem: dict | None) -> str:
    """Extract first provenance name from element dict."""
    if not elem:
        return ""
    for p in elem.get("provenance", []):
        name = p.get("name", "")
        if name:
            return name
    return ""


def range_overlap_score(
    min_a: float | None,
    max_a: float | None,
    min_b: float | None,
    max_b: float | None,
) -> float:
    """Compute range overlap as intersection / union. Returns 0.0-1.0."""
    if min_a is None or max_a is None or min_b is None or max_b is None:
        return 0.0  # Can't compare without ranges

    if max_a < min_b or max_b < min_a:
        return 0.0  # No overlap

    intersection = max(0.0, min(max_a, max_b) - max(min_a, min_b))
    union = max(max_a, max_b) - min(min_a, min_b)

    if union == 0:
        return 1.0 if intersection == 0 else 0.0

    return intersection / union


def valueset_jaccard(choices_a: list[str], choices_b: list[str]) -> float:
    """Compute Jaccard similarity of two valuesets."""
    if not choices_a or not choices_b:
        return 0.0

    set_a = {v.lower() for v in choices_a}
    set_b = {v.lower() for v in choices_b}

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union if union > 0 else 0.0


def compute_similarity(
    elem_a: dict,
    elem_b: dict,
    embedding_store: EmbeddingStore | None = None,
    uri_a: str | None = None,
    uri_b: str | None = None,
) -> dict:
    """Compute overall similarity between two element dicts.

    Returns: {score, relation, components: {semantic_embedding, ontology_match,
              range_overlap, valueset_jaccard}}
    """
    sem_a = elem_a.get("semantic", elem_a)
    sem_b = elem_b.get("semantic", elem_b)

    # Component 1: ontology match (weight 0.4) — uses primary annotation
    onto_a = _get_primary_ontology_uri(sem_a)
    onto_b = _get_primary_ontology_uri(sem_b)
    ontology_match = 1.0 if (onto_a and onto_b and onto_a == onto_b) else 0.0

    # Component 2: semantic embedding similarity (weight 0.3)
    embedding_sim = semantic_embedding_similarity(
        uri_a or "", uri_b or "", embedding_store, elem_a, elem_b
    )

    # Component 3: range overlap (weight 0.15)
    r_overlap = range_overlap_score(
        sem_a.get("min_value"),
        sem_a.get("max_value"),
        sem_b.get("min_value"),
        sem_b.get("max_value"),
    )

    # Component 4: valueset Jaccard (weight 0.15)
    choices_a = _extract_choices(sem_a)
    choices_b = _extract_choices(sem_b)
    vs_jaccard = valueset_jaccard(choices_a, choices_b)

    # Weighted score
    score = 0.4 * ontology_match + 0.3 * embedding_sim + 0.15 * r_overlap + 0.15 * vs_jaccard

    # Determine SKOS relation
    relation = map_to_skos(score, sem_a, sem_b)

    return {
        "score": round(score, 4),
        "relation": relation,
        "components": {
            "semantic_embedding": round(embedding_sim, 4),
            "ontology_match": ontology_match,
            "range_overlap": round(r_overlap, 4),
            "valueset_jaccard": round(vs_jaccard, 4),
        },
    }


def map_to_skos(score: float, sem_a: dict, sem_b: dict) -> str:
    """Map similarity score to SKOS mapping relation."""
    if score >= 0.95:
        return "skos:exactMatch"

    # Check range subsumption
    min_a, max_a = sem_a.get("min_value"), sem_a.get("max_value")
    min_b, max_b = sem_b.get("min_value"), sem_b.get("max_value")
    if min_a is not None and max_a is not None and min_b is not None and max_b is not None:
        if min_a <= min_b and max_a >= max_b:
            return "skos:broadMatch"  # A subsumes B
        if min_b <= min_a and max_b >= max_a:
            return "skos:narrowMatch"  # B subsumes A

    if score >= 0.8:
        return "skos:closeMatch"
    if score >= 0.5:
        return "skos:relatedMatch"

    return "none"


def _get_primary_ontology_uri(sem: dict) -> str | None:
    """Get the primary ontology annotation URI from semantic dict."""
    annotations = sem.get("ontology_annotations", [])
    if annotations:
        for ann in annotations:
            if isinstance(ann, dict) and ann.get("primary"):
                return ann.get("term_uri")
        # Fallback: first annotation
        if isinstance(annotations[0], dict):
            return annotations[0].get("term_uri")
    return None


def _extract_choices(sem: dict) -> list[str]:
    """Extract choice values from response_options or constraints.allowed_values."""
    opts = sem.get("response_options")
    if opts:
        return [o.get("value", "") for o in opts if isinstance(o, dict)]
    constraints = sem.get("constraints", {})
    if constraints and constraints.get("allowed_values"):
        return constraints["allowed_values"]
    return []
