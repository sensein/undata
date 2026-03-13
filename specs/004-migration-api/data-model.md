# Data Model: Dynamic Schema Construction and Migration API
**Feature**: 004-migration-api | **Date**: 2026-03-07

This service is stateless with respect to element and mapping data — all persistence
is delegated to 002-schema-backend. It introduces one new backend resource (`Pathway`)
and owns its own async job state.

---

## New Backend Resource: MigrationPathway

Stored in 002-schema-backend via a new `/pathways` resource endpoint.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `name` | TEXT | Human label |
| `source_schema_id` | UUID | FK → DynamicSchema |
| `target_schema_id` | UUID | FK → DynamicSchema |
| `direction` | TEXT | "forward", "backward", "bidirectional" |
| `status` | TEXT | "active", "broken", "draft" |
| `inverse_pathway_id` | UUID, nullable | Auto-set if inverse derivable |
| `steps` | JSONB | Ordered list: `[{position, mapping_id}]` |
| `created_at` | TIMESTAMPTZ | |
| `created_by` | TEXT | |
| `version_num` | INT | Optimistic lock |

---

## New Backend Resource: DynamicSchema

Stored in 002-schema-backend via a new `/schemas` resource endpoint.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `name` | TEXT | Client-assigned name |
| `version` | TEXT | CalVer string |
| `classes` | JSONB | `[{name, element_ids}]` |
| `linkml_yaml` | TEXT | Serialized generated YAML |
| `status` | TEXT | "draft", "published" |
| `created_at` | TIMESTAMPTZ | |

---

## Migration API Internal Structures (in-memory, per request)

### MigrationContext

State object passed through a migration execution.

```python
@dataclass
class MigrationContext:
    pathway_id: str
    source_schema_id: str
    target_schema_id: str
    steps: list[MappingStep]        # ordered, resolved from backend
    input_record: dict
    output_record: dict             # built up during execution
    report: MigrationReport
```

### MappingStep

One resolved step in a migration execution.

```python
@dataclass
class MappingStep:
    position: int
    mapping_id: str
    function_type: str              # "identity" | "custom"
    input_element_names: list[str]
    output_element_name: str
    expression: str
    expression_type: str            # "identity" | "python_expr" | "plugin"
    parameter_schema: dict | None
```

### MigrationReport (output artifact)

```python
@dataclass
class MigrationReport:
    pathway_id: str
    source_schema_id: str
    target_schema_id: str
    overall_status: str             # "PASS" | "FAIL" | "PARTIAL"
    steps_applied: list[StepResult]
    unmapped_fields: list[str]
    passthrough_fields: list[str]   # fields with no mapping, passed through
    validation_result: ValidationResult
    duration_ms: int

@dataclass
class StepResult:
    position: int
    mapping_id: str
    output_element: str
    input_values: dict
    output_value: Any
    status: str                     # "OK" | "ERROR" | "SKIPPED"
    error_message: str | None

@dataclass
class ValidationResult:
    status: str                     # "PASS" | "FAIL"
    violations: list[Violation]

@dataclass
class Violation:
    field: str
    violation_type: str             # "MISSING_REQUIRED" | "TYPE_MISMATCH" | "ENUM_VIOLATION"
    severity: str                   # "ERROR" | "WARNING" | "INFO"
    message: str
```

---

## Schema Diff Structure

```python
@dataclass
class SchemaDiff:
    source_schema_id: str
    target_schema_id: str
    coverage: str                   # "FULL" | "PARTIAL" | "NONE"
    added: list[ElementRef]         # in target, not in source
    removed: list[ElementRef]       # in source, not in target
    renamed: list[RenameEntry]      # alias pairs
    type_changed: list[ChangeEntry]
    constraint_changed: list[ChangeEntry]
    description_changed: list[ChangeEntry]
    draft_pathway: PathwaySummary | None   # assembled from existing mappings

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
```

---

## Async Job State (Redis-backed)

```python
@dataclass
class AsyncJob:
    job_id: str                     # UUID
    job_type: str                   # "schema_construction" | "batch_migration"
    status: str                     # "pending" | "running" | "done" | "failed"
    progress: int                   # 0–100 percent
    result: dict | None             # serialized result when done
    error: str | None
    created_at: str                 # ISO timestamp
    completed_at: str | None
```
