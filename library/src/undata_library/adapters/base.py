"""Base adapter interface and data types for schema ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef


@dataclass
class ClassifiedEntity:
    """Output of an adapter — a classified schema entity with provenance."""

    entity_type: EntityType
    semantic: dict[str, Any]
    provenance: dict[str, Any]
    confidence: float
    source_ref: SourceRef
    source_context: dict[str, Any] | None = None


class BaseAdapter(ABC):
    """Abstract interface for schema source adapters.

    Adapters convert source schemas to LinkML SchemaDefinition via to_linkml().
    The standard extractor then classifies entities from the SchemaDefinition.

    Common options accepted by all adapters:
    - repo: str — upstream repository URL (e.g., GitHub)
    - committish: str — git commit SHA, tag, or branch
    These populate source_ref on every ClassifiedEntity.
    """

    def to_linkml(self, source_path: Path, **options: Any) -> Any:
        """Convert source schema to a LinkML SchemaDefinition.

        All neuroscience source adapters (bids, nwb, dandi, openminds, aind,
        reproschema, nda, openneuro) MUST implement this. Generic adapters
        (json-schema, csv, code-repo) may return None and override extract().

        Returns None if not implemented or source unavailable.
        """
        return None

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract and classify all entities from a source.

        Default implementation calls to_linkml() then the standard extractor.
        Override only if the adapter needs custom post-processing.
        """
        from .extractor import extract_from_schema_definition

        schema_def = self.to_linkml(source_path, **options)
        if schema_def is None:
            return []
        return extract_from_schema_definition(schema_def, source_name=self.name)

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter name for provenance tracking."""

    @property
    def supported_formats(self) -> list[str]:
        """File extensions this adapter handles (e.g., ['.json', '.yaml'])."""
        return []
