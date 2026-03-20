"""Fetch ontology terms from OLS API for the offline cache."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

OLS_BASE = "https://www.ebi.ac.uk/ols4/api"

# Ontology IDs in OLS
SUPPORTED_ONTOLOGIES = {
    "ncit": "ncit",
    "pato": "pato",
    "hp": "hp",
    "obi": "obi",
    "ncbitaxon": "ncbitaxon",
}


def fetch_ontology(
    name: str,
    max_terms: int = 5000,
    delay: float = 1.0,
) -> dict:
    """Fetch term labels + parents from OLS API.

    Returns a dict suitable for OntologyCache.save().
    """
    ols_id = SUPPORTED_ONTOLOGIES.get(name.lower())
    if not ols_id:
        raise ValueError(f"Unsupported ontology: {name}. Supported: {list(SUPPORTED_ONTOLOGIES)}")

    terms: dict[str, dict] = {}
    page = 0
    page_size = 500

    while len(terms) < max_terms:
        url = f"{OLS_BASE}/ontologies/{ols_id}/terms"
        params = {"page": page, "size": page_size}

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  Warning: OLS request failed (page {page}): {exc}")
            break

        data = resp.json()
        embedded = data.get("_embedded", {}).get("terms", [])
        if not embedded:
            break

        for term in embedded:
            iri = term.get("iri", "")
            if not iri:
                continue
            label = term.get("label", "")
            synonyms = term.get("synonyms", []) or []
            is_obsolete = term.get("is_obsolete", False)

            # Extract parent IRIs
            parents = []
            for link in term.get("_links", {}).get("parents", {}).get("href", []):
                pass  # Parents require separate API call; skip for now
            # Use annotation-based parents if available
            if term.get("annotation", {}).get("subClassOf"):
                parents = term["annotation"]["subClassOf"]

            terms[iri] = {
                "label": label,
                "synonyms": synonyms if synonyms else [],
                "parents": parents,
                "deprecated": is_obsolete,
            }

        total_pages = data.get("page", {}).get("totalPages", 0)
        page += 1
        if page >= total_pages:
            break

        time.sleep(delay)

    return {
        "ontology": name.upper(),
        "version": "fetched",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "terms": terms,
    }
