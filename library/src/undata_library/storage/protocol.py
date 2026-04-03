"""Storage backend protocol definitions.

Defines the StorageBackend protocol and its sub-protocols (EntityStore,
FlagStore, RunStore) that pipeline functions use to read/write entities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..models import CurationFlag, FlagStatus, FlagType, RunSummary


@runtime_checkable
class EntityStore(Protocol):
    """Protocol for reading/writing core entities (elements, schemas, values, valuesets)."""

    def read(self, entity_type: str, identifier: str) -> dict | None:
        """Load a single entity by identifier. Returns None if not found."""
        ...

    def write(self, entity_type: str, data: dict, identifier: str | None = None) -> str:
        """Write an entity. Returns the identifier used.

        If identifier is None, the backend generates one (e.g., UUID for staging,
        content-addressed for committed).
        """
        ...

    def list(self, entity_type: str, **filters: object) -> Iterator[dict]:
        """List entities with optional filtering.

        Supported filters:
        - source: str — filter by provenance source name
        - has_annotations: bool — filter by presence of ontology_annotations
        - data_type: str — filter by semantic.data_type (elements only)
        """
        ...

    def exists(self, entity_type: str, identifier: str) -> bool:
        """Check if an entity exists."""
        ...

    def delete(self, entity_type: str, identifier: str) -> bool:
        """Delete an entity. Returns True if deleted, False if not found."""
        ...

    def merge_provenance(self, entity_type: str, identifier: str, provenance: list[dict]) -> dict:
        """Append provenance entries to an existing entity.

        Deduplicates by (source, name) — does not add entries that already exist.
        Returns the updated entity dict.
        """
        ...

    def count(self, entity_type: str, **filters: object) -> int:
        """Count entities matching optional filters."""
        ...

    def find_by_hash(self, entity_type: str, short_key: str) -> dict | None:
        """Find an entity by content-addressed hash prefix (first 12 hex chars).

        Returns the entity dict if found, None otherwise.
        """
        ...

    def write_batch(self, entity_type: str, entities: list[dict], source: str | None = None) -> int:
        """Write a batch of entities. Returns count written.

        For large batches (>1000), implementations SHOULD use binary container
        format (Parquet) instead of individual files.
        """
        ...

    def read_batch(self, entity_type: str, source: str | None = None) -> list[dict]:
        """Read all entities of a type, optionally filtered by source.

        Returns list of entity dicts.
        """
        ...


@runtime_checkable
class FlagStore(Protocol):
    """Protocol for curation flag lifecycle management."""

    def write_flag(self, flag: CurationFlag) -> str:
        """Create a new curation flag. Returns the flag ID."""
        ...

    def read_flags(
        self,
        status: FlagStatus | str | None = None,
        flag_type: FlagType | str | None = None,
    ) -> list[CurationFlag]:
        """List curation flags with optional status/type filtering."""
        ...

    def resolve_flag(
        self,
        flag_id: str,
        action: FlagStatus | str,
        resolved_by: str,
        note: str | None = None,
    ) -> CurationFlag | None:
        """Resolve a curation flag. Returns updated flag or None if not found."""
        ...


@runtime_checkable
class RunStore(Protocol):
    """Protocol for pipeline run summary management."""

    def save_summary(self, summary: RunSummary) -> str:
        """Save a run summary. Returns the identifier."""
        ...

    def load_previous(self, source: str) -> RunSummary | None:
        """Load the most recent run summary for a given source."""
        ...

    def list_runs(self, source: str | None = None, limit: int | None = None) -> list[RunSummary]:
        """List run summaries with optional source filter and limit."""
        ...


@runtime_checkable
class StorageBackend(Protocol):
    """Composite protocol for all storage operations.

    A StorageBackend provides access to entity, flag, and run stores.
    Pipeline functions accept this as their storage parameter.
    """

    @property
    def entities(self) -> EntityStore:
        """Access the entity store."""
        ...

    @property
    def flags(self) -> FlagStore:
        """Access the curation flag store."""
        ...

    @property
    def runs(self) -> RunStore:
        """Access the run summary store."""
        ...


VALID_ENTITY_TYPES = frozenset({"elements", "schemas", "values", "valuesets"})
