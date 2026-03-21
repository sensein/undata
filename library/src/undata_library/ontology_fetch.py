"""Fetch ontology terms via bulk OBO/OWL download from OBO Foundry."""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Canonical OBO download URLs (prefer OBO format for speed + size)
SUPPORTED_ONTOLOGIES = {
    "ncit": "http://purl.obolibrary.org/obo/ncit.obo",
    "pato": "http://purl.obolibrary.org/obo/pato.obo",
    "hp": "http://purl.obolibrary.org/obo/hp.obo",
    "obi": "http://purl.obolibrary.org/obo/obi.obo",
    "ncbitaxon": "http://purl.obolibrary.org/obo/ncbitaxon.obo",
}


def fetch_ontology(name: str) -> dict:
    """Fetch full ontology via bulk OBO download, parse with pronto.

    Falls back to OLS API if download fails.
    Returns a dict suitable for OntologyCache.save().
    """
    url = SUPPORTED_ONTOLOGIES.get(name.lower())
    if not url:
        raise ValueError(f"Unsupported ontology: {name}. Supported: {list(SUPPORTED_ONTOLOGIES)}")

    try:
        return _fetch_bulk_obo(name, url)
    except Exception as exc:
        logger.warning("Bulk OBO download failed for %s: %s. Falling back to OLS API.", name, exc)
        return _fetch_ols_fallback(name)


def _fetch_bulk_obo(name: str, url: str) -> dict:
    """Download OBO file and parse with pronto."""
    import pronto

    logger.info("Downloading %s from %s", name, url)

    with tempfile.NamedTemporaryFile(suffix=".obo", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Stream download for large files
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)

        logger.info("Parsing %s (%s bytes)", name, tmp_path.stat().st_size)
        ont = pronto.Ontology(str(tmp_path))

        terms: dict[str, dict] = {}
        for term in ont.terms():
            uri = str(term.id)
            # Convert OBO ID to full URI if needed
            if ":" in uri and not uri.startswith("http"):
                prefix, local = uri.split(":", 1)
                uri = f"http://purl.obolibrary.org/obo/{prefix}_{local}"

            label = term.name or ""
            synonyms = [s.description for s in term.synonyms] if term.synonyms else []
            parents = []
            for parent in term.superclasses(distance=1, with_self=False):
                pid = str(parent.id)
                if ":" in pid and not pid.startswith("http"):
                    prefix, local = pid.split(":", 1)
                    pid = f"http://purl.obolibrary.org/obo/{prefix}_{local}"
                parents.append(pid)

            terms[uri] = {
                "label": label,
                "synonyms": synonyms,
                "parents": parents,
                "deprecated": term.obsolete,
            }

        logger.info("Parsed %s: %d terms", name, len(terms))

        return {
            "ontology": name.upper(),
            "version": "bulk",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "terms": terms,
        }

    finally:
        tmp_path.unlink(missing_ok=True)


def _fetch_ols_fallback(name: str, max_terms: int = 5000) -> dict:
    """Legacy OLS API fallback — paginated, slower, truncated."""
    import time

    import requests

    OLS_BASE = "https://www.ebi.ac.uk/ols4/api"
    ols_id = name.lower()

    terms: dict[str, dict] = {}
    page = 0

    while len(terms) < max_terms:
        url = f"{OLS_BASE}/ontologies/{ols_id}/terms"
        try:
            resp = requests.get(url, params={"page": page, "size": 500}, timeout=30)
            resp.raise_for_status()
        except Exception:
            break

        data = resp.json()
        embedded = data.get("_embedded", {}).get("terms", [])
        if not embedded:
            break

        for term in embedded:
            iri = term.get("iri", "")
            if not iri:
                continue
            terms[iri] = {
                "label": term.get("label", ""),
                "synonyms": term.get("synonyms", []) or [],
                "parents": [],
                "deprecated": term.get("is_obsolete", False),
            }

        total_pages = data.get("page", {}).get("totalPages", 0)
        page += 1
        if page >= total_pages:
            break
        time.sleep(1)

    return {
        "ontology": name.upper(),
        "version": "ols_fallback",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "terms": terms,
    }
