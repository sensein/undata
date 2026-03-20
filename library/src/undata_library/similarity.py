"""Semantic similarity scoring between data elements."""

from __future__ import annotations

import difflib


def name_similarity(name_a: str, name_b: str) -> float:
    """Compute name similarity using embeddings (if available) or difflib fallback."""
    try:
        return _embedding_similarity(name_a, name_b)
    except (ImportError, Exception):
        return _difflib_similarity(name_a, name_b)


def _difflib_similarity(a: str, b: str) -> float:
    """Fallback similarity using SequenceMatcher."""
    a_clean = a.lower().replace("_", " ").strip()
    b_clean = b.lower().replace("_", " ").strip()
    return difflib.SequenceMatcher(None, a_clean, b_clean).ratio()


_EMBEDDING_MODEL = None


def _embedding_similarity(a: str, b: str) -> float:
    """Compute cosine similarity using sentence-transformers."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer

        _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

    embeddings = _EMBEDDING_MODEL.encode([a, b])
    # Cosine similarity
    import numpy as np

    cos_sim = float(
        np.dot(embeddings[0], embeddings[1])
        / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
    )
    return max(0.0, min(1.0, cos_sim))


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


def compute_similarity(elem_a: dict, elem_b: dict) -> dict:
    """Compute overall similarity between two element semantic dicts.

    Returns: {score, relation, components: {name_sim, ontology_match, range_overlap, valueset_jaccard}}
    """
    sem_a = elem_a.get("semantic", elem_a)
    sem_b = elem_b.get("semantic", elem_b)

    # Component 1: ontology match
    onto_a = sem_a.get("ontology_term")
    onto_b = sem_b.get("ontology_term")
    ontology_match = 1.0 if (onto_a and onto_b and onto_a == onto_b) else 0.0

    # Component 2: name similarity
    name_a = ""
    name_b = ""
    for p in elem_a.get("provenance", []):
        name_a = p.get("name", "")
        if name_a:
            break
    for p in elem_b.get("provenance", []):
        name_b = p.get("name", "")
        if name_b:
            break
    name_sim = name_similarity(name_a, name_b) if name_a and name_b else 0.0

    # Component 3: range overlap
    r_overlap = range_overlap_score(
        sem_a.get("min_value"),
        sem_a.get("max_value"),
        sem_b.get("min_value"),
        sem_b.get("max_value"),
    )

    # Component 4: valueset Jaccard
    choices_a = _extract_choices(sem_a)
    choices_b = _extract_choices(sem_b)
    vs_jaccard = valueset_jaccard(choices_a, choices_b)

    # Weighted score
    weights = {"ontology": 0.4, "name": 0.3, "range": 0.15, "valueset": 0.15}
    score = (
        weights["ontology"] * ontology_match
        + weights["name"] * name_sim
        + weights["range"] * r_overlap
        + weights["valueset"] * vs_jaccard
    )

    # Determine SKOS relation
    relation = map_to_skos(score, sem_a, sem_b)

    return {
        "score": round(score, 4),
        "relation": relation,
        "components": {
            "name_sim": round(name_sim, 4),
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


def _extract_choices(sem: dict) -> list[str]:
    """Extract choice values from response_options or constraints.allowed_values."""
    opts = sem.get("response_options")
    if opts:
        return [o.get("value", "") for o in opts if isinstance(o, dict)]
    constraints = sem.get("constraints", {})
    if constraints and constraints.get("allowed_values"):
        return constraints["allowed_values"]
    return []
