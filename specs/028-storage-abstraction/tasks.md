# Tasks: Library Storage Abstraction

**Input**: Design documents from `/specs/028-storage-abstraction/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/storage-protocol.md

**Tests**: Included — constitution requires TDD. Protocol conformance tests before implementation, regression tests throughout.

**Organization**: Tasks grouped by user story. US1+US2 are tightly coupled (protocol + file backend) and form Phase 3 together. US3 is the pipeline refactor. US4 and US5 are independent P2 stories.

**Phase mapping** (tasks.md → plan.md): Tasks Phase 1-2 = plan Setup; Tasks Phase 3 = plan Phase 1; Tasks Phase 4 = plan Phase 2; Tasks Phase 5 = plan Phase 3; Tasks Phase 6 = plan Phase 4; Tasks Phase 7 = plan Polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- All paths relative to `library/src/undata_library/` unless noted

## Phase 1: Setup

**Purpose**: Create storage module structure

- [X] T001 Create `storage/` package directory with `__init__.py` in `library/src/undata_library/storage/__init__.py`
- [X] T002 Run full test suite to establish baseline — record passing count in `library/tests/` (`uv run pytest tests/ -v`)

**Checkpoint**: Module structure exists, baseline test count recorded

---

## Phase 2: Foundational — Protocol Definition

**Purpose**: Define the StorageBackend protocol (blocking all subsequent work)

**⚠️ CRITICAL**: No implementation work can begin until the protocol is defined and reviewed

- [X] T003 Define `EntityStore` protocol with read/write/list/exists/delete/merge_provenance/count/find_by_hash in `storage/protocol.py`
- [X] T004 Define `FlagStore` protocol with write_flag/read_flags/resolve_flag in `storage/protocol.py`
- [X] T005 Define `RunStore` protocol with save_summary/load_previous/list_runs in `storage/protocol.py`
- [X] T006 Define `StorageBackend` composite protocol (entities + flags + runs) in `storage/protocol.py`
- [X] T007 Write protocol conformance test suite in `library/tests/test_storage_protocol.py` — tests that any backend must pass (round-trip, list, exists, merge_provenance, find_by_hash, filters [source, has_annotations, data_type], flag lifecycle, run lifecycle, concurrent reads)

**Checkpoint**: Protocol defined, conformance tests written (will fail until backends are implemented)

---

## Phase 3: User Stories 1+2 — FileBackend + Zero Regressions (Priority: P1) 🎯 MVP

**Goal**: Implement FileBackend wrapping current YAML behavior. All 343 existing tests pass unchanged.

**Independent Test**: `uv run pytest tests/ -v` — 343+ tests pass, 0 test files modified

### Tests

- [X] T008 [P] [US1] Write FileBackend-specific tests in `library/tests/test_file_backend.py` — entity CRUD with YAML files, directory layout, filename patterns
- [X] T009 [P] [US1] Write MockBackend tests in `library/tests/test_mock_backend.py` — in-memory dict behavior, operation recording

### Implementation

- [X] T010 [US2] Implement `FileEntityStore` in `storage/file_backend.py` — wraps `safe_load_yaml`/`write_yaml`/glob for elements/schemas/values/valuesets
- [X] T011 [P] [US2] Implement `FileFlagStore` in `storage/file_backend.py` — wraps current `curation.py` file I/O for curation-flags/
- [X] T012 [P] [US2] Implement `FileRunStore` in `storage/file_backend.py` — wraps current `run_summary.py` file I/O for runs/
- [X] T013 [US2] Implement `FileBackend` class composing EntityStore + FlagStore + RunStore in `storage/file_backend.py`
- [X] T014 [US1] Implement `MockBackend` with in-memory dict storage and operation recording in `storage/mock_backend.py`
- [X] T015 [US1] Export `StorageBackend`, `FileBackend`, `MockBackend` from `storage/__init__.py`
- [X] T016 [US2] Run protocol conformance tests against FileBackend — all must pass in `library/tests/test_storage_protocol.py`
- [X] T017 [US1] Run protocol conformance tests against MockBackend — all must pass in `library/tests/test_storage_protocol.py`
- [X] T018 [US2] Run full existing test suite — verify all 343+ tests still pass (`uv run pytest tests/ -v`)

**Checkpoint**: FileBackend and MockBackend satisfy protocol. All existing tests pass. Zero test files modified.

---

## Phase 4: User Story 3 — Pipeline Functions Accept Backend (Priority: P1)

**Goal**: Refactor all pipeline functions to accept StorageBackend parameter. CLI creates FileBackend transparently.

**Independent Test**: Pipeline functions work with both FileBackend (same output as before) and MockBackend (no file system access)

### Tests

- [X] T019 [US3] Write pipeline integration tests with MockBackend in `library/tests/test_pipeline_with_backend.py` — verify each function calls expected backend methods

### Implementation

- [ ] T020 [US3] Refactor `ingest.py` — replace `library_path: Path` parameter with `staging: StorageBackend | None = None` (auto-creates FileBackend from path if None), use `staging.entities.write()` instead of direct file I/O
- [ ] T021 [US3] Refactor `enrich.py` — replace `staging_dir: Path` with `staging: StorageBackend`, use `staging.entities.list()`/`read()`/`write()` for in-place updates
- [ ] T022 [US3] Refactor `commit.py` — replace `staging_dir: Path, output_dir: Path` with `staging: StorageBackend, output: StorageBackend`, use `output.entities.find_by_hash()` for merge detection
- [ ] T023 [US3] Refactor `align.py` — replace `elements_dir: Path` with `backend: StorageBackend`, use `backend.entities.list("elements")` for alias detection
- [ ] T024 [US3] Refactor `cross_align.py` — replace `registry_dir: Path` with `backend: StorageBackend`, use entity listing and in-place writes
- [ ] T025 [US3] Refactor `transform.py` — replace path parameters with `backend: StorageBackend`
- [X] T026 [US3] Refactor `curation.py` — delegate to `backend.flags` (write_flag, read_flags, resolve_flag) instead of direct file I/O
- [X] T027 [US3] Refactor `run_summary.py` — delegate to `backend.runs` (save_summary, load_previous) instead of direct file I/O
- [ ] T028 [US3] Refactor `staging.py` — create staging as `FileBackend(staging_dir)` instead of manual directory management
- [ ] T029 [US3] Refactor `cli.py` — create `FileBackend(output_dir)` and pass to all pipeline functions, update all CLI commands
- [ ] T030 [US3] Run full existing test suite — verify all 343+ tests still pass (`uv run pytest tests/ -v`)
- [ ] T031 [US3] Run pipeline integration tests with MockBackend — verify no file system access in `library/tests/test_pipeline_with_backend.py`

**Checkpoint**: All pipeline functions accept StorageBackend. CLI behavior identical. MockBackend tests pass.

---

## Phase 5: User Story 4 — Adapter Cleanup (Priority: P2)

**Goal**: All 5 adapters produce LinkML SchemaDefinition via `to_linkml()`. Standard extractor handles classification.

**Independent Test**: Each adapter's `to_linkml()` returns a SchemaDefinition. Entity counts within 5% of baseline.

### Implementation

- [ ] T032 [US4] Create standard `extract_from_schema_definition()` function in `adapters/extractor.py` — converts LinkML SchemaDefinition → [ClassifiedEntity]
- [ ] T033 [US4] Update `BaseAdapter` in `adapters/base.py` — rename `extract()` to `to_linkml()` returning SchemaDefinition
- [ ] T034 [P] [US4] Update BIDSAdapter in `adapters/bids.py` — pure `to_linkml()`, remove any direct ClassifiedEntity creation
- [ ] T035 [P] [US4] Update NWBAdapter in `adapters/nwb.py` — pure `to_linkml()`, remove any direct ClassifiedEntity creation
- [ ] T036 [P] [US4] Update DANDIAdapter in `adapters/dandi.py` — pure `to_linkml()`, remove any direct ClassifiedEntity creation
- [ ] T037 [P] [US4] Update openMINDSAdapter in `adapters/openminds.py` — pure `to_linkml()`, remove any direct ClassifiedEntity creation
- [ ] T038 [P] [US4] Update AINDAdapter in `adapters/aind.py` — pure `to_linkml()`, remove any direct ClassifiedEntity creation
- [ ] T039 [US4] Update `ingest.py` to call `adapter.to_linkml()` → `extract_from_schema_definition()` instead of `adapter.extract()`
- [ ] T040 [US4] Update adapter registry in `adapters/registry.py` to reflect new interface
- [ ] T041 [US4] Run extraction for all 5 sources, compare entity counts to baseline (2,191 elements, 915 schemas, 5,500 values, 214 valuesets) — document deltas
- [ ] T042 [US4] Run full test suite — verify all tests pass (`uv run pytest tests/ -v`)

**Checkpoint**: All adapters produce LinkML only. Standard extractor classifies. Entity counts documented.

---

## Phase 6: User Story 5 — Pipeline Stage Reordering (Priority: P2)

**Goal**: Pipeline runs extract→enrich→align→commit→transform. Annotation transfers happen before content addressing.

**Independent Test**: Pipeline output shows align step before commit. Annotation transfers visible in committed entities.

### Implementation

- [ ] T043 [US5] Modify `align.py` to work on staged entities (not just committed) — accept staging backend, read from staging entity store
- [ ] T044 [US5] Modify `cross_align.py` to work on staged entities — transfer annotations in staging before commit
- [ ] T045 [US5] Update pipeline command in `cli.py` — change stage order from extract→enrich→commit→align to extract→enrich→align→commit→transform
- [ ] T046 [US5] Run full pipeline with new order, verify annotation transfers happen before commit — check that committed entities contain transferred annotations
- [ ] T047 [US5] Run full test suite — verify all tests pass (`uv run pytest tests/ -v`)

**Checkpoint**: Pipeline stages reordered. Annotation transfer before commit verified.

---

## Phase 7: Polish & Validation

**Purpose**: Final validation, evaluation record, cleanup

- [ ] T048 Run full pipeline for all 5 sources, record entity counts in `eval-record.md` at repository root
- [ ] T049 Compare entity counts with brainstorm v1 baseline — document any changes and reasons
- [ ] T050 Run quickstart validation scenarios QS-001 through QS-008 from `specs/028-storage-abstraction/quickstart.md`
- [ ] T051 Verify `ruff check` and `ruff format` pass on all modified files
- [ ] T052 Push branch and verify CI is green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Protocol)**: Depends on Phase 1
- **Phase 3 (FileBackend)**: Depends on Phase 2 — BLOCKS pipeline refactor
- **Phase 4 (Pipeline Refactor)**: Depends on Phase 3
- **Phase 5 (Adapter Cleanup)**: Depends on Phase 4 (needs new ingest.py signatures)
- **Phase 6 (Pipeline Reorder)**: Depends on Phase 4 (needs backend-aware align/commit)
- **Phase 7 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1+US2 (Protocol + FileBackend)**: No dependencies — start after protocol definition
- **US3 (Pipeline Refactor)**: Depends on US1+US2 (needs FileBackend)
- **US4 (Adapter Cleanup)**: Depends on US3 (needs refactored ingest.py)
- **US5 (Pipeline Reorder)**: Depends on US3 (needs backend-aware pipeline functions)
- **US4 and US5**: Can run in parallel after US3

### Parallel Opportunities

**Phase 3** (within FileBackend implementation):
- T008, T009 — tests can run in parallel
- T011, T012 — FlagStore and RunStore are independent files within file_backend.py

**Phase 4** (pipeline refactor — mostly sequential due to shared imports, but some parallel):
- T020-T025 can be done in parallel (different files) after T029 (cli.py) establishes the pattern

**Phase 5** (adapter cleanup):
- T034, T035, T036, T037, T038 — all 5 adapters can be updated in parallel

---

## Parallel Example: Phase 5 (Adapter Cleanup)

```bash
# After T032 (extractor) and T033 (base adapter) are done,
# launch all 5 adapter updates in parallel:
Task: "Update BIDSAdapter in adapters/bids.py"
Task: "Update NWBAdapter in adapters/nwb.py"
Task: "Update DANDIAdapter in adapters/dandi.py"
Task: "Update openMINDSAdapter in adapters/openminds.py"
Task: "Update AINDAdapter in adapters/aind.py"
```

---

## Implementation Strategy

### MVP First (US1+US2+US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Protocol definition
3. Complete Phase 3: FileBackend (all existing tests pass)
4. Complete Phase 4: Pipeline refactor (MockBackend tests pass)
5. **STOP and VALIDATE**: 343+ tests pass, pipeline produces identical output, MockBackend proves decoupling

### Full Delivery

6. Complete Phase 5: Adapter cleanup (entity counts validated)
7. Complete Phase 6: Pipeline reorder (annotation transfer before commit)
8. Complete Phase 7: Polish + eval record + CI green

---

## Notes

- The critical invariant is SC-001: all 343+ existing tests pass after every phase
- Run `uv run pytest tests/ -v` after every phase — if any test fails, fix before proceeding
- FileBackend must produce byte-identical YAML output to current implementation
- No new dependencies added to pyproject.toml (protocol uses only typing stdlib)
- Commit after each completed phase
