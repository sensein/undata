"""Ontology lookup tool for LLM — validates URIs against the ontology store."""

from __future__ import annotations


async def lookup_ontology_term(query: str, ontology: str | None = None, limit: int = 5) -> dict:
    """Search the ontology store for a term. Returns validated URIs."""
    try:
        from pathlib import Path

        from undata_library.ontology_store import OntologyStore

        store_path = Path.home() / ".cache" / "undata" / "ontology-store"
        if not store_path.exists():
            return {"results": [], "error": "Ontology store not available"}

        store = OntologyStore(store_path)
        results = store.search_terms(query, ontology=ontology, limit=limit)
        return {
            "results": [
                {
                    "uri": r.get("uri", ""),
                    "label": r.get("label", ""),
                    "ontology": r.get("ontology", ""),
                    "synonyms": r.get("synonyms", []),
                }
                for r in results
            ]
        }
    except Exception as e:
        return {"results": [], "error": str(e)}
