# Implementation Plan: Dynamic Schema Construction and Migration API

**Branch**: `004-migration-api` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-migration-api/spec.md`

## Summary

A stateless FastAPI service that constructs dynamic LinkML schemas from stored data
elements, registers and executes migration pathways between schemas, and provides
schema diff + compatibility analysis. All persistence delegated to 002-schema-backend.
Async job queue (Celery + Redis) handles large operations.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI 0.111+, Pydantic v2, httpx 0.27+, linkml-runtime 1.8+,
simpleeval 1.0+, RestrictedPython 7.x, Celery 5.x, Redis 7.x, sssom-utils 0.15+
**Storage**: No local DB — uses 002-schema-backend API + Redis for job state
**Testing**: pytest, pytest-asyncio, httpx, respx (httpx mock)
**Target Platform**: Linux server (Docker container)
**Project Type**: web-service (REST API)
**Performance Goals**: p95 < 200ms for single-record migration; batch of 100 records
in < 10s; schema construction (50 elements) in < 2s
**Constraints**: Per-record failure isolation in batches; broken pathway detection
before execution; async jobs for > 50 element schemas or > 100 record batches
**Scale/Scope**: ~100 pathways, ~1k schema constructions, batch migrations up to 10k records

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | ✅ PASS | Stateless; no local DB; delegates storage to 002 |
| II. Test-Driven Development | ✅ PASS | Full REST contract defined; unit tests for expression evaluation before implementation |
| III. API-First Design | ✅ PASS | contracts/rest-api.md defines all endpoints |
| IV. Observability | ✅ PASS | Every migration execution produces a structured report; JSON logs |
| V. CalVer | ✅ PASS | Dynamic schema versions use CalVer; API version tagged |

**Dependency gate**: 002-schema-backend must have `/pathways` and `/schemas` endpoints
implemented before this service can run integration tests.

## Project Structure

### Source Code (repository root)

```text
migration-api/
├── src/
│   ├── api/
│   │   └── v1/
│   │       ├── schemas.py        # /schemas construction endpoints
│   │       ├── pathways.py       # /pathways CRUD
│   │       ├── migrate.py        # /migrate execution
│   │       ├── diff.py           # /diff comparison
│   │       └── jobs.py           # /jobs polling
│   ├── services/
│   │   ├── schema_builder.py     # linkml-runtime SchemaDefinition builder
│   │   ├── pathway_executor.py   # step-by-step migration runner
│   │   ├── expression_eval.py    # simpleeval + RestrictedPython dispatcher
│   │   ├── schema_differ.py      # diff computation logic
│   │   └── backend_client.py     # httpx async client for 002
│   ├── tasks/
│   │   ├── celery_app.py         # Celery configuration
│   │   ├── build_schema.py       # async schema construction task
│   │   └── batch_migrate.py      # async batch migration task
│   └── main.py
├── tests/
│   ├── unit/
│   │   ├── test_expression_eval.py
│   │   ├── test_schema_builder.py
│   │   └── test_schema_differ.py
│   ├── integration/
│   │   ├── test_pathway_execution.py
│   │   └── test_migrate_endpoint.py
│   └── fixtures/
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Phase 0 Research Summary

See [research.md](research.md).

| Question | Decision |
|----------|----------|
| Expression evaluation | simpleeval (Tier 1) + RestrictedPython plugins (Tier 2) |
| Pathway storage | New /pathways resource in 002-schema-backend |
| Dynamic schema construction | linkml-runtime SchemaDefinition API |
| Async jobs | Celery 5.x + Redis |
| SSSOM support | Deferred — `sssom-utils` is not the PyPI package name (correct: `sssom`); TSV export out of scope for v1 |

## Phase 1 Design Artifacts

- [data-model.md](data-model.md) — pathway structure, migration context, report shapes
- [contracts/rest-api.md](contracts/rest-api.md) — full REST API contract
- [quickstart.md](quickstart.md) — developer validation checklist
