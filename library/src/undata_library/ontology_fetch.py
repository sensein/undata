"""Fetch ontology terms via bulk OBO download from OBO Foundry.

Small ontologies (PATO, HP, OBI): full OBO download + pronto parse.
Large ontologies (NCIT, NCBITaxon): OBO download + streaming line parse
(no full pronto load — too slow for 200MB+ files).
"""

from __future__ import annotations

import logging
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Canonical OBO download URLs
SUPPORTED_ONTOLOGIES = {
    "ncit": "http://purl.obolibrary.org/obo/ncit.obo",
    "pato": "http://purl.obolibrary.org/obo/pato.obo",
    "hp": "http://purl.obolibrary.org/obo/hp.obo",
    "obi": "http://purl.obolibrary.org/obo/obi.obo",
    "ncbitaxon": "http://purl.obolibrary.org/obo/ncbitaxon.obo",
}

# Ontologies small enough for full pronto parse (< 50MB)
_PRONTO_ONTOLOGIES = {"pato", "hp", "obi"}

# Large ontologies — use fast line-based OBO parser
_LARGE_ONTOLOGIES = {"ncit", "ncbitaxon"}


def fetch_ontology(name: str) -> dict:
    """Fetch ontology via bulk OBO download.

    Uses pronto for small ontologies, fast line parser for large ones.
    Falls back to OLS API on failure.
    """
    url = SUPPORTED_ONTOLOGIES.get(name.lower())
    if not url:
        raise ValueError(f"Unsupported ontology: {name}. Supported: {list(SUPPORTED_ONTOLOGIES)}")

    try:
        obo_path = _download_obo(name, url)
        try:
            if name.lower() in _PRONTO_ONTOLOGIES:
                return _parse_with_pronto(name, obo_path)
            else:
                return _parse_obo_fast(name, obo_path)
        finally:
            obo_path.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Bulk OBO failed for %s: %s. Falling back to OLS API.", name, exc)
        return _fetch_ols_fallback(name)


def _download_obo(name: str, url: str) -> Path:
    """Download OBO file, return path to temp file."""
    logger.info("Downloading %s from %s", name, url)
    tmp = tempfile.NamedTemporaryFile(suffix=".obo", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    with httpx.stream("GET", url, follow_redirects=True, timeout=600) as resp:
        resp.raise_for_status()
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=65536):
                f.write(chunk)

    size_mb = tmp_path.stat().st_size / 1024 / 1024
    logger.info("Downloaded %s: %.1f MB", name, size_mb)
    return tmp_path


def _parse_with_pronto(name: str, obo_path: Path) -> dict:
    """Parse small ontologies with pronto (full object model)."""
    import pronto

    logger.info("Parsing %s with pronto", name)
    ont = pronto.Ontology(str(obo_path))

    terms: dict[str, dict] = {}
    for term in ont.terms():
        uri = _obo_id_to_uri(str(term.id))
        terms[uri] = {
            "label": term.name or "",
            "synonyms": [s.description for s in term.synonyms] if term.synonyms else [],
            "parents": [
                _obo_id_to_uri(str(p.id)) for p in term.superclasses(distance=1, with_self=False)
            ],
            "deprecated": term.obsolete,
        }

    logger.info("Parsed %s: %d terms", name, len(terms))
    return _build_result(name, terms)


def _parse_obo_fast(name: str, obo_path: Path) -> dict:
    """Fast line-based OBO parser for large ontologies (NCIT, NCBITaxon).

    Parses [Term] stanzas without building a full object graph.
    ~10x faster than pronto for 200MB+ files.
    """
    logger.info("Fast-parsing %s (%d MB)", name, obo_path.stat().st_size // 1024 // 1024)

    terms: dict[str, dict] = {}
    current_id: str | None = None
    current: dict | None = None

    with open(obo_path, encoding="utf-8", errors="replace") as f:
        in_term = False
        for line in f:
            line = line.rstrip("\n")

            if line == "[Term]":
                # Save previous term
                if current_id and current:
                    terms[current_id] = current
                in_term = True
                current_id = None
                current = {"label": "", "synonyms": [], "parents": [], "deprecated": False}
                continue

            if line.startswith("[") and line.endswith("]"):
                # End of [Term] stanza (start of [Typedef] or another)
                if current_id and current:
                    terms[current_id] = current
                in_term = False
                current_id = None
                current = None
                continue

            if not in_term or current is None:
                continue

            if line.startswith("id: "):
                current_id = _obo_id_to_uri(line[4:].strip())
            elif line.startswith("name: "):
                current["label"] = line[6:].strip()
            elif line.startswith("synonym: "):
                # synonym: "text" SCOPE [xref]
                m = re.match(r'^synonym:\s+"([^"]*)"', line)
                if m:
                    current["synonyms"].append(m.group(1))
            elif line.startswith("is_a: "):
                parent_id = line[6:].strip().split("!")[0].strip()
                current["parents"].append(_obo_id_to_uri(parent_id))
            elif line.startswith("is_obsolete: true"):
                current["deprecated"] = True

        # Save last term
        if current_id and current:
            terms[current_id] = current

    logger.info("Fast-parsed %s: %d terms", name, len(terms))
    return _build_result(name, terms)


def _obo_id_to_uri(obo_id: str) -> str:
    """Convert OBO ID (NCIT:C25150) to full URI."""
    if obo_id.startswith("http"):
        return obo_id
    if ":" in obo_id:
        prefix, local = obo_id.split(":", 1)
        return f"http://purl.obolibrary.org/obo/{prefix}_{local}"
    return obo_id


def _build_result(name: str, terms: dict) -> dict:
    return {
        "ontology": name.upper(),
        "version": "bulk",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "terms": terms,
    }


def _fetch_ols_fallback(name: str, max_terms: int = 10000) -> dict:
    """Legacy OLS API fallback."""
    import time

    import requests

    OLS_BASE = "https://www.ebi.ac.uk/ols4/api"

    terms: dict[str, dict] = {}
    page = 0

    while len(terms) < max_terms:
        url = f"{OLS_BASE}/ontologies/{name.lower()}/terms"
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
        time.sleep(0.5)

    return _build_result(name, terms)
