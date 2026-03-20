"""Verify ontology alignment of elements against the offline cache."""

from __future__ import annotations

import difflib
from pathlib import Path

import yaml

from .ontology_cache import OntologyCache


def verify_elements(
    elements_dir: Path,
    cache: OntologyCache,
) -> list[dict]:
    """Verify each element's ontology_term against the cache.

    Returns a list of warning dicts: {file, term, issue, severity}.
    """
    warnings: list[dict] = []
    all_terms = cache.load_all()

    for f in sorted(elements_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not data or "semantic" not in data:
            continue

        onto = data["semantic"].get("ontology_term")
        if not onto:
            continue

        term_info = all_terms.get(onto)

        # Check 1: term exists in cache
        if term_info is None:
            warnings.append(
                {
                    "file": f.name,
                    "term": onto,
                    "issue": "term not found in ontology cache",
                    "severity": "WARNING",
                }
            )
            continue

        # Check 2: term not deprecated
        if term_info.get("deprecated", False):
            warnings.append(
                {
                    "file": f.name,
                    "term": onto,
                    "issue": f"term is deprecated (label: {term_info.get('label', '?')})",
                    "severity": "WARNING",
                }
            )

        # Check 3: label similarity to element name
        element_name = ""
        for p in data.get("provenance", []):
            element_name = p.get("name", "")
            if element_name:
                break

        if element_name and term_info.get("label"):
            term_label = term_info["label"].lower()
            elem_lower = element_name.lower().replace("_", " ")

            # Check exact match or synonym match first
            synonyms = [s.lower() for s in term_info.get("synonyms", [])]
            if term_label == elem_lower or elem_lower in synonyms:
                continue  # Perfect match

            # Fuzzy match
            similarity = difflib.SequenceMatcher(None, elem_lower, term_label).ratio()
            if similarity < 0.5:
                warnings.append(
                    {
                        "file": f.name,
                        "term": onto,
                        "issue": (
                            f"low label similarity ({similarity:.2f}): "
                            f"element='{element_name}' vs term='{term_info['label']}'"
                        ),
                        "severity": "INFO",
                    }
                )

    return warnings
