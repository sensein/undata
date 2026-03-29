"""Import flat-file YAML registry into PostgreSQL via DatabaseBackend.

Reads YAML files from a registry directory and writes them through the
DatabaseBackend, which handles upsert (idempotent re-import).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.database_backend import DatabaseBackend
from undata_library.models import CurationFlag, FlagStatus, FlagType, RunSummary

logger = logging.getLogger(__name__)


async def import_registry(
    session: AsyncSession,
    registry_dir: str | Path,
    clear_existing: bool = False,
) -> dict[str, int]:
    """Import all entities from a flat-file YAML registry into the database.

    Uses DatabaseBackend.entities.write() for upsert semantics — re-importing
    the same data merges provenance without creating duplicates.

    Args:
        session: SQLAlchemy async session
        registry_dir: Path to the registry directory
        clear_existing: If True, delete all existing records before import

    Returns: {elements, schemas, values, valuesets, flags, runs}
    """
    registry_dir = Path(registry_dir)
    backend = DatabaseBackend(session)
    stats: dict[str, int] = {}

    if clear_existing:
        from src.db.models import (
            CurationFlag as CurationFlagModel,
            Element,
            RunSummary as RunSummaryModel,
            Schema,
            Value,
            ValueSet,
        )

        for model in [Element, Schema, Value, ValueSet, CurationFlagModel, RunSummaryModel]:
            await session.execute(model.__table__.delete())

    # Import core entity types via DatabaseBackend
    for entity_type in ("elements", "schemas", "values", "valuesets"):
        entity_dir = registry_dir / entity_type
        if not entity_dir.exists():
            stats[entity_type] = 0
            continue

        count = 0
        for f in sorted(entity_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "semantic" not in data:
                    continue
                await backend.entities.write(entity_type, data, identifier=f.stem)
                count += 1
            except Exception as exc:
                logger.warning("Failed to import %s: %s", f, exc)

        stats[entity_type] = count

    # Import transforms
    transforms_dir = registry_dir / "transforms"
    if transforms_dir.exists():
        from src.db.models import Transform as TransformModel

        count = 0
        for f in sorted(transforms_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                sha = data.get("sha256", f.stem)
                func_spec = data.get("function", {})
                prov = data.get("provenance", [])
                # Upsert by sha256
                from sqlalchemy import select
                existing = await session.execute(
                    select(TransformModel).where(TransformModel.sha256 == sha)
                )
                if existing.scalar_one_or_none() is None:
                    row = TransformModel(
                        sha256=sha,
                        file_name=f.stem,
                        source_element=data.get("source_element", ""),
                        target_element=data.get("target_element", ""),
                        function_type=func_spec.get("function_type"),
                        input_type=func_spec.get("input_type"),
                        output_type=func_spec.get("output_type"),
                        expression=func_spec.get("expression"),
                        expression_type=func_spec.get("expression_type"),
                        confidence=data.get("confidence"),
                        description=data.get("description"),
                        semantic=data.get("semantic", {}),
                        provenance=prov,
                    )
                    session.add(row)
                    count += 1
            except Exception as exc:
                logger.warning("Failed to import transform %s: %s", f, exc)
        stats["transforms"] = count
    else:
        stats["transforms"] = 0

    # Import curation flags
    flags_dir = registry_dir / "curation-flags"
    if flags_dir.exists():
        count = 0
        for f in sorted(flags_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                flag = CurationFlag(
                    id=data.get("id", f.stem),
                    entity_type=data.get("entity_type", ""),
                    entity_ref=data.get("entity_ref", ""),
                    flag_type=FlagType(data["flag_type"]) if data.get("flag_type") else FlagType.needs_review,
                    context=data.get("context", {}),
                    status=FlagStatus(data["status"]) if data.get("status") else FlagStatus.pending,
                    created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
                )
                await backend.flags.write_flag(flag)
                count += 1
            except Exception as exc:
                logger.warning("Failed to import flag %s: %s", f, exc)
        stats["flags"] = count
    else:
        stats["flags"] = 0

    # Import run summaries
    runs_dir = registry_dir / "runs"
    if runs_dir.exists():
        count = 0
        for f in sorted(runs_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                summary = RunSummary(
                    run_id=data.get("run_id", f.stem),
                    source=data.get("source", ""),
                    started_at=data.get("started_at", ""),
                    entity_counts=data.get("entity_counts", {}),
                )
                await backend.runs.save_summary(summary)
                count += 1
            except Exception as exc:
                logger.warning("Failed to import run %s: %s", f, exc)
        stats["runs"] = count
    else:
        stats["runs"] = 0

    await session.flush()
    logger.info("Imported: %s", stats)
    return stats
