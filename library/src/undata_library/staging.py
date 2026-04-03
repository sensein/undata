"""Staging directory management for the extract → enrich → commit pipeline.

Parquet-only: all staging uses ParquetStore. No YAML files created.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


def generate_run_id() -> str:
    """Generate a unique pipeline run ID."""
    import uuid

    return str(uuid.uuid4())[:12]


def create_staging_dir(output_dir: Path, run_id: str) -> Path:
    """Create a staging directory for a pipeline run.

    Structure: {output_dir}/.staging/{run_id}/{elements,schemas,values,valuesets}/
    """
    staging = output_dir / ".staging" / run_id
    for subdir in ("elements", "schemas", "values", "valuesets"):
        (staging / subdir).mkdir(parents=True, exist_ok=True)
    return staging


def cleanup_stale_staging(output_dir: Path, max_age_hours: int = 24) -> int:
    """Remove staging directories older than max_age_hours. Returns count removed."""
    staging_root = output_dir / ".staging"
    if not staging_root.exists():
        return 0

    removed = 0
    now = datetime.now(timezone.utc).timestamp()

    for run_dir in sorted(staging_root.iterdir()):
        if not run_dir.is_dir():
            continue
        age_hours = (now - run_dir.stat().st_mtime) / 3600
        if age_hours > max_age_hours:
            shutil.rmtree(run_dir)
            removed += 1

    if staging_root.exists() and not any(staging_root.iterdir()):
        staging_root.rmdir()

    return removed


def write_staged_batch(
    staging_dir: Path,
    entity_type: str,
    entities: list[dict],
    source: str,
) -> int:
    """Write a batch of entities to staging using Parquet.

    Returns number of entities written.
    """
    if not entities:
        return 0

    from .storage.parquet_store import ParquetStore

    store = ParquetStore(staging_dir)
    return store.write_batch(entity_type, entities, source=source)


def count_staged(staging_dir: Path, entity_type: str) -> int:
    """Count staged entities (Parquet only)."""
    from .storage.parquet_store import ParquetStore

    store = ParquetStore(staging_dir)
    return store.count(entity_type)


def iter_staged(staging_dir: Path, entity_type: str):
    """Iterate all staged entities from Parquet."""
    from .storage.parquet_store import ParquetStore

    store = ParquetStore(staging_dir)
    yield from store.list(entity_type)
