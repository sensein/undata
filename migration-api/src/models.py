"""Shared Pydantic request/response models and internal dataclasses for migration-api."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Schema construction
# ---------------------------------------------------------------------------


class ClassSpec(BaseModel):
    name: str
    element_ids: list[UUID]


class SchemaConstructionRequest(BaseModel):
    name: str
    version: str = "2026.03.0"
    classes: list[ClassSpec]
    save: bool = False


class SchemaConstructionResponse(BaseModel):
    schema_id: str | None = None
    name: str
    version: str
    linkml_yaml: str
    linkml_jsonld: str | None = None
    status: str = "draft"


# ---------------------------------------------------------------------------
# Pathways
# ---------------------------------------------------------------------------


class PathwayStepSpec(BaseModel):
    position: int
    mapping_id: UUID


class PathwayCreateRequest(BaseModel):
    name: str
    source_schema_id: UUID
    target_schema_id: UUID
    direction: str = "forward"
    steps: list[PathwayStepSpec] = Field(default_factory=list)


class PathwayResponse(BaseModel):
    id: str
    name: str
    source_schema_id: str
    target_schema_id: str
    direction: str
    status: str
    inverse_pathway_id: str | None
    steps: list[dict[str, Any]]
    version_num: int


class PathwayComposeRequest(BaseModel):
    pathway_a_id: UUID
    pathway_b_id: UUID
    save: bool = False


# ---------------------------------------------------------------------------
# Migration execution
# ---------------------------------------------------------------------------


class MigrateRequest(BaseModel):
    pathway_id: UUID
    records: list[dict[str, Any]]


class RecordResult(BaseModel):
    input_record: dict[str, Any]
    output_record: dict[str, Any] | None
    status: str  # "PASS" | "FAIL"
    report: dict[str, Any]


class MigrateResponse(BaseModel):
    pathway_id: str
    total: int
    succeeded: int
    failed: int
    results: list[RecordResult]
    job_id: str | None = None


# ---------------------------------------------------------------------------
# Schema diff
# ---------------------------------------------------------------------------


class DiffRequest(BaseModel):
    source_schema_id: UUID
    target_schema_id: UUID


class DiffResponse(BaseModel):
    source_schema_id: str
    target_schema_id: str
    coverage: str  # "FULL" | "PARTIAL" | "NONE"
    added: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    renamed: list[dict[str, Any]]
    type_changed: list[dict[str, Any]]
    constraint_changed: list[dict[str, Any]]
    description_changed: list[dict[str, Any]]
    draft_pathway: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Async jobs
# ---------------------------------------------------------------------------


class JobStatus(BaseModel):
    job_id: str
    job_type: str
    status: str  # "pending" | "running" | "done" | "failed"
    progress: int  # 0–100
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None
    poll_url: str | None = None


# ---------------------------------------------------------------------------
# Internal dataclasses (in-memory, per request)
# ---------------------------------------------------------------------------


@dataclass
class MappingStep:
    position: int
    mapping_id: str
    function_type: str
    input_element_names: list[str]
    output_element_name: str
    expression: str
    expression_type: str
    parameter_schema: dict | None = None


@dataclass
class Violation:
    field: str
    violation_type: str
    severity: str
    message: str


@dataclass
class ValidationResult:
    status: str
    violations: list[Violation] = field(default_factory=list)


@dataclass
class StepResult:
    position: int
    mapping_id: str
    output_element: str
    input_values: dict
    output_value: Any
    status: str  # "OK" | "ERROR" | "SKIPPED"
    error_message: str | None = None


@dataclass
class MigrationReport:
    pathway_id: str
    source_schema_id: str
    target_schema_id: str
    overall_status: str  # "PASS" | "FAIL" | "PARTIAL"
    steps_applied: list[StepResult] = field(default_factory=list)
    unmapped_fields: list[str] = field(default_factory=list)
    passthrough_fields: list[str] = field(default_factory=list)
    validation_result: ValidationResult | None = None
    duration_ms: int = 0


@dataclass
class MigrationContext:
    pathway_id: str
    source_schema_id: str
    target_schema_id: str
    steps: list[MappingStep]
    input_record: dict
    output_record: dict = field(default_factory=dict)
    report: MigrationReport | None = None


@dataclass
class ElementRef:
    element_id: str
    name: str
    schema_id: str


@dataclass
class RenameEntry:
    source_element: ElementRef
    target_element: ElementRef
    alias_group_id: str


@dataclass
class SchemaDiff:
    source_schema_id: str
    target_schema_id: str
    coverage: str  # "FULL" | "PARTIAL" | "NONE"
    added: list[ElementRef] = field(default_factory=list)
    removed: list[ElementRef] = field(default_factory=list)
    renamed: list[RenameEntry] = field(default_factory=list)
    type_changed: list[dict] = field(default_factory=list)
    constraint_changed: list[dict] = field(default_factory=list)
    description_changed: list[dict] = field(default_factory=list)
    draft_pathway: dict | None = None


@dataclass
class AsyncJob:
    job_id: str
    job_type: str
    status: str  # "pending" | "running" | "done" | "failed"
    progress: int = 0
    result: dict | None = None
    error: str | None = None
    created_at: str = ""
    completed_at: str | None = None
