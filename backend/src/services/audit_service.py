"""Audit service — writes W3C PROV-O style audit log entries for all mutations."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AuditLog

logger = logging.getLogger(__name__)


async def write_audit(
    session: AsyncSession,
    *,
    activity: str,
    agent: str,
    agent_type: str = "user",
    entity_type: str,
    entity_ref: str,
    generated_entity_ref: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Write a single audit log entry.

    Args:
        session: Database session (caller commits).
        activity: Action performed (create, update, delete, approve, reject, enrich, ingest, version).
        agent: Who performed it (user email/name or "system").
        agent_type: "user" or "system".
        entity_type: Target entity type (element, schema, value, valueset, transform, flag, proposal).
        entity_ref: Target entity identifier (sha256 or UUID).
        generated_entity_ref: Optional new entity created by this activity (e.g., new version sha256).
        details: Optional JSONB dict with extra context.

    Returns:
        The created AuditLog row.
    """
    entry = AuditLog(
        activity=activity,
        agent=agent,
        agent_type=agent_type,
        entity_type=entity_type,
        entity_ref=entity_ref,
        generated_entity_ref=generated_entity_ref,
        details=details,
    )
    session.add(entry)
    logger.info("audit: %s %s %s/%s by %s", activity, agent_type, entity_type, entity_ref, agent)
    return entry
