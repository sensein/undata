"""Pydantic v2 models for undata-library v2 — content-addressed RDF property model."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


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


class SchemaProvenance(BaseModel):
    """One source's attestation of this class shape."""

    source: str
    name: str
    description: str | None = None


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
