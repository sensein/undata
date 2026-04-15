# Implementation Plan: Backend–Library Alignment

**Branch**: `017-backend-library-alignment` | **Date**: 2026-03-17 | **Spec**: spec.md

## Summary

Replace the backend's flat element model with the library's content-addressed
model. The `undata-library` package becomes a dependency of the backend. Postgres
tables mirror the library data model. API endpoints return semantic + provenance.
Frontend renders the new structure.

## Technical Context

**Backend**: Python 3.14 + FastAPI + SQLAlchemy 2.x async + PostgreSQL 16
**Library**: Python 3.12+ (content-addressed models, hashing, extractors)
**Frontend**: TypeScript + Next.js 15.x + React

**Key dependency**: `undata-library` added to `backend/pyproject.toml`

## Phases

### Phase 1: Add Library Dependency + New DB Tables (non-breaking)

Create new tables alongside existing ones. No API changes yet.

- Add `undata-library` to `backend/pyproject.toml` dependencies
- Create Alembic migration adding new tables: `element_v2`, `element_provenance`,
  `value_concept`, `value_provenance`, `schema_shape`, `schema_provenance`,
  `element_mapping_v2`
- Create SQLAlchemy ORM models in `backend/src/models/` that import from
  `undata_library.models` for Pydantic validation
- Write ElementV2Service with `create_or_merge()` using content hash dedup

### Phase 2: Data Migration

Migrate existing `data_element` + `data_element_version` data into new tables.

- Alembic migration that: reads each DataElement, computes semantic hash via
  `undata_library.hashing`, inserts into `element_v2` + `element_provenance`
- Handle duplicates: elements with same hash merge provenance
- Verify record counts match (no data loss)

### Phase 3: API v2 Endpoints

New endpoints coexisting with v1 (no breaking changes).

- `POST /api/v2/elements` — accepts `{semantic, provenance}`, returns URI
- `GET /api/v2/elements` — returns semantic + provenance structure
- `GET /api/v2/elements/{uri}` — single element with full provenance
- `POST/GET /api/v2/values` — value concept CRUD
- `POST/GET /api/v2/schemas` — schema shape CRUD
- `POST/GET /api/v2/mappings` — mapping with expressions

### Phase 4: Library Export/Import via Backend API

Update library CLI to use v2 backend endpoints.

- Rewrite `export.py` to fetch from `/api/v2/elements` → v2 YAML
- Rewrite `import_lib.py` to POST to `/api/v2/elements` from v2 YAML
- Add `--backend-url` to `ingest` command (writes to backend instead of local)

### Phase 5: Frontend Updates

Update frontend to render v2 data model.

- Element detail: semantic identity block + provenance list
- Elements list: cross-source badge, filter by source
- New pages: value concepts, mapping explorer
- Update API client to use v2 endpoints

### Phase 6: Deprecate v1 + Polish

- Route v1 endpoints to v2 with backward-compatible wrappers
- Drop old `data_element` / `data_element_version` tables (future migration)
- Update all tests
- Update documentation

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Library as backend dependency | Single source of truth for models + hashing |
| New tables alongside old | Non-breaking migration; v1 API stays until cutover |
| v2 API namespace | Coexists with v1; no breaking changes for existing consumers |
| Alembic data migration | Preserves existing data with content-addressed identity |
| Frontend incremental update | Existing pages work during transition |

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Data loss during migration | Migration is additive (new tables); old tables preserved |
| Performance regression | Content hash computation is <1ms; JSONB indexing on semantic fields |
| Frontend breakage | v1 API stays active; frontend switches to v2 incrementally |
| Library dependency conflict | Library requires Python 3.12+; backend is 3.14 — compatible |
