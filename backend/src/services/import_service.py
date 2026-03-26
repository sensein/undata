"""Import flat-file YAML registry into PostgreSQL database."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CurationFlag, Element, RunSummary, Schema, Value, ValueSet

logger = logging.getLogger(__name__)


async def import_registry(
    session: AsyncSession,
    registry_dir: str | Path,
    clear_existing: bool = True,
) -> dict[str, int]:
    registry_dir = Path(registry_dir)
    """Import all entities from a flat-file YAML registry into the database.

    Args:
        session: SQLAlchemy async session
        registry_dir: Path to the registry directory
        clear_existing: If True, delete all existing records before import

    Returns: {elements, schemas, values, valuesets, flags, runs}
    """
    stats: dict[str, int] = {}

    if clear_existing:
        for model in [Element, Schema, Value, ValueSet, CurationFlag, RunSummary]:
            await session.execute(model.__table__.delete())

    # Import each entity type
    for entity_type, model_cls, parse_fn in [
        ("elements", Element, _parse_element),
        ("schemas", Schema, _parse_schema),
        ("values", Value, _parse_value),
        ("valuesets", ValueSet, _parse_valueset),
    ]:
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
                record = parse_fn(data, f.name)
                session.add(record)
                count += 1
            except Exception as exc:
                logger.warning("Failed to import %s: %s", f, exc)

        stats[entity_type] = count

    # Import curation flags
    flags_dir = registry_dir / "curation-flags"
    if flags_dir.exists():
        count = 0
        for f in sorted(flags_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                record = CurationFlag(
                    entity_type=data.get("entity_type", ""),
                    entity_ref=data.get("entity_ref", ""),
                    flag_type=data.get("flag_type", ""),
                    context=data.get("context", {}),
                    llm_verification=data.get("llm_verification"),
                    status=data.get("status", "pending"),
                    resolved_by=data.get("resolved_by"),
                    resolution_note=data.get("resolution_note"),
                )
                session.add(record)
                count += 1
            except Exception as exc:
                logger.warning("Failed to import flag %s: %s", f, exc)
        stats["flags"] = count

    # Import run summaries
    runs_dir = registry_dir / "runs"
    if runs_dir.exists():
        count = 0
        for f in sorted(runs_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                record = RunSummary(
                    run_id=data.get("run_id", f.stem),
                    source=data.get("source", ""),
                    started_at=data.get("started_at", ""),
                    completed_at=data.get("completed_at"),
                    entity_counts=data.get("entity_counts", {}),
                    enrichment_rate=data.get("enrichment_rate"),
                    curation_flags=data.get("curation_flags"),
                    delta=data.get("delta"),
                    timing=data.get("timing"),
                )
                session.add(record)
                count += 1
            except Exception as exc:
                logger.warning("Failed to import run %s: %s", f, exc)
        stats["runs"] = count

    await session.flush()
    logger.info("Imported: %s", stats)
    return stats


def _parse_element(data: dict, file_name: str) -> Element:
    sem = data.get("semantic", {})
    return Element(
        sha256=data.get("sha256"),
        file_name=file_name,
        data_type=sem.get("data_type"),
        unit=sem.get("unit"),
        pattern=sem.get("pattern"),
        value_domain=sem.get("value_domain"),
        description=sem.get("description"),
        min_value=sem.get("min_value"),
        max_value=sem.get("max_value"),
        type_ref=sem.get("type_ref"),
        semantic=sem,
        provenance=data.get("provenance", []),
        ontology_annotations=sem.get("ontology_annotations", []),
    )


def _parse_schema(data: dict, file_name: str) -> Schema:
    sem = data.get("semantic", {})
    return Schema(
        sha256=data.get("sha256"),
        file_name=file_name,
        properties=sem.get("properties", []),
        subclass_of=sem.get("subclass_of"),
        is_mixin=sem.get("is_mixin", False),
        description=sem.get("description"),
        semantic=sem,
        provenance=data.get("provenance", []),
        ontology_annotations=sem.get("ontology_annotations", []),
    )


def _parse_value(data: dict, file_name: str) -> Value:
    sem = data.get("semantic", {})
    return Value(
        sha256=data.get("sha256"),
        file_name=file_name,
        label=sem.get("label", ""),
        value_type=sem.get("value_type"),
        ontology_id=sem.get("ontology_id"),
        description=sem.get("description"),
        semantic=sem,
        provenance=data.get("provenance", []),
        ontology_annotations=sem.get("ontology_annotations", []),
    )


def _parse_valueset(data: dict, file_name: str) -> ValueSet:
    sem = data.get("semantic", {})
    return ValueSet(
        sha256=data.get("sha256"),
        file_name=file_name,
        name=sem.get("name", ""),
        members=sem.get("members", []),
        description=sem.get("description"),
        semantic=sem,
        provenance=data.get("provenance", []),
        ontology_annotations=sem.get("ontology_annotations", []),
    )
