from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ExtractionMode = Literal["code", "file", "both"]


@dataclass
class NormalizedElement:
    name: str
    data_type: str  # "string"|"number"|"boolean"|"object"|"array"
    description: str
    required: bool
    multivalued: bool
    allowed_values: list[str] | None
    constraints: dict
    source_local_id: str
    source_name: str  # "BIDS"|"DANDI"|"openMINDS"|"NWB"
    extraction_path: str = "file"  # "code"|"file"|"both"
    raw_metadata: dict = field(default_factory=dict)


@dataclass
class IngestionResult:
    source_name: str
    elements_submitted: int
    elements_succeeded: int
    elements_failed: int
    failures: list[dict]
    duration_seconds: float


@dataclass
class SchemaClassPayload:
    """Represents a class/category extracted from a schema adapter.

    extraction_path: which extraction path produced this class
    - "code"   — Python library introspection (all adapters code-path)
    - "file"   — schema file parsing (JSON/YAML/JSON-LD/Turtle)
    - "both"   — present in both paths (after merge, deduplicated)

    schema_format: the specific format used (informational)
    - "json"   — JSON Schema (DANDI file-path, AIND)
    - "yaml"   — YAML GroupSpec (NWB) or BIDS YAML objects
    - "jsonld" — JSON-LD / .schema.omi.json (openMINDS)
    - "ttl"    — Turtle RDF (openMINDS Turtle path)
    - "code"   — Python library introspection
    """

    class_name: str
    description: str
    element_source_local_ids: list[str] = field(default_factory=list)
    parent_class_name: str | None = None
    extraction_path: str = "file"
    schema_format: str | None = None


@dataclass
class AdapterResult:
    """Pipeline-level wrapper combining adapter outputs with conflict metadata.

    NOT returned by extract_elements() or extract_classes() directly — those
    return list[NormalizedElement] and list[SchemaClassPayload] respectively.
    Constructed by pipeline callers that need a single envelope with conflict info.
    """

    elements: list[NormalizedElement]
    classes: list[SchemaClassPayload]
    mode_used: str
    conflicts: list[dict] = field(default_factory=list)


@dataclass
class AliasCandidate:
    element_a_id: str
    element_b_id: str
    similarity_score: float
    predicate: str  # "skos:exactMatch" | "skos:closeMatch"
    detection_method: str  # "exact_name" | "embedding" | "token_synonym"
