"""Pydantic v2 models for undata-library v2 — content-addressed RDF property model."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Classification of a schema entity."""

    CLASS = "class"  # sh:NodeShape → SchemaRecord
    ATTRIBUTE = "attribute"  # rdf:Property → ElementRecord
    ENUM_VALUE = "enum_value"  # → ValueConcept
    VALUESET = "valueset"  # → ValueSetRecord


class DataType(str, Enum):
    string = "string"
    integer = "integer"
    float_ = "float"
    boolean = "boolean"
    array = "array"
    object_ = "object"


class MappingFunctionType(str, Enum):
    identity = "identity"
    unit_conversion = "unit_conversion"
    scaling = "scaling"
    structural = "structural"
    unknown = "unknown"


class ActivityType(str, Enum):
    ingestion = "ingestion"
    curation = "curation"
    enrichment = "enrichment"
    migration = "migration"


# ---------------------------------------------------------------------------
# Element (rdf:Property)
# ---------------------------------------------------------------------------


class ResponseOption(BaseModel):
    """A structured choice/enum value with optional ontology link."""

    value: str
    label: str | None = None
    ontology_term: str | None = None


class Constraints(BaseModel):
    """Legacy constraint block. Use min_value/max_value on SemanticIdentity for ranges."""

    minimum: float | None = None  # deprecated — use SemanticIdentity.min_value
    maximum: float | None = None  # deprecated — use SemanticIdentity.max_value
    pattern: str | None = None
    allowed_values: list[str] | None = None


class SemanticIdentity(BaseModel):
    """Identity block — hashed for content-addressed URI.

    Fields IN the hash: ontology_term, data_type, unit, constraints (pattern + allowed_values only),
    min_value, max_value, response_options (sorted by value).
    Fields NOT in hash: question_text, value_domain.
    """

    ontology_term: str | None = None
    data_type: DataType
    unit: str | None = None
    constraints: Constraints | None = None
    # reproschema-aligned fields:
    response_options: list[ResponseOption] | None = None  # IN hash (sorted by value)
    question_text: str | None = None  # NOT in hash
    value_domain: str | None = None  # NOT in hash (categorical|numeric|text|date|boolean)
    min_value: float | None = None  # IN hash — replaces constraints.minimum
    max_value: float | None = None  # IN hash — replaces constraints.maximum
    # Disambiguators for underspecified elements (no ontology_term/unit).
    # Stored in the semantic block so the backend can reproduce the same hash.
    source_attribute: str | None = None  # IN hash when present
    source_class: str | None = None  # IN hash when present
    type_ref: str | None = None  # IN hash — URI of referenced SchemaRecord when data_type=object


class ProvenanceEntry(BaseModel):
    """One source's attestation of this property, with W3C PROV-O metadata."""

    source: str
    class_: str = Field(alias="class")
    name: str
    description: str | None = None
    required: bool | None = None
    multivalued: bool | None = None
    # W3C PROV-O fields:
    generated_at: str | None = None  # prov:generatedAtTime (ISO 8601)
    attributed_to: str | None = None  # prov:wasAttributedTo (agent URI)
    activity: str | None = None  # prov:wasGeneratedBy (ingestion|curation|enrichment|migration)
    derived_from: str | None = None  # prov:wasDerivedFrom (element URI)

    model_config = {"populate_by_name": True}


class ElementRecord(BaseModel):
    """A data element (rdf:Property) with semantic identity + provenance."""

    semantic: SemanticIdentity
    provenance: list[ProvenanceEntry] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Schema (sh:NodeShape)
# ---------------------------------------------------------------------------


class SchemaIdentity(BaseModel):
    """Identity block for a class shape — hashed."""

    properties: list[str] = Field(default_factory=list)
    subclass_of: str | None = None
    mixins: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    """Precise origin tracking for provenance entries."""

    repo: str | None = None  # GitHub URL or null for non-git sources
    committish: str | None = None  # git SHA, tag, or branch
    file: str  # relative path within repo, or absolute for non-git
    checksum: str  # SHA-256 of source file content
    package_version: str | None = None  # pip/npm version (Docker sources only)


class SchemaProvenance(BaseModel):
    """One source's attestation of this class shape — PROV-O aligned."""

    source: str
    name: str
    description: str | None = None
    generated_at: str | None = None
    attributed_to: str | None = None
    activity: str | None = None
    derived_from: str | None = None
    source_ref: SourceRef | None = None


class SchemaRecord(BaseModel):
    """A class shape (sh:NodeShape) with semantic identity + provenance."""

    semantic: SchemaIdentity
    provenance: list[SchemaProvenance] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Value Concept (categorical/enum value as semantic entity)
# ---------------------------------------------------------------------------


class ValueSemanticIdentity(BaseModel):
    """Identity block for a value concept — hashed for content-addressed URI."""

    ontology_term: str | None = None
    value_type: str = "categorical"
    label: str


class ValueProvenance(BaseModel):
    """One source's representation of this value."""

    source: str
    raw_value: str


class ValueConcept(BaseModel):
    """A categorical value with content-addressed identity + provenance."""

    semantic: ValueSemanticIdentity
    provenance: list[ValueProvenance] = Field(min_length=1)


# ---------------------------------------------------------------------------
# ValueSet (named collection of ValueConcept URIs)
# ---------------------------------------------------------------------------


class ValueSetIdentity(BaseModel):
    """Identity block for a valueset — hashed for content-addressed URI."""

    name: str  # e.g., "units", "modalities"
    members: list[str] = Field(default_factory=list)  # sorted ValueConcept URIs — IN hash


class ValueSetRecord(BaseModel):
    """A named collection of enum values with content-addressed identity + provenance."""

    semantic: ValueSetIdentity
    provenance: list[ProvenanceEntry] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Workflow + Ingestion Report
# ---------------------------------------------------------------------------


class WorkflowSource(BaseModel):
    """A source entry in a workflow spec."""

    path: str
    adapter: str | None = None
    options: dict = Field(default_factory=dict)


class WorkflowClassification(BaseModel):
    """Classification settings in a workflow spec."""

    overrides: dict[str, str] = Field(default_factory=dict)
    confidence_threshold: float = 0.7
    llm_model: str | None = None


class WorkflowDocker(BaseModel):
    """Docker settings in a workflow spec."""

    enabled: bool = False
    image: str | None = None
    timeout: int = 300


class WorkflowValidation(BaseModel):
    """Validation settings in a workflow spec."""

    strict: bool = False
    checks: list[str] = Field(default_factory=list)


class WorkflowSpec(BaseModel):
    """YAML-defined ingestion workflow."""

    sources: list[WorkflowSource] = Field(default_factory=list)
    classification: WorkflowClassification = Field(default_factory=WorkflowClassification)
    docker: WorkflowDocker = Field(default_factory=WorkflowDocker)
    validation: WorkflowValidation = Field(default_factory=WorkflowValidation)


class IngestionViolation(BaseModel):
    """A single validation violation in an ingestion report."""

    file: str
    entity_type: str
    check: str
    message: str
    severity: str = "ERROR"


class IngestionReport(BaseModel):
    """Per-run validation report."""

    generated_at: str | None = None
    workflow: str | None = None
    sources_processed: int = 0
    stats: dict = Field(default_factory=dict)
    validation_passed: bool = True
    violations: list[IngestionViolation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


class MappingProvenance(BaseModel):
    source: str
    attributed_to: str | None = None


class MappingRecord(BaseModel):
    source_element: str
    target_element: str
    function_type: MappingFunctionType
    expression: str | None = None
    expression_type: str | None = None
    confidence: float | None = None
    sssom_predicate: str | None = None
    provenance: list[MappingProvenance] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Hash Registry
# ---------------------------------------------------------------------------


class HashRegistryEntry(BaseModel):
    sha256: str
    attribute: str | None = None
    name: str | None = None
    uri: str


class HashRegistry(BaseModel):
    elements: dict[str, HashRegistryEntry] = Field(default_factory=dict)
    schemas: dict[str, HashRegistryEntry] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation report (reused from v1)
# ---------------------------------------------------------------------------


class ValidationViolation(BaseModel):
    field: str
    message: str
    severity: str = "ERROR"


class ValidationReport(BaseModel):
    valid: bool
    path: str
    violations: list[ValidationViolation] = Field(default_factory=list)
