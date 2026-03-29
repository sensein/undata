"""Strawberry GraphQL types matching the 027 contract."""

from __future__ import annotations

import enum
from typing import Optional

import strawberry
from strawberry.scalars import JSON


# --- Enums ---


@strawberry.enum
class FlagType(enum.Enum):
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_MATCH = "ambiguous_match"
    MULTIPLE_CANDIDATES = "multiple_candidates"
    UNKNOWN_TRANSFORM = "unknown_transform"
    NEEDS_REVIEW = "needs_review"
    SUSPICIOUS_SOURCE = "suspicious_source"
    PROVENANCE_BLOAT = "provenance_bloat"


@strawberry.enum
class FlagStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@strawberry.enum
class ContributionType(enum.Enum):
    SUGGEST_ANNOTATION = "suggest_annotation"
    COMMENT = "comment"
    FLAG_ISSUE = "flag_issue"
    SUGGEST_EDIT = "suggest_edit"


@strawberry.enum
class ContributionStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@strawberry.enum
class CurationStatus(enum.Enum):
    UNFLAGGED = "unflagged"
    PENDING = "pending"
    CURATED = "curated"


@strawberry.enum
class DataType(enum.Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@strawberry.enum
class EntityType(enum.Enum):
    ELEMENT = "element"
    SCHEMA = "schema"
    VALUE = "value"
    VALUESET = "valueset"
    TRANSFORM = "transform"


# --- Nested Types ---


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
    class_name: str  # 'class' is reserved in Python
    name: str
    description: str


# --- Core Entity Types ---


@strawberry.type
class Element:
    sha256: str
    file_name: Optional[str] = None
    data_type: Optional[str] = None
    unit: Optional[str] = None
    unit_uri: Optional[str] = None
    pattern: Optional[str] = None
    value_domain: Optional[str] = None
    description: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    type_ref: Optional[str] = None
    semantic: JSON = strawberry.field(default_factory=dict)
    provenance: list[ProvenanceEntry] = strawberry.field(default_factory=list)
    ontology_annotations: list[OntologyAnnotation] = strawberry.field(default_factory=list)


@strawberry.type
class Schema:
    sha256: str
    file_name: Optional[str] = None
    subclass_of: Optional[str] = None
    is_mixin: Optional[bool] = None
    properties: list[str] = strawberry.field(default_factory=list)
    description: Optional[str] = None
    semantic: JSON = strawberry.field(default_factory=dict)
    provenance: list[ProvenanceEntry] = strawberry.field(default_factory=list)
    ontology_annotations: list[OntologyAnnotation] = strawberry.field(default_factory=list)


@strawberry.type
class Value:
    sha256: str
    file_name: Optional[str] = None
    label: Optional[str] = None
    value_type: Optional[str] = None
    ontology_id: Optional[str] = None
    description: Optional[str] = None
    semantic: JSON = strawberry.field(default_factory=dict)
    provenance: list[ProvenanceEntry] = strawberry.field(default_factory=list)
    ontology_annotations: list[OntologyAnnotation] = strawberry.field(default_factory=list)


@strawberry.type
class ValueSet:
    sha256: str
    file_name: Optional[str] = None
    name: Optional[str] = None
    members: list[str] = strawberry.field(default_factory=list)
    description: Optional[str] = None
    semantic: JSON = strawberry.field(default_factory=dict)
    provenance: list[ProvenanceEntry] = strawberry.field(default_factory=list)
    ontology_annotations: list[OntologyAnnotation] = strawberry.field(default_factory=list)


@strawberry.type
class FunctionSpec:
    function_type: Optional[str] = None
    input_type: Optional[str] = None
    output_type: Optional[str] = None
    expression: Optional[str] = None
    expression_type: Optional[str] = None


@strawberry.type
class Transform:
    sha256: str
    file_name: Optional[str] = None
    source_element: str = ""
    target_element: str = ""
    function_type: Optional[str] = None
    input_type: Optional[str] = None
    output_type: Optional[str] = None
    expression: Optional[str] = None
    expression_type: Optional[str] = None
    confidence: Optional[float] = None
    description: Optional[str] = None
    semantic: JSON = strawberry.field(default_factory=dict)
    provenance: list[ProvenanceEntry] = strawberry.field(default_factory=list)


@strawberry.type
class CurationFlag:
    id: strawberry.ID
    entity_type: str
    entity_ref: str
    flag_type: FlagType
    context: JSON
    llm_verification: Optional[JSON] = None
    status: FlagStatus
    created_at: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None


@strawberry.type
class Contribution:
    id: strawberry.ID
    entity_type: str
    entity_ref: str
    contribution_type: ContributionType
    content: JSON
    status: ContributionStatus
    contributor: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None
    created_at: str


@strawberry.type
class RunSummary:
    run_id: str
    source: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    entity_counts: JSON = strawberry.field(default_factory=dict)
    enrichment_rate: Optional[JSON] = None
    curation_flags: Optional[JSON] = None
    delta: Optional[JSON] = None
    timing: Optional[JSON] = None


@strawberry.type
class ImportResult:
    elements: int
    schemas: int
    values: int
    valuesets: int
    transforms: int
    flags: int
    runs: int


# --- Pagination (Relay-style) ---


@strawberry.type
class PageInfo:
    has_next_page: bool
    end_cursor: Optional[str] = None


@strawberry.type
class ElementEdge:
    cursor: str
    node: Element


@strawberry.type
class ElementConnection:
    edges: list[ElementEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class SchemaEdge:
    cursor: str
    node: Schema


@strawberry.type
class SchemaConnection:
    edges: list[SchemaEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class ValueEdge:
    cursor: str
    node: Value


@strawberry.type
class ValueConnection:
    edges: list[ValueEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class ValueSetEdge:
    cursor: str
    node: ValueSet


@strawberry.type
class ValueSetConnection:
    edges: list[ValueSetEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class TransformEdge:
    cursor: str
    node: Transform


@strawberry.type
class TransformConnection:
    edges: list[TransformEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class CurationFlagEdge:
    cursor: str
    node: CurationFlag


@strawberry.type
class CurationFlagConnection:
    edges: list[CurationFlagEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class ContributionEdge:
    cursor: str
    node: Contribution


@strawberry.type
class ContributionConnection:
    edges: list[ContributionEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class RunSummaryEdge:
    cursor: str
    node: RunSummary


@strawberry.type
class RunSummaryConnection:
    edges: list[RunSummaryEdge]
    page_info: PageInfo
    total_count: int


# --- Input Types ---


@strawberry.input
class ResolveFlagInput:
    flag_id: strawberry.ID
    action: FlagStatus
    resolved_by: str
    note: Optional[str] = None


@strawberry.input
class BatchResolveFlagInput:
    flag_ids: list[strawberry.ID]
    action: FlagStatus
    resolved_by: str
    note: Optional[str] = None


@strawberry.input
class SubmitContributionInput:
    entity_type: str
    entity_ref: str
    contribution_type: ContributionType
    content: JSON
    contributor: Optional[str] = None


@strawberry.input
class ReviewContributionInput:
    contribution_id: strawberry.ID
    action: ContributionStatus
    reviewed_by: str
    note: Optional[str] = None


@strawberry.input
class UpdateElementInput:
    reason: str  # Required — change attribution (FR-008)
    data_type: Optional[str] = None
    unit: Optional[str] = None
    unit_uri: Optional[str] = None
    description: Optional[str] = None
    pattern: Optional[str] = None
    value_domain: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    type_ref: Optional[str] = None
    ontology_annotations: Optional[JSON] = None


@strawberry.input
class UpdateSchemaInput:
    reason: str
    description: Optional[str] = None
    subclass_of: Optional[str] = None
    is_mixin: Optional[bool] = None
    properties: Optional[list[str]] = None
    ontology_annotations: Optional[JSON] = None


@strawberry.input
class UpdateValueInput:
    reason: str
    label: Optional[str] = None
    value_type: Optional[str] = None
    description: Optional[str] = None
    ontology_id: Optional[str] = None
    ontology_annotations: Optional[JSON] = None


@strawberry.input
class UpdateValueSetInput:
    reason: str
    name: Optional[str] = None
    description: Optional[str] = None
    members: Optional[list[str]] = None
    ontology_annotations: Optional[JSON] = None
