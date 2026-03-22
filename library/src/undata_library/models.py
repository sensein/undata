"""Pydantic v2 models for undata-library v2 — content-addressed RDF property model."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class MatchLevel(str, Enum):
    """Whether an ontology alignment is a concept-level or data-element-level match."""

    concept_match = "concept_match"  # ontology term = concept (no type/unit info)
    element_match = "element_match"  # ontology term = exact data value


class OntologyAnnotation(BaseModel):
    """A single ontology alignment for an entity — qualitative + quantitative."""

    term_uri: str
    term_label: str
    ontology: str  # e.g., "ncit", "pato", "uberon"
    mapping_relation: str  # skos:exactMatch, closeMatch, broadMatch, narrowMatch, relatedMatch
    match_level: MatchLevel
    score: float  # cosine similarity 0.0–1.0
    model: str  # embedding model name (e.g., "all-MiniLM-L6-v2")
    primary: bool = False  # True for the best match


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
    type_conversion = "type_conversion"
    scaling = "scaling"
    structural = "structural"
    value_mapping = "value_mapping"
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


class SemanticIdentity(BaseModel):
    """Identity block — hashed post-enrichment at commit time.

    Two hash modes (see hashing.py compute_identity_hash):
    1. Ontology-anchored: data_type + unit + pattern + response_options + min/max + type_ref + primary_ontology_uri
    2. Structural fallback: data_type + unit + pattern + response_options + min/max + type_ref + class + attribute + description (from first provenance)

    Fields NOT in hash: question_text, value_domain, ontology_annotations, description (in ontology-anchored mode).
    """

    data_type: DataType
    unit: str | None = None
    pattern: str | None = None  # regex constraint (replaces constraints.pattern)
    response_options: list[ResponseOption] | None = None  # IN hash (sorted by value)
    question_text: str | None = None  # NOT in hash
    value_domain: str | None = None  # NOT in hash (categorical|numeric|text|date|boolean)
    min_value: float | None = None  # IN hash
    max_value: float | None = None  # IN hash
    type_ref: str | None = None  # IN hash — URI of referenced SchemaRecord when data_type=object
    description: str | None = (
        None  # IN hash (structural fallback only); NOT in hash (ontology-anchored)
    )
    ontology_annotations: list[OntologyAnnotation] | None = (
        None  # NOT in hash — enrichment metadata
    )


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
    source_ref: SourceRef | None = None  # precise origin tracking

    model_config = {"populate_by_name": True}


class ElementRecord(BaseModel):
    """A data element (rdf:Property) with semantic identity + provenance."""

    semantic: SemanticIdentity
    provenance: list[ProvenanceEntry] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Schema (sh:NodeShape)
# ---------------------------------------------------------------------------


class SchemaIdentity(BaseModel):
    """Identity block for a class shape — hashed post-enrichment."""

    properties: list[str] = Field(default_factory=list)
    subclass_of: str | None = None
    mixins: list[str] = Field(default_factory=list)
    description: str | None = None  # IN hash (structural fallback only)
    ontology_annotations: list[OntologyAnnotation] | None = None  # NOT in hash


class SourceRef(BaseModel):
    """Precise origin tracking for provenance entries."""

    repo: str | None = None  # GitHub URL or null for non-git sources
    committish: str | None = None  # git SHA, tag, or branch
    file: str  # relative path within repo, or absolute for non-git
    checksum: str  # SHA-256 of source file content
    package_version: str | None = None  # pip/npm version (Docker sources only)


class SchemaRecord(BaseModel):
    """A class shape (sh:NodeShape) with semantic identity + provenance."""

    semantic: SchemaIdentity
    provenance: list[ProvenanceEntry] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Value Concept (categorical/enum value as semantic entity)
# ---------------------------------------------------------------------------


class ValueSemanticIdentity(BaseModel):
    """Identity block for a value concept — hashed for content-addressed URI."""

    value_type: str = "categorical"
    label: str
    description: str | None = None
    ontology_annotations: list[OntologyAnnotation] | None = None  # NOT in hash


class ValueConcept(BaseModel):
    """A categorical value with content-addressed identity + provenance."""

    semantic: ValueSemanticIdentity
    provenance: list[ProvenanceEntry] = Field(min_length=1)


# ---------------------------------------------------------------------------
# ValueSet (named collection of ValueConcept URIs)
# ---------------------------------------------------------------------------


class ValueSetIdentity(BaseModel):
    """Identity block for a valueset — hashed for content-addressed URI."""

    name: str  # e.g., "units", "modalities"
    members: list[str] = Field(default_factory=list)  # sorted ValueConcept URIs — IN hash
    description: str | None = None
    ontology_annotations: list[OntologyAnnotation] | None = None  # NOT in hash


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


class SourceDefinition(BaseModel):
    """Declarative specification for a schema source."""

    name: str
    repo: str
    default_version: str = "latest"
    acquisition: str  # git_clone | pip_install | download_file
    package: str | None = None  # Python package name (for pip_install)
    adapter: str  # adapter name from registry
    schema_path: str | None = None  # glob pattern for schema files
    isolation: str = "none"  # none | venv | docker
    python_version: str | None = None  # e.g., "3.12" for bridge venvs


class RegistryConfig:
    """Resolve the output directory for library registry data.

    Resolution order: CLI flag > $UNDATA_REGISTRY_DIR env var > XDG default.
    """

    _XDG_DEFAULT = Path.home() / ".local" / "share" / "undata" / "registry"

    @classmethod
    def resolve(cls, cli_output_dir: str | None = None) -> Path:
        """Resolve the output directory."""
        import os

        if cli_output_dir:
            p = Path(cli_output_dir)
        elif os.environ.get("UNDATA_REGISTRY_DIR"):
            p = Path(os.environ["UNDATA_REGISTRY_DIR"])
        else:
            p = cls._XDG_DEFAULT
        p.mkdir(parents=True, exist_ok=True)
        return p


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


class FunctionSpec(BaseModel):
    """Typed function specification for a transform."""

    function_type: MappingFunctionType
    input_type: str  # data_type of source element
    output_type: str  # data_type of target element
    expression: str | None = None  # formula, named function, or template
    expression_type: str = "none"  # arithmetic|named_function|template|lookup_table|none
    parameters: dict | None = None  # e.g., {factor: 12, unit_from: "year"}


class TransformRecord(BaseModel):
    """Content-addressed bidirectional transform between two elements."""

    source_element: str  # element URI
    target_element: str  # element URI
    function: FunctionSpec
    confidence: float | None = None
    sssom_predicate: str | None = None
    provenance: list[ProvenanceEntry] = Field(default_factory=list)


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
