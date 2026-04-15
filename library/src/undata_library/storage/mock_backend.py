"""In-memory mock storage backend for testing.

Provides a MockBackend that stores entities in Python dicts,
records all operations for assertion, and requires no file system.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Iterator

from ..models import CurationFlag, FlagStatus, FlagType, RunSummary
from .protocol import VALID_ENTITY_TYPES


class MockEntityStore:
    """EntityStore implementation using in-memory dicts."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, dict]] = {t: {} for t in VALID_ENTITY_TYPES}
        self.operations: list[tuple[str, str, str]] = []  # (method, entity_type, identifier)

    def read(self, entity_type: str, identifier: str) -> dict | None:
        self._validate_type(entity_type)
        self.operations.append(("read", entity_type, identifier))
        data = self._store[entity_type].get(identifier)
        return copy.deepcopy(data) if data else None

    def write(self, entity_type: str, data: dict, identifier: str | None = None) -> str:
        self._validate_type(entity_type)
        if identifier is None:
            identifier = str(uuid.uuid4())
        self._store[entity_type][identifier] = copy.deepcopy(data)
        self.operations.append(("write", entity_type, identifier))
        return identifier

    def list(self, entity_type: str, **filters: object) -> Iterator[dict]:
        self._validate_type(entity_type)
        self.operations.append(("list", entity_type, ""))

        source_filter = filters.get("source")
        has_annotations = filters.get("has_annotations")
        data_type_filter = filters.get("data_type")

        for identifier, data in sorted(self._store[entity_type].items()):
            item = copy.deepcopy(data)
            item["_identifier"] = identifier

            if source_filter is not None:
                provenance = item.get("provenance", [])
                sources = {p.get("source", "") for p in provenance if isinstance(p, dict)}
                if source_filter not in sources:
                    continue

            if has_annotations is not None:
                annotations = item.get("semantic", {}).get("ontology_annotations", [])
                has_any = bool(annotations)
                if has_annotations != has_any:
                    continue

            if data_type_filter is not None:
                dt = item.get("semantic", {}).get("data_type")
                if dt != data_type_filter:
                    continue

            yield item

    def exists(self, entity_type: str, identifier: str) -> bool:
        self._validate_type(entity_type)
        self.operations.append(("exists", entity_type, identifier))
        return identifier in self._store[entity_type]

    def delete(self, entity_type: str, identifier: str) -> bool:
        self._validate_type(entity_type)
        self.operations.append(("delete", entity_type, identifier))
        if identifier in self._store[entity_type]:
            del self._store[entity_type][identifier]
            return True
        return False

    def merge_provenance(self, entity_type: str, identifier: str, provenance: list[dict]) -> dict:
        self._validate_type(entity_type)
        self.operations.append(("merge_provenance", entity_type, identifier))
        data = self._store[entity_type].get(identifier)
        if data is None:
            raise KeyError(f"Entity not found: {entity_type}/{identifier}")

        existing_prov = data.get("provenance", [])
        existing_keys = {(p.get("source", ""), p.get("name", "")) for p in existing_prov}
        for p in provenance:
            key = (p.get("source", ""), p.get("name", ""))
            if key not in existing_keys:
                existing_prov.append(copy.deepcopy(p))
                existing_keys.add(key)

        data["provenance"] = existing_prov
        return copy.deepcopy(data)

    def count(self, entity_type: str, **filters: object) -> int:
        self._validate_type(entity_type)
        if not filters:
            return len(self._store[entity_type])
        return sum(1 for _ in self.list(entity_type, **filters))

    def find_by_hash(self, entity_type: str, short_key: str) -> dict | None:
        self._validate_type(entity_type)
        self.operations.append(("find_by_hash", entity_type, short_key))
        # Search by identifier suffix (name_shortkey pattern)
        for identifier, data in self._store[entity_type].items():
            if identifier.endswith(f"_{short_key}") or identifier == short_key:
                return copy.deepcopy(data)
        return None

    def _validate_type(self, entity_type: str) -> None:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity type: {entity_type!r}. Must be one of {VALID_ENTITY_TYPES}"
            )

    @property
    def write_count(self) -> int:
        return sum(1 for op in self.operations if op[0] == "write")


class MockFlagStore:
    """FlagStore implementation using in-memory dicts."""

    def __init__(self) -> None:
        self._flags: dict[str, dict] = {}
        self.operations: list[tuple[str, str]] = []

    def write_flag(self, flag: CurationFlag) -> str:
        flag_id = str(flag.id) if hasattr(flag, "id") and flag.id else str(uuid.uuid4())
        self._flags[flag_id] = {
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
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.operations.append(("write_flag", flag_id))
        return flag_id

    def read_flags(
        self,
        status: FlagStatus | str | None = None,
        flag_type: FlagType | str | None = None,
    ) -> list[CurationFlag]:
        status_str = status.value if isinstance(status, FlagStatus) else status
        ftype_str = flag_type.value if isinstance(flag_type, FlagType) else flag_type

        result = []
        for data in self._flags.values():
            if status_str is not None and data.get("status") != status_str:
                continue
            if ftype_str is not None and data.get("flag_type") != ftype_str:
                continue
            result.append(
                CurationFlag(
                    id=data["id"],
                    entity_type=data["entity_type"],
                    entity_ref=data["entity_ref"],
                    flag_type=FlagType(data["flag_type"]),
                    context=data.get("context", {}),
                    status=FlagStatus(data["status"]),
                    created_at=data.get("created_at", ""),
                    resolved_by=data.get("resolved_by"),
                    resolution_note=data.get("resolution_note"),
                )
            )
        self.operations.append(("read_flags", f"status={status_str},type={ftype_str}"))
        return result

    def resolve_flag(
        self,
        flag_id: str,
        action: FlagStatus | str,
        resolved_by: str,
        note: str | None = None,
    ) -> CurationFlag | None:
        if flag_id not in self._flags:
            return None

        action_str = action.value if isinstance(action, FlagStatus) else action
        data = self._flags[flag_id]
        data["status"] = action_str
        data["resolved_by"] = resolved_by
        data["resolved_at"] = datetime.now(timezone.utc).isoformat()
        if note:
            data["resolution_note"] = note

        self.operations.append(("resolve_flag", flag_id))
        return CurationFlag(
            id=data["id"],
            entity_type=data["entity_type"],
            entity_ref=data["entity_ref"],
            flag_type=FlagType(data["flag_type"]),
            context=data.get("context", {}),
            status=FlagStatus(action_str),
            created_at=data.get("created_at", ""),
            resolved_by=resolved_by,
            resolution_note=note,
        )


class MockRunStore:
    """RunStore implementation using in-memory dicts."""

    def __init__(self) -> None:
        self._runs: list[dict] = []
        self.operations: list[tuple[str, str]] = []

    def save_summary(self, summary: RunSummary) -> str:
        rid = summary.run_id or str(uuid.uuid4())
        self._runs.append(
            {
                "run_id": rid,
                "source": summary.source,
                "started_at": summary.started_at,
                "entity_counts": summary.entity_counts,
            }
        )
        self.operations.append(("save_summary", rid))
        return rid

    def _to_summary(self, r: dict) -> RunSummary:
        return RunSummary(
            run_id=r["run_id"],
            source=r["source"],
            started_at=r.get("started_at", ""),
            entity_counts=r["entity_counts"],
        )

    def load_previous(self, source: str) -> RunSummary | None:
        self.operations.append(("load_previous", source))
        for run in reversed(self._runs):
            if run["source"] == source:
                return self._to_summary(run)
        return None

    def list_runs(self, source: str | None = None, limit: int | None = None) -> list[RunSummary]:
        self.operations.append(("list_runs", f"source={source},limit={limit}"))
        filtered = (
            self._runs if source is None else [r for r in self._runs if r["source"] == source]
        )
        if limit is not None:
            filtered = filtered[-limit:]
        return [self._to_summary(r) for r in filtered]


class MockBackend:
    """StorageBackend implementation using in-memory storage.

    Useful for testing pipeline functions without file system access.
    Records all operations for assertion in tests.
    """

    def __init__(self) -> None:
        self._entities = MockEntityStore()
        self._flags = MockFlagStore()
        self._runs = MockRunStore()

    @property
    def entities(self) -> MockEntityStore:
        return self._entities

    @property
    def flags(self) -> MockFlagStore:
        return self._flags

    @property
    def runs(self) -> MockRunStore:
        return self._runs

    @property
    def write_count(self) -> int:
        """Total writes across all stores."""
        return self._entities.write_count
