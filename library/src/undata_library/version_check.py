"""Dependency version detection — check registered ontologies/sources for updates.

Compares current checksums against stored checksums to detect version changes.
Returns a list of VersionTransition dicts for changed dependencies.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


def check_ontology_versions(
    ontology_store=None,
) -> list[dict]:
    """Check all registered ontology sources for version changes.

    Compares the stored checksum against the current checksum from the source URL.
    Returns a list of VersionTransition dicts for changed ontologies.
    """
    if ontology_store is None:
        from .ontology_store import OntologyStore

        ontology_store = OntologyStore()

    transitions = []
    loaded = ontology_store.list_loaded()

    for entry in loaded:
        name = entry.get("name", "")
        url = entry.get("url", "")
        old_checksum = entry.get("checksum", "")

        if not url or not old_checksum:
            continue

        try:
            new_checksum = _fetch_checksum(url)
            if new_checksum and new_checksum != old_checksum:
                transitions.append(
                    {
                        "dependency_type": "ontology",
                        "dependency_name": name,
                        "old_version": old_checksum,
                        "new_version": new_checksum,
                        "affected_entities": 0,  # populated by caller after re-enrichment
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                logger.info(
                    "Version change detected for %s: %s -> %s",
                    name,
                    old_checksum[:12],
                    new_checksum[:12],
                )
        except Exception as e:
            logger.warning("Failed to check version for %s: %s", name, e)

    return transitions


def _fetch_checksum(url: str, timeout: float = 30.0) -> str | None:
    """Fetch content from URL and compute SHA-256 checksum."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return hashlib.sha256(resp.content).hexdigest()
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None
