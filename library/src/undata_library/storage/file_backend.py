"""File-based storage backend — entities in Parquet, flags/runs in YAML.

FileEntityStore is a thin wrapper around ParquetStore for all entity
operations. FileFlagStore and FileRunStore still use YAML for flags and
run summaries respectively.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


from ..models import CurationFlag, FlagStatus, FlagType, RunSummary
from ..utils import safe_load_yaml, write_yaml
from .parquet_store import ParquetStore
from .protocol import VALID_ENTITY_TYPES

logger = logging.getLogger(__name__)


class FileEntityStore:
    """EntityStore implementation backed by ParquetStore.

    All entity read/write operations delegate to ParquetStore.
    This class exists to satisfy the EntityStore protocol and provide
    a consistent interface with FileBackend.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._pq = ParquetStore(base_dir)

    def _validate_type(self, entity_type: str) -> None:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity type: {entity_type!r}. Must be one of {VALID_ENTITY_TYPES}"
            )

    def read(self, entity_type: str, identifier: str) -> dict | None:
        self._validate_type(entity_type)
        return self._pq.read(entity_type, identifier)

    def write(self, entity_type: str, data: dict, identifier: str | None = None) -> str:
        self._validate_type(entity_type)
        if identifier is None:
            identifier = data.get("sha256") or str(uuid.uuid4())
        # Ensure sha256 is set on the entity
        if not data.get("sha256"):
            data["sha256"] = identifier
        # Determine source from provenance
        prov = data.get("provenance", [])
        source = "unknown"
        if prov and isinstance(prov[0], dict):
            source = prov[0].get("source", "unknown")
        self._pq.write_batch(entity_type, [data], source=source)
        return identifier

    def list(self, entity_type: str, **filters: object) -> Iterator[dict]:
        self._validate_type(entity_type)
        source_filter = filters.get("source")
        has_annotations = filters.get("has_annotations")
        data_type_filter = filters.get("data_type")

        for entity in self._pq.list(
            entity_type,
            source=source_filter if source_filter else None,
        ):
            # Apply additional filters
            if has_annotations is not None:
                anns = entity.get("ontology_annotations", [])
                if has_annotations != bool(anns):
                    continue
            if data_type_filter is not None:
                if entity.get("data_type") != data_type_filter:
                    continue

            entity["_identifier"] = entity.get("sha256", "") or entity.get("file_name", "")
            yield entity

    def exists(self, entity_type: str, identifier: str) -> bool:
        self._validate_type(entity_type)
        return self._pq.exists(entity_type, identifier)

    def delete(self, entity_type: str, identifier: str) -> bool:
        logger.warning(
            "delete() is not supported for Parquet-backed store; ignoring delete for %s/%s",
            entity_type,
            identifier,
        )
        return False

    def merge_provenance(self, entity_type: str, identifier: str, provenance: list[dict]) -> dict:
        self._validate_type(entity_type)
        entity = self._pq.read(entity_type, identifier)
        if entity is None:
            raise KeyError(f"Entity not found: {entity_type}/{identifier}")

        existing_prov = entity.get("provenance", [])
        existing_keys = {(p.get("source", ""), p.get("name", "")) for p in existing_prov}
        for p in provenance:
            key = (p.get("source", ""), p.get("name", ""))
            if key not in existing_keys:
                existing_prov.append(p)
                existing_keys.add(key)

        return self._pq.update(entity_type, identifier, {"provenance": existing_prov}) or entity

    def count(self, entity_type: str, **filters: object) -> int:
        self._validate_type(entity_type)
        if not filters:
            return self._pq.count(entity_type)
        return sum(1 for _ in self.list(entity_type, **filters))

    def find_by_hash(self, entity_type: str, short_key: str) -> dict | None:
        self._validate_type(entity_type)
        return self._pq.read(entity_type, short_key)

    def write_batch(
        self,
        entity_type: str,
        entities: list[dict],
        source: str | None = None,
    ) -> int:
        """Write a batch of entities to Parquet."""
        if not entities:
            return 0
        self._validate_type(entity_type)
        return self._pq.write_batch(entity_type, entities, source=source or "unknown")

    def read_batch(self, entity_type: str, source: str | None = None) -> list[dict]:
        """Read all entities of a type from Parquet."""
        self._validate_type(entity_type)
        return list(self._pq.list(entity_type, source=source))


class FileFlagStore:
    """FlagStore implementation backed by YAML files in curation-flags/."""

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir / "curation-flags"
        self._dir.mkdir(parents=True, exist_ok=True)

    def write_flag(self, flag: CurationFlag) -> str:
        flag_id = str(flag.id) if hasattr(flag, "id") and flag.id else str(uuid.uuid4())
        data = {
            "id": flag_id,
            "entity_type": flag.entity_type,
            "entity_ref": flag.entity_ref,
            "flag_type": flag.flag_type.value
            if isinstance(flag.flag_type, FlagType)
            else str(flag.flag_type),
            "context": flag.context if isinstance(flag.context, dict) else {},
            "status": flag.status.value
            if isinstance(flag.status, FlagStatus)
            else str(flag.status),
            "created_at": str(flag.created_at)
            if hasattr(flag, "created_at") and flag.created_at
            else datetime.now(timezone.utc).isoformat(),
        }
        if hasattr(flag, "llm_verification") and flag.llm_verification:
            data["llm_verification"] = flag.llm_verification
        if hasattr(flag, "resolved_at") and flag.resolved_at:
            data["resolved_at"] = (
                flag.resolved_at.isoformat()
                if hasattr(flag.resolved_at, "isoformat")
                else str(flag.resolved_at)
            )
        if hasattr(flag, "resolved_by") and flag.resolved_by:
            data["resolved_by"] = flag.resolved_by
        if hasattr(flag, "resolution_note") and flag.resolution_note:
            data["resolution_note"] = flag.resolution_note

        path = self._dir / f"{flag_id}.yaml"
        write_yaml(path, data)
        return flag_id

    def read_flags(
        self,
        status: FlagStatus | str | None = None,
        flag_type: FlagType | str | None = None,
    ) -> list[CurationFlag]:
        flags = []
        if not self._dir.exists():
            return flags

        status_str = status.value if isinstance(status, FlagStatus) else status
        ftype_str = flag_type.value if isinstance(flag_type, FlagType) else flag_type

        for f in sorted(self._dir.glob("*.yaml")):
            data = safe_load_yaml(f)
            if data is None:
                continue
            if status_str is not None and data.get("status") != status_str:
                continue
            if ftype_str is not None and data.get("flag_type") != ftype_str:
                continue
            flags.append(self._dict_to_flag(data))
        return flags

    def resolve_flag(
        self,
        flag_id: str,
        action: FlagStatus | str,
        resolved_by: str,
        note: str | None = None,
    ) -> CurationFlag | None:
        path = self._dir / f"{flag_id}.yaml"
        if not path.exists():
            return None

        data = safe_load_yaml(path)
        if data is None:
            return None

        action_str = action.value if isinstance(action, FlagStatus) else action
        data["status"] = action_str
        data["resolved_by"] = resolved_by
        data["resolved_at"] = datetime.now(timezone.utc).isoformat()
        if note:
            data["resolution_note"] = note

        write_yaml(path, data)
        return self._dict_to_flag(data)

    @staticmethod
    def _dict_to_flag(data: dict) -> CurationFlag:
        return CurationFlag(
            id=data.get("id", ""),
            entity_type=data.get("entity_type", ""),
            entity_ref=data.get("entity_ref", ""),
            flag_type=FlagType(data["flag_type"])
            if data.get("flag_type")
            else FlagType.NEEDS_REVIEW,
            context=data.get("context", {}),
            status=FlagStatus(data["status"]) if data.get("status") else FlagStatus.PENDING,
            created_at=data.get("created_at", ""),
            resolved_at=data.get("resolved_at"),
            resolved_by=data.get("resolved_by"),
            resolution_note=data.get("resolution_note"),
        )


class FileRunStore:
    """RunStore implementation backed by YAML files in runs/."""

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir / "runs"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_summary(self, summary: RunSummary) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%Sp%f")
        source = summary.source or "unknown"
        filename = f"{ts}-{source}"
        data = {
            "run_id": summary.run_id,
            "source": summary.source,
            "entity_counts": summary.entity_counts,
        }
        if hasattr(summary, "started_at") and summary.started_at:
            data["started_at"] = summary.started_at
        if hasattr(summary, "completed_at") and summary.completed_at:
            data["completed_at"] = summary.completed_at
        if hasattr(summary, "enrichment_rate") and summary.enrichment_rate:
            data["enrichment_rate"] = summary.enrichment_rate
        if hasattr(summary, "curation_flags") and summary.curation_flags:
            data["curation_flags"] = summary.curation_flags
        if hasattr(summary, "delta") and summary.delta:
            data["delta"] = summary.delta
        if hasattr(summary, "timing") and summary.timing:
            data["timing"] = summary.timing

        path = self._dir / f"{filename}.yaml"
        write_yaml(path, data)
        return filename

    def load_previous(self, source: str) -> RunSummary | None:
        if not self._dir.exists():
            return None
        candidates = sorted(self._dir.glob(f"*-{source}.yaml"), reverse=True)
        if not candidates:
            return None
        data = safe_load_yaml(candidates[0])
        if data is None:
            return None
        return self._dict_to_summary(data)

    def list_runs(self, source: str | None = None, limit: int | None = None) -> list[RunSummary]:
        if not self._dir.exists():
            return []

        pattern = f"*-{source}.yaml" if source else "*.yaml"
        files = sorted(self._dir.glob(pattern), reverse=True)
        if limit is not None:
            files = files[:limit]

        result = []
        for f in files:
            data = safe_load_yaml(f)
            if data is not None:
                result.append(self._dict_to_summary(data))
        return result

    @staticmethod
    def _dict_to_summary(data: dict) -> RunSummary:
        return RunSummary(
            run_id=data.get("run_id", ""),
            source=data.get("source", ""),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
            entity_counts=data.get("entity_counts", {}),
            enrichment_rate=data.get("enrichment_rate"),
            curation_flags=data.get("curation_flags"),
            delta=data.get("delta"),
            timing=data.get("timing"),
        )


class FileBackend:
    """StorageBackend implementation — entities in Parquet, flags/runs in YAML.

    Directory layout:
        base_dir/
        ├── elements/*.parquet
        ├── schemas/*.parquet
        ├── values/*.parquet
        ├── valuesets/*.parquet
        ├── curation-flags/*.yaml
        └── runs/*.yaml
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._entities = FileEntityStore(self._base)
        self._flags = FileFlagStore(self._base)
        self._runs = FileRunStore(self._base)

    @property
    def entities(self) -> FileEntityStore:
        return self._entities

    @property
    def flags(self) -> FileFlagStore:
        return self._flags

    @property
    def runs(self) -> FileRunStore:
        return self._runs

    @property
    def base_dir(self) -> Path:
        """Access the underlying directory path (FileBackend-specific)."""
        return self._base
