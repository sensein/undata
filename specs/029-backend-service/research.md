# Research: Backend Service

## R1: DatabaseBackend Architecture

**Decision**: DatabaseBackend implements StorageBackend protocol using SQLAlchemy async with the existing ORM models from `backend/src/models/db.py`. JSONB columns store semantic, provenance, and ontology_annotations as dicts — matching FileBackend's YAML structure.

**Rationale**: The existing ORM models already have the right shape (sha256, file_name, JSONB columns). DatabaseBackend translates between the StorageBackend protocol's dict-based interface and SQLAlchemy ORM objects. No new tables needed — just a new access layer.

**Alternatives considered**:
- Raw SQL without ORM — simpler but loses type safety and relationship management
- Separate database schema from ORM models — unnecessary complexity when models already match

## R2: Sync vs Async DatabaseBackend

**Decision**: DatabaseBackend methods are synchronous, wrapping async SQLAlchemy calls with `asyncio.run_coroutine_threadsafe()` or running in a sync context. The GraphQL resolvers call DatabaseBackend methods directly (Strawberry supports sync resolvers with async FastAPI).

**Rationale**: The StorageBackend protocol is synchronous (to match FileBackend and library pipeline functions). Making it async would require changing the protocol and all pipeline functions. Instead, the backend creates a synchronous wrapper over async SQLAlchemy. For GraphQL resolvers, Strawberry's FastAPI integration handles the async/sync bridge.

**Alternative**: Make the protocol async — rejected because the library must work without async (CLI, tests). Two separate protocols (sync + async) would be over-engineering per constitution Principle I.

## R3: GraphQL Pagination Strategy

**Decision**: All browse queries use Relay-style cursor pagination with base64-encoded cursors based on (created_at, id) composite keys.

**Rationale**: The 027 contract specifies Relay-style pagination. Offset-based pagination (current implementation) breaks when data changes between pages. Cursor-based is stable and efficient with indexed composite keys.

**Alternatives considered**:
- Offset/limit (current) — breaks under concurrent inserts/deletes
- Keyset (created_at only) — ties between same-timestamp rows cause skips

## R4: Docker Stack Simplification

**Decision**: Remove Keycloak from docker-compose.yml (auth deferred to 030). Keep only PostgreSQL + backend. Add a seed script that imports a sample registry on first startup.

**Rationale**: Keycloak adds startup time and complexity for zero benefit in this feature (all operations are anonymous). A minimal stack starts faster and is easier to debug.

## R5: Seed Data Strategy

**Decision**: Ship a small sample registry (50 elements, 20 schemas, 30 values, 5 valuesets) as YAML files in `backend/seed/`. The Docker entrypoint imports them on first startup if the database is empty.

**Rationale**: Full 8,820-entity registry import takes too long for first-time developer experience. A curated sample shows the UI working immediately. Full import available as a CLI command.

## R6: Test Database Strategy

**Decision**: Use a separate `undata_test` PostgreSQL database created by an init script. Each test gets a fresh transaction that rolls back after the test.

**Rationale**: Per-test transaction rollback is the fastest isolation strategy. No table drop/recreate per test (too slow), no shared state between tests (flaky).
