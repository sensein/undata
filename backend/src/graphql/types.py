"""Strawberry GraphQL types for the undata registry.

Maps the flat-file registry entities (elements, schemas, values, valuesets)
and curation infrastructure (flags, contributions, users) to GraphQL types.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import strawberry


@strawberry.enum
class DataType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@strawberry.enum
class FlagType(Enum):
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_MATCH = "ambiguous_match"
    MULTIPLE_CANDIDATES = "multiple_candidates"
    UNKNOWN_TRANSFORM = "unknown_transform"
    NEEDS_REVIEW = "needs_review"
    SUSPICIOUS_SOURCE = "suspicious_source"
    PROVENANCE_BLOAT = "provenance_bloat"


@strawberry.enum
class FlagStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@strawberry.enum
class ContributionType(Enum):
    SUGGEST_ANNOTATION = "suggest_annotation"
    COMMENT = "comment"
    FLAG_ISSUE = "flag_issue"
    SUGGEST_EDIT = "suggest_edit"


@strawberry.enum
class ContributionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@strawberry.enum
class UserRole(Enum):
    CONTRIBUTOR = "contributor"
    CURATOR = "curator"
    ADMIN = "admin"


@strawberry.type
class OntologyAnnotation:
    term_uri: str
    term_label: str
    ontology: str
    mapping_relation: str
    match_level: str
    score: float
    model: str
    primary: bool


@strawberry.type
class ProvenanceEntry:
    source: str
    class_name: str  # "class" is reserved in Python
    name: str
    description: Optional[str] = None
    generated_at: Optional[str] = None
    attributed_to: Optional[str] = None
    activity: Optional[str] = None


@strawberry.type
class Element:
    sha256: Optional[str]
    data_type: Optional[str]
    unit: Optional[str]
    pattern: Optional[str]
    value_domain: Optional[str]
    description: Optional[str]
    min_value: Optional[float]
    max_value: Optional[float]
    type_ref: Optional[str]
    ontology_annotations: list[OntologyAnnotation]
    provenance: list[ProvenanceEntry]
    # File-level metadata
    file_name: str
    entity_type: str = "element"


@strawberry.type
class Schema:
    sha256: Optional[str]
    properties: list[str]
    subclass_of: Optional[str]
    mixins: list[str]
    is_mixin: bool
    description: Optional[str]
    ontology_annotations: list[OntologyAnnotation]
    provenance: list[ProvenanceEntry]
    file_name: str
    entity_type: str = "schema"


@strawberry.type
class Value:
    sha256: Optional[str]
    label: str
    value_type: Optional[str]
    description: Optional[str]
    ontology_id: Optional[str]
    ontology_annotations: list[OntologyAnnotation]
    provenance: list[ProvenanceEntry]
    file_name: str
    entity_type: str = "value"


@strawberry.type
class ValueSet:
    sha256: Optional[str]
    name: str
    members: list[str]
    description: Optional[str]
    ontology_annotations: list[OntologyAnnotation]
    provenance: list[ProvenanceEntry]
    file_name: str
    entity_type: str = "valueset"


@strawberry.type
class CurationFlag:
    id: str
    entity_type: str
    entity_ref: str
    flag_type: FlagType
    context: strawberry.scalars.JSON
    status: FlagStatus
    created_at: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None


@strawberry.type
class RunSummary:
    run_id: str
    source: str
    started_at: str
    completed_at: Optional[str]
    entity_counts: strawberry.scalars.JSON
    enrichment_rate: Optional[strawberry.scalars.JSON]
    curation_flags: Optional[strawberry.scalars.JSON]
    delta: Optional[strawberry.scalars.JSON]
    timing: Optional[strawberry.scalars.JSON]


@strawberry.type
class Contribution:
    id: str
    entity_type: str
    entity_ref: str
    contribution_type: ContributionType
    content: strawberry.scalars.JSON
    status: ContributionStatus
    contributor: str
    reviewed_by: Optional[str] = None
    created_at: str


# Connection types for cursor-based pagination
@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None


@strawberry.type
class ElementEdge:
    node: Element
    cursor: str


@strawberry.type
class ElementConnection:
    edges: list[ElementEdge]
    page_info: PageInfo
    total_count: int
