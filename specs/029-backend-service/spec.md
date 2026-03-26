# Feature Specification: Backend Service

**Feature Branch**: `029-backend-service`
**Created**: 2026-03-26
**Status**: Draft
**Input**: Phase 2 of iteration 2 — rebuild the backend as a working service with DatabaseBackend, GraphQL API, registry import, and developer-friendly Docker stack.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Working Docker Stack (Priority: P1)

As a developer, I need the full stack to start from a single command so I can begin developing and testing immediately after checkout.

**Why this priority**: Nothing works until the services run. The backend can't serve data, the frontend can't connect, and tests can't execute without a running database and API server.

**Independent Test**: Run the stack start command, then verify the health endpoint returns 200 and the API playground is accessible in a browser.

**Acceptance Scenarios**:

1. **Given** a fresh checkout with no running services, **When** the developer starts the stack, **Then** the database initializes, the backend starts, and the health endpoint returns 200 within 90 seconds.
2. **Given** a running backend, **When** a developer navigates to the API playground URL, **Then** they see the interactive query editor with the full schema visible.
3. **Given** a running stack, **When** the developer stops and restarts it, **Then** previously imported data persists across restarts (database volume is preserved).

---

### User Story 2 — Database Storage Backend (Priority: P1)

As a library maintainer, I need a database-backed implementation of the StorageBackend protocol so the backend can call the same pipeline functions the CLI uses, but store results in a database instead of files.

**Why this priority**: The StorageBackend protocol (feature 028) defines the interface. Without a database implementation, the backend must use a separate import service to copy files into the database — duplicating logic and creating drift risk.

**Independent Test**: Run the same conformance test suite that FileBackend passes, but against the database backend with a real database. All tests pass.

**Acceptance Scenarios**:

1. **Given** a running database, **When** the protocol conformance tests run against the database backend, **Then** all tests pass (round-trip, list, exists, merge_provenance, find_by_hash, filters, flag lifecycle, run lifecycle).
2. **Given** the database backend, **When** a pipeline function is called with it, **Then** entities are written to and read from the database — no files are created.
3. **Given** both backends, **When** the same data is written to each, **Then** reading it back produces identical results (semantic content, provenance, annotations).

---

### User Story 3 — Registry Import (Priority: P1)

As a developer, I need to load the existing flat-file registry (YAML files from pipeline output) into the database so the API has data to serve and the UI has content to display.

**Why this priority**: Without seed data, the API returns empty results and the UI shows blank pages. The registry import is the bridge between the library's file output and the backend's database.

**Independent Test**: Run the import operation, then query entity counts via the API — they match the number of YAML files in the source registry.

**Acceptance Scenarios**:

1. **Given** a flat-file registry with known entity counts, **When** the import operation runs, **Then** all entities (elements, schemas, values, valuesets), curation flags, and run summaries are loaded into the database.
2. **Given** an imported registry, **When** entity counts are queried through the API, **Then** they match the source file counts exactly.
3. **Given** a registry that has already been imported, **When** the import runs again, **Then** it is idempotent — no duplicates are created, provenance is merged for existing entities.

---

### User Story 4 — Complete GraphQL API (Priority: P1)

As a frontend developer, I need all queries and mutations from the API contract so every page in the UI has a working data source and users can take actions.

**Why this priority**: The frontend pages exist from brainstorm v1 but are wired to an incomplete API. Without the full API, element browsing, schema lookups, curation queue, and contribution submission all fail.

**Independent Test**: Run the API introspection query and verify all types, queries, and mutations from the contract are present. Execute each with test data.

**Acceptance Scenarios**:

1. **Given** a populated database, **When** any single-entity lookup query is sent (element, schema, value, valueset by identifier), **Then** the full entity is returned with all nested fields (semantic, provenance, ontology annotations).
2. **Given** a populated database, **When** any browse query is sent with cursor-based pagination, **Then** the response includes edges, nodes, and pageInfo with hasNextPage and endCursor.
3. **Given** a pending curation flag, **When** a resolveFlag mutation is sent, **Then** the flag status updates and the resolution metadata is persisted.
4. **Given** the API, **When** a triggerPipelineRun mutation is sent, **Then** the pipeline runs asynchronously and the result is queryable through run summaries.
5. **Given** the API, **When** an importRegistry mutation is sent with a path to a flat-file registry, **Then** entities are loaded into the database and counts are returned.

---

### User Story 5 — Frontend Connection (Priority: P2)

As a user browsing the web interface, I need the element browser to display real data from the backend so I can explore the registry.

**Why this priority**: The frontend pages exist but can't display data without a working API connection. This story validates the full vertical slice: database → API → UI. It's P2 because the API (US4) must work first.

**Independent Test**: Open the element browser in a browser — it displays elements with names, data types, and source information loaded from the database.

**Acceptance Scenarios**:

1. **Given** a running stack with imported data, **When** a user opens the element browser, **Then** elements are displayed with names, data types, sources, and pagination controls.
2. **Given** the element browser, **When** a user clicks an element, **Then** the detail page shows semantic identity, provenance chain, and ontology annotations.
3. **Given** the frontend, **When** it sends a query to the backend, **Then** the response arrives in under 2 seconds and renders without errors.

---

### User Story 6 — Developer Experience (Priority: P1)

As a new contributor, I need to go from checkout to a working system with sample data in minutes, not hours, so I can start contributing immediately.

**Why this priority**: Developer friction kills contributions. If the stack is hard to run, people won't test, won't develop, and won't contribute. This is as important as the features themselves.

**Independent Test**: Time from `git clone` to seeing elements in the browser — must be under 5 minutes (mostly Docker image pull time).

**Acceptance Scenarios**:

1. **Given** a fresh checkout, **When** the developer runs the stack start command, **Then** the database is seeded with sample data and the UI shows content on first load.
2. **Given** a running stack, **When** the developer modifies a backend source file, **Then** the change is reflected without restarting the service (hot reload).
3. **Given** the project README or developer guide, **When** a developer reads it, **Then** they find copy-pasteable commands for: starting the stack, running tests, importing data, and accessing the API playground.

---

### User Story 7 — Backend Tests and CI (Priority: P1)

As a maintainer, I need automated tests that verify the API works correctly against a real database so regressions are caught before merge.

**Why this priority**: Without tests, every change risks breaking the API silently. Without CI, the tests don't run automatically. The constitution requires CI green before merge.

**Independent Test**: Run the test suite — it starts a test database, creates tables, runs all query and mutation tests, and reports pass/fail.

**Acceptance Scenarios**:

1. **Given** the test suite, **When** it runs, **Then** all GraphQL queries return expected results against a real database (not mocks).
2. **Given** the CI pipeline, **When** a push is made to the feature branch, **Then** both library tests (400+) and backend tests run, and both must pass.
3. **Given** a test that creates data, **When** the test completes, **Then** the database is cleaned up (no test data leaks between tests).

---

### Edge Cases

- What happens when the database is empty and a browse query is sent? The API returns an empty connection with `hasNextPage: false` and zero edges.
- What happens when an import is interrupted mid-way? The import uses database transactions — partial imports are rolled back, leaving the database in a consistent state.
- What happens when the same entity exists in both files and database with different provenance? The import merges provenance (appends new sources, deduplicates by source+name).
- What happens when a GraphQL query requests a depth of 10 nested relations? The API limits query depth to prevent abuse and returns an error for excessively deep queries.
- What happens when the frontend sends a malformed query? The API returns a structured error with a clear message, not a 500.
- What happens when the database connection drops during a request? The API returns a 503 with a retry-after header; the health endpoint reflects the degraded state.
- What happens when two users resolve the same flag simultaneously? The database uses optimistic locking — the second resolution fails with a conflict error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST start all services (database, backend) from a single command with no manual configuration steps.
- **FR-002**: System MUST create database tables automatically on first startup.
- **FR-003**: System MUST implement the StorageBackend protocol (from feature 028) backed by a relational database with identical semantics to FileBackend.
- **FR-004**: System MUST pass the same protocol conformance tests (52 tests) that FileBackend passes, against a real database.
- **FR-005**: System MUST import a flat-file YAML registry into the database, preserving all entity fields, provenance chains, and ontology annotations.
- **FR-006**: Registry import MUST be idempotent — re-importing the same data produces no duplicates.
- **FR-007**: System MUST expose a GraphQL API with all queries from the 027 contract: element, schema, value, valueset lookups; browseElements, browseSchemas, browseValues, browseTransforms; curationQueue; contributions; runSummaries; latestRun.
- **FR-008**: System MUST expose all mutations from the 027 contract: resolveFlag, batchResolveFlags, submitContribution, reviewContribution, triggerPipelineRun, importRegistry.
- **FR-009**: All browse queries MUST support Relay-style cursor pagination with first, after, pageInfo (hasNextPage, endCursor).
- **FR-010**: System MUST prevent excessive query depth to protect against abuse.
- **FR-011**: System MUST provide a health endpoint that reports service and database status.
- **FR-012**: System MUST seed the database with sample data on first startup so the UI has content immediately.
- **FR-013**: Backend MUST support hot reload during development so code changes are reflected without restart.
- **FR-014**: System MUST include an automated test suite that runs GraphQL queries and mutations against a real database.
- **FR-015**: CI pipeline MUST run both library tests and backend tests, and both MUST pass before merge.
- **FR-016**: System MUST provide structured error responses for all failure cases (malformed queries, missing entities, database errors).
- **FR-017**: The frontend MUST connect to the backend API and render entity data without errors.
- **FR-018**: System MUST log all API requests and errors in a structured format.
- **FR-019**: Pipeline operations triggered via the API MUST reuse library functions with the database backend — no reimplementation of pipeline logic.

### Key Entities

- **DatabaseBackend**: An implementation of StorageBackend (from 028) backed by a relational database. Provides EntityStore, FlagStore, and RunStore over SQL tables.
- **Element, Schema, Value, ValueSet**: Core entity types stored in database tables with JSONB columns for semantic, provenance, and ontology_annotations.
- **CurationFlag**: Quality review items with status lifecycle, stored in a database table.
- **RunSummary**: Pipeline execution records stored in a database table.
- **Contribution**: User-submitted annotations, comments, or edits linked to entities.
- **UserProfile**: Authenticated user with role (viewer, contributor, curator, admin). Authentication deferred to feature 030 — this feature uses anonymous/test users.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full stack starts and serves the health endpoint within 90 seconds of the start command.
- **SC-002**: The database backend passes all 52 protocol conformance tests from feature 028.
- **SC-003**: Registry import loads 8,820+ entities and counts match the source files exactly.
- **SC-004**: All GraphQL queries and mutations from the 027 contract pass automated tests.
- **SC-005**: Browse queries return results in under 500ms at the 95th percentile with 10,000 entities.
- **SC-006**: The frontend element browser displays real data from the backend without errors.
- **SC-007**: A developer goes from checkout to seeing data in the browser in under 5 minutes.
- **SC-008**: The CI pipeline runs library tests (400+) and backend tests, both passing, in under 15 minutes.
- **SC-009**: All 400+ library tests continue to pass (no regressions from backend work).

## Scope Boundaries

### In Scope

- Docker Compose stack (PostgreSQL + FastAPI backend)
- DatabaseBackend implementing StorageBackend protocol
- Registry import from flat files to database
- Complete GraphQL API matching 027 contract
- Frontend connection verification (element browser works)
- Seed data for development
- Backend test suite with CI integration
- Hot reload for development
- Structured logging and error handling

### Out of Scope

- Authentication and authorization (deferred to feature 030)
- Task manager for async operations (deferred — pipeline runs synchronously for now)
- Frontend modifications beyond verifying connection works
- New source adapters or ontology expansion
- Production deployment, SSL, domain configuration
- Real-time subscriptions (WebSocket/SSE)

## Assumptions

- The StorageBackend protocol from feature 028 is the authoritative interface
- The 027 GraphQL contract (specs/027-library-hardening-pipeline/contracts/graphql-schema.md) defines the API shape
- The existing backend code from brainstorm v1 can be overwritten or deleted entirely
- PostgreSQL 16 with pgvector extension is available via Docker
- The frontend already has pages and Apollo Client setup from brainstorm v1
- Authentication is deferred — all API operations are anonymous for this feature
- Pipeline operations run synchronously (async task manager deferred)

## Dependencies

- Feature 028 (storage abstraction) — provides StorageBackend protocol, FileBackend, conformance tests
- Feature 027 (library hardening) — provides the library pipeline, GraphQL contract, frontend pages
- PostgreSQL 16 Docker image with pgvector
- Strawberry GraphQL library
- Apollo Client in the frontend
