"""Detect alias candidates across elements using semantic similarity."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .similarity import compute_similarity
from .utils import BASE_URI, safe_load_yaml

if TYPE_CHECKING:
    from .embeddings import EmbeddingStore


def detect_aliases(
    elements_dir: Path,
    threshold: float = 0.5,
    embedding_store: EmbeddingStore | None = None,
) -> list[dict]:
    """Scan all elements and compute pairwise similarity for alias detection.

    Returns candidate pairs sorted by score descending.
    Optimized: skip pairs with different data_type (can't be aliases).
    """
    # Load all elements grouped by data_type for optimization
    # Read from both YAML files and Parquet
    by_type: dict[str, list[tuple[str, str, dict]]] = {}
    seen_sha: set[str] = set()

    # Parquet entities first (have embeddings)
    try:
        from .storage.parquet_store import ParquetStore

        pq = ParquetStore(elements_dir.parent)
        for data in pq.list("elements"):
            if "semantic" not in data:
                continue
            sha = data.get("sha256", "")
            if sha:
                seen_sha.add(sha)
            dt = data["semantic"].get("data_type", "")
            uri = f"{BASE_URI}/elements/{sha or id(data)}"
            fname = data.get("file_name", sha[:12] if sha else "")
            by_type.setdefault(dt, []).append((fname, uri, data))
    except Exception:
        pass

    # Then YAML files (skip if already in Parquet)
    for f in sorted(elements_dir.glob("*.yaml")):
        data = safe_load_yaml(f)
        if data is None or "semantic" not in data:
            continue
        sha = data.get("sha256", "")
        if sha and sha in seen_sha:
            continue
        dt = data["semantic"].get("data_type", "")
        uri = f"{BASE_URI}/elements/{f.stem}"
        by_type.setdefault(dt, []).append((f.name, uri, data))

    candidates: list[dict] = []

    for dt, elements in by_type.items():
        n = len(elements)
        for i in range(n):
            fname_a, uri_a, data_a = elements[i]
            for j in range(i + 1, n):
                fname_b, uri_b, data_b = elements[j]

                result = compute_similarity(
                    data_a,
                    data_b,
                    embedding_store=embedding_store,
                    uri_a=uri_a,
                    uri_b=uri_b,
                )

                score = result["score"]

                # Boost score for elements with shared alias_hints
                # (e.g., NDA elements appearing in multiple structures)
                hints_a = set(data_a.get("semantic", {}).get("alias_hints", []))
                hints_b = set(data_b.get("semantic", {}).get("alias_hints", []))
                if hints_a and hints_b and hints_a & hints_b:
                    # Shared alias hints → high-confidence pre-verified alias
                    score = max(score, 0.95)
                    result["components"]["alias_hint_boost"] = True

                if score >= threshold:
                    candidates.append(
                        {
                            "element_a": fname_a,
                            "element_b": fname_b,
                            "score": score,
                            "relation": result["relation"],
                            "components": result["components"],
                        }
                    )

    candidates.sort(key=lambda x: -x["score"])
    return candidates
