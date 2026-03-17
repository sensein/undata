# Tasks: Backend–Library Alignment

**Feature**: `017-backend-library-alignment` | **Branch**: `017-backend-library-alignment`

---

## Phase 1: Library Dependency + New DB Tables

- [X] T001 Add `undata-library` as dependency in `backend/pyproject.toml` (path dependency: `../library`); verify `from undata_library.models import ElementRecord` works in backend context
- [X] T002 Create SQLAlchemy ORM models in `backend/src/models/element.py`: `Element` (semantic_hash CHAR(64) unique, uri VARCHAR, semantic JSONB, created_at), `ElementProvenanceV2` (FK → Element, source, class_, name, description, required, multivalued, added_at)
- [X] T003 [P] Create ORM models in `backend/src/models/value.py`: `ValueConcept` (semantic_hash, uri, semantic JSONB), `ValueProvenanceV2` (FK, source, raw_value, added_at)
- [X] T004 [P] Create ORM models in `backend/src/models/schema.py`: `SchemaShape` (semantic_hash, uri, semantic JSONB), `SchemaProvenanceV2` (FK, source, name, description)
- [X] T005 [P] Create ORM model in `backend/src/models/mapping.py`: `ElementMapping` (source_element_uri, target_element_uri, function_type, expression, expression_type, sssom_predicate, confidence)
- [X] T006 Create Alembic migration `0004_v2_tables.py`: add all v2 tables (non-destructive, old tables untouched)
- [X] T007 Write `backend/src/services/element_service.py`: `create_or_merge(semantic, provenance)` — computes hash via `undata_library.hashing`, checks existence, appends provenance or creates new; returns URI
- [X] T008 Write tests for element_service: (a) create new element returns URI; (b) same semantic graph returns same URI + appends provenance; (c) different graph returns different URI
- [ ] T009 Run migration + tests; commit Phase 1

## Phase 2: Data Migration

- [ ] T010 Create Alembic migration `0005_migrate_v1_to_v2.py`: read each `data_element` + `data_element_version`, compute semantic hash, insert into `element` + `element_provenance_v2`; merge duplicates by hash
- [ ] T011 Write migration verification script: compare record counts, verify no data loss, check hash uniqueness
- [ ] T012 Run migration on test DB; verify all records migrated; commit Phase 2

## Phase 3: API v2 Endpoints

- [X] T013 Create `backend/src/routes/elements.py`: `POST /api/v2/elements` (accepts `{semantic, provenance}`, returns URI), `GET /api/v2/elements` (list with filters: source, data_type, ontology_term), `GET /api/v2/elements/{uri}` (single with full provenance)
- [X] T014 [P] Create `backend/src/routes/values.py`: `POST/GET /api/v2/values`
- [X] T015 [P] Create `backend/src/routes/schemas.py`: `POST/GET /api/v2/schemas`
- [X] T016 [P] Create `backend/src/routes/mappings.py`: `POST/GET /api/v2/mappings`
- [X] T017 Register v2 routes in `backend/src/main.py`
- [X] T018 Write API tests: (a) POST element → 201 with URI; (b) POST same semantic → 200 with merged provenance; (c) GET elements filters by source; (d) GET element by URI returns full provenance
- [ ] T019 Run tests; commit Phase 3

## Phase 4: Library Export/Import via v2 API

- [X] T020 Rewrite `library/src/undata_library/export.py`: fetch from `/api/v2/elements`, `/api/v2/values`, `/api/v2/schemas` → write v2 YAML files + hash-registry
- [X] T021 Rewrite `library/src/undata_library/import_lib.py`: read v2 YAML files → POST to `/api/v2/elements`, `/api/v2/values`, `/api/v2/schemas`
- [X] T022 Add `--backend-url` option to `ingest` CLI command: extract from raw schemas → POST to backend API instead of writing local files
- [ ] T023 Write tests: (a) export produces valid v2 YAML; (b) import creates elements via API; (c) round-trip export→import preserves data
- [ ] T024 Commit Phase 4

## Phase 5: Frontend Updates

- [X] T025 Update `frontend/lib/types.ts`: add `Element`, `ProvenanceEntry`, `ValueConcept`, `SchemaShape`, `ElementMapping` types matching v2 API
- [X] T026 Create `frontend/lib/api/elements-v2.ts`: API client for v2 endpoints
- [X] T027 Update `frontend/app/elements/[id]/page.tsx` + create `frontend/components/ElementDetailV2.tsx`: render semantic identity block + provenance list with cross-source badges
- [X] T028 [P] Create `frontend/app/values/page.tsx` + `frontend/components/ValueConceptCard.tsx`: browse value concepts with ontology terms and raw_value per source
- [X] T029 [P] Create `frontend/components/MappingExplorer.tsx`: show bidirectional mappings with transform expressions
- [X] T030 Update `frontend/components/ElementCard.tsx`: show cross-source badge (provenance count > 1)
- [X] T031 Update nav in `frontend/app/layout.tsx`: add Values link
- [X] T032 Write vitest tests for ElementDetailV2, ValueConceptCard, MappingExplorer
- [ ] T033 Lint + build; commit Phase 5

## Phase 6: Deprecate v1 + Polish

- [ ] T034 Create backward-compatible v1 wrappers: `/api/v1/elements` routes to v2 with flat response format
- [ ] T035 Update all backend tests to use v2 models
- [X] T036 Update `README.md` (root + library) with v2 architecture diagram
- [X] T037 Update CLAUDE.md
- [ ] T038 Final commit and push

---

## Dependencies

```
T001 → T002-T005 (parallel) → T006 → T007 → T008 → T009
T010 → T011 → T012
T013-T016 (parallel) → T017 → T018 → T019
T020-T022 (parallel) → T023 → T024
T025 → T026 → T027-T029 (parallel) → T030 → T031 → T032 → T033
T034 → T035 → T036 → T037 → T038
```

## Implementation Strategy

1. **MVP** (Phases 1-3): New tables + data migration + v2 API. Backend serves both v1 and v2.
2. **Integration** (Phase 4): Library export/import uses v2 API. Round-trip validated.
3. **Frontend** (Phase 5): UI renders v2 data model. Cross-source provenance visible.
4. **Cutover** (Phase 6): v1 deprecated, v2 becomes default.
