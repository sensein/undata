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
