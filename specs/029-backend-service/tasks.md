# Tasks: Backend Service

**Input**: Design documents from `/specs/029-backend-service/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — constitution requires TDD. Conformance tests before DatabaseBackend, GraphQL tests before resolvers.

**Organization**: 7 user stories mapped to 6 implementation phases. US3+US6 merged (import + seed = one flow). US7 (tests) integrated throughout.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1–US7)
- All paths relative to `backend/` unless noted

## Phase 1: Setup

**Purpose**: Clean project structure, remove broken artifacts

- [X] T001 Delete all stale files from brainstorm v1 backend — remove old routes, services, migrations that don't match the plan structure
- [X] T002 Create clean directory structure per plan: `src/{core,db,storage,graphql,services}/`, `tests/`, `seed/`
- [X] T003 Update `pyproject.toml` — ensure deps match plan (fastapi, sqlalchemy[asyncio], asyncpg, strawberry-graphql[fastapi], pydantic-settings, httpx, pytest, pytest-asyncio, ruff)

**Checkpoint**: Clean directory structure, no stale imports

---

## Phase 2: Foundational — Docker + Database (US1)

**Purpose**: Running stack with health endpoint — BLOCKS all other work

**⚠️ CRITICAL**: No backend code work until docker compose up succeeds

- [ ] T004 [US1] Rewrite `docker-compose.yml` — PostgreSQL 16 (pgvector) + backend service only. Remove Keycloak, Redis, migration-api, celery. Backend on port 8002, DB on 5432
- [ ] T005 [US1] Rewrite `Dockerfile` — Python 3.14-slim, uv, install undata-library from ../library (editable), install backend with dev deps, expose 8002
- [ ] T006 [US1] Rewrite `entrypoint.sh` — create tables via Python script, then exec uvicorn with --reload for dev
- [ ] T007 [US1] Rewrite `src/db/session.py` — async engine factory (`create_async_engine` with asyncpg), `AsyncSessionLocal` session maker, `Base` declarative base
- [ ] T008 [US1] Rewrite `src/db/models.py` — ORM models for all 8 tables (Element, Schema, Value, ValueSet, CurationFlag, Contribution, RunSummary, UserProfile) with UUID PKs, JSONB columns, server_default timestamps
- [ ] T009 [US1] Rewrite `src/core/config.py` — pydantic-settings Settings class with DATABASE_URL, LOG_LEVEL, UNDATA_BASE_URL
- [ ] T010 [P] [US1] Keep/update `src/core/logging.py` — structured JSON logging with pythonjsonlogger
- [ ] T011 [US1] Rewrite `src/main.py` — FastAPI app with lifespan (create_all on startup), CORS middleware, HTTP request logging middleware (method/path/status/duration), structured error handlers (ValidationError → 422, DB errors → 503, unknown → 500 with JSON body), health endpoint returning DB status, minimal GraphQL mount placeholder
- [ ] T012 [US1] Verify: `docker compose up -d && curl http://localhost:8002/health` returns 200 with `{"status": "ok"}`

**Checkpoint**: Stack starts, health returns 200, GraphQL playground accessible at /graphql

---

## Phase 3: User Story 2 — DatabaseBackend (Priority: P1)

**Goal**: DatabaseBackend passes all 52 StorageBackend conformance tests from feature 028.

**Independent Test**: `uv run pytest tests/test_database_backend.py -v` — 52 tests pass

### Tests

- [ ] T013 [US2] Write `tests/conftest.py` — test database URL, async engine fixture, per-test transaction with rollback, create_all/drop_all around test session
- [ ] T014 [US2] Write `tests/test_database_backend.py` — port conformance tests from `library/tests/test_storage_protocol.py`, parametrize for DatabaseBackend against real PostgreSQL

### Implementation

- [ ] T015 [US2] Implement `DatabaseEntityStore` in `src/storage/database_backend.py` — read/write/list/exists/delete/merge_provenance/count/find_by_hash using SQLAlchemy async queries on Element/Schema/Value/ValueSet models
- [ ] T016 [P] [US2] Implement `DatabaseFlagStore` in `src/storage/database_backend.py` — write_flag/read_flags/resolve_flag using CurationFlag model
- [ ] T017 [P] [US2] Implement `DatabaseRunStore` in `src/storage/database_backend.py` — save_summary/load_previous/list_runs using RunSummary model
- [ ] T018 [US2] Implement `DatabaseBackend` composite class in `src/storage/database_backend.py` — entities + flags + runs properties, constructor takes async session
- [ ] T019 [US2] Run conformance tests: `uv run pytest tests/test_database_backend.py -v` — all 52 must pass

**Checkpoint**: DatabaseBackend satisfies StorageBackend protocol. 52 conformance tests green.

---

## Phase 4: User Stories 3+6 — Registry Import + Seed Data (Priority: P1)

**Goal**: Import flat-file registry into DB via DatabaseBackend. docker compose up starts with seed data.

**Independent Test**: Start stack, query browseElements — returns entities

- [ ] T020 [US3] Rewrite `src/services/import_service.py` — async function that reads YAML files from a directory and calls `DatabaseBackend.entities.write()` for each entity type, `flags.write_flag()` for curation flags, `runs.save_summary()` for run summaries. Must be idempotent: use upsert (ON CONFLICT sha256 DO UPDATE provenance) so re-imports merge provenance without duplicating entities. Returns counts dict.
- [ ] T021 [US6] Create `seed/` directory with sample YAML files — ~50 elements, ~20 schemas, ~30 values, ~5 valuesets, ~3 curation flags, ~1 run summary (curated from library pipeline output)
- [ ] T022 [US6] Add seed logic to `entrypoint.sh` — on startup, check if DB is empty (count elements), if empty run import_service on seed/ directory
- [ ] T023 [US3] Add `importRegistry` mutation to GraphQL — accepts registry path, calls import_service, returns counts
- [ ] T024 [US6] Verify: `docker compose down -v && docker compose up -d` → wait → `curl http://localhost:8002/graphql` query browseElements returns >0 results

**Checkpoint**: Stack starts with seed data. Import mutation works.

---

## Phase 5: User Story 4 — Complete GraphQL API (Priority: P1)

**Goal**: All queries and mutations from the 027 contract work against the database.

**Independent Test**: GraphQL introspection shows all types/queries/mutations. Each query returns expected data.

### Tests

- [ ] T025 [US7] Write `tests/test_graphql_queries.py` — tests for all query resolvers: element, schema, value, valueset lookups; browseElements/Schemas/Values/Transforms with pagination; curationQueue; runSummaries; latestRun
- [ ] T026 [US7] Write `tests/test_graphql_mutations.py` — tests for: resolveFlag, batchResolveFlags, submitContribution, reviewContribution, triggerPipelineRun, importRegistry

### Implementation — Types

- [ ] T027 [US4] Rewrite `src/graphql/types.py` — Strawberry types matching 027 contract: Element, Schema, Value, ValueSet, CurationFlag, Contribution, RunSummary, OntologyAnnotation, ProvenanceEntry, PageInfo, all Connection/Edge types, all enums (FlagType, FlagStatus, ContributionType, ContributionStatus, CurationStatus, DataType, EntityType)

### Implementation — Query Resolvers

- [ ] T028 [US4] Implement single-entity lookups in `src/graphql/resolvers.py` — element(sha256), schema(sha256), value(sha256), valueset(sha256) using DatabaseBackend.entities.read()
- [ ] T029 [US4] Implement browse queries with Relay cursor pagination in `src/graphql/resolvers.py` — browseElements(source, dataType, ontology, curationStatus, searchText, first, after), browseSchemas, browseValues, browseTransforms. Cursors: base64(created_at|id)
- [ ] T030 [US4] Implement curation queries in `src/graphql/resolvers.py` — curationQueue(flagType, status, first, after), contributions(status, first, after)
- [ ] T031 [US4] Implement pipeline queries in `src/graphql/resolvers.py` — runSummaries(source, first, after), latestRun(source)

### Implementation — Mutation Resolvers

- [ ] T032 [US4] Implement flag mutations in `src/graphql/resolvers.py` — resolveFlag(input), batchResolveFlags(input) using DatabaseBackend.flags
- [ ] T033 [US4] Implement contribution mutations in `src/graphql/resolvers.py` — submitContribution(input), reviewContribution(input) using direct ORM
- [ ] T034 [US4] Implement pipeline mutations in `src/graphql/resolvers.py` — triggerPipelineRun(source) calling library pipeline with DatabaseBackend, importRegistry(registryPath) calling import_service

### Implementation — Schema Assembly

- [ ] T035 [US4] Rewrite `src/graphql/schema.py` — Strawberry Schema with Query + Mutation classes, wire all resolvers, add query depth limiting
- [ ] T036 [US4] Update `src/main.py` — mount the full GraphQL schema (replace placeholder)
- [ ] T037 [US4] Run GraphQL tests: `uv run pytest tests/test_graphql_queries.py tests/test_graphql_mutations.py -v`

**Checkpoint**: All GraphQL queries and mutations work. Tests pass.

---

## Phase 6: User Story 5 — Frontend Connection (Priority: P2)

**Goal**: Frontend connects to backend and renders element browser with real data.

**Independent Test**: Open browser to http://localhost:3000 — elements displayed

- [ ] T038 [US5] Verify `frontend/lib/apollo.ts` points to correct backend URL (http://localhost:8002/graphql)
- [ ] T039 [US5] Verify `frontend/graphql/queries.ts` query shapes match the implemented GraphQL schema — fix any field name mismatches
- [ ] T040 [US5] Test element browser page loads with real data from backend — verify in browser
- [ ] T041 [US5] Test element detail page renders when clicking an element — verify semantic, provenance, annotations display
- [ ] T042 [US5] Fix any TypeScript type mismatches in `frontend/graphql/types.ts`

**Checkpoint**: Frontend displays real data from backend without errors

---

## Phase 7: Polish & Validation

**Purpose**: CI setup, final checks, documentation

- [ ] T043 [US7] Set up CI workflow in `.github/workflows/` — job that starts PostgreSQL service, runs `uv run pytest tests/ -v` in backend
- [ ] T044 [US7] Ensure CI also runs library tests (400+ tests) as a separate job
- [ ] T045 Verify `ruff check` and `ruff format` pass on all backend files
- [ ] T046 Update `CLAUDE.md` with backend developer commands (docker compose up, running tests, accessing GraphQL playground, importing registry)
- [ ] T047 Run quickstart validation scenarios QS-001 through QS-010 from `specs/029-backend-service/quickstart.md`
- [ ] T048 Push branch and verify CI is green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Docker/DB)**: Depends on Phase 1 — BLOCKS everything
- **Phase 3 (DatabaseBackend)**: Depends on Phase 2 (needs running DB)
- **Phase 4 (Import/Seed)**: Depends on Phase 3 (needs DatabaseBackend)
- **Phase 5 (GraphQL API)**: Depends on Phase 3 (needs DatabaseBackend for resolvers)
- **Phase 6 (Frontend)**: Depends on Phase 5 (needs working API)
- **Phase 7 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (Docker)**: Independent — start first
- **US2 (DatabaseBackend)**: Depends on US1 (needs running DB)
- **US3+US6 (Import/Seed)**: Depends on US2 (needs DatabaseBackend)
- **US4 (GraphQL)**: Depends on US2 (needs DatabaseBackend) — can parallel with US3
- **US5 (Frontend)**: Depends on US4 (needs working API)
- **US7 (Tests/CI)**: Tests written alongside implementation, CI in final phase

### Parallel Opportunities

**Phase 3** (DatabaseBackend):
- T016, T017 — FlagStore and RunStore are independent

**Phase 5** (GraphQL):
- T028, T029, T030, T031 — query resolvers are independent files/functions
- T032, T033, T034 — mutation resolvers are independent

**Phase 6** (Frontend):
- T038-T042 — all frontend verification tasks are independent

---

## Implementation Strategy

### MVP First (Phases 1-4)

1. Phase 1: Clean structure
2. Phase 2: Docker stack + health endpoint
3. Phase 3: DatabaseBackend + 52 conformance tests
4. Phase 4: Import + seed data
5. **STOP and VALIDATE**: docker compose up shows elements in GraphQL playground

### Full Delivery

6. Phase 5: Complete GraphQL API
7. Phase 6: Frontend connection
8. Phase 7: CI + polish

---

## Notes

- Backend can be rewritten from scratch — no backwards compatibility needed (Constitution V)
- All ORM columns with `nullable=False` must have `server_default` (lesson from v1)
- Use `selectinload()` for relationships in async context (lazy loading fails)
- Test fixtures: per-test transaction rollback (not per-test table drop/recreate)
- Commit after each completed phase
