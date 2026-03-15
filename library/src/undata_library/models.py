"""Pydantic v2 models matching library-schema.linkml.yaml."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

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


class MappingStatus(str, Enum):
    active = "active"
    pending_curation = "pending_curation"


class SemanticGraph(BaseModel):
    ontology_term: str | None = None
    unit: str | None = None
    external_uri: str | None = None
    cmixf_valid: bool | None = None


class ChangeEntry(BaseModel):
    change_type: str
    reason: str | None = None
    breaking: bool | None = None


class ElementVersion(BaseModel):
    version_num: int
    name: str
    data_type: DataType
    description: str | None = None
    required: bool | None = None
    multivalued: bool | None = None
    allowed_values: list[str] | None = None
    constraints: dict[str, Any] | None = None
    semantic_graph: SemanticGraph | None = None
    created_at: datetime
    created_by: str | None = None
    changelog: list[ChangeEntry] | None = None


class ElementMetadata(BaseModel):
    id: str
    source_local_id: str
    source_id: str | None = None
    created_at: datetime


class ElementRecord(BaseModel):
    element: ElementMetadata
    versions: list[ElementVersion] = Field(min_length=1)
    current_version: int


class MappingVersion(BaseModel):
    version_num: int
    function_type: MappingFunctionType | None = None
    expression: str | None = None
    expression_type: str | None = None
    input_element_ids: list[str] | None = None
    sssom_predicate: str | None = None
    created_at: datetime
    created_by: str | None = None


class MappingMetadata(BaseModel):
    id: str
    output_element_id: str | None = None
    status: MappingStatus | None = None
    attributed_to: str | None = None
    confidence_score: float | None = None
    created_at: datetime


class MappingRecord(BaseModel):
    mapping: MappingMetadata
    versions: list[MappingVersion] = Field(min_length=1)
    current_version: int


class ValidationViolation(BaseModel):
    field: str
    message: str
    severity: str = "ERROR"


class ValidationReport(BaseModel):
    valid: bool
    path: str
    violations: list[ValidationViolation] = Field(default_factory=list)
