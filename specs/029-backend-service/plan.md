# Implementation Plan: Backend Service

**Branch**: `029-backend-service` | **Date**: 2026-03-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/029-backend-service/spec.md`

## Summary

Rebuild the backend as a working service: DatabaseBackend implementing StorageBackend protocol over PostgreSQL, complete Strawberry GraphQL API matching the 027 contract, registry import, seed data, Docker stack, and test suite with CI.

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14"`)
**Primary Dependencies**: FastAPI 0.111+, SQLAlchemy 2.x async, asyncpg, Strawberry GraphQL 0.250+, pydantic 2.x
**Storage**: PostgreSQL 16 + pgvector (via Docker)
**Testing**: pytest + pytest-asyncio, httpx for ASGI testing
**Target Platform**: Docker Compose (PostgreSQL + FastAPI backend)
**Project Type**: Web service (GraphQL API)
**Performance Goals**: Browse queries < 500ms p95 with 10K entities
**Constraints**: Must pass 52 StorageBackend conformance tests from 028
**Scale/Scope**: ~8,820 entities, 7 GraphQL query types, 6 mutation types

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | DatabaseBackend wraps existing ORM models. No new abstractions beyond the protocol. |
| II. Test-Driven Development | PASS | Conformance tests from 028 run against DatabaseBackend. GraphQL tests written before resolvers. |
| III. API-First Design | PASS | GraphQL contract from 027 is the authoritative spec. Implemented via Strawberry types. |
| IV. Observability | PASS | Structured JSON logging on all requests. Health endpoint reports DB status. |
| V. No Deprecation, No Migration | PASS | Backend rewritten from scratch. create_all on startup, no Alembic migrations. |
| VI. Environment Isolation | PASS | Docker Compose with uv venv inside image. |
| VII. Developer Experience | PASS | docker compose up starts everything with seed data. Hot reload via uvicorn --reload. |
| Git Commit Discipline | PASS | Commit per task phase. |
| CI Green Before Merge | PASS | Library tests + backend tests in CI. |
| Evaluation Record | PASS | Import counts recorded. |

## Project Structure

### Documentation

```text
specs/029-backend-service/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/           # Uses 027 GraphQL contract as-is
└── checklists/
    └── requirements.md
```

### Source Code

```text
backend/
├── src/
│   ├── main.py                    # REWRITE: clean FastAPI app, health, GraphQL mount
│   ├── core/
│   │   ├── config.py              # KEEP: pydantic-settings
│   │   └── logging.py             # KEEP: structured JSON logging
│   ├── db/
│   │   ├── session.py             # REWRITE: async engine + session factory
│   │   └── models.py              # REWRITE: ORM models (from models/db.py)
│   ├── storage/
│   │   └── database_backend.py    # NEW: DatabaseBackend implementing StorageBackend
│   ├── graphql/
│   │   ├── schema.py              # REWRITE: Strawberry Query + Mutation
│   │   ├── types.py               # REWRITE: Strawberry types matching 027 contract
│   │   └── resolvers.py           # NEW: resolver functions using DatabaseBackend
│   └── services/
│       └── import_service.py      # REWRITE: import via DatabaseBackend (not raw SQL)
├── tests/
│   ├── conftest.py                # NEW: DB fixtures, test session, cleanup
│   ├── test_database_backend.py   # NEW: 52 conformance tests against real DB
│   ├── test_graphql_queries.py    # NEW: all query resolvers
│   └── test_graphql_mutations.py  # NEW: all mutation resolvers
├── seed/                          # NEW: sample registry YAML for dev seeding
├── docker-compose.yml             # REWRITE: PostgreSQL only (no Keycloak)
├── Dockerfile                     # REWRITE: clean Python 3.14 + uv
├── entrypoint.sh                  # REWRITE: create tables + seed + start uvicorn
└── pyproject.toml                 # KEEP: update deps
```

## Implementation Approach

### Phase 1: Docker + Database Foundation (US1)
1. Rewrite docker-compose.yml — PostgreSQL 16 only (remove Keycloak, Redis)
2. Rewrite Dockerfile — Python 3.14, uv, install library + backend
3. Rewrite db/session.py — async engine factory
4. Move models to db/models.py (from models/db.py)
5. Rewrite main.py — health endpoint, table creation, GraphQL mount
6. Verify: docker compose up → health returns 200

### Phase 2: DatabaseBackend (US2)
1. Implement DatabaseEntityStore — read/write/list/exists/delete/merge_provenance/count/find_by_hash
2. Implement DatabaseFlagStore — write_flag/read_flags/resolve_flag
3. Implement DatabaseRunStore — save_summary/load_previous/list_runs
4. Implement DatabaseBackend composite
5. Port conformance tests from 028 — parametrize for database backend
6. Verify: 52 conformance tests pass against real PostgreSQL

### Phase 3: Registry Import + Seed Data (US3 + US6)
1. Rewrite import_service.py — use DatabaseBackend.entities.write() instead of raw SQL
2. Create seed/ directory with sample YAML entities
3. Add seed logic to entrypoint.sh — import seed data if DB empty
4. Verify: docker compose up → browse elements returns data

### Phase 4: Complete GraphQL API (US4)
1. Rewrite graphql/types.py — all types from 027 contract
2. Implement all query resolvers (element, schema, value, valueset lookups; browse queries with cursor pagination; curationQueue; runSummaries; latestRun)
3. Implement all mutation resolvers (resolveFlag, batchResolveFlags, submitContribution, reviewContribution, triggerPipelineRun, importRegistry)
4. Add query depth limiting
5. Verify: introspection matches 027 contract

### Phase 5: Frontend Connection (US5)
1. Verify Apollo Client config points to backend URL
2. Test element browser loads with real data
3. Test element detail page renders
4. Fix any query/type mismatches

### Phase 6: Tests + CI (US7)
1. Write conftest.py — test DB, session fixtures, cleanup
2. Write GraphQL query tests
3. Write GraphQL mutation tests
4. Set up CI workflow — library tests + backend tests
5. Verify: CI green

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Sync DatabaseBackend wrapping async SQLAlchemy | StorageBackend protocol is sync (matches FileBackend + library) | Async protocol would require changing library pipeline functions and 028's protocol |
