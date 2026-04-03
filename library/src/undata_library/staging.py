"""Staging directory management for the extract → enrich → commit pipeline."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


def generate_run_id() -> str:
    """Generate a unique pipeline run ID."""
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
        # Check age by directory mtime
        age_hours = (now - run_dir.stat().st_mtime) / 3600
        if age_hours > max_age_hours:
            shutil.rmtree(run_dir)
            removed += 1

    # Remove empty .staging root
    if staging_root.exists() and not any(staging_root.iterdir()):
        staging_root.rmdir()

    return removed


def write_staged_entity(
    staging_dir: Path,
    entity_type: str,
    data: dict,
) -> Path:
    """Write an entity to the staging directory with a UUID filename.

    entity_type: 'elements', 'schemas', 'values', 'valuesets'
    Returns path to the written file.
    """
    import yaml

    entity_id = str(uuid.uuid4())
    filename = f"{entity_id}.yaml"
    filepath = staging_dir / entity_type / filename
    filepath.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return filepath


def write_staged_batch(
    staging_dir: Path,
    entity_type: str,
    entities: list[dict],
    source: str,
) -> int:
    """Write a batch of entities to staging using Parquet format.

    Returns number of entities written.
    """
    if not entities:
        return 0

    from .storage.parquet_store import ParquetStore

    store = ParquetStore(staging_dir)
    return store.write_batch(entity_type, entities, source=source)


def count_staged(staging_dir: Path, entity_type: str) -> int:
    """Count staged entities (YAML files + Parquet rows)."""
    d = staging_dir / entity_type
    if not d.exists():
        return 0

    yaml_count = len(list(d.glob("*.yaml")))

    parquet_count = 0
    for pf in d.glob("*.parquet"):
        if pf.stem.startswith("_"):
            continue
        try:
            import pyarrow.parquet as pq

            parquet_count += pq.read_metadata(pf).num_rows
        except Exception:
            pass

    return yaml_count + parquet_count


def iter_staged(staging_dir: Path, entity_type: str):
    """Iterate all staged entities (from YAML files and Parquet)."""
    import yaml as _yaml

    from .storage.parquet_store import ParquetStore, _deserialize_row

    d = staging_dir / entity_type
    if not d.exists():
        return

    # YAML files
    for f in sorted(d.glob("*.yaml")):
        try:
            data = _yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                yield data
        except Exception:
            pass

    # Parquet files
    import pyarrow.parquet as pq

    for pf in sorted(d.glob("*.parquet")):
        if pf.stem.startswith("_"):
            continue
        try:
            table = pq.read_table(pf)
            for i in range(table.num_rows):
                row = {col: table.column(col).to_pylist()[i] for col in table.column_names}
                yield _deserialize_row(row)
        except Exception:
            pass
