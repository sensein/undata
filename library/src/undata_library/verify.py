"""Verify ontology alignment of elements against the ontology store."""

from __future__ import annotations

import difflib
from pathlib import Path

import yaml


def verify_elements(
    elements_dir: Path,
    store=None,
    cache=None,
) -> list[dict]:
    """Verify each element's ontology_term.

    Accepts either an OntologyStore (preferred) or legacy OntologyCache.
    Returns a list of warning dicts: {file, term, issue, severity}.
    """
    warnings: list[dict] = []

    for f in sorted(elements_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not data or "semantic" not in data:
            continue

        onto = data["semantic"].get("ontology_term")
        if not onto:
            continue

        # Lookup term via store or cache
        term_info = None
        if store is not None:
            term_info = store.lookup_term(onto)
        elif cache is not None:
            all_terms = cache.load_all()
            term_info = all_terms.get(onto)

        if term_info is None:
            warnings.append(
                {
                    "file": f.name,
                    "term": onto,
                    "issue": "term not found in ontology store",
                    "severity": "WARNING",
                }
            )
            continue

        if term_info.get("deprecated", False):
            warnings.append(
                {
                    "file": f.name,
                    "term": onto,
                    "issue": f"term is deprecated (label: {term_info.get('label', '?')})",
                    "severity": "WARNING",
                }
            )

        element_name = ""
        for p in data.get("provenance", []):
            element_name = p.get("name", "")
            if element_name:
                break

        if element_name and term_info.get("label"):
            term_label = term_info["label"].lower()
            elem_lower = element_name.lower().replace("_", " ")
            synonyms = [s.lower() for s in term_info.get("synonyms", [])]
            if term_label == elem_lower or elem_lower in synonyms:
                continue

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
