# Implementation Plan: Schema Enrichment — Classes, Validation, Inheritance & Provenance

**Branch**: `005-schema-enrichment` | **Date**: 2026-03-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-schema-enrichment/spec.md`

## Summary

Extend the `002-schema-backend` FastAPI service and the `001-neuro-schema-integration`
ingestion library to support:

1. **Schema Class Analysis** — extract `SchemaClass` records from ingested
   source schemas, classify DataElements by kind (scalar / enumeration /
   complex / array), and store `SchemaEnumeration` members.
2. **Validation Rules** — first-class `ValidationRule` entities attached to
   DataElements with automatic BREAKING / NON_BREAKING classification on
   every mutation.
3. **Schema Inheritance & Mixins** — `parent_id` FK on `DynamicSchema` for
   single-parent inheritance; `SchemaMixin` join table for multiple mixins;
   C3 MRO resolution exposed via `GET /api/v1/schemas/{id}/resolved`.
4. **Provenance** — `SchemaChangeLog` table with W3C PROV-DM fields for every
   schema mutation; system-seeded `ProvenanceMixin` schema; PROV-DM JSON-LD
   endpoint.

All work is additive to `002-schema-backend` (new migrations 0004–0009, new
API endpoints) and to `001-neuro-schema-integration` (adapters emit
`SchemaClass` + `ValidationRule` payloads during ingestion).

## Technical Context

**Language/Version**: Python 3.14 (backend 002)
**Primary Dependencies**: FastAPI 0.111+, SQLAlchemy 2.x async, Alembic,
Pydantic v2, PostgreSQL 16, authlib 1.x, httpx (ingestion client)
**New Dependencies**: None — all requirements covered by existing stack
**Storage**: PostgreSQL 16; 6 new tables (migrations 0004–0009)
**Testing**: pytest, pytest-asyncio, httpx `ASGITransport`; TDD (Principle II)
**Target Platform**: Developer workstation + Docker Compose
**Project Type**: Backend service extension + ingestion library extension
**Performance Goals**:
- `GET /schemas/{id}/resolved` (3-level chain, ≤ 200 elements): < 200 ms p95
- `GET /schemas/{id}/classes` (≤ 200 elements): < 500 ms p95
- MRO resolution cache hit: < 5 ms
**Constraints**:
- Max inheritance depth: 20 (enforced at write time)
- One active `ValidationRule` per `rule_type` per `DataElement`
- `ProvenanceMixin` is immutable by non-admin users
- `is_system` schemas cannot be deleted
**Scale/Scope**: ≤ 200 schemas, ≤ 100 classes, ≤ 2000 data elements, ≤ 5
validation rules per element in initial deployment

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | ✅ PASS | Adjacency list (not closure table); JSONB rules (not typed tables); no new dependencies |
| II. Test-Driven Development | ✅ PASS | Contract + unit tests written before implementation; TDD enforced |
| III. API-First Design | ✅ PASS | Contracts defined in contracts/rest-api.md before coding |
| IV. Observability | ✅ PASS | SchemaChangeLog is the structured audit trail; existing JSON logger used |
| V. CalVer | ✅ PASS | No library version bump needed; service remains CalVer-versioned |
| VI. Environment Isolation | ✅ PASS | Python 3.14, `uv venv` + `uv pip install`; no new external tooling |

## Project Structure

### Documentation (this feature)

```text
specs/005-schema-enrichment/
├── plan.md              ← this file
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── rest-api.md
```

### Source Code Changes (additive — no existing files removed)

```text
backend/
├── src/
│   ├── models/
│   │   └── db.py          ← add element_kind/node_kind to DataElement,
│   │                         parent_id/is_mixin/is_system to DynamicSchema,
│   │                         + new ORM classes: SchemaClassInheritance,
│   │                         SchemaEnumeration, ValidationRule,
│   │                         ValidationRuleChange, SchemaMixin,
│   │                         SchemaChangeLog
│   │                         (NOTE: classes are DataElement rows with
│   │                          node_kind='class', NOT a separate table)
│   ├── services/
│   │   ├── schema_class.py    ← NEW: SchemaClassService
│   │   ├── validation_rule.py ← NEW: ValidationRuleService
│   │   │                           + SemanticChangeClassifier
│   │   └── schema_mro.py      ← NEW: MROService (C3 + cycle detection)
│   └── api/v1/
│       ├── schemas.py     ← extend with /classes, /resolved,
│       │                     /inheritance-tree, /parent, /mixins,
│       │                     /provenance-mixin, /changelog, /provenance
│       └── elements.py    ← extend with /validation-rules CRUD
│
├── alembic/versions/
│   ├── 0004_element_kind_node_kind.py
│   ├── 0005_schema_inheritance.py
│   ├── 0006_schema_classes.py
│   ├── 0007_validation_rules.py
│   ├── 0008_schema_mixins_changelog.py
│   └── 0009_seed_provenance_mixin.py
│
└── tests/
    ├── unit/
    │   ├── test_semantic_classifier.py  ← ValidationRuleChange.breaking logic
    │   └── test_mro_service.py          ← C3 MRO + cycle detection
    ├── contract/
    │   ├── test_schema_classes_api.py
    │   ├── test_validation_rules_api.py
    │   ├── test_schema_inheritance_api.py
    │   └── test_schema_provenance_api.py
    └── integration/
        └── test_schema_enrichment_pipeline.py  ← ingest→class→rule→resolve
```

```text
ingestion/
└── src/undata/
    ├── adapters/
    │   ├── base.py      ← extend SchemaAdapter Protocol: add extract_classes()
    │   ├── bids.py      ← extract_classes() via YAML parsing (structured-text path)
    │   ├── dandi.py     ← extract_classes() via Pydantic model introspection (code path)
    │   ├── nwb.py       ← extract_classes() via YAML group parsing (structured-text path)
    │   ├── openminds.py ← extract_classes() via JSON-LD parsing (json path)
    │   └── aind.py      ← extract_classes() via JSON Schema fixture parsing (json path)
    ├── models.py        ← add SchemaClassPayload dataclass (with extraction_path field)
    └── ingestion.py     ← POST /sources/{id}/classes + /elements/{id}/validation-rules
```

## Phase 0 Research Summary

See [research.md](research.md).

| Question | Decision |
|----------|----------|
| Schema inheritance storage | Adjacency list + `WITH RECURSIVE` CTE |
| Breaking change classification | 6-rule application-layer engine |
| Validation rule storage | `validation_rules` table, polymorphic JSONB |
| Provenance model | W3C PROV-DM via `SchemaChangeLog` + JSON-LD API |
| MRO resolution | Python C3 linearization, in-memory LRU cache |
| SchemaClass vs DynamicSchema | Classes-as-DataElements: `node_kind='class'` discriminator on `DataElement`; `SchemaClassInheritance` join table for source-schema hierarchy |
| Multi-path class extraction | Two paths: JSON/YAML parsing (BIDS, openMINDS, AIND) + code introspection (DANDI Pydantic models, NWB YAML groups); both produce `SchemaClassPayload`; per-adapter strategy documented in research Q8 |

## Phase 1 Design Artifacts

- [data-model.md](data-model.md) — 7 new/extended entities + migration sequence
- [contracts/rest-api.md](contracts/rest-api.md) — 16 new API endpoints
- [quickstart.md](quickstart.md) — end-to-end validation scenarios

## Implementation Notes

### SemanticChangeClassifier (pure function, easy to unit test)

```python
def classify(rule_type: str, old_value: dict, new_value: dict) -> bool:
    """Returns True if the change is BREAKING."""
    if rule_type == "enum_set":
        old_set = set(old_value["values"])
        new_set = set(new_value["values"])
        return not new_set.issuperset(old_set)  # removed values = breaking
    if rule_type == "range":
        breaking = False
        if "min" in new_value and "min" in old_value:
            breaking |= new_value["min"] > old_value["min"]
        if "max" in new_value and "max" in old_value:
            breaking |= new_value["max"] < old_value["max"]
        return breaking
    if rule_type == "type_constraint":
        return old_value["type"] != new_value["type"]
    if rule_type == "pattern":
        return "regex" in new_value and "regex" not in old_value
    if rule_type == "cardinality":
        breaking = False
        if "min_count" in new_value:
            breaking |= new_value.get("min_count", 0) > old_value.get("min_count", 0)
        if "max_count" in new_value:
            breaking |= new_value.get("max_count", 9999) < old_value.get("max_count", 9999)
        return breaking
    return False
```

### MRO Service — C3 linearization

```python
def c3_merge(sequences):
    result = []
    while True:
        sequences = [s for s in sequences if s]
        if not sequences:
            return result
        for seq in sequences:
            candidate = seq[0]
            if all(candidate not in s[1:] for s in sequences):
                result.append(candidate)
                for s in sequences:
                    if s[0] == candidate:
                        s.pop(0)
                break
        else:
            raise CycleError("Inconsistent hierarchy (C3 failure)")

async def resolve(schema_id, db) -> list[SchemaId]:
    schema = await db.get(DynamicSchema, schema_id)
    own = [schema_id]
    parent_mro = await resolve(schema.parent_id, db) if schema.parent_id else []
    mixin_mros = [await resolve(m.mixin_id, db) for m in sorted(schema.mixins, key=lambda m: m.position)]
    return c3_merge([own] + [parent_mro] + mixin_mros + [[schema.parent_id] if schema.parent_id else []] + [[m.mixin_id] for m in schema.mixins])
```

### ingestion.py — Class and rule posting

Adapters will be updated to return `SchemaClass` metadata via a new
`extract_classes() → list[SchemaClassPayload]` method on the `SchemaAdapter`
Protocol. The `IngestionPipeline` will post to
`POST /api/v1/sources/{source_id}/classes` and
`POST /api/v1/elements/{id}/validation-rules` during the ingest run.

```python
@dataclass
class SchemaClassPayload:
    class_name: str                          # canonical class identifier
    description: str                         # human-readable summary
    element_source_local_ids: list[str]      # ordered element IDs in this class
    parent_class_name: str | None = None     # for source-schema inheritance
    extraction_path: str = "json"            # "json"|"yaml"|"jsonld"|"code" — informational only
                                             # BIDS→"yaml", NWB→"yaml", openMINDS→"jsonld",
                                             # AIND→"json", DANDI→"code" — NOT stored in DB
```

### Per-Adapter Class Extraction Strategy

| Adapter | Source | Extraction Path | Class Boundary | `extract_classes()` approach |
|---------|--------|-----------------|----------------|------------------------------|
| **BIDS** | YAML via bidsschematools | Structured-text parsing (`extraction_path="yaml"`) | Metadata domain category (inferred from field namespace in schema YAML; fall back to splitting `source_local_id` on first `_`) | Group `self._raw_fields` by namespace/category; one `SchemaClassPayload` per category |
| **DANDI** | Python Pydantic `BaseModel` subclasses | **Code introspection** (`extraction_path="code"`) | Pydantic model class name | Re-use the `BaseModel` subclass list from `extract_elements()`; group elements by model name prefix (`Subject.field_name` → class `Subject`) |
| **NWB** | YAML group definitions | Structured-text parsing (`extraction_path="yaml"`) | `neurodata_type` of each top-level group | Iterate `self._raw["groups"]`; each group with a `neurodata_type` becomes one class; child groups map `parent_class_name` |
| **openMINDS** | JSON-LD template files | JSON-LD parsing (`extraction_path="jsonld"`) | Root `@type` URI per file | One class per loaded file; class name = last path segment of `@type`; all properties are its members |
| **AIND** | Pre-exported JSON Schema fixtures | JSON parsing (`extraction_path="json"`) | Schema file stem | One class per `_SCHEMA_FILES` entry; class name from `title` key or filename stem; all properties are members |

**Code-introspection path** (DANDI): Elements already have `source_local_id` of
the form `ModelName.field_name`. `extract_classes()` groups by the prefix before
the first `.` to reconstruct the class membership list — no re-import needed.

**JSON/YAML parsing path** (BIDS, NWB, openMINDS, AIND): Adapters hold the raw
parsed structure in `self._raw_fields` / `self._raw` / `self._schemas`. Class
extraction reads that same cached structure a second time — no additional I/O.

## Complexity Tracking

| Item | Justification |
|------|--------------|
| C3 MRO in application code | Cannot implement correctly in SQL; Python is more readable and testable |
| 6 new DB tables (migrations 0004–0009) | Each maps to a distinct domain concept; no consolidation possible without losing semantics |
| Polymorphic JSONB for rule_value | Avoids 5-table explosion; GIN-indexed; consistent with existing constraints JSONB pattern |
| Dual-path class extraction (code + JSON) | DANDI/NWB source-of-truth is Python code; forcing JSON normalisation loses model boundaries. BIDS/openMINDS/AIND have no Python API; JSON parsing is the only path. Dual-path is mandatory, not a design preference. |
