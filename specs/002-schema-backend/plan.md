# Implementation Plan: Schema Backend Service

**Branch**: `002-schema-backend` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-schema-backend/spec.md`

> **Note**: This file was accidentally overwritten on 2026-03-09 by a `setup-plan.sh`
> test invocation and reconstructed from `research.md`, `data-model.md`, `contracts/`,
> and `tasks.md`. Content is authoritative; all implementation decisions are preserved.

---

## Summary

Persistent REST API backend for the undata integration system. Stores normalised
neuroscience schema elements (BIDS, DANDI, NWB, openMINDS) and their mappings,
enforces a two-tier canonical architecture (source space + undata canonical space),
and assigns stable HTTP URIs to every entity. Implemented with Python 3.14, FastAPI,
SQLAlchemy 2.x async, PostgreSQL 16 + pgvector, Keycloak OIDC federation, and uv-managed
virtual environments. All environments run inside an isolated venv per Constitution
Principle VI.

---

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14"`; uv-managed venv)
**Primary Dependencies**: FastAPI 0.111+, SQLAlchemy 2.x async, asyncpg, Alembic, Pydantic v2,
  authlib 1.x, cachetools 5.x, sentence-transformers 3.x, pgvector, rdflib ≥ 7.0, cmixf ≥ 0.2
**Storage**: PostgreSQL 16 + pgvector extension (HNSW index for embedding similarity)
**Testing**: pytest + pytest-asyncio (mode `auto`) + httpx + pytest-benchmark
**Target Platform**: Linux server (Docker + Docker Compose); exposed on port 8002
**Project Type**: Web service (REST API, async)
**Performance Goals**:
  - API p95 < 500 ms for read endpoints under typical load
  - Bulk ingest ≥ 1 000 elements/min
  - Token validate (cache hit) < 5 ms
  - QUDT TTL load at startup < 3 s (2 896 units, ~60 k triples)
**Constraints**:
  - All write endpoints require valid Bearer token (API key)
  - Actor identity always server-derived from token; never accepted from request body
  - URIs assigned at creation are immutable; supersession creates a new URI
  - No system Python — all Python invocations via uv or explicit venv binary
**Scale/Scope**: ≤ 200 k elements, ≤ 10 k mappings, ≤ 10 k users, multi-replica capable

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Simplicity First | ✅ | Single FastAPI service; no microservice split. Service-layer split from router layer is the minimum needed for independent testability. |
| II — TDD (NON-NEGOTIABLE) | ✅ | Every phase begins with test tasks marked "⚠️ Write FIRST — must FAIL before TN". Confirmed: 160/160 tests pass in Docker. |
| III — API-First Design | ✅ | `contracts/rest-api.md` written before implementation. OpenAPI auto-generated from Pydantic models. |
| IV — Observability | ✅ | `python-json-logger` JsonFormatter emitting structured JSON on all runtime paths. `get_logger` used in every service. Silent failures prohibited. |
| V — Versioning & Stability | ✅ | CalVer `2026.03.0` in `pyproject.toml` and `main.py`. Alembic migration files tagged with CalVer prefix. |
| VI — Environment Isolation | ✅ | `uv venv /app/.venv` in Dockerfile; `ENV PATH`/`ENV VIRTUAL_ENV` set; no `--system` installs. Test container uses `/app/.venv/bin/python`. Python 3.14 pinned. |

**Complexity violations requiring justification**:

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Two-layer cycle detection (DFS + advisory lock CTE) | TOCTOU: two concurrent inserts can each pass an optimistic DFS check | Single-pass advisory lock only: too slow for p99; single-pass DFS only: race condition under concurrent load |
| Separate `*_version` tables for history | Constitution requires full version history; application-level versioning is testable unlike triggers | Single-table with `current_version` boolean: breaks history queries; no clean FK to "current" version |
| `UnitResolutionService` TTL pre-load at startup | 2 896 units × RDF parse = ~2 s; per-request load would breach latency targets | Lazy load per request: 2+ s latency on first element create; unacceptable |

---

## Project Structure

### Documentation (this feature)

```text
specs/002-schema-backend/
├── plan.md           ← this file
├── spec.md
├── research.md       ← 14 architecture decisions
├── data-model.md     ← 16 ORM entities + indexes + state machines
├── quickstart.md     ← 22-step end-to-end validation checklist
├── contracts/
│   └── rest-api.md   ← full endpoint contracts (request/response shapes)
├── checklists/
│   └── quickstart-results.md
└── tasks.md          ← 102 tasks, all [x] complete
```

### Source Code

```text
backend/
├── src/
│   ├── core/
│   │   ├── config.py           # pydantic-settings Settings singleton
│   │   ├── logging.py          # get_logger (python-json-logger)
│   │   └── uri.py              # mint_element_uri / mint_mapping_uri / mint_schema_uri
│   ├── db/
│   │   ├── session.py          # AsyncEngine, get_db dependency, Base
│   │   └── migrations/
│   │       ├── env.py          # async Alembic env; -x url= flag for test override
│   │       └── versions/
│   │           ├── 2026_03_0_initial_schema.py   # 16 tables
│   │           ├── 2026_03_1_hnsw_index.py       # HNSW on embeddings
│   │           └── 2026_03_2_fix_metadata_col.py # metadata_ → metadata rename
│   ├── models/
│   │   ├── db.py               # 16 SQLAlchemy ORM models
│   │   └── schemas.py          # Pydantic v2 request/response models
│   ├── services/
│   │   ├── audit.py            # AuditService.record + .query
│   │   ├── aliases.py          # AliasGroupService (detect, create, CRUD)
│   │   ├── auth.py             # AuthService (OIDC + Keycloak)
│   │   ├── authz.py            # require_role, require_source_access, get_current_user
│   │   ├── cycle_detection.py  # CycleDetector.detect_cycle_dfs (pure Python)
│   │   ├── dynamic_schemas.py  # DynamicSchemaService
│   │   ├── elements.py         # ElementService (CRUD, nesting, supersession, semantic dedup)
│   │   ├── mappings.py         # MappingService (CRUD, cycle detection, URI minting)
│   │   ├── similarity.py       # SimilarityService (sentence-transformers + pgvector)
│   │   ├── sources.py          # SourceService
│   │   ├── tokens.py           # TokenService (issue, validate, revoke; TTLCache)
│   │   ├── units.py            # UnitResolutionService (cmixf + QUDT rdflib)
│   │   └── users.py            # UserService (upsert from OIDC, RBAC, memberships)
│   └── api/v1/
│       ├── aliases.py          # /aliases, /aliases/detect
│       ├── audit.py            # /audit
│       ├── auth.py             # /auth/login, /auth/callback, /auth/logout
│       ├── elements.py         # /elements (+ /bulk, /{id}/children, /{id}/supersede)
│       ├── mappings.py         # /mappings
│       ├── schemas.py          # /schemas (+ /{id}/supersede)
│       ├── sources.py          # /sources
│       ├── tokens.py           # /tokens
│       ├── units.py            # /units, /units/unresolvable
│       └── users.py            # /users, /users/me
├── tests/
│   ├── conftest.py             # session fixtures: migrations (subprocess), seed, client
│   ├── contract/               # HTTP-level response shape assertions
│   ├── integration/            # full lifecycle tests (real DB, real service)
│   └── unit/                   # pure-logic tests (no DB, no FastAPI)
├── data/qudt/
│   └── VOCAB_QUDT-UNITS-ALL.ttl  # QUDT v3.1.x — bundled, loaded at startup
├── keycloak/
│   └── realm-export.json       # undata realm bootstrap (Globus/GitHub/InCommon stubs)
├── postgres-init/
│   └── 01-create-test-db.sql   # creates undata_test DB on fresh Postgres container
├── Dockerfile                  # python:3.14-slim + uv venv + explicit PATH/VIRTUAL_ENV
├── docker-compose.yml          # backend, db, keycloak, test services
├── alembic.ini
├── pyproject.toml              # CalVer 2026.03.0, requires-python >=3.14
└── pytest.ini                  # asyncio_mode = auto
```

---

## Architecture Decisions

All 14 decisions are documented in full in [`research.md`](research.md). Summary:

| # | Decision | Choice |
|---|----------|--------|
| 1 | Storage backend | PostgreSQL 16 (relational + JSONB + GIN + pgvector) |
| 2 | ORM / async stack | SQLAlchemy 2.x async + asyncpg; Alembic migrations |
| 3 | Versioning / audit | `*_version` tables + `audit_log`; no DB triggers; optimistic lock via `version_num` |
| 4 | Cycle detection | Two-layer: in-memory DFS (optimistic) + advisory lock + CTE (race-safe) |
| 5 | Alias similarity | `sentence-transformers` all-MiniLM-L6-v2 (384-dim); threshold 0.88; SSSOM predicates |
| 6 | API framework | FastAPI 0.111+ + Pydantic v2; auto OpenAPI |
| 7 | OIDC / auth | Keycloak 24 as federation hub; authlib RS256/JWKS; JWT validated offline |
| 8 | RBAC + ReBAC | Four-tier RBAC enum + `source_membership` table; FastAPI Depends; no external engine |
| 9 | API key storage | `secrets.token_hex(32)`; SHA-256 hash stored; in-process `cachetools.TTLCache` (5 min) |
| 10 | URI minting | HTTP URIs: `{UNDATA_BASE_URL}/{type}/{uuid}`; deterministic; stored immutably in DB |
| 11 | Nesting / DynamicSchema | `DataElementChild` join table; `DynamicSchema` + `DynamicSchemaElement` tables; all with independent UUIDs + URIs |
| 12 | Semantic graph | `semantic_graph` JSONB on `DataElementVersion`; denormalised `unit TEXT` for B-tree indexed filtering |
| 13 | Semantic change / supersession | `POST /{id}/supersede` creates new entity with new URI; old entity gains `superseded_by`; both remain resolvable |
| 14 | Unit standardization | cmixf-12 for symbol validation; QUDT TTL (rdflib) for URI resolution; enrichment non-blocking |

---

## Data Model

16 ORM entities documented in full in [`data-model.md`](data-model.md):

`UserProfile` · `APIKey` · `UserRole` · `SourceMembership` · `SchemaSource` ·
`DataElement` · `DataElementVersion` · `DataElementChild` · `MappingFunction` ·
`MappingInput` · `MappingFunctionVersion` · `AliasGroup` · `AliasGroupMember` ·
`DynamicSchema` · `DynamicSchemaElement` · `AuditLog`

Key design invariants:
- `DataElement.uri`, `MappingFunction.uri`, `DynamicSchema.uri` — TEXT NOT NULL UNIQUE; assigned once; never updated
- `AuditLog.actor_id` — UUID FK to `UserProfile` (not a plain text string)
- `DataElementVersion.unit` — TEXT extracted from `semantic_graph.unit.label`; B-tree indexed
- `DataElement.superseded_by` / `DynamicSchema.superseded_by` — self-referential UUID FK; set in same transaction as supersession

---

## Implementation Phases

| Phase | Scope | Tasks | Status |
|-------|-------|-------|--------|
| 1 — Setup | Dockerfile, docker-compose, pyproject.toml, .env.example, realm-export.json | T001–T006 | ✅ |
| 2 — Foundational | Settings, DB session, 16 ORM models, Pydantic schemas, Alembic migrations, URI util, AuditService, logging, conftest, main.py, undata seed | T007–T017, T084(phase2) | ✅ |
| 3 — US4 Identity | TokenService, UserService, AuthService, authz dependencies, tokens/users/auth routers | T018–T030 | ✅ |
| 4 — US1 Elements | SourceService, ElementService (CRUD + nesting + supersession + semantic dedup), sources/elements routers | T031–T042, T073–T075 | ✅ |
| 5 — US5 DynamicSchema | DynamicSchemaService (CRUD + supersession), schemas router | T043–T048, T076–T078 | ✅ |
| 6 — US2 Mappings | CycleDetector, SimilarityService, HNSW migration, MappingService, AliasGroupService, mappings/aliases routers | T049–T062 | ✅ |
| 7 — US3 Audit | AuditService.query, audit router | T063–T066 | ✅ |
| 8 — Polish | Cross-cutting contract tests, URI stability tests, performance benchmarks, supersession integration, full quickstart validation | T067–T072, T079–T080, T082–T083 | ✅ |
| 9 — Gap Closure | Element response enrichment tests, semantic dedup guard tests, alias/mapping back-ref tests | T084–T090 (phase 9) | ✅ |
| 10 — US7 Unit Std. | Dockerfile Python 3.14 + uv, rdflib + cmixf deps, QUDT TTL bundle, UnitResolutionService, units router, element enrichment | T091–T101 | ✅ |

**All 102 tasks complete. 160/160 tests pass in Docker (clean rebuild confirmed 2026-03-09).**

---

## Service Endpoints Summary

| Prefix | Resource | Auth required |
|--------|----------|---------------|
| `GET /health` | Health check | None |
| `/api/v1/auth/` | OIDC login, callback, logout | None |
| `/api/v1/tokens/` | API key issuance, listing, revocation | Bearer (own key) |
| `/api/v1/users/` | User profiles, role assignment | Bearer; admin for write |
| `/api/v1/sources/` | SchemaSource CRUD | Bearer (curator) for write |
| `/api/v1/elements/` | DataElement CRUD, bulk, nesting, supersession | Bearer (curator/contributor) for write |
| `/api/v1/mappings/` | MappingFunction CRUD | Bearer (curator) for write |
| `/api/v1/aliases/` | AliasGroup CRUD + detect | Bearer (curator) for write |
| `/api/v1/schemas/` | DynamicSchema CRUD + supersession | Bearer (curator) for write |
| `/api/v1/audit/` | AuditLog query | None (read-only) |
| `/api/v1/units/` | Unit coverage + unresolvable list | None (read-only) |

Full request/response shapes in [`contracts/rest-api.md`](contracts/rest-api.md).

---

## Key Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://undata:undata@db:5432/undata` | Primary DB |
| `TEST_DATABASE_URL` | `…/undata_test` | Test DB (separate schema) |
| `UNDATA_BASE_URL` | `http://localhost:8002` | URI prefix for minted URIs |
| `SECRET_KEY` | *(required)* | itsdangerous session signing |
| `KEYCLOAK_URL` | `http://keycloak:8080` | Keycloak base URL |
| `KEYCLOAK_REALM` | `undata` | |
| `KEYCLOAK_CLIENT_ID` | *(required)* | |
| `KEYCLOAK_CLIENT_SECRET` | *(required)* | |
| `ALIAS_SIMILARITY_THRESHOLD` | `0.88` | Cosine similarity threshold for alias detection |
| `TOKEN_CACHE_TTL_SECONDS` | `300` | In-process token cache TTL (max revocation lag) |
| `LOG_LEVEL` | `INFO` | JSON log level |
| `QUDT_TTL_PATH` | `data/qudt/VOCAB_QUDT-UNITS-ALL.ttl` | Bundled QUDT vocabulary |
