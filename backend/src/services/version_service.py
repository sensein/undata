"""Version dependency management — detect and respond to ontology/source updates."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.audit_service import write_audit

logger = logging.getLogger(__name__)


async def check_dependency_versions(session: AsyncSession) -> list[dict]:
    """Check all registered dependencies for version changes.

    Returns list of VersionTransition dicts.
    """
    from undata_library.version_check import check_ontology_versions

    transitions = check_ontology_versions()

    for t in transitions:
        await write_audit(
            session,
            activity="version_change_detected",
            agent="system",
            agent_type="system",
            entity_type="ontology",
            entity_ref=t["dependency_name"],
            details=t,
        )

    return transitions
