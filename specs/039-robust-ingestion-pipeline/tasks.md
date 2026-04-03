# Tasks: Robust Ingestion Pipeline v2

**Input**: Design documents from `/specs/039-robust-ingestion-pipeline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

**Purpose**: Parquet infrastructure, pyarrow dependency

- [X] T001 Add pyarrow dependency to library/pyproject.toml
- [X] T002 Create ParquetStore class with read/write/query methods for entity collections in library/src/undata_library/storage/parquet_store.py
- [X] T003 Add unit tests for ParquetStore — write entities, read by sha256, dedup on re-write in library/tests/test_parquet_store.py

**Checkpoint**: Parquet read/write working with tests

---

## Phase 2: Foundational

**Purpose**: Extend StorageBackend protocol + FileBackend to support Parquet

- [X] T004 Extend StorageBackend protocol with write_batch() and read_batch() methods in library/src/undata_library/storage/protocol.py
- [X] T005 Update FileBackend to use ParquetStore when entity count > threshold (default 1000) in library/src/undata_library/storage/file_backend.py
- [X] T006 Update staging module to write entities to Parquet when batch size exceeds threshold in library/src/undata_library/staging.py
- [X] T007 Update commit module to read from Parquet staging and write Parquet registry in library/src/undata_library/commit.py
- [X] T008 Add cross-source index (_index.parquet) generation during commit for sha256→source lookup in library/src/undata_library/commit.py

**Checkpoint**: Pipeline uses Parquet for large sources, YAML for small sources

---

## Phase 3: User Story 1 — Scalable Entity Storage (Priority: P1)

**Goal**: 2.7M entities stored in Parquet containers, not individual files

**Independent Test**: Ingest NDA → entities in .parquet files → CLI can query individual entities

- [X] T009 [US1] Add CLI inspect command to query individual entities from Parquet files by sha256 or name in library/src/undata_library/cli.py
- [ ] T010 [US1] Update import_service.py to read Parquet registry format when importing to database in backend/src/services/import_service.py
- [X] T011 [US1] Add integration test: write 10K entities to Parquet, read back, verify dedup works, assert Parquet file size < 10x individual YAML equivalent in library/tests/test_parquet_store.py
- [ ] T012 [US1] Update export_service.py to export Parquet format alongside YAML in backend/src/services/export_service.py

**Checkpoint**: Full Parquet round-trip — write, read, query, import to DB, export

---

## Phase 4: User Story 2 — All Adapters Through Pipeline (Priority: P1)

**Goal**: Every source (including batch OpenNeuro/NDA) routes through extract → enrich → align → commit → transform

**Independent Test**: `undata-library pipeline --source nda --all` → all entities enriched + committed with sha256

- [X] T013 [US2] Add --batch N flag to pipeline CLI for multi-dataset sources in library/src/undata_library/cli.py
- [X] T014 [US2] Add --all flag to pipeline CLI for API-backed sources (NDA) in library/src/undata_library/cli.py
- [X] T015 [US2] Implement batch_ingest() function — iterate datasets/structures, accumulate entities in staging in library/src/undata_library/ingest.py
- [X] T016 [US2] Wire OpenNeuro batch: clone via git+datalad → extract → cleanup → next dataset in library/src/undata_library/ingest.py
- [X] T017 [US2] Wire NDA batch: fetch structure from API → extract → next structure in library/src/undata_library/ingest.py
- [X] T018 [US2] Add BatchRunSummary with per-dataset breakdown to run summary output in library/src/undata_library/run_summary.py
- [X] T019 [US2] Remove ad-hoc batch scripts (replaced by CLI) and add test asserting no code writes directly to registry outside pipeline in library/scripts/ingest_openneuro_fast.py, library/scripts/ingest_openneuro_batch.py, and library/tests/test_no_direct_writes.py
- [X] T020 [US2] Add progress reporting to batch pipeline — log [N/total] dataset_id → entity_count (time) in library/src/undata_library/ingest.py

**Checkpoint**: `pipeline --source nda --all` completes through full pipeline stages

---

## Phase 5: User Story 3 — NDA Alias Preservation (Priority: P1)

**Goal**: NDA cross-structure aliases preserved and used in alignment

**Independent Test**: Ingest 2 NDA structures sharing elements → alias_hints populated → alignment groups them

- [X] T021 [US3] Add alias dedup to NDA adapter — group elements by name+type across structures, merge provenance in library/src/undata_library/adapters/nda.py
- [X] T022 [US3] Add alias_hints field to ClassifiedEntity semantic dict (list of source refs for shared elements) in library/src/undata_library/adapters/nda.py
- [X] T023 [US3] Update alignment step to check alias_hints and boost confidence for pre-verified aliases in library/src/undata_library/align.py
- [X] T024 [US3] Add test: two NDA structures with shared element → alias_hints populated → alignment links them with higher confidence than embedding-only baseline in library/tests/test_nda_aliases.py

**Checkpoint**: NDA aliases used as high-confidence hints in alignment

---

## Phase 6: User Story 4 — Element Range Display (Priority: P1)

**Goal**: Element detail page shows range/constraint info (valueset, min/max, pattern, type_ref)

**Independent Test**: Browse element with response_options → see linked valueset; element with min/max → see range

- [ ] T025 [P] [US4] Audit BIDS adapter for range field population (response_options, min/max, pattern, type_ref) in library/src/undata_library/adapters/bids.py
- [ ] T026 [P] [US4] Audit NWB adapter — add min/max extraction from hdmf attribute metadata in library/src/undata_library/adapters/nwb.py
- [ ] T027 [P] [US4] Audit openMINDS adapter — add min/max extraction from range constraints in library/src/undata_library/adapters/openminds.py
- [ ] T028 [P] [US4] Audit OpenNeuro adapter — extract range from JSON sidecar MinValue/MaxValue in library/src/undata_library/adapters/openneuro.py
- [X] T029 [US4] Add range display section to EntityDetailLayout — show min/max, pattern, response_options, type_ref in frontend/components/EntityDetailLayout.tsx
- [X] T030 [US4] Link response_options values to ValueSet entities in element detail page in frontend/app/elements/[id]/page.tsx
- [X] T031 [US4] Link type_ref to Schema detail page in element detail in frontend/app/elements/[id]/page.tsx

**Checkpoint**: Element detail page shows all range constraints with linked entities

---

## Phase 7: User Story 5 — Batch Pipeline CLI (Priority: P2)

**Goal**: Single CLI command for batch ingestion with progress and error reporting

**Independent Test**: `undata-library pipeline --source openneuro --batch 10` → 10 datasets processed with summary

- [X] T032 [US5] Add graceful error handling for individual dataset failures in batch mode in library/src/undata_library/ingest.py
- [X] T033 [US5] Add consolidated batch run summary with success/fail/skip counts and per-dataset timing in library/src/undata_library/run_summary.py
- [ ] T034 [US5] Test batch pipeline: --source openneuro --batch 5 completes with summary in library/tests/test_batch_pipeline.py

**Checkpoint**: Batch CLI handles failures gracefully and produces consolidated summary

---

## Phase 8: User Story 6 — Enrichment at Scale (Priority: P2)

**Goal**: Enrichment handles 220K+ elements efficiently with species-level precision

**Independent Test**: Enrich 220K elements → completes <30min → mouse matches "Mus musculus" not "Mus"

- [X] T035 [US6] Add chunk-based enrichment — process elements in batches of 10K to control memory in library/src/undata_library/enrich.py
- [X] T036 [US6] Add species precision post-filter — remove genus-level matches when species-level exists in library/src/undata_library/enrich.py
- [ ] T037 [US6] Test enrichment species precision: element about mouse → primary match is Mus musculus not Mus in library/tests/test_enrich.py

**Checkpoint**: Enrichment scales to 220K+ elements with species-level precision

---

## Phase 9: Polish

**Purpose**: Final verification, seed update, cleanup

- [ ] T038 Regenerate curated seed subset from Parquet registry with all sources in backend/seed/
- [ ] T039 Run full pipeline for all 8 sources end-to-end and verify registry integrity
- [ ] T040 [P] Verify backend imports from Parquet registry correctly
- [ ] T041 [P] Verify frontend element detail shows range information for seed elements

---

## Dependencies & Execution Order

- **Setup + Foundational (Phase 1-2)**: Start immediately — Parquet infrastructure
- **US1 Storage (Phase 3)**: After Foundational — CLI inspect + DB import
- **US2 Pipeline Routing (Phase 4)**: After Foundational — batch CLI + pipeline wiring
- **US3 NDA Aliases (Phase 5)**: After US2 (needs batch NDA ingestion working)
- **US4 Range Display (Phase 6)**: Independent of US1-US3 (adapter audit + frontend)
- **US5 Batch CLI (Phase 7)**: After US2 (extends batch infrastructure)
- **US6 Enrichment (Phase 8)**: Independent of US1-US5
- **Polish (Phase 9)**: After all stories

### Parallel Opportunities

- T025-T028 (adapter audits) — all independent, different files
- US4 (range display) can run in parallel with US1-US3
- US6 (enrichment scaling) is fully independent
- T040, T041 (polish verification) — independent

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Setup + Foundational → Parquet infrastructure
2. US1 → Parquet storage round-trip
3. US2 → Batch pipeline routing
4. **STOP and VALIDATE**: `pipeline --source nda --all` produces Parquet registry

### Incremental Delivery

1. Setup + Foundational → Parquet infra
2. US1 + US2 (sequential) → storage + pipeline routing (MVP)
3. US3 + US4 (parallel) → NDA aliases + range display
4. US5 + US6 (parallel) → batch CLI polish + enrichment scaling
5. Polish → verification + seed regeneration
