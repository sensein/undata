"""Pydantic v2 request/response models for the Schema Backend API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Shared / generic
# ---------------------------------------------------------------------------


class PaginatedList(BaseModel, Generic[T]):
    total: int
    limit: int
    offset: int
    items: list[T]


class ErrorEnvelope(BaseModel):
    error: str
    message: str
    details: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Semantic graph models
# ---------------------------------------------------------------------------


class SemanticGraphEntity(BaseModel):
    label: str
    type: str
    role: str
    external_uri: str | None = None


class SemanticGraphProperty(BaseModel):
    label: str
    type: str
    external_uri: str | None = None


class SemanticGraphUnit(BaseModel):
    label: str
    symbol: str | None = None
    external_uri: str | None = None
    # Server-populated fields — clients may omit; server always overwrites on create/update
    cmixf_valid: bool | None = None
    qudt_unresolvable: bool = False


class SemanticGraphRelation(BaseModel):
    subject: str
    predicate: str
    object: str


class SemanticGraph(BaseModel):
    entities: list[SemanticGraphEntity] = Field(default_factory=list)
    property: SemanticGraphProperty | None = None
    unit: SemanticGraphUnit | None = None
    relations: list[SemanticGraphRelation] = Field(default_factory=list)
    domain: str | None = None
    range_type: str | None = None
    context: str | None = None


class SemanticGraphOverlap(BaseModel):
    """Result of comparing semantic graphs between two elements.

    domain_match is None when domain is absent from both elements' graphs
    (not applicable), False when one has domain and the other does not,
    True when both have matching domains.
    """

    property_match: bool
    unit_match: bool
    entity_labels_match: bool
    domain_match: bool | None


# ---------------------------------------------------------------------------
# User / auth models
# ---------------------------------------------------------------------------


class UserProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    display_name: str | None
    is_active: bool


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    display_name: str | None
    is_active: bool
    roles: list[str] = Field(default_factory=list)
    source_memberships: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    last_login_at: datetime | None


class RoleAssignRequest(BaseModel):
    roles: list[str]


class SourceMembershipRequest(BaseModel):
    role: str


class SourceMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    source_id: UUID
    role: str
    granted_at: datetime


# ---------------------------------------------------------------------------
# API key models
# ---------------------------------------------------------------------------


class APIKeySummary(BaseModel):
    """API key listing — token field intentionally absent."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str | None
    issued_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class APIKeyCreateResponse(BaseModel):
    """Returned once on creation — token not shown again."""

    id: UUID
    label: str | None
    token: str  # plaintext, shown once
    issued_at: datetime


class TokenIssueRequest(BaseModel):
    label: str | None = None


# ---------------------------------------------------------------------------
# Schema source models
# ---------------------------------------------------------------------------


class SchemaSourceCreate(BaseModel):
    name: str
    format: str
    url: str | None = None
    version_tag: str | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None


class SchemaSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str
    format: str
    url: str | None
    version_tag: str | None
    content_hash: str | None
    ingested_at: datetime | None
    is_active: bool
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    version_num: int | None = None


# ---------------------------------------------------------------------------
# Data element models
# ---------------------------------------------------------------------------


class DataElementCreate(BaseModel):
    """
    Create a new data element.

    Notes:
    - No `created_by` field — identity inferred from auth token.
    - No `unit` field — extracted from `semantic_graph.unit.label` by service.
    """

    name: str
    data_type: str
    description: str | None = None
    required: bool = False
    multivalued: bool = False
    source_id: UUID
    source_local_id: str | None = None
    allowed_values: list[Any] | None = None
    constraints: dict[str, Any] | None = None
    semantic_graph: SemanticGraph | None = None
    child_element_ids: list[dict[str, Any]] | None = None  # [{element_id, field_name, position}]
    element_kind: str | None = None  # derived at service layer; optional on create
    node_kind: str | None = None  # defaults to 'field' at service layer


class DataElementUpdate(BaseModel):
    """
    Update a data element. version_num required for optimistic concurrency.
    No `updated_by` — inferred from auth token.
    """

    name: str | None = None
    data_type: str | None = None
    description: str | None = None
    required: bool | None = None
    multivalued: bool | None = None
    allowed_values: list[Any] | None = None
    constraints: dict[str, Any] | None = None
    semantic_graph: SemanticGraph | None = None
    version_num: int  # required for optimistic concurrency check


class DataElementChildRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uri: str
    field_name: str | None
    position: int


class DataElementSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uri: str
    name: str
    data_type: str
    description: str | None
    required: bool
    multivalued: bool
    source: SchemaSourceResponse | None = None
    unit: str | None
    superseded_by: str | None  # URI of superseding element
    alias_count: int = 0
    mapping_count: int = 0
    version_num: int


class DataElementVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    element_id: UUID
    version_num: int
    name: str
    data_type: str
    description: str | None
    required: bool
    multivalued: bool
    allowed_values: list[Any] | None
    constraints: dict[str, Any] | None
    semantic_graph: SemanticGraph | None
    unit: str | None
    created_at: datetime
    created_by_display_name: str | None


class DataElementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uri: str
    name: str
    data_type: str
    description: str | None
    required: bool
    multivalued: bool
    allowed_values: list[Any] | None
    constraints: dict[str, Any] | None
    semantic_graph: SemanticGraph | None
    unit: str | None
    superseded_by: str | None  # URI of superseding element
    supersedes: str | None  # URI of superseded element
    source: SchemaSourceResponse | None = None
    source_local_id: str | None
    children: list[DataElementChildRef] = Field(default_factory=list)
    alias_groups: list[dict[str, Any]] = Field(default_factory=list)
    mappings_as_input: list[dict[str, Any]] = Field(default_factory=list)
    mappings_as_output: list[dict[str, Any]] = Field(default_factory=list)
    version_num: int
    created_at: datetime
    deleted_at: datetime | None
    element_kind: str = "scalar"
    node_kind: str = "field"


class SupersedeElementRequest(BaseModel):
    supersede_reason: str  # REQUIRED — must document why element is superseded
    new_element_data: DataElementCreate  # full payload for the replacement element


class BulkElementItem(BaseModel):
    index: int
    id: UUID
    uri: str


class BulkErrorItem(BaseModel):
    index: int
    error: str
    message: str


class BulkCreateRequest(BaseModel):
    elements: list[DataElementCreate]


class BulkCreateResponse(BaseModel):
    succeeded: list[BulkElementItem]
    failed: list[BulkErrorItem]


# ---------------------------------------------------------------------------
# Alias / similarity models
# ---------------------------------------------------------------------------


class AliasDetectRequest(BaseModel):
    source_id: UUID | None = None
    threshold: float | None = None
    cross_source_only: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AliasCandidatePair(BaseModel):
    element_a: DataElementSummary
    element_b: DataElementSummary
    similarity_score: float
    suggested_predicate: str
    semantic_graph_overlap: SemanticGraphOverlap | None = None


class AliasGroupCreate(BaseModel):
    name: str | None = None
    element_ids: list[UUID]
    sssom_predicate: str = "skos:exactMatch"
    confidence: float | None = None
    detection_method: str | None = None


class AliasGroupUpdate(BaseModel):
    name: str | None = None
    add_element_ids: list[UUID] | None = None
    remove_element_ids: list[UUID] | None = None
    sssom_predicate: str | None = None
    confidence: float | None = None


class AliasGroupSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str | None
    sssom_predicate: str
    confidence: float | None
    detection_method: str | None
    member_count: int
    created_at: datetime


class AliasGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str | None
    sssom_predicate: str
    confidence: float | None
    detection_method: str | None
    members: list[DataElementSummary] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Mapping function models
# ---------------------------------------------------------------------------


class MappingFunctionCreate(BaseModel):
    function_type: str
    output_element_id: UUID
    description: str | None = None
    expression: str | None = None
    expression_type: str | None = None
    parameter_schema: dict[str, Any] | None = None
    sssom_predicate: str | None = None
    input_element_ids: list[dict[str, Any]] | None = None  # [{element_id, position}]


class MappingFunctionUpdate(BaseModel):
    description: str | None = None
    expression: str | None = None
    expression_type: str | None = None
    parameter_schema: dict[str, Any] | None = None
    sssom_predicate: str | None = None
    version_num: int  # required for optimistic concurrency


class MappingFunctionVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mapping_id: UUID
    version_num: int
    description: str | None
    expression: str | None
    expression_type: str | None
    parameter_schema: dict[str, Any] | None
    inverse_mapping_id: UUID | None
    sssom_predicate: str | None
    created_at: datetime
    created_by_display_name: str | None


class MappingFunctionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uri: str
    function_type: str
    output_element_id: UUID
    status: str
    version_num: int
    created_at: datetime


class MappingFunctionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uri: str
    function_type: str
    output_element_id: UUID
    status: str
    version_num: int
    created_at: datetime
    deleted_at: datetime | None
    current_version: MappingFunctionVersionResponse | None = None
    inputs: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Dynamic schema models
# ---------------------------------------------------------------------------


class DynamicSchemaElementItem(BaseModel):
    element_id: UUID
    position: int = 0
    field_alias: str | None = None


class DynamicSchemaCreate(BaseModel):
    name: str
    description: str | None = None
    elements: list[DynamicSchemaElementItem] = Field(default_factory=list)


class DynamicSchemaUpdate(BaseModel):
    add: list[DynamicSchemaElementItem] | None = None
    remove: list[UUID] | None = None  # element_ids to remove
    name: str | None = None
    description: str | None = None
    version_num: int  # required for optimistic concurrency


class DynamicSchemaElementRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    element_id: UUID
    element_uri: str
    element_name: str
    position: int
    field_alias: str | None
    element_unit: str | None
    element_superseded_by: str | None  # URI of superseding element if applicable


class DynamicSchemaSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uri: str
    name: str
    element_count: int
    version_num: int
    created_at: datetime


class DynamicSchemaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uri: str
    name: str
    description: str | None
    elements: list[DynamicSchemaElementRef] = Field(default_factory=list)
    version_num: int
    superseded_by: str | None  # URI of superseding schema
    supersedes: str | None  # URI of schema this supersedes
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
    parent_id: UUID | None = None
    is_mixin: bool = False
    is_system: bool = False


class SupersedeSchemaRequest(BaseModel):
    supersede_reason: str  # REQUIRED — must document why schema is superseded
    new_schema_data: DynamicSchemaCreate  # full payload for the replacement schema


# ---------------------------------------------------------------------------
# Audit log models
# ---------------------------------------------------------------------------


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    record_type: str
    record_id: UUID
    operation: str
    actor_id: UUID
    actor_display_name: str | None
    timestamp: datetime
    version_num: int | None
    diff: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Schema enrichment models (005-schema-enrichment)
# ---------------------------------------------------------------------------

# --- ValidationRule models ---

class ValidationRuleCreate(BaseModel):
    rule_type: str
    rule_value: dict[str, Any]
    severity: str = "error"
    description: str | None = None


class ValidationRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    element_id: UUID
    rule_type: str
    rule_value: dict[str, Any]
    severity: str
    description: str | None
    created_at: datetime
    created_by: UUID


class ValidationRuleUpdate(BaseModel):
    rule_value: dict[str, Any]
    severity: str | None = None
    description: str | None = None
    reason: str | None = None


class ValidationRuleChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rule_id: UUID
    element_id: UUID
    operation: str
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    breaking: bool
    actor_id: UUID
    timestamp: datetime
    reason: str | None


class ValidationRulesResponse(BaseModel):
    element_id: UUID
    rules: list[ValidationRuleRead]


class ValidationRuleUpdateResponse(BaseModel):
    rule: ValidationRuleRead
    change: ValidationRuleChangeRead


class ValidationRuleDeleteResponse(BaseModel):
    deleted: bool
    breaking: bool
    change: ValidationRuleChangeRead


# --- SchemaClass models ---

class SchemaClassElementRef(BaseModel):
    element_id: UUID
    name: str
    data_type: str
    element_kind: str
    required: bool
    allowed_values: list[Any] | None = None
    position: int


class SchemaClassRead(BaseModel):
    id: UUID
    class_name: str
    description: str | None
    parent_class_id: UUID | None
    elements: list[SchemaClassElementRef] = Field(default_factory=list)


class SchemaClassesResponse(BaseModel):
    schema_id: UUID | None = None
    classes: list[SchemaClassRead]


class SchemaClassCreate(BaseModel):
    class_name: str
    description: str | None = None
    parent_class_id: UUID | None = None


class SchemaClassElementLink(BaseModel):
    element_id: UUID
    position: int


class SchemaClassElementLinkResponse(BaseModel):
    class_id: UUID
    element_id: UUID
    position: int


# --- Inheritance / MRO models ---

class ResolvedElementRef(BaseModel):
    element_id: UUID
    name: str
    data_type: str
    element_kind: str
    required: bool
    source_schema: str
    source_schema_id: UUID
    override: bool = False


class ResolvedSchemaResponse(BaseModel):
    schema_id: UUID
    name: str
    mro_order: list[str]  # C3 linearized schema names (avoids shadowing BaseModel.__mro__)
    elements: list[ResolvedElementRef]


class InheritanceTreeNode(BaseModel):
    id: UUID
    name: str
    is_mixin: bool


class InheritanceTreeEdge(BaseModel):
    child_id: UUID
    parent_id: UUID
    type: str  # "inherits" | "mixin"
    position: int | None = None


class InheritanceTreeResponse(BaseModel):
    schema_id: UUID
    nodes: list[InheritanceTreeNode]
    edges: list[InheritanceTreeEdge]


class SetParentRequest(BaseModel):
    parent_id: UUID | None


class AddMixinRequest(BaseModel):
    mixin_id: UUID
    position: int = 0


class SchemaMixinRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schema_id: UUID
    mixin_id: UUID
    position: int


# --- Schema Changelog / Provenance models ---

class SchemaChangeLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schema_id: UUID
    version_num: int
    operation: str
    actor_id: UUID
    actor_name: str | None = None
    timestamp: datetime
    activity_type: str
    diff: dict[str, Any] | None
    breaking: bool
    semantic_boundary_crossed: bool
    reason: str | None


class SchemaChangeLogResponse(BaseModel):
    schema_id: UUID
    total: int
    page: int
    size: int
    entries: list[SchemaChangeLogEntry]


class ProvenanceMixinAttachResponse(BaseModel):
    attached: bool
    mixin_id: UUID


# --- Element provenance (assembled from DataElementVersion history) ---
# The full PROV-DM JSON-LD is returned as a plain dict / Any from the endpoint.


# ---------------------------------------------------------------------------
# MigrationPathway
# ---------------------------------------------------------------------------


class PathwayStep(BaseModel):
    position: int
    mapping_id: UUID


class MigrationPathwayCreate(BaseModel):
    name: str
    source_schema_id: UUID
    target_schema_id: UUID
    direction: str = "forward"
    steps: list[PathwayStep] = Field(default_factory=list)


class MigrationPathwayUpdate(BaseModel):
    name: str | None = None
    steps: list[PathwayStep] | None = None
    status: str | None = None


class MigrationPathwayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_schema_id: UUID
    target_schema_id: UUID
    direction: str
    status: str
    inverse_pathway_id: UUID | None
    steps: list[dict[str, Any]] | None
    created_at: datetime
    version_num: int
