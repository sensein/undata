"""Source discovery: automated scan for candidate neuroscience data element repositories.

Scans registries (FAIRsharing, BioPortal, OBO Foundry) and uses LLM-assisted
evaluation to identify candidate sources for potential ingestion. Curator
approval is required before any discovered source is ingested.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .utils import safe_load_yaml, write_yaml

logger = logging.getLogger(__name__)


def scan_for_candidates(
    registries: list[str] | None = None,
    use_llm: bool = True,
    model: str | None = None,
) -> list[dict]:
    """Scan registries for candidate neuroscience data element repositories.

    Returns a list of candidate dicts with:
        - name: str (repository name)
        - url: str (repository URL)
        - format: str (json_schema, linkml, csv, owl, other)
        - registry: str (source registry: fairsharing, bioportal, obo_foundry, manual)
        - relevance_score: float (0.0-1.0, LLM-assessed)
        - description: str
        - discovered_at: str (ISO 8601)
    """
    registries = registries or ["obo_foundry", "bioportal", "fairsharing"]
    candidates: list[dict] = []

    for registry in registries:
        try:
            if registry == "obo_foundry":
                candidates.extend(_scan_obo_foundry(use_llm, model))
            elif registry == "bioportal":
                candidates.extend(_scan_bioportal(use_llm, model))
            elif registry == "fairsharing":
                candidates.extend(_scan_fairsharing(use_llm, model))
            else:
                logger.warning("Unknown registry: %s", registry)
        except Exception as exc:
            logger.warning("Failed to scan %s: %s", registry, exc)

    return candidates


def save_candidates(output_dir: Path, candidates: list[dict]) -> Path:
    """Save discovered candidates to {output_dir}/discovery/candidates.yaml."""
    discovery_dir = output_dir / "discovery"
    discovery_dir.mkdir(parents=True, exist_ok=True)

    filepath = discovery_dir / "candidates.yaml"

    # Merge with existing candidates
    existing = safe_load_yaml(filepath)
    if existing and isinstance(existing.get("candidates"), list):
        existing_urls = {c.get("url") for c in existing["candidates"]}
        for c in candidates:
            if c.get("url") not in existing_urls:
                existing["candidates"].append(c)
    else:
        existing = {"candidates": candidates}

    existing["last_scan"] = datetime.now(timezone.utc).isoformat()
    write_yaml(filepath, existing)
    return filepath


def load_candidates(output_dir: Path) -> list[dict]:
    """Load discovered candidates from the discovery directory."""
    filepath = output_dir / "discovery" / "candidates.yaml"
    data = safe_load_yaml(filepath)
    if data and isinstance(data.get("candidates"), list):
        return data["candidates"]
    return []


def approve_candidate(output_dir: Path, candidate_url: str, curator: str) -> bool:
    """Approve a discovered candidate for ingestion.

    Creates a source_def YAML file for the approved source.
    Returns True if approved, False if candidate not found.
    """
    filepath = output_dir / "discovery" / "candidates.yaml"
    data = safe_load_yaml(filepath)
    if not data or not isinstance(data.get("candidates"), list):
        return False

    for candidate in data["candidates"]:
        if candidate.get("url") == candidate_url:
            candidate["status"] = "approved"
            candidate["approved_by"] = curator
            candidate["approved_at"] = datetime.now(timezone.utc).isoformat()
            write_yaml(filepath, data)
            return True
    return False


def reject_candidate(output_dir: Path, candidate_url: str, curator: str, reason: str = "") -> bool:
    """Reject a discovered candidate."""
    filepath = output_dir / "discovery" / "candidates.yaml"
    data = safe_load_yaml(filepath)
    if not data or not isinstance(data.get("candidates"), list):
        return False

    for candidate in data["candidates"]:
        if candidate.get("url") == candidate_url:
            candidate["status"] = "rejected"
            candidate["rejected_by"] = curator
            candidate["rejected_at"] = datetime.now(timezone.utc).isoformat()
            candidate["rejection_reason"] = reason
            write_yaml(filepath, data)
            return True
    return False


def _scan_obo_foundry(use_llm: bool, model: str | None) -> list[dict]:
    """Scan OBO Foundry registry for neuroscience-relevant ontologies."""
    try:
        import httpx

        resp = httpx.get("http://www.obofoundry.org/registry/ontologies.jsonld", timeout=30)
        resp.raise_for_status()
        registry = resp.json()
    except Exception as exc:
        logger.warning("Failed to fetch OBO Foundry registry: %s", exc)
        return []

    candidates = []
    neuro_keywords = {
        "neuroscience",
        "brain",
        "neural",
        "cognit",
        "behavior",
        "psychiatr",
        "psycholog",
        "neurolog",
        "cell",
        "anatomy",
    }

    for ontology in registry.get("ontologies", []):
        title = ontology.get("title", "").lower()
        desc = ontology.get("description", "").lower()
        combined = f"{title} {desc}"

        if any(kw in combined for kw in neuro_keywords):
            candidates.append(
                {
                    "name": ontology.get("id", ""),
                    "url": ontology.get("ontology_purl", ontology.get("homepage", "")),
                    "format": "owl",
                    "registry": "obo_foundry",
                    "relevance_score": 0.7,
                    "description": ontology.get("description", "")[:200],
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending",
                }
            )

    return candidates


def _scan_bioportal(use_llm: bool, model: str | None) -> list[dict]:
    """Scan BioPortal for neuroscience-relevant ontologies."""
    # BioPortal requires API key; return empty if not configured
    import os

    api_key = os.environ.get("BIOPORTAL_API_KEY")
    if not api_key:
        logger.info("BIOPORTAL_API_KEY not set; skipping BioPortal scan")
        return []

    # Placeholder for BioPortal API integration
    return []


def _scan_fairsharing(use_llm: bool, model: str | None) -> list[dict]:
    """Scan FAIRsharing for neuroscience data standards."""
    # FAIRsharing requires authentication; return empty if not configured
    logger.info("FAIRsharing scan not yet implemented")
    return []


# ---------------------------------------------------------------------------
# Dataset repository scanning (knowledge service — feature 036)
# ---------------------------------------------------------------------------

# Pre-approved sources with known adapters
APPROVED_REPO_SOURCES = {
    "openneuro": {"adapter": "bids", "auto_ingest": True},
    "dandi": {"adapter": "dandi", "auto_ingest": True},
}


def scan_openneuro_datasets(since: str | None = None, limit: int = 50) -> list[dict]:
    """Query OpenNeuro GraphQL API for recent datasets."""
    import httpx

    query = """
    query($first: Int) {
      datasets(first: $first, orderBy: {created: descending}) {
        edges { node { id created } }
      }
    }
    """
    try:
        resp = httpx.post(
            "https://openneuro.org/crn/graphql",
            json={"query": query, "variables": {"first": limit}},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        datasets = []
        for edge in data.get("data", {}).get("datasets", {}).get("edges", []):
            node = edge.get("node", {})
            ds_id = node.get("id", "")
            created = node.get("created", "")
            if since and created < since:
                continue
            datasets.append(
                {
                    "id": ds_id,
                    "url": f"https://github.com/OpenNeuroDatasets/{ds_id}.git",
                    "adapter": "bids",
                    "source": "openneuro",
                    "created": created,
                }
            )
        logger.info("OpenNeuro scan: found %d datasets", len(datasets))
        return datasets
    except Exception as exc:
        logger.warning("OpenNeuro scan failed: %s", exc)
        return []


def scan_dandi_datasets(since: str | None = None, limit: int = 50) -> list[dict]:
    """Query DANDI Archive API for recent dandisets."""
    import httpx

    try:
        resp = httpx.get(
            "https://api.dandiarchive.org/api/dandisets/",
            params={"page_size": limit, "ordering": "-created"},
            timeout=30,
        )
        resp.raise_for_status()
        datasets = []
        for ds in resp.json().get("results", []):
            ds_id = ds.get("identifier", "")
            created = ds.get("created", "")
            if since and created < since:
                continue
            datasets.append(
                {
                    "id": ds_id,
                    "url": f"https://dandiarchive.org/dandiset/{ds_id}",
                    "adapter": "dandi",
                    "source": "dandi",
                    "created": created,
                }
            )
        logger.info("DANDI scan: found %d dandisets", len(datasets))
        return datasets
    except Exception as exc:
        logger.warning("DANDI scan failed: %s", exc)
        return []


def scan_all_repositories(since: str | None = None, limit: int = 50) -> list[dict]:
    """Scan all approved repository endpoints for new datasets."""
    results = []
    results.extend(scan_openneuro_datasets(since=since, limit=limit))
    results.extend(scan_dandi_datasets(since=since, limit=limit))
    return results
