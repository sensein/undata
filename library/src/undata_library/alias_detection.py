"""Detect alias candidates across elements using semantic similarity."""

from __future__ import annotations

from pathlib import Path

import yaml

from .similarity import compute_similarity


def detect_aliases(
    elements_dir: Path,
    threshold: float = 0.5,
) -> list[dict]:
    """Scan all elements and compute pairwise similarity for alias detection.

    Returns candidate pairs sorted by score descending.
    Optimized: skip pairs with different data_type (can't be aliases).
    """
    # Load all elements grouped by data_type for optimization
    by_type: dict[str, list[tuple[str, dict]]] = {}
    for f in sorted(elements_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not data or "semantic" not in data:
            continue
        dt = data["semantic"].get("data_type", "")
        by_type.setdefault(dt, []).append((f.name, data))

    candidates: list[dict] = []

    for dt, elements in by_type.items():
        n = len(elements)
        for i in range(n):
            fname_a, data_a = elements[i]
            for j in range(i + 1, n):
                fname_b, data_b = elements[j]

                result = compute_similarity(data_a, data_b)
                if result["score"] >= threshold:
                    candidates.append(
                        {
                            "element_a": fname_a,
                            "element_b": fname_b,
                            "score": result["score"],
                            "relation": result["relation"],
                            "components": result["components"],
                        }
                    )

    candidates.sort(key=lambda x: -x["score"])
    return candidates
