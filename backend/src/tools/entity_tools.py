"""Entity CRUD tools for LLM curation assistant."""

from __future__ import annotations

from sqlalchemy import select

from src.db.models import ENTITY_MODEL_MAP
from src.db.session import AsyncSessionLocal


async def propose_entity_change(entity_type: str, sha256: str, field: str, value: object) -> dict:
    """Propose a field change. Returns diff preview (not applied yet)."""
    async with AsyncSessionLocal() as session:
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return {"success": False, "validation_error": f"Invalid entity type: {entity_type}"}

        stmt = select(model).where(model.sha256.startswith(sha256)).limit(1)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return {"success": False, "validation_error": f"Entity not found: {sha256}"}

        semantic = row.semantic or {}
        old_value = semantic.get(field, getattr(row, field, None))

        return {
            "success": True,
            "diff": {"field": field, "old_value": old_value, "new_value": value},
            "validation_error": None,
        }


async def create_entity(entity_type: str, data: dict) -> dict:
    """Preview a new entity creation. Returns entity preview."""
    if entity_type not in ENTITY_MODEL_MAP:
        return {"success": False, "validation_error": f"Invalid entity type: {entity_type}"}

    semantic = data.get("semantic", data)
    required = {"data_type"} if entity_type == "elements" else set()
    missing = required - set(semantic.keys())
    if missing:
        return {"success": False, "validation_error": f"Missing required fields: {missing}"}

    return {"success": True, "preview": data, "validation_error": None}


async def delete_entity(entity_type: str, sha256: str, reason: str) -> dict:
    """Propose entity deletion. Returns entity summary for confirmation."""
    async with AsyncSessionLocal() as session:
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return {"success": False, "entity_summary": ""}

        stmt = select(model).where(model.sha256.startswith(sha256)).limit(1)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return {"success": False, "entity_summary": f"Not found: {sha256}"}

        prov = (row.provenance or [{}])[0] if row.provenance else {}
        return {
            "success": True,
            "entity_summary": (
                f"{entity_type}/{prov.get('name', sha256[:12])}"
                f" from {prov.get('source', 'unknown')}"
            ),
        }


async def fetch_entity(entity_type: str, sha256: str) -> dict | None:
    """Load full entity details for LLM context."""
    async with AsyncSessionLocal() as session:
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return None

        stmt = select(model).where(model.sha256.startswith(sha256)).limit(1)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None

        return {
            "sha256": row.sha256,
            "semantic": row.semantic or {},
            "provenance": row.provenance or [],
            "ontology_annotations": row.ontology_annotations or [],
        }
