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

    Common options accepted by all adapters:
    - repo: str — upstream repository URL (e.g., GitHub)
    - committish: str — git commit SHA, tag, or branch
    These populate source_ref on every ClassifiedEntity.
    """

    @abstractmethod
    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract and classify all entities from a source."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter name for provenance tracking."""

    @property
    def supported_formats(self) -> list[str]:
        """File extensions this adapter handles (e.g., ['.json', '.yaml'])."""
        return []
