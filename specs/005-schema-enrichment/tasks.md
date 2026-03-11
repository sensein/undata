# Tasks: Schema Enrichment — Classes, Validation, Inheritance & Provenance

**Feature**: `005-schema-enrichment` | **Branch**: `005-schema-enrichment`
**Input**: Design documents from `/specs/005-schema-enrichment/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/rest-api.md ✅, quickstart.md ✅

**Tests**: TDD approach — Constitution Principle II is NON-NEGOTIABLE.
Test tasks are marked ⚠️ and MUST FAIL before their corresponding implementation tasks.

**User Stories**:
- US1 P1 — Schema Class Analysis (extract classes via JSON/YAML + code-introspection paths, element_kind, enumerations)
- US2 P2 — Validation Rules (typed rules + BREAKING/NON_BREAKING classifier)
- US3 P3 — Schema Inheritance & Mixins (parent_id, SchemaMixin, C3 MRO resolution)
- US4 P4 — Schema Provenance (SchemaChangeLog, W3C PROV-DM, ProvenanceMixin)

**Dual extraction paths** (research Q8):
- **Structured-file path**: BIDS (`extraction_path="yaml"`), NWB (`extraction_path="yaml"`), openMINDS (`extraction_path="jsonld"`), AIND (`extraction_path="json"`)
- **Code-introspection path**: DANDI only (`extraction_path="code"` — Pydantic `BaseModel` subclasses via `inspect`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline, confirm migration tooling is ready for 6 new migrations

- [X] T001 Run `cd backend && uv run pytest tests/ -q --tb=short` to establish passing baseline (all existing 002 tests must pass before any 005 work begins)
- [X] T002 [P] Verify Alembic migration head is at `0003` by running `cd backend && uv run alembic current`; confirm output matches expectations
- [X] T003 [P] Create empty Alembic migration stubs 0004–0009 in `backend/alembic/versions/` with correct `down_revision` chain: `uv run alembic revision --rev-id 0004 -m "element_kind_node_kind"` (repeat for 0005–0009 with sequential down_revision)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema additions and ORM model updates required by ALL user stories

**⚠️ CRITICAL**: No user story work can begin until all migrations are applied and models are updated

- [X] T004 Implement Alembic migration `0004` in `backend/alembic/versions/0004_element_kind_node_kind.py`: add `element_kind TEXT NOT NULL DEFAULT 'scalar'` and `node_kind TEXT NOT NULL DEFAULT 'field'` to `data_elements`; add `agent_type TEXT NOT NULL DEFAULT 'person'` to `user_profiles`; add `caused_by_activity_id UUID REFERENCES audit_log(id)` (nullable) to `audit_log`; backfill `element_kind` from existing `allowed_values`/`data_type` (non-empty `allowed_values` → `'enumeration'`; `data_type='object'` → `'complex'`; `data_type='array'` → `'array'`; else `'scalar'`)
- [X] T005 Implement Alembic migration `0005` in `backend/alembic/versions/0005_schema_inheritance.py`: add `parent_id UUID REFERENCES dynamic_schemas(id)` (nullable), `is_mixin BOOLEAN NOT NULL DEFAULT FALSE`, `is_system BOOLEAN NOT NULL DEFAULT FALSE` to `dynamic_schemas`
- [X] T006 [P] Implement Alembic migration `0006` in `backend/alembic/versions/0006_schema_classes.py`: create `schema_class_inheritance (parent_class_id UUID FK→data_elements NOT NULL, child_class_id UUID FK→data_elements NOT NULL, relationship_type TEXT NOT NULL DEFAULT 'is_a', PRIMARY KEY (parent_class_id, child_class_id))`; create `schema_enumerations (id UUID PK, element_id UUID FK→data_elements NOT NULL, value TEXT NOT NULL, label TEXT, description TEXT, position INT NOT NULL, UNIQUE(element_id, value))`
- [X] T007 [P] Implement Alembic migration `0007` in `backend/alembic/versions/0007_validation_rules.py`: create `validation_rules (id UUID PK, element_id UUID FK→data_elements NOT NULL, rule_type TEXT NOT NULL, rule_value JSONB NOT NULL, severity TEXT NOT NULL DEFAULT 'error', description TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), created_by UUID FK→user_profiles NOT NULL, deleted_at TIMESTAMPTZ, UNIQUE(element_id, rule_type) WHERE deleted_at IS NULL)`; create `validation_rule_changes (id UUID PK, rule_id UUID FK→validation_rules NOT NULL, element_id UUID FK→data_elements NOT NULL, operation TEXT NOT NULL, old_value JSONB, new_value JSONB, breaking BOOLEAN NOT NULL, actor_id UUID FK→user_profiles NOT NULL, timestamp TIMESTAMPTZ NOT NULL DEFAULT now(), reason TEXT)`
- [X] T008 [P] Implement Alembic migration `0008` in `backend/alembic/versions/0008_schema_mixins_changelog.py`: create `schema_mixins (schema_id UUID FK→dynamic_schemas NOT NULL, mixin_id UUID FK→dynamic_schemas NOT NULL, position INT NOT NULL, PRIMARY KEY(schema_id, mixin_id))`; create `schema_change_log (id UUID PK, schema_id UUID FK→dynamic_schemas NOT NULL, version_num INT NOT NULL, operation TEXT NOT NULL, actor_id UUID FK→user_profiles NOT NULL, timestamp TIMESTAMPTZ NOT NULL DEFAULT now(), activity_type TEXT NOT NULL, diff JSONB, breaking BOOLEAN NOT NULL DEFAULT FALSE, semantic_boundary_crossed BOOLEAN NOT NULL DEFAULT FALSE, reason TEXT)`
- [X] T009 Implement Alembic migration `0009` in `backend/alembic/versions/0009_seed_provenance_mixin.py`: insert `DynamicSchema` record (`name='ProvenanceMixin'`, `is_system=TRUE`, `is_mixin=TRUE`) linked to the `undata` SchemaSource; insert 4 `DataElement` rows (`prov_created_by` string required, `prov_created_at` string required, `prov_modified_at` string optional, `prov_derived_from` string optional) each with `node_kind='field'`, `element_kind='scalar'`; insert `DynamicSchemaElement` join rows linking them to ProvenanceMixin
- [X] T010 Update SQLAlchemy ORM in `backend/src/models/db.py`: add `element_kind: Mapped[str]`, `node_kind: Mapped[str]` to `DataElement`; add `agent_type: Mapped[str]` to `UserProfile`; add `caused_by_activity_id: Mapped[UUID | None]` FK to `AuditLog`; add `parent_id: Mapped[UUID | None]`, `is_mixin: Mapped[bool]`, `is_system: Mapped[bool]` to `DynamicSchema`; add new ORM classes `SchemaClassInheritance`, `SchemaEnumeration`, `ValidationRule`, `ValidationRuleChange`, `SchemaMixin`, `SchemaChangeLog` with all columns and relationships (use `selectinload` compatible relationship configs)
- [X] T011 [P] Update Pydantic schemas in `backend/src/models/schemas.py`: add `element_kind`, `node_kind` to `DataElementResponse` and `DataElementCreate`; add new models `SchemaClassInheritanceRead`, `SchemaEnumerationRead`, `ValidationRuleCreate`, `ValidationRuleRead`, `ValidationRuleUpdate`, `ValidationRuleChangeRead`, `SchemaMixinCreate`, `SchemaChangeLogEntry`, `ResolvedSchemaResponse`, `SchemaClassesResponse`, `InheritanceTreeResponse`, `ProvDMProvenanceResponse`
- [X] T012 Apply all migrations and verify: `cd backend && uv run alembic upgrade head` then `uv run alembic current` (must show `0009 (head)`); run `uv run pytest tests/ -q` to confirm no regressions from ORM/schema changes

**Checkpoint**: All 6 migrations applied; ORM and Pydantic models updated; existing tests still pass

---

## Phase 3: User Story 1 — Schema Class Analysis (Priority: P1) 🎯 MVP

**Goal**: Extract SchemaClass nodes (`node_kind='class'`) from ingested source schemas using
both JSON/YAML and code-introspection paths; classify DataElements by `element_kind`;
expose `/classes` endpoint; update all 5 ingestion adapters.

**Independent Test**: After ingesting AIND schema, `GET /api/v1/schemas/{aind_schema_uuid}/classes`
returns ≥ 5 classes (one per schema file); at least one element has `element_kind='enumeration'`.

### Tests for User Story 1 ⚠️ Write FIRST — must FAIL before implementation

- [X] T013 [P] [US1] Unit test for `element_kind` derivation logic: given `allowed_values=[...]` → `enumeration`; `data_type='object'` → `complex`; `data_type='array'` → `array`; otherwise → `scalar`; and `node_kind` defaults to `'field'`; test in `backend/tests/unit/test_element_classification.py`
- [X] T014 [P] [US1] Unit test for `extract_classes()` **structured-file path**: load BIDS fixture (YAML), openMINDS fixture (JSON-LD), AIND fixture (JSON Schema) and call `extract_classes()` on each; assert ≥ 1 `SchemaClassPayload` returned with correct per-adapter `extraction_path` (BIDS → `'yaml'`, openMINDS → `'jsonld'`, AIND → `'json'`); `element_source_local_ids` non-empty; test in `ingestion/tests/unit/test_adapter_class_extraction.py`
- [X] T015 [P] [US1] Unit test for `extract_classes()` **code-introspection path (DANDI) + YAML path (NWB)**: call DANDI adapter `extract_classes()` and assert classes keyed by Pydantic model name (e.g. `Subject`, `BioSample`) with `extraction_path='code'`; call NWB adapter `extract_classes()` and assert classes keyed by `neurodata_type` (e.g. `TimeSeries`) with `extraction_path='yaml'` (NWB uses YAML parsing, not code introspection); test in `ingestion/tests/unit/test_adapter_class_extraction.py`
- [X] T016 [P] [US1] Contract test for `GET /api/v1/schemas/{id}/classes`: mock a schema with a class `DataElement` (`node_kind='class'`) that has 3 child elements including one enumeration; assert response matches contracts/rest-api.md §Schema Classes shape; test in `backend/tests/contract/test_schema_classes_api.py`
- [X] T017 [P] [US1] Contract test for `POST /api/v1/sources/{source_id}/classes` (create class node) and `GET /api/v1/sources/{source_id}/classes` (list classes); assert 201 on create with returned id; assert list includes created class; test in `backend/tests/contract/test_schema_classes_api.py`
- [X] T018 [P] [US1] Contract test for `POST /api/v1/sources/{source_id}/classes/{class_id}/elements`: link a DataElement to a class; assert 201; assert position ordering preserved in subsequent GET; test in `backend/tests/contract/test_schema_classes_api.py`

### Implementation for User Story 1

- [X] T019 [P] [US1] Add `SchemaClassPayload` dataclass to `ingestion/src/undata/models.py`: fields `class_name: str`, `description: str`, `element_source_local_ids: list[str]`, `parent_class_name: str | None = None`, `extraction_path: str = "json"` where allowed values are `"json"` (AIND), `"yaml"` (BIDS, NWB), `"jsonld"` (openMINDS), `"code"` (DANDI) — informational only, not stored in DB; extend `SchemaAdapter` Protocol in `ingestion/src/undata/adapters/base.py` to declare `extract_classes() -> list[SchemaClassPayload]`; export `SchemaClassPayload` from `ingestion/src/undata/__init__.py`
- [X] T020 [P] [US1] Implement `SchemaClassService` in `backend/src/services/schema_class.py`: `create_class(source_id, class_name, description, parent_class_name, db)` creates a `DataElement` row with `node_kind='class'`; `add_element_to_class(class_id, element_id, position, db)` inserts `DataElementChild` join; `get_classes_for_schema(schema_id, db)` joins via source_id + uses `WITH RECURSIVE` CTE for inherited elements; `get_classes_for_source(source_id, db)` lists all class nodes for the source
- [X] T021 [US1] Add `GET /api/v1/schemas/{schema_id}/classes` endpoint in `backend/src/api/v1/schemas.py` calling `SchemaClassService.get_classes_for_schema()`; returns `SchemaClassesResponse`
- [X] T022 [US1] Add `POST /api/v1/sources/{source_id}/classes`, `GET /api/v1/sources/{source_id}/classes`, and `POST /api/v1/sources/{source_id}/classes/{class_id}/elements` endpoints in `backend/src/api/v1/sources.py`; all protected by Bearer auth
- [X] T023 [P] [US1] Implement `extract_classes()` in `ingestion/src/undata/adapters/bids.py` (YAML path): group `self._raw_fields` dict by BIDS schema namespace/category field if present; fall back to splitting `source_local_id` on first `_`; return one `SchemaClassPayload` per category with `extraction_path='yaml'`
- [X] T024 [P] [US1] Implement `extract_classes()` in `ingestion/src/undata/adapters/dandi.py` (code-introspection path): re-use the `BaseModel` subclass list already iterated in `extract_elements()`; group `source_local_id` values by the model name prefix before first `.` (e.g. `Subject.field` → class `Subject`); return one `SchemaClassPayload` per model with `extraction_path='code'` (DANDI is the only code-introspection adapter)
- [X] T025 [P] [US1] Implement `extract_classes()` in three adapters: (a) `ingestion/src/undata/adapters/nwb.py` (YAML path, `extraction_path='yaml'`): iterate `self._raw["groups"]`; each group with `neurodata_type` becomes one class; child groups set `parent_class_name`; (b) `ingestion/src/undata/adapters/openminds.py` (JSON-LD path, `extraction_path='jsonld'`): one class per loaded file with class name from last segment of root `@type` URI; all properties are its members; (c) `ingestion/src/undata/adapters/aind.py` (JSON path, `extraction_path='json'`): one class per `_SCHEMA_FILES` entry; class name from `title` key or filename stem; all resolved properties are members
- [X] T026 [US1] Update `ingestion/src/undata/ingestion.py` `IngestionPipeline.ingest()`: after element bulk-POST call `adapter.extract_classes()`; for each `SchemaClassPayload` POST to `POST /api/v1/sources/{source_id}/classes`; then link each `element_source_local_id` to the class via `POST .../classes/{class_id}/elements`; log counts at INFO level
- [X] T062a ⚠️ [P] [US1] Unit test for `SchemaEnumeration` row creation: given a DataElement with `element_kind='enumeration'` and `allowed_values=["M","F","O"]`, assert three `SchemaEnumeration` rows are inserted with correct `value` and `position`; assert no rows for non-enumeration elements; must FAIL before T062b; test in `backend/tests/unit/test_element_classification.py`
- [X] T062b [P] [US1] Implement `SchemaEnumeration` row creation in `backend/src/services/schema_class.py`: when a `DataElement` is created or updated with `element_kind='enumeration'`, insert one `SchemaEnumeration` row per value in `allowed_values` (`value` from array item, `position` from array index, `label=None`)
- [X] T063a ⚠️ [P] [US1] Unit test for `DataElementChild` creation and depth guard: given a `DataElement` with `element_kind='complex'`, assert `DataElementChild` rows are created for each nested property; assert nesting beyond 10 levels raises `ValueError` logged as ERROR (no infinite loop); must FAIL before T063b; test in `backend/tests/unit/test_element_classification.py`
- [X] T063b [P] [US1] Implement `DataElementChild` row creation for complex elements in `backend/src/services/schema_class.py`: when a `DataElement` has `element_kind='complex'` (`data_type='object'`), resolve its nested property elements and insert `DataElementChild` rows; enforce max nesting depth of 10 with `ValueError` logged as ERROR

**Checkpoint**: `GET /schemas/{id}/classes` returns classes; DANDI uses `extraction_path='code'`; BIDS+NWB use `'yaml'`; openMINDS uses `'jsonld'`; AIND uses `'json'`

---

## Phase 4: User Story 2 — Validation Rules (Priority: P2)

**Goal**: Attach typed `ValidationRule` records to DataElements via CRUD API; classify every
rule mutation as BREAKING or NON_BREAKING using the 6-rule engine.

**Independent Test**: POST a `range` rule to an element; PUT narrowing it returns `breaking: true`;
PUT widening it returns `breaking: false`; DELETE returns `breaking: false`.

### Tests for User Story 2 ⚠️ Write FIRST — must FAIL before implementation

- [X] T027 [P] [US2] Unit test for `SemanticChangeClassifier` covering all 6 rule types: `enum_set` (narrow=breaking, widen=non-breaking), `range` (tighten min↑/max↓=breaking, loosen=non-breaking), `pattern` (add=breaking, remove=non-breaking), `type_constraint` (any change=breaking), `cardinality` (increase min or decrease max=breaking); test in `backend/tests/unit/test_semantic_classifier.py`
- [X] T028 [P] [US2] Contract test for `POST /api/v1/elements/{id}/validation-rules`: create `enum_set` rule → 201 + stable `id` returned; 409 on duplicate `rule_type`; 422 on invalid `rule_value` JSON; test in `backend/tests/contract/test_validation_rules_api.py`
- [X] T029 [P] [US2] Contract test for `GET /api/v1/elements/{id}/validation-rules`: returns all active rules ordered by `rule_type`; soft-deleted rules excluded; test in `backend/tests/contract/test_validation_rules_api.py`
- [X] T030 [P] [US2] Contract test for `PUT /api/v1/elements/{id}/validation-rules/{rule_id}`: narrow `enum_set` → `breaking=true`; widen `range` → `breaking=false`; response includes `change.old_value`, `change.new_value`; test in `backend/tests/contract/test_validation_rules_api.py`
- [X] T031 [P] [US2] Contract test for `DELETE /api/v1/elements/{id}/validation-rules/{rule_id}`: soft-deletes rule; response has `breaking=false`; rule absent from subsequent GET; test in `backend/tests/contract/test_validation_rules_api.py`

### Implementation for User Story 2

- [X] T032 [P] [US2] Implement `SemanticChangeClassifier` pure function `classify(rule_type, old_value, new_value) -> bool` in `backend/src/services/validation_rule.py` per the 6-rule logic in plan.md §SemanticChangeClassifier
- [X] T033 [US2] Implement `ValidationRuleService` in `backend/src/services/validation_rule.py`: `create()`, `update() -> (rule, change)`, `delete()`, `list()` — each mutation creates a `ValidationRuleChange` row via `SemanticChangeClassifier`; when `breaking=True`, query `DynamicSchemaElement` to find schemas containing this element and insert a new `SchemaChangeLog` row for each affected schema with `operation='RULE_CHANGE'`, `breaking=True`, `semantic_boundary_crossed=True`
- [X] T034 [US2] Add `GET`, `POST` endpoints for `/api/v1/elements/{element_id}/validation-rules` and `PUT`, `DELETE` for `/api/v1/elements/{element_id}/validation-rules/{rule_id}` in `backend/src/api/v1/elements.py`; return `ValidationRuleRead` and `ValidationRuleChangeRead` in responses

**Checkpoint**: All 4 CRUD endpoints functional; breaking-change classification matches unit tests

---

## Phase 5: User Story 3 — Schema Inheritance & Mixins (Priority: P3)

**Goal**: Support `parent_id` FK for single-parent inheritance and `SchemaMixin` for multiple
mixins on `DynamicSchema`; resolve full MRO via C3 algorithm; expose `/resolved` and
`/inheritance-tree` endpoints.

**Independent Test**: Create BaseSchema → ChildSchema (inherits) → attach ProvenanceMixin;
`GET /schemas/{child}/resolved` returns all elements from base + child + mixin in C3 order.

### Tests for User Story 3 ⚠️ Write FIRST — must FAIL before implementation

- [X] T035 [P] [US3] Unit test for `MROService.c3_linearize()`: simple A→B; diamond A→B,C→D; mixin precedence by position; cycle detection raises `CycleError`; depth > 20 raises `DepthError`; test in `backend/tests/unit/test_mro_service.py`
- [X] T036 [P] [US3] Contract test for `PUT /api/v1/schemas/{id}/parent`: set valid parent → 200; cycle → 409; depth > 20 → 422; parent not found → 404; test in `backend/tests/contract/test_schema_inheritance_api.py`
- [X] T037 [P] [US3] Contract test for `POST /api/v1/schemas/{id}/mixins` and `DELETE .../mixins/{mixin_id}`: attach `is_mixin=true` schema → 201; attach non-mixin → 400; duplicate attach → 409; delete → 204; test in `backend/tests/contract/test_schema_inheritance_api.py`
- [X] T038 [P] [US3] Contract test for `GET /api/v1/schemas/{id}/resolved`: 3-level chain returns all elements with `source_schema` annotation, no duplicates, child definition overrides parent on name collision; test in `backend/tests/contract/test_schema_inheritance_api.py`
- [X] T039 [P] [US3] Contract test for `GET /api/v1/schemas/{id}/inheritance-tree`: returns `nodes` + `edges` adjacency list matching contracts/rest-api.md §inheritance-tree shape; test in `backend/tests/contract/test_schema_inheritance_api.py`

### Implementation for User Story 3

- [X] T040 [P] [US3] Implement `MROService` in `backend/src/services/schema_mro.py`: `c3_linearize(schema_id, db) -> list[UUID]` using async recursive DB traversal; LRU cache (max 256 entries, keyed on `schema_id + version_num`); `detect_cycle(schema_id, proposed_parent_id, db) -> bool` via `WITH RECURSIVE` CTE; `check_depth(schema_id, db) -> int`
- [X] T041 [US3] Add `PUT /api/v1/schemas/{schema_id}/parent` endpoint in `backend/src/api/v1/schemas.py`: validate cycle-free + depth ≤ 20 via `MROService`; update `DynamicSchema.parent_id`; record `SchemaChangeLog` with `operation='UPDATE_PARENT'`
- [X] T042 [US3] Add `POST /api/v1/schemas/{schema_id}/mixins` and `DELETE .../mixins/{mixin_id}` endpoints in `backend/src/api/v1/schemas.py`: validate `mixin_id.is_mixin=TRUE`; validate cycle-free; insert/delete `SchemaMixin` row with position; record `SchemaChangeLog`
- [X] T043 [US3] Add `GET /api/v1/schemas/{schema_id}/resolved` endpoint in `backend/src/api/v1/schemas.py`: call `MROService.c3_linearize()` to get ordered schema IDs; fetch elements for each via `DynamicSchemaElement`; deduplicate by `source_local_id` (child wins, per FR-011); return `ResolvedSchemaResponse` with `mro` list and annotated elements
- [X] T044 [P] [US3] Add `GET /api/v1/schemas/{schema_id}/inheritance-tree` endpoint in `backend/src/api/v1/schemas.py`: build adjacency list from `parent_id` and `SchemaMixin` rows recursively; return `InheritanceTreeResponse`

**Checkpoint**: Inheritance chain + mixin resolution work; cycle rejected with 409; `/resolved` returns correct element precedence

---

## Phase 6: User Story 4 — Schema Provenance (Priority: P4)

**Goal**: Record every schema mutation in `SchemaChangeLog` with W3C PROV-DM semantics;
seed and expose the ProvenanceMixin; provide JSON-LD provenance endpoints.

**Independent Test**: Update a schema (add element); `GET /schemas/{id}/changelog` shows entry
with `actor_id/timestamp/diff/breaking`; attach ProvenanceMixin; `/resolved` shows 4 `prov_` elements;
`GET /schemas/{id}/provenance` returns valid PROV-DM JSON-LD.

### Tests for User Story 4 ⚠️ Write FIRST — must FAIL before implementation

- [X] T045 [P] [US4] Contract test for `GET /api/v1/schemas/{id}/changelog`: after CREATE + ADD_ELEMENT + REMOVE_ELEMENT operations, returns paginated entries with `operation/actor_id/timestamp/diff/breaking` fields; assert REMOVE_ELEMENT entry has `breaking=true`; `breaking_only=true` filter works; test in `backend/tests/contract/test_schema_provenance_api.py`
- [X] T046 [P] [US4] Contract test for `POST /api/v1/schemas/{id}/provenance-mixin` and `DELETE`: attach → 201 + `attached=true`; detach → 204; `GET /schemas/{id}/resolved` after attach shows 4 `prov_` elements with `source_schema='ProvenanceMixin'`; test in `backend/tests/contract/test_schema_provenance_api.py`
- [X] T047 [P] [US4] Contract test for `GET /api/v1/schemas/{id}/provenance`: response `Content-Type` is `application/ld+json`; `@graph` contains `prov:Entity`, `prov:Activity`, `prov:Agent` nodes with required PROV-DM fields; test in `backend/tests/contract/test_schema_provenance_api.py`
- [X] T048 [P] [US4] Contract test for `GET /api/v1/elements/{id}/provenance`: returns PROV-DM JSON-LD for element version history; `Content-Type: application/ld+json`; test in `backend/tests/contract/test_schema_provenance_api.py`

### Implementation for User Story 4

- [X] T049 [P] [US4] Implement `SchemaChangeLogService` in `backend/src/services/schema_changelog.py`: `record(schema_id, operation, actor_id, diff, breaking, reason, activity_type)` inserts `SchemaChangeLog` row; `list(schema_id, breaking_only, page, size)` paginated query; `to_prov_jsonld(schema_id)` assembles W3C PROV-DM JSON-LD from `SchemaChangeLog` + `UserProfile` rows
- [X] T050 [US4] Instrument existing `SchemaService` mutations in `backend/src/services/schema.py` to call `SchemaChangeLogService.record()` on every mutation (create, add_element, remove_element); instrument the `PUT /parent`, `POST /mixins`, `DELETE /mixins` endpoints added in T041/T042
- [X] T051 [US4] Add `GET /api/v1/schemas/{schema_id}/changelog` endpoint in `backend/src/api/v1/schemas.py`: calls `SchemaChangeLogService.list()`; supports `?breaking_only=true&page=N&size=N`
- [X] T052 [US4] Add `GET /api/v1/schemas/{schema_id}/provenance` endpoint in `backend/src/api/v1/schemas.py`: calls `SchemaChangeLogService.to_prov_jsonld()`; sets `Content-Type: application/ld+json`
- [X] T053 [US4] Add `POST /api/v1/schemas/{schema_id}/provenance-mixin` and `DELETE .../provenance-mixin` endpoints in `backend/src/api/v1/schemas.py`: look up system ProvenanceMixin ID (cached at startup); call `POST /mixins` logic; record changelog entry with `activity_type='mixin_attach'`
- [X] T054 [P] [US4] Add `GET /api/v1/elements/{element_id}/provenance` endpoint in `backend/src/api/v1/elements.py`: assemble PROV-DM JSON-LD from `DataElementVersion` history + `AuditLog` entries; return `Content-Type: application/ld+json`

**Checkpoint**: All provenance endpoints functional; `SchemaChangeLog` populated on every mutation; PROV-DM JSON-LD validates against W3C shape

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, performance checks, code quality

- [X] T055 Create end-to-end integration test in `backend/tests/integration/test_schema_enrichment_pipeline.py`: ingest mock source → POST classes using mock AIND adapter (`extraction_path='json'`) and mock DANDI adapter (`extraction_path='code'`) to exercise both structured-file and code-introspection extraction paths → POST validation rules → attach ProvenanceMixin → GET /resolved; assert class nodes with `node_kind='class'`, validation rules returned, 4 prov_ elements present in resolved view
- [X] T056 [P] Run quickstart.md validation checklist: execute every `curl` scenario in `specs/005-schema-enrichment/quickstart.md`; all expected responses must match
- [X] T057 [P] Run full backend test suite: `cd backend && uv run pytest tests/ -v` — all tests must pass including existing 002 tests
- [X] T058 [P] Run linting and formatting: `cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/` — 0 violations; `cd ingestion && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
- [X] T059 [P] Verify performance targets: `GET /schemas/{id}/resolved` (3-level, 20 elements) < 200 ms p95; `GET /schemas/{id}/classes` (50 elements) < 500 ms p95; MRO cache hit < 5 ms; confirm with `time curl` or pytest timing markers
- [X] T060 [P] Run ingestion test suite after adapter updates: `cd ingestion && uv run pytest tests/ -q` — all existing tests plus new T014/T015 dual-path tests must pass; assert DANDI uses `extraction_path='code'`; assert BIDS and NWB use `extraction_path='yaml'`; assert openMINDS uses `extraction_path='jsonld'`; assert AIND uses `extraction_path='json'`
- [X] T061 [P] Update `CLAUDE.md` Recent Changes section to document 005-schema-enrichment: dual-path class extraction (JSON/code), ValidationRule breaking-change classifier, C3 MRO, SchemaChangeLog PROV-DM, ProvenanceMixin; migrations 0004–0009
- [X] T064 [P] Implement mixin soft-delete safety: when a `DynamicSchema` with `is_mixin=TRUE` is soft-deleted, verify existing `SchemaMixin` rows are NOT cascade-deleted (FK must be `ON DELETE RESTRICT` or handled in service layer); add assertion to existing test file `backend/tests/contract/test_schema_inheritance_api.py` [⚠️ test added to existing test file — write failing assertion before implementing the RESTRICT constraint]
- [X] T065 [P] Implement mixin element-name collision WARNING: in `MROService.c3_linearize()` (or `GET /resolved` handler), when two schemas in the resolved MRO define the same element name, emit a structured `WARNING` log entry via the existing JSON logger with fields `schema_id`, `element_name`, `winning_source`, `losing_source`; add assertion to existing test file `backend/tests/unit/test_mro_service.py` [⚠️ test added to existing test file — write failing assertion before implementing the warning emission]
- [X] T066 [P] Implement ValidationRule cascade soft-delete: when a `DataElement` is soft-deleted (via existing element delete endpoint), also soft-delete all active `ValidationRule` rows for that element (`deleted_at = now()`); add assertion to existing test file `backend/tests/contract/test_validation_rules_api.py` [⚠️ test added to existing test file — write failing assertion before implementing cascade delete]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T002 and T003 can run in parallel with T001 as verification
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; T004→T005→T006/T007/T008 (migration chain, 0006/0007/0008 parallel after 0005); T009 after T008; T010/T011 parallel after migrations drafted; T012 last
- **US1 (Phase 3)**: Depends on Phase 2 complete; tests T013–T018 first then implementation; T062a must precede T062b; T063a must precede T063b
- **US2 (Phase 4)**: Depends on Phase 2 complete; independent of US1 (different service + endpoint files)
- **US3 (Phase 5)**: Depends on Phase 2 complete; uses `SchemaChangeLog` written in US4 service — implement T049 `SchemaChangeLogService` before T041/T042 if doing US3 before US4, OR stub the record() call
- **US4 (Phase 6)**: Depends on Phase 2 complete; instruments mutations from US3
- **Polish (Phase 7)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Start after Phase 2 — no dependency on US2/US3/US4
- **US2 (P2)**: Start after Phase 2 — no dependency on US1/US3/US4; T033 (`ValidationRuleService`) depends on `SchemaChangeLogService` (T049) — stub or pre-implement T049 before T033
- **US3 (P3)**: Start after Phase 2 — depends on `SchemaChangeLogService` from US4 (stub or pre-implement T049)
- **US4 (P4)**: Start after Phase 2 — instruments US3 endpoints; best implemented after US3

### Within Each User Story

1. Tests written first ⚠️ and MUST FAIL before implementation starts
2. Protocol/model tasks [P] before service tasks
3. Service tasks before endpoint tasks
4. Core implementation before integration pipeline update

### Parallel Opportunities

- All Setup T002/T003 can run alongside T001
- Migrations T006/T007/T008 can run in parallel (different tables)
- T010/T011 (ORM + Pydantic) can run in parallel
- US1 tests T013–T018 all parallel
- US1 adapter implementations T023/T024/T025 all parallel (different files)
- US2 tests T027–T031 all parallel
- US3 tests T035–T039 all parallel; T040/T044 parallel
- US4 tests T045–T048 all parallel; T049/T054 parallel

---

## Parallel Example: User Story 1 (Schema Class Analysis)

```bash
# Step 1 — Run all US1 tests in parallel (must fail first):
T013: unit test element_kind derivation in backend/tests/unit/test_element_classification.py
T014: unit test extract_classes() structured-file path (BIDS→yaml, openMINDS→jsonld, AIND→json) in ingestion/tests/unit/test_adapter_class_extraction.py
T015: unit test extract_classes() code-introspection path (DANDI) + YAML path (NWB) in ingestion/tests/unit/test_adapter_class_extraction.py
T016: contract test GET /schemas/{id}/classes in backend/tests/contract/test_schema_classes_api.py
T017: contract test POST/GET /sources/{id}/classes in backend/tests/contract/test_schema_classes_api.py
T018: contract test POST .../classes/{id}/elements in backend/tests/contract/test_schema_classes_api.py

# Step 2 — Implement Protocol + 5 adapters in parallel:
T019: SchemaClassPayload + Protocol in ingestion/src/undata/models.py + adapters/base.py
T023: BIDS extract_classes() in adapters/bids.py          ← YAML path
T024: DANDI extract_classes() in adapters/dandi.py         ← code-introspection path
T025: NWB + openMINDS + AIND extract_classes()             ← yaml / jsonld / json paths

# Step 3 — Backend service + endpoints (sequential):
T020: SchemaClassService in backend/src/services/schema_class.py
T021: GET /schemas/{id}/classes endpoint
T022: POST/GET /sources/{id}/classes endpoints
T026: IngestionPipeline.ingest() update
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (schema class analysis, both extraction paths)
4. **STOP and VALIDATE**: `GET /schemas/{id}/classes` returns classes; DANDI uses `extraction_path='code'`; BIDS+NWB use `'yaml'`; openMINDS uses `'jsonld'`; AIND uses `'json'`
5. Deploy / demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 (P1) → classes extracted via dual path → validate → demo
3. US2 (P2) → validation rules + breaking-change classification → validate
4. US3 (P3) → inheritance, mixins, MRO resolution → validate
5. US4 (P4) → provenance changelog + JSON-LD → validate
6. Polish → full suite green

### Parallel Team Strategy

With multiple developers after Phase 2:
- **Dev A**: US1 (P1) — adapter dual-path extraction + `/classes` endpoint
- **Dev B**: US2 (P2) — `ValidationRuleService` + `/validation-rules` CRUD
- **Dev C**: US3 + US4 (P3 + P4) — MRO service + provenance (US3 and US4 are tightly coupled)

---

## Notes

- [P] tasks = different files, no blocking dependencies — can run concurrently
- [US*] label maps each task to its user story for traceability
- **Dual extraction path**: DANDI→`extraction_path='code'`; BIDS→`'yaml'`; NWB→`'yaml'`; openMINDS→`'jsonld'`; AIND→`'json'` — `extraction_path` is informational only and NOT stored in the DB. **Note**: 006-dual-path-adapters (T002, T035) renames format-specific values to path-type: `'yaml'`/`'json'`/`'jsonld'` → `'file'`; `'code'` retained.
- `SchemaClassPayload.extraction_path` is an adapter implementation detail; the backend API contract is format-agnostic
- `semantic_boundary_crossed` on `SchemaChangeLog` is set by `ValidationRuleService` when a breaking rule change affects elements that belong to an active schema
- Tests MUST fail before implementation; commit test files before writing production code
- Mark each task `[x]` in this file immediately upon completion
- Stop at each phase checkpoint to validate the story independently before proceeding
