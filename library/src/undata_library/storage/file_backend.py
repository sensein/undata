"""File-based storage backend using YAML files in a directory tree.

Wraps the existing library behavior: entities stored as YAML files in
entity-type subdirectories (elements/, schemas/, values/, valuesets/),
curation flags in curation-flags/, run summaries in runs/.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


from ..models import CurationFlag, FlagStatus, FlagType, RunSummary
from ..utils import safe_load_yaml, write_yaml
from .protocol import VALID_ENTITY_TYPES


class FileEntityStore:
    """EntityStore implementation backed by YAML files."""

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def _type_dir(self, entity_type: str) -> Path:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity type: {entity_type!r}. Must be one of {VALID_ENTITY_TYPES}"
            )
        d = self._base / entity_type
        d.mkdir(parents=True, exist_ok=True)
        return d

    def read(self, entity_type: str, identifier: str) -> dict | None:
        d = self._type_dir(entity_type)
        path = d / f"{identifier}.yaml"
        if not path.exists():
            # Try with .yaml extension already in identifier
            if not identifier.endswith(".yaml"):
                return None
            path = d / identifier
            if not path.exists():
                return None
        return safe_load_yaml(path)

    def write(self, entity_type: str, data: dict, identifier: str | None = None) -> str:
        d = self._type_dir(entity_type)
        if identifier is None:
            identifier = str(uuid.uuid4())
        path = d / f"{identifier}.yaml"
        write_yaml(path, data)
        return identifier

    def list(self, entity_type: str, **filters: object) -> Iterator[dict]:
        d = self._type_dir(entity_type)
        if not d.exists():
            return

        source_filter = filters.get("source")
        has_annotations = filters.get("has_annotations")
        data_type_filter = filters.get("data_type")

        for f in sorted(d.glob("*.yaml")):
            data = safe_load_yaml(f)
            if data is None:
                continue

            # Inject _identifier for downstream use
            data["_identifier"] = f.stem

            # Apply filters
            if source_filter is not None:
                provenance = data.get("provenance", [])
                sources = {p.get("source", "") for p in provenance if isinstance(p, dict)}
                if source_filter not in sources:
                    continue

            if has_annotations is not None:
                annotations = data.get("semantic", {}).get("ontology_annotations", [])
                has_any = bool(annotations)
                if has_annotations != has_any:
                    continue

            if data_type_filter is not None:
                dt = data.get("semantic", {}).get("data_type")
                if dt != data_type_filter:
                    continue

            yield data

    def exists(self, entity_type: str, identifier: str) -> bool:
        d = self._type_dir(entity_type)
        return (d / f"{identifier}.yaml").exists()

    def delete(self, entity_type: str, identifier: str) -> bool:
        d = self._type_dir(entity_type)
        path = d / f"{identifier}.yaml"
        if path.exists():
            path.unlink()
            return True
        return False

    def merge_provenance(self, entity_type: str, identifier: str, provenance: list[dict]) -> dict:
        data = self.read(entity_type, identifier)
        if data is None:
            raise KeyError(f"Entity not found: {entity_type}/{identifier}")

        existing_prov = data.get("provenance", [])
        # Deduplicate by (source, name)
        existing_keys = {(p.get("source", ""), p.get("name", "")) for p in existing_prov}
        for p in provenance:
            key = (p.get("source", ""), p.get("name", ""))
            if key not in existing_keys:
                existing_prov.append(p)
                existing_keys.add(key)

        data["provenance"] = existing_prov
        # Remove internal metadata before writing
        clean = {k: v for k, v in data.items() if not k.startswith("_")}
        self.write(entity_type, clean, identifier)
        return data

    def count(self, entity_type: str, **filters: object) -> int:
        if not filters:
            d = self._type_dir(entity_type)
            return len(list(d.glob("*.yaml")))
        return sum(1 for _ in self.list(entity_type, **filters))

    def find_by_hash(self, entity_type: str, short_key: str) -> dict | None:
        d = self._type_dir(entity_type)
        matches = list(d.glob(f"*_{short_key}.yaml"))
        if not matches:
            # Also try exact match on identifier
            exact = d / f"{short_key}.yaml"
            if exact.exists():
                return safe_load_yaml(exact)
            # Try Parquet files
            from .parquet_store import ParquetStore

            pq_store = ParquetStore(self._base)
            return pq_store.read(entity_type, short_key)
        return safe_load_yaml(matches[0])

    def write_batch(
        self,
        entity_type: str,
        entities: list[dict],
        source: str | None = None,
        threshold: int = 1000,
    ) -> int:
        """Write a batch of entities.

        If count > threshold, uses Parquet format. Otherwise writes individual YAML files.
        """
        if not entities:
            return 0

        if len(entities) > threshold:
            from .parquet_store import ParquetStore

            pq_store = ParquetStore(self._base)
            return pq_store.write_batch(entity_type, entities, source=source or "unknown")

        # Small batch — write individual YAML files
        for entity in entities:
            identifier = entity.get("sha256") or entity.get("file_name", "")
            if identifier:
                self.write(entity_type, entity, identifier)
        return len(entities)

    def read_batch(self, entity_type: str, source: str | None = None) -> list[dict]:
        """Read all entities of a type, from both YAML files and Parquet."""
        results = list(self.list(entity_type, **({"source": source} if source else {})))

        # Also read from Parquet files
        from .parquet_store import ParquetStore

        pq_store = ParquetStore(self._base)
        seen = {r.get("sha256", r.get("_identifier", "")) for r in results}
        for entity in pq_store.list(entity_type, source=source):
            if entity.get("sha256") not in seen:
                results.append(entity)
                seen.add(entity.get("sha256", ""))
        return results


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
    """StorageBackend implementation using YAML files in a directory tree.

    Directory layout:
        base_dir/
        ├── elements/*.yaml
        ├── schemas/*.yaml
        ├── values/*.yaml
        ├── valuesets/*.yaml
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
