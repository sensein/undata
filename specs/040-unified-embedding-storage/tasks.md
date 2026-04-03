# Tasks: Unified Embedding & Storage

**Input**: Design documents from `/specs/040-unified-embedding-storage/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

**Purpose**: Prepare unified store interface

- [ ] T001 Add dataframe() method to ParquetStore for bulk DataFrame access in library/src/undata_library/storage/parquet_store.py
- [ ] T002 Add update() method to ParquetStore for in-place entity updates in library/src/undata_library/storage/parquet_store.py
- [ ] T003 Add tests for dataframe() and update() methods in library/tests/test_parquet_store.py

**Checkpoint**: ParquetStore has full interface matching data model

---

## Phase 2: Foundational — Unified Store (US5)

**Purpose**: Single store interface replacing all entity access paths

- [ ] T004 [US5] Rewrite FileBackend to delegate all entity operations to ParquetStore (remove YAML read/write) in library/src/undata_library/storage/file_backend.py
- [ ] T005 [US5] Remove FileEntityStore class (YAML-backed entity store) from library/src/undata_library/storage/file_backend.py
- [ ] T006 [US5] Update StorageBackend protocol — remove write_batch/read_batch (ParquetStore handles natively) in library/src/undata_library/storage/protocol.py
- [ ] T007 [US5] Update all pipeline callers to use ParquetStore directly: enrich.py, align.py, alias_detection.py, transform.py in library/src/undata_library/
- [ ] T008 [US5] Remove iter_staged YAML path and write_staged_entity from library/src/undata_library/staging.py
- [ ] T009 [US5] Run full test suite — verify no tests depend on YAML entity files in library/tests/

**Checkpoint**: All entity access goes through ParquetStore; no YAML entity I/O remains

---

## Phase 3: User Story 1 — Parquet-Only Pipeline (Priority: P1)

**Goal**: Extract, enrich, and commit all produce Parquet only — zero YAML entity files

**Independent Test**: Pipeline run for BIDS → find /output -name "*.yaml" | grep -v runs → 0 results

- [ ] T010 [US1] Rewrite ingest_source to collect entities in memory and call ParquetStore.write_batch instead of writing individual YAML files in library/src/undata_library/ingest.py
- [ ] T011 [US1] Rewrite commit_staged to read from ParquetStore, compute sha256, write committed entities to ParquetStore (no YAML output) in library/src/undata_library/commit.py
- [ ] T012 [US1] Rewrite cross-reference resolution (_resolve_cross_references) to operate on DataFrames from ParquetStore in library/src/undata_library/commit.py
- [ ] T013 [US1] Remove yaml.dump calls from commit path and yaml_to_parquet conversion step in library/src/undata_library/commit.py and library/src/undata_library/staging.py
- [ ] T014 [US1] Update batch_ingest to use ParquetStore throughout (no YAML intermediaries) in library/src/undata_library/ingest.py
- [ ] T015 [US1] Add test: pipeline run produces zero YAML entity files in library/tests/test_parquet_pipeline.py

**Checkpoint**: `find output -name "*.yaml" -not -path "*/runs/*"` returns 0

---

## Phase 4: User Story 2 — Embeddings at Commit (Priority: P1)

**Goal**: Every committed entity has an embedding computed from comprehensive text

**Independent Test**: Inspect any committed entity → has 384-dim embedding vector

- [ ] T016 [US2] Create build_comprehensive_embedding_text() that uses name + description + type + unit + annotations + provenance in library/src/undata_library/embeddings.py
- [ ] T017 [US2] Add embedding computation step to commit_staged — after sha256 computation, compute embeddings for all entities in batch in library/src/undata_library/commit.py
- [ ] T018 [US2] Ensure all entity types (elements, schemas, values, valuesets) get embeddings at commit in library/src/undata_library/commit.py
- [ ] T019 [US2] Update backend import to skip embedding model loading when all entities have pre-computed embeddings in backend/src/storage/database_backend.py
- [ ] T020 [US2] Update backend import_service to read Parquet-only (remove YAML import path) in backend/src/services/import_service.py
- [ ] T021 [US2] Add test: committed entity has embedding field with 384 floats in library/tests/test_parquet_pipeline.py
- [ ] T022 [US2] Add test: backend import of 100 entities with embeddings completes without loading sentence-transformers model in backend/tests/test_import.py

**Checkpoint**: 100% of committed entities have embeddings; backend import <30s for 7K entities

---

## Phase 5: User Story 3 — Recompute on Update (Priority: P1)

**Goal**: Entity mutations trigger embedding recomputation

**Independent Test**: Update element description → embedding vector changes

- [ ] T023 [US3] Add recompute_embedding() helper to backend embedding_service that computes from entity dict in backend/src/services/embedding_service.py
- [ ] T024 [US3] Wire recompute_embedding into resolve_update_entity (element, schema, value updates) in backend/src/graphql/resolvers.py
- [ ] T025 [US3] Wire recompute_embedding into resolve_approve_annotation and resolve_reject_annotation in backend/src/graphql/resolvers.py
- [ ] T026 [US3] Wire recompute_embedding into resolve_version_element in backend/src/graphql/resolvers.py

**Checkpoint**: Any entity mutation results in fresh embedding reflecting new content

---

## Phase 6: User Story 4 — Missing Embedding Detection (Priority: P2)

**Goal**: Backend detects entities without embeddings, computes them, flags for re-alignment

**Independent Test**: Import entity without embedding → embedding computed → alignment flagged

- [ ] T027 [US4] Add missing embedding detection during import — log warning and compute on demand in backend/src/storage/database_backend.py
- [ ] T028 [US4] Add alignment_needed flag to entities imported without embeddings for background re-alignment in backend/src/storage/database_backend.py
- [ ] T029 [US4] Add background task to process alignment_needed entities (compute embedding + check alignment) in backend/src/services/embedding_service.py

**Checkpoint**: Legacy entities without embeddings are detected, embedded, and flagged

---

## Phase 7: Polish

**Purpose**: Final verification, cleanup, test suite green

- [ ] T030 Run full library test suite — all tests pass with Parquet-only pipeline in library/tests/
- [ ] T031 Run full pipeline for BIDS source end-to-end — verify zero YAML, embeddings present, cross-references resolved (schema properties → sha256), storage <2GB, import <30s
- [ ] T032 [P] Verify CLI inspect command works with Parquet-only registry
- [ ] T033 [P] Verify frontend displays entities imported from Parquet registry with pre-computed embeddings

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: Start immediately
- **US5 Unified Store (Phase 2)**: After Setup — foundational for all stories
- **US1 Parquet Pipeline (Phase 3)**: After US5 — rewrites pipeline
- **US2 Embeddings at Commit (Phase 4)**: After US1 — adds to commit step
- **US3 Recompute on Update (Phase 5)**: After US2 — backend mutations
- **US4 Missing Embeddings (Phase 6)**: After US2 — detection during import
- **Polish (Phase 7)**: After all stories

### Parallel Opportunities

- T023-T026 (mutation wiring) — all modify different functions, parallelizable
- T030-T033 (polish verification) — independent
- US3 and US4 can run in parallel after US2

---

## Implementation Strategy

### MVP First (US5 + US1 + US2)

1. Unified Store → single interface
2. Parquet Pipeline → zero YAML
3. Embeddings at Commit → pre-computed, fast import
4. **STOP and VALIDATE**: Pipeline produces Parquet-only with embeddings, import <30s

### Incremental Delivery

1. US5 → unified store (foundational)
2. US1 → Parquet-only pipeline
3. US2 → embeddings at commit
4. US3 + US4 (parallel) → recompute + missing detection
5. Polish → verification
