"""Full registry export service — export all entities from DB to YAML + embeddings.

Exports directly via DatabaseBackend (no API overhead). Produces the standard
registry directory structure consumed by import_service.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def export_full_registry(
    session: AsyncSession,
    output_dir: str | Path,
    version: str | None = None,
    compress: bool = True,
) -> dict:
    """Export the entire registry to a directory of YAML files + embeddings.

    Returns manifest dict with entity counts and file path.
    """
    from src.db.models import (
        ENTITY_MODEL_MAP,
        CurationFlag,
        RunSummary,
    )

    output_dir = Path(output_dir)
    if version:
        export_dir = output_dir / f"undata-registry-{version}"
    else:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        export_dir = output_dir / f"undata-registry-{now}"

    export_dir.mkdir(parents=True, exist_ok=True)
    entity_counts: dict[str, int] = {}

    # Export core entity types
    for entity_type, model in ENTITY_MODEL_MAP.items():
        type_dir = export_dir / entity_type
        type_dir.mkdir(exist_ok=True)
        count = 0

        rows = (await session.execute(select(model))).scalars().all()
        for row in rows:
            data = _row_to_dict(row, entity_type)
            fname = f"{row.file_name or row.sha256[:12]}.yaml"
            (type_dir / fname).write_text(
                yaml.dump(data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            count += 1

        entity_counts[entity_type] = count
        logger.info("Exported %d %s", count, entity_type)

        # Also export as Parquet for bulk consumption
        if count > 0:
            try:
                from undata_library.storage.parquet_store import ParquetStore

                pq_store = ParquetStore(export_dir)
                pq_entities = []
                for row in rows:
                    pq_entities.append(_row_to_dict(row, entity_type))
                pq_store.write_batch(entity_type, pq_entities, source="export")
                logger.info("Exported %d %s as Parquet", count, entity_type)
            except ImportError:
                pass  # ParquetStore not available in this environment

    # Export curation flags
    flags_dir = export_dir / "curation-flags"
    flags_dir.mkdir(exist_ok=True)
    flag_count = 0
    for row in (await session.execute(select(CurationFlag))).scalars().all():
        data = {
            "id": str(row.id),
            "entity_type": row.entity_type,
            "entity_ref": row.entity_ref,
            "flag_type": row.flag_type,
            "context": row.context or {},
            "status": row.status,
            "created_at": str(row.created_at),
        }
        if row.resolved_by:
            data["resolved_by"] = row.resolved_by
            data["resolved_at"] = str(row.resolved_at)
            data["resolution_note"] = row.resolution_note
        (flags_dir / f"{row.id}.yaml").write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        flag_count += 1
    entity_counts["curation_flags"] = flag_count

    # Export run summaries
    runs_dir = export_dir / "runs"
    runs_dir.mkdir(exist_ok=True)
    run_count = 0
    for row in (await session.execute(select(RunSummary))).scalars().all():
        data = {
            "run_id": row.run_id,
            "source": row.source,
            "started_at": row.started_at,
            "entity_counts": row.entity_counts or {},
        }
        (runs_dir / f"{row.run_id}.yaml").write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        run_count += 1
    entity_counts["runs"] = run_count

    # Export embeddings
    try:
        await _export_embeddings(session, export_dir)
    except Exception as exc:
        logger.warning("Failed to export embeddings: %s", exc)

    # Generate manifest
    from undata_library.manifest import generate_manifest

    manifest = generate_manifest(export_dir, version=version, entity_counts=entity_counts)

    # Compress if requested
    file_path = str(export_dir)
    file_size = 0
    if compress:
        from undata_library.archive import compress_directory
        from undata_library.manifest import compute_archive_checksum

        archive = compress_directory(export_dir)
        manifest["checksum"] = compute_archive_checksum(archive)
        file_path = str(archive)
        file_size = archive.stat().st_size

    logger.info("Export complete: %s (%s)", file_path, entity_counts)
    return {
        "version": version or manifest["version"],
        "file_path": file_path,
        "file_size": file_size,
        "entity_counts": entity_counts,
        "manifest": manifest,
    }


async def _export_embeddings(session: AsyncSession, export_dir: Path) -> None:
    """Export entity embeddings as parquet."""
    from src.db.models import Element

    # Check if embedding column exists and has data
    try:
        rows = (
            await session.execute(
                select(Element.sha256, Element.embedding).where(Element.embedding.isnot(None))
            )
        ).all()
    except Exception:
        return

    if not rows:
        return

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        sha256s = [r[0] for r in rows]
        vectors = [list(r[1]) if r[1] is not None else [] for r in rows]

        table = pa.table(
            {
                "sha256": sha256s,
                "entity_type": ["element"] * len(sha256s),
                "vector": vectors,
            }
        )
        pq.write_table(table, export_dir / "embeddings.parquet")
        logger.info("Exported %d embeddings", len(sha256s))
    except ImportError:
        logger.warning("pyarrow not available; skipping embedding export")


def _row_to_dict(row, entity_type: str) -> dict:
    """Convert an ORM row to a YAML-serializable dict."""
    data: dict = {
        "semantic": row.semantic or {},
        "provenance": row.provenance or [],
    }

    if hasattr(row, "sha256"):
        data["sha256"] = row.sha256
    if hasattr(row, "ontology_annotations"):
        if row.ontology_annotations:
            data["semantic"]["ontology_annotations"] = row.ontology_annotations

    # Entity-type-specific fields
    if entity_type == "elements":
        sem = data["semantic"]
        if row.data_type:
            sem["data_type"] = row.data_type
        if row.unit:
            sem["unit"] = row.unit
        if row.unit_uri:
            sem["unit_uri"] = row.unit_uri
        if row.pattern:
            sem["pattern"] = row.pattern
        if row.value_domain:
            sem["value_domain"] = row.value_domain
        if row.description:
            sem["description"] = row.description
        if row.min_value is not None:
            sem["min_value"] = row.min_value
        if row.max_value is not None:
            sem["max_value"] = row.max_value
    elif entity_type == "schemas":
        sem = data["semantic"]
        if row.properties:
            sem["properties"] = row.properties
        if row.subclass_of:
            sem["subclass_of"] = row.subclass_of
        if row.is_mixin:
            sem["is_mixin"] = row.is_mixin
        if row.description:
            sem["description"] = row.description
    elif entity_type == "values":
        sem = data["semantic"]
        if row.label:
            sem["label"] = row.label
        if row.value_type:
            sem["value_type"] = row.value_type
        if row.description:
            sem["description"] = row.description
    elif entity_type == "valuesets":
        sem = data["semantic"]
        if row.name:
            sem["name"] = row.name
        if row.members:
            sem["members"] = row.members
        if row.description:
            sem["description"] = row.description
    elif entity_type == "transforms":
        data["source_element"] = row.source_element
        data["target_element"] = row.target_element
        data["function"] = {
            "function_type": row.function_type,
            "input_type": row.input_type,
            "output_type": row.output_type,
        }
        if row.expression:
            data["function"]["expression"] = row.expression

    return data
