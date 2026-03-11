# Tasks: Dynamic Schema Construction and Migration API (004)

**Input**: Design documents from `/specs/004-migration-api/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/rest-api.md ✅, quickstart.md ✅

**Tests**: Included per constitution Principle II (TDD is NON-NEGOTIABLE).
Tests must be written FIRST and must FAIL before any implementation task begins.

**Organization**: Tasks grouped by user story. US1 (schema construction) → US2 (pathway
definition) → US3 (migration execution) → US4 (schema diff). US2–US4 are independently
testable but build on the BackendClient and models established in Phase 2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 maps to user stories in spec.md

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create the `migration-api/` service from scratch with all infrastructure files.

- [X] T001 Create migration-api/ directory structure: src/api/v1/, src/services/, src/tasks/, src/models.py, src/main.py; tests/unit/, tests/contract/, tests/fixtures/; pyproject.toml with FastAPI 0.111+, Pydantic v2, httpx 0.27+, linkml-runtime 1.8+, simpleeval 1.0+, RestrictedPython 7.x, Celery 5.x, redis 5.x in migration-api/pyproject.toml (sssom-utils removed — not available under that PyPI name; SSSOM TSV export deferred)
- [X] T002 [P] Create migration-api/Dockerfile: Python 3.12, uv venv, install deps, expose port 8004 in migration-api/Dockerfile
- [X] T003 [P] Create migration-api/docker-compose.yml: migration-api service (port 8004) + celery worker + redis 7.x; environment vars BACKEND_URL, REDIS_URL, SECRET_KEY in migration-api/docker-compose.yml
- [X] T004 [P] Create migration-api/.gitignore with Python patterns (__pycache__, .venv, *.pyc, dist/, *.egg-info, .env) in migration-api/.gitignore
- [X] T005 Create migration-api/src/main.py: FastAPI app with lifespan, include routers for /schemas, /pathways, /migrate, /diff, /jobs; JSON structured logging; health endpoint GET /health in migration-api/src/main.py
- [X] T006 Create migration-api/tests/conftest.py: AsyncClient fixture wired to app, respx mock fixture for BackendClient calls, sample pathway/schema fixtures in migration-api/tests/conftest.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend /pathways extension, shared Pydantic models, BackendClient, and Celery
config that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 Extend 002-schema-backend: add MigrationPathway ORM model (id UUID PK, name TEXT, source_schema_id UUID, target_schema_id UUID, direction TEXT, status TEXT default "active", inverse_pathway_id UUID nullable, steps JSONB, created_at TIMESTAMPTZ server_default now(), version_num INT default 0) to backend/src/models/db.py; add Alembic migration 0010_add_migration_pathway.py in backend/src/db/migrations/versions/
- [X] T008 Extend 002-schema-backend: implement POST /pathways (create with step validation), GET /pathways (filter by source_schema_id, target_schema_id, direction, status), GET /pathways/{id}, PUT /pathways/{id}, DELETE /pathways/{id} (soft-delete) in backend/src/api/v1/pathways.py; register router in backend/src/main.py
- [X] T009 Create shared Pydantic request/response models in migration-api/src/models.py: SchemaConstructionRequest, SchemaConstructionResponse, PathwayCreateRequest, PathwayResponse, MigrateRequest, MigrateResponse, DiffRequest, DiffResponse, JobStatus; internal dataclasses MigrationContext, MappingStep, MigrationReport, StepResult, ValidationResult, Violation, SchemaDiff, AsyncJob per data-model.md
- [X] T010 Implement BackendClient: async httpx client wrapping 002-schema-backend API; methods get_element(id), get_elements(ids), get_mapping(id), get_schema(id), create_schema(payload), get_pathway(id), create_pathway(payload), update_pathway(id, payload) in migration-api/src/services/backend_client.py
- [X] T011 Configure Celery with Redis broker and result backend; register tasks package; configure task serialization (JSON); add worker entrypoint in migration-api/src/tasks/celery_app.py

**Checkpoint**: Foundation ready — US1, US2, US3, US4 can proceed (US2+ depend on T007–T008)

---

## Phase 3: User Story 1 — Dynamic Schema Construction (Priority: P1) 🎯 MVP

**Goal**: Clients can assemble a custom LinkML schema from stored data elements via API.

**Independent Test**: POST /schemas with valid element_ids returns a LinkML YAML that
passes `linkml-runtime` validation. Unknown IDs return 422. >50 elements return 202+job_id.

### Tests for User Story 1 (write FIRST — must FAIL)

- [X] T012 [P] [US1] Write failing unit tests for SchemaBuilder: test build() produces valid SchemaDefinition with correct slots and classes, test unknown IDs raise ValueError, test name collision detection raises ConflictError with details in migration-api/tests/unit/test_schema_builder.py
- [X] T013 [P] [US1] Write failing contract tests: POST /schemas with 3 valid element_ids → 200 + linkml_yaml; POST /schemas with unknown id → 422 + unknown_ids in detail; POST /schemas with 51 elements → 202 + job_id; GET /schemas/{id} → stored schema; GET /schemas/{id}/versions → list in migration-api/tests/contract/test_schemas.py

### Implementation for User Story 1

- [X] T014 [P] [US1] Implement SchemaBuilder.build(classes, elements): fetch elements from BackendClient, construct linkml_runtime SchemaDefinition with SlotDefinition + ClassDefinition, serialize to YAML + JSON-LD, detect name collisions across source schemas in migration-api/src/services/schema_builder.py
- [X] T015 [P] [US1] Implement POST /schemas endpoint: validate element_ids (call backend), detect collisions (409), dispatch sync if ≤50 elements else enqueue Celery task + return 202, save result to backend via BackendClient.create_schema() if save=true in migration-api/src/api/v1/schemas.py
- [X] T016 [P] [US1] Implement GET /schemas/{id} (fetch from backend, return linkml_yaml) and GET /schemas/{id}/versions (list all versions for schema name) in migration-api/src/api/v1/schemas.py
- [X] T017 [US1] Implement async build_schema Celery task: same logic as sync path but updates job status in Redis at each step (0%→50%→100%); stores result JSON in Redis on completion in migration-api/src/tasks/build_schema.py
- [X] T018 [US1] Implement GET /jobs/{id} polling endpoint: read AsyncJob from Redis, return status/progress/result/error in migration-api/src/api/v1/jobs.py

**Checkpoint**: US1 complete — POST /schemas + async jobs working

---

## Phase 4: User Story 2 — Migration Pathway Definition (Priority: P2)

**Goal**: Data stewards can register, retrieve, compose, and manage migration pathways.

**Independent Test**: POST /pathways with valid source/target schema UUIDs and mapped step
IDs returns 201 with a stored pathway. POST /pathways/compose(A→B, B→C) returns A→C pathway.

### Tests for User Story 2 (write FIRST — must FAIL)

- [X] T019 [P] [US2] Write failing unit tests for pathway validation: unknown mapping_id → rejected; auto-inverse derivation when all steps have inverses; pathway composition intermediate schema mismatch → error; BROKEN detection logic in migration-api/tests/unit/test_pathway_service.py
- [X] T020 [P] [US2] Write failing contract tests: POST /pathways valid → 201 + inverse_pathway_id auto-set; POST /pathways unknown mapping_id → 422; GET /pathways?source_schema_id=X → list; GET /pathways/{id} → full steps resolved; POST /pathways/compose valid → 200 composed pathway; POST /pathways/compose schema mismatch → 422 in migration-api/tests/contract/test_pathways.py

### Implementation for User Story 2

- [X] T021 [US2] Implement POST /pathways: validate all mapping_id refs exist via BackendClient.get_mapping(); detect source+target+direction conflict (409); auto-derive inverse pathway when all steps have inverse_mapping_id; persist via BackendClient.create_pathway() in migration-api/src/api/v1/pathways.py
- [X] T022 [P] [US2] Implement GET /pathways (filter by source_schema_id, target_schema_id, direction, status), GET /pathways/{id} (resolve full step details), PUT /pathways/{id} (update steps, re-validate, set status=active/broken), DELETE /pathways/{id} (soft-delete via backend) in migration-api/src/api/v1/pathways.py
- [X] T023 [US2] Implement POST /pathways/compose: fetch pathway_a and pathway_b, validate pathway_a.target_schema_id == pathway_b.source_schema_id (else 422), concatenate steps with re-indexed positions, optionally persist composed pathway in migration-api/src/api/v1/pathways.py

**Checkpoint**: US2 complete — full pathway lifecycle working

---

## Phase 5: User Story 3 — Data Migration Execution (Priority: P3)

**Goal**: Data engineers can migrate records between schemas using registered pathways.

**Independent Test**: POST /migrate with a test record + valid pathway_id returns output
record + full MigrationReport accounting for every input field. Batch of 3 records with
one failing step: 2 records succeed, 1 has status FAIL — other records not affected.

### Tests for User Story 3 (write FIRST — must FAIL)

- [X] T024 [P] [US3] Write failing unit tests for ExpressionEvaluator: simpleeval arithmetic expression "input_0 * 365" → correct result; string concat "input_0 + ' ' + input_1" → correct; unsafe expression (import, exec) → EvalError; plugin dispatch to named callable → routed correctly in migration-api/tests/unit/test_expression_eval.py
- [X] T025 [P] [US3] Write failing unit tests for PathwayExecutor: single step identity mapping → StepResult OK; step raising ValueError → StepResult ERROR, execution halts for that record; passthrough_fields populated for unmapped input fields; MigrationReport.overall_status PASS/FAIL/PARTIAL logic in migration-api/tests/unit/test_pathway_executor.py
- [X] T026 [P] [US3] Write failing contract tests: POST /migrate single record valid → 200 + report with steps_applied; POST /migrate BROKEN pathway → 409 + broken_step; POST /migrate 101 records → 202 + job_id; POST /migrate 3 records, 1 failing step → all 3 records in results, 1 with FAIL, 2 with PASS in migration-api/tests/contract/test_migrate.py

### Implementation for User Story 3

- [X] T027 [P] [US3] Implement ExpressionEvaluator: Tier 1 uses simpleeval.SimpleEval with allowed_names={input_0, input_1, ...}; Tier 2 loads plugin by dotted module.function string via importlib, wraps in RestrictedPython compile context; raises EvalError on unsafe code or import attempt in migration-api/src/services/expression_eval.py
- [X] T028 [US3] Implement PathwayExecutor.execute(context): resolve pathway steps from BackendClient; for each step call ExpressionEvaluator with input values; collect StepResult; gather unmapped input fields as passthrough (with WARN log per spec FR-013); validate output record against target schema; return complete MigrationReport in migration-api/src/services/pathway_executor.py
- [X] T029 [US3] Implement POST /migrate endpoint: check pathway status == "active" (else 409 BROKEN); dispatch sync if ≤100 records (call PathwayExecutor per record, collect results); dispatch Celery batch_migrate task if >100 records (return 202 + job_id); include per-record failure isolation — wrap each record execution in try/except in migration-api/src/api/v1/migrate.py
- [X] T030 [US3] Implement batch_migrate Celery task: iterate records in chunks of 50; call PathwayExecutor per record; update job progress in Redis; collect all results; store MigrateResponse in Redis on completion in migration-api/src/tasks/batch_migrate.py

**Checkpoint**: US3 complete — full migration execution with reports + async batching

---

## Phase 6: User Story 4 — Schema Diff and Compatibility Analysis (Priority: P4)

**Goal**: Architects can compare two schemas and get a structured compatibility report with
a draft migration pathway assembled from existing mappings.

**Independent Test**: POST /diff on two schemas with 3 added, 2 removed, 1 type-changed
element returns SchemaDiff with exactly those classifications and correct coverage assessment.

### Tests for User Story 4 (write FIRST — must FAIL)

- [X] T031 [P] [US4] Write failing unit tests for SchemaDiffer: test all 6 diff types (ADDED, REMOVED, RENAMED via alias_group, TYPE_CHANGED, CONSTRAINT_CHANGED, DESCRIPTION_CHANGED) computed correctly; FULL coverage when all diffs have registered mappings; PARTIAL coverage with gap list; draft_pathway assembled from existing mappings in migration-api/tests/unit/test_schema_differ.py
- [X] T032 [P] [US4] Write failing contract test for POST /diff: known source+target → 200 SchemaDiff with correct coverage field and all diff categories populated; identical schemas → 200 with all lists empty and coverage=FULL in migration-api/tests/contract/test_diff.py

### Implementation for User Story 4

- [X] T033 [US4] Implement SchemaDiffer.diff(source_schema_id, target_schema_id): fetch both schema element sets from BackendClient; compute set difference for ADDED/REMOVED; check alias_group memberships for RENAMED; compare element types for TYPE_CHANGED; compare constraint/description for others; assess coverage by checking registered mappings via BackendClient; assemble draft PathwaySummary from mapped elements in migration-api/src/services/schema_differ.py
- [X] T034 [US4] Implement POST /diff endpoint: validate both schema_ids exist (404 if not), call SchemaDiffer.diff(), return SchemaDiff response; if coverage == FULL or PARTIAL also include draft_pathway with gaps marked in migration-api/src/api/v1/diff.py

**Checkpoint**: All 4 user stories complete

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T035 Run `uv run ruff check migration-api/src/ migration-api/tests/` and `uv run ruff format migration-api/src/ migration-api/tests/`; fix all lint errors in migration-api/ source files
- [X] T036 Run `uv run pytest migration-api/tests/ -v` from repo root; verify all unit + contract tests pass
- [X] T037 Verify docker-compose.yml: run `docker compose up -d` in migration-api/, confirm migration-api health endpoint returns 200, confirm Redis connection, confirm Celery worker connects
- [X] T038 Update /Users/satra/software/undata/CLAUDE.md: add migration-api tech stack entry (FastAPI 0.111+ + Celery 5.x + Redis + simpleeval + RestrictedPython + linkml-runtime), add port 8004, add service description

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: T001 first (creates structure); T002–T004 parallel; T005 after T001; T006 after T005
- **Phase 2 (Foundational)**: T007 first (backend model); T008 after T007 (backend routes); T009 after T001 (models); T010 after T009 (BackendClient); T011 after T001 (Celery); all must complete before Phase 3+
- **US1 (Phase 3)**: Tests T012–T013 after Phase 2; Implementations T014–T018 after tests fail; T017–T018 (Celery/jobs) after T015
- **US2 (Phase 4)**: Tests T019–T020 after Phase 2 + T008; Implementations T021–T023 after tests fail
- **US3 (Phase 5)**: Tests T024–T026 after Phase 2; T025 depends on T027 (ExpressionEvaluator used in executor); Implementations T027–T030; T028 after T027; T029 after T028; T030 after T028
- **US4 (Phase 6)**: Tests T031–T032 after Phase 2; Implementations T033–T034 after tests fail; independent of US2/US3
- **Polish (Phase 7)**: T035→T036→T037 sequential; T038 parallel with T035

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 only — no dependency on US2/US3/US4
- **US2 (P2)**: Depends on Phase 2 + backend /pathways (T007–T008)
- **US3 (P3)**: Depends on Phase 2 + US2 (pathway retrieval) + US1 (schema validation)
- **US4 (P4)**: Depends on Phase 2 only — can be developed in parallel with US2/US3

### MVP Scope

Implement Phase 1 + Phase 2 + Phase 3 (US1) only for minimal demonstrable value:
a working schema construction endpoint that produces valid LinkML from element IDs.
US2–US4 can follow in subsequent iterations.

---

## Parallel Execution Examples

**Within Phase 2**: T009, T010, T011 can all run in parallel after T001 (different files).

**Within US1**: T012 and T013 are parallel (different test files). T014, T015, T016 are
parallel once tests are failing (different service/endpoint files).

**US4 parallel with US2/US3**: T031–T034 have no dependency on US2 or US3 — can be
developed alongside them by a separate agent.
