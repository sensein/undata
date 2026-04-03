"""Parquet-based entity storage for million-scale registries.

Replaces per-entity YAML files with one Parquet file per entity type per source.
Columns: sha256, file_name, semantic (JSON), provenance (JSON),
         ontology_annotations (JSON), source, created_at.

Usage:
    store = ParquetStore(base_dir)
    store.write_batch("elements", entities, source="nda")
    entity = store.read("elements", sha256)
    for e in store.list("elements", source="bids"):
        ...
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

# Schema for entity Parquet files
ENTITY_SCHEMA = pa.schema(
    [
        pa.field("sha256", pa.string()),
        pa.field("file_name", pa.string()),
        pa.field("source", pa.string()),
        pa.field("semantic", pa.string()),  # JSON-serialized
        pa.field("provenance", pa.string()),  # JSON-serialized
        pa.field("ontology_annotations", pa.string()),  # JSON-serialized
        pa.field("embedding", pa.string()),  # JSON-serialized float list (384-dim)
        pa.field("created_at", pa.string()),
    ]
)


def _serialize_entity(entity: dict, source: str | None = None) -> dict:
    """Convert an entity dict to Parquet-compatible row."""
    prov = entity.get("provenance", [])
    src = source
    if not src and prov:
        src = prov[0].get("source", "") if isinstance(prov[0], dict) else ""

    embedding = entity.get("embedding")
    emb_str = json.dumps(embedding) if embedding is not None else ""

    # ontology_annotations may live at the top level or inside semantic
    annotations = entity.get("ontology_annotations")
    if not annotations:
        annotations = entity.get("semantic", {}).get("ontology_annotations", [])

    return {
        "sha256": entity.get("sha256", ""),
        "file_name": entity.get("file_name", ""),
        "source": src or "",
        "semantic": json.dumps(entity.get("semantic", {}), default=str),
        "provenance": json.dumps(prov, default=str),
        "ontology_annotations": json.dumps(annotations, default=str),
        "embedding": emb_str,
        "created_at": entity.get("created_at", datetime.now(timezone.utc).isoformat()),
    }


def _deserialize_row(row: dict) -> dict:
    """Convert a Parquet row back to an entity dict."""
    entity = {
        "sha256": row.get("sha256", ""),
        "file_name": row.get("file_name", ""),
    }

    for field in ("semantic", "provenance", "ontology_annotations"):
        raw = row.get(field, "{}" if field == "semantic" else "[]")
        try:
            entity[field] = json.loads(raw) if raw else ({} if field == "semantic" else [])
        except (json.JSONDecodeError, TypeError):
            entity[field] = {} if field == "semantic" else []

    # Embedding (JSON-serialized float list)
    emb_raw = row.get("embedding", "")
    if emb_raw:
        try:
            entity["embedding"] = json.loads(emb_raw)
        except (json.JSONDecodeError, TypeError):
            pass

    # Flatten semantic fields to top level for compatibility with YAML format
    sem = entity.get("semantic", {})
    for key in (
        "data_type",
        "unit",
        "unit_uri",
        "pattern",
        "value_domain",
        "description",
        "min_value",
        "max_value",
        "type_ref",
        "label",
        "value_type",
        "name",
        "members",
        "subclass_of",
        "properties",
        "response_options",
        "question_text",
    ):
        if key in sem:
            entity[key] = sem[key]

    return entity


class ParquetStore:
    """Read/write entity collections as Parquet files.

    One file per entity type per source (e.g., elements/nda.parquet).
    Supports deduplication on re-write (same sha256 → merge provenance).
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def _parquet_path(self, entity_type: str, source: str) -> Path:
        """Get path for a source-specific Parquet file."""
        safe_source = source.replace("/", "_").replace("\\", "_")
        d = self.base_dir / entity_type
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{safe_source}.parquet"

    def _all_parquet_files(self, entity_type: str) -> list[Path]:
        """List all Parquet files for an entity type."""
        d = self.base_dir / entity_type
        if not d.exists():
            return []
        return sorted(d.glob("*.parquet"))

    def write_batch(
        self,
        entity_type: str,
        entities: list[dict],
        source: str,
    ) -> int:
        """Write a batch of entities to a Parquet file.

        Deduplicates by sha256: if entity already exists, merge provenance.
        Returns number of entities written.
        """
        if not entities:
            return 0

        path = self._parquet_path(entity_type, source)

        # Load existing entities for dedup
        existing: dict[str, dict] = {}
        if path.exists():
            try:
                table = pq.read_table(path)
                for row in table.to_pydict()["sha256"]:
                    idx = table.column("sha256").to_pylist().index(row)
                    existing[row] = {
                        col: table.column(col).to_pylist()[idx] for col in table.column_names
                    }
            except Exception:
                pass

        # Merge new entities
        rows = []
        for entity in entities:
            serialized = _serialize_entity(entity, source)
            sha = serialized["sha256"]

            if sha in existing:
                # Merge provenance
                old_prov = json.loads(existing[sha].get("provenance", "[]"))
                new_prov = json.loads(serialized["provenance"])
                seen = {(p.get("source"), p.get("name")) for p in old_prov if isinstance(p, dict)}
                for p in new_prov:
                    if isinstance(p, dict) and (p.get("source"), p.get("name")) not in seen:
                        old_prov.append(p)
                serialized["provenance"] = json.dumps(old_prov, default=str)

            rows.append(serialized)
            existing[sha] = serialized  # update for subsequent dedup within batch

        # Write all (existing merged + new)
        all_rows = list(existing.values())
        table = pa.table(
            {col: [r.get(col, "") for r in all_rows] for col in ENTITY_SCHEMA.names},
            schema=ENTITY_SCHEMA,
        )
        pq.write_table(table, path, compression="snappy")

        logger.info(
            "Wrote %d entities to %s (%d total in file)",
            len(entities),
            path.name,
            len(all_rows),
        )
        return len(entities)

    def read(self, entity_type: str, sha256: str) -> dict | None:
        """Read a single entity by sha256 (prefix match supported)."""
        for path in self._all_parquet_files(entity_type):
            try:
                table = pq.read_table(path)
                sha_col = table.column("sha256").to_pylist()
                for i, sha in enumerate(sha_col):
                    if sha.startswith(sha256):
                        row = {col: table.column(col).to_pylist()[i] for col in table.column_names}
                        return _deserialize_row(row)
            except Exception:
                continue
        return None

    def list(
        self,
        entity_type: str,
        source: str | None = None,
        **filters: object,
    ) -> Iterator[dict]:
        """Iterate entities with optional source filter."""
        files = self._all_parquet_files(entity_type)
        if source:
            safe = source.replace("/", "_").replace("\\", "_")
            files = [f for f in files if f.stem == safe]

        for path in files:
            try:
                table = pq.read_table(path)
                n = table.num_rows
                for i in range(n):
                    row = {col: table.column(col).to_pylist()[i] for col in table.column_names}
                    yield _deserialize_row(row)
            except Exception as e:
                logger.warning("Failed to read %s: %s", path, e)

    def count(self, entity_type: str, source: str | None = None) -> int:
        """Count entities in Parquet files."""
        total = 0
        files = self._all_parquet_files(entity_type)
        if source:
            safe = source.replace("/", "_").replace("\\", "_")
            files = [f for f in files if f.stem == safe]
        for path in files:
            try:
                meta = pq.read_metadata(path)
                total += meta.num_rows
            except Exception:
                pass
        return total

    def exists(self, entity_type: str, sha256: str) -> bool:
        """Check if an entity exists by sha256."""
        return self.read(entity_type, sha256) is not None

    def build_index(self, entity_type: str) -> Path:
        """Build a cross-source index mapping sha256 → source file."""
        index_rows: list[dict] = []
        for path in self._all_parquet_files(entity_type):
            if path.stem.startswith("_"):
                continue
            try:
                table = pq.read_table(path, columns=["sha256", "source"])
                for sha, src in zip(
                    table.column("sha256").to_pylist(),
                    table.column("source").to_pylist(),
                ):
                    index_rows.append(
                        {
                            "sha256": sha,
                            "source": src,
                            "parquet_file": path.name,
                        }
                    )
            except Exception:
                pass

        index_path = self.base_dir / entity_type / "_index.parquet"
        if index_rows:
            index_schema = pa.schema(
                [
                    pa.field("sha256", pa.string()),
                    pa.field("source", pa.string()),
                    pa.field("parquet_file", pa.string()),
                ]
            )
            table = pa.table(
                {col: [r[col] for r in index_rows] for col in index_schema.names},
                schema=index_schema,
            )
            pq.write_table(table, index_path, compression="snappy")
            logger.info("Built index for %s: %d entries", entity_type, len(index_rows))
        return index_path

    def dataframe(self, entity_type: str, source: str | None = None) -> pa.Table:
        """Load all entities as a PyArrow Table for bulk operations.

        Returns an empty table with ENTITY_SCHEMA if no data exists.
        """
        files = self._all_parquet_files(entity_type)
        if source:
            safe = source.replace("/", "_").replace("\\", "_")
            files = [f for f in files if f.stem == safe]

        tables = []
        for path in files:
            if path.stem.startswith("_"):
                continue
            try:
                tables.append(pq.read_table(path))
            except Exception:
                pass

        if not tables:
            return pa.table({col: [] for col in ENTITY_SCHEMA.names}, schema=ENTITY_SCHEMA)
        return pa.concat_tables(tables, promote_options="default")

    def update(self, entity_type: str, sha256: str, changes: dict) -> dict | None:
        """Update an entity in-place by sha256. Returns updated entity or None.

        Reads the entity, applies changes to the semantic dict, writes back.
        """
        entity = self.read(entity_type, sha256)
        if entity is None:
            return None

        # Apply changes to semantic
        sem = entity.get("semantic", {})
        for key, value in changes.items():
            if key == "embedding":
                entity["embedding"] = value
            elif key in ("provenance", "ontology_annotations"):
                entity[key] = value
            else:
                sem[key] = value
        entity["semantic"] = sem

        # Find which file contains this entity and update it
        for path in self._all_parquet_files(entity_type):
            try:
                table = pq.read_table(path)
                sha_col = table.column("sha256").to_pylist()
                if sha256 in sha_col:
                    idx = sha_col.index(sha256)
                    # Rebuild the row
                    source = table.column("source").to_pylist()[idx]
                    serialized = _serialize_entity(entity, source)
                    # Replace the row in the table
                    rows = []
                    for i in range(table.num_rows):
                        if i == idx:
                            rows.append(serialized)
                        else:
                            rows.append(
                                {
                                    col: table.column(col).to_pylist()[i]
                                    for col in table.column_names
                                }
                            )
                    new_table = pa.table(
                        {col: [r.get(col, "") for r in rows] for col in ENTITY_SCHEMA.names},
                        schema=ENTITY_SCHEMA,
                    )
                    pq.write_table(new_table, path, compression="snappy")
                    return entity
            except Exception:
                continue
        return None
