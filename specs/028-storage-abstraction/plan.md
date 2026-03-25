# Implementation Plan: Library Storage Abstraction

**Branch**: `028-storage-abstraction` | **Date**: 2026-03-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/028-storage-abstraction/spec.md`

## Summary

Introduce a `StorageBackend` protocol that decouples pipeline functions from the file system, implement `FileBackend` wrapping current YAML behavior with zero regressions, refactor pipeline functions to accept backend parameters, clean up adapters to pure LinkML-first pattern, and reorder pipeline stages so alignment informs content addressing.

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14"`)
**Primary Dependencies**: pydantic 2.x, linkml-runtime 1.8+, sentence-transformers, litellm, pyoxigraph
**Storage**: YAML flat files (FileBackend); protocol enables future PostgreSQL (DatabaseBackend)
**Testing**: pytest + pytest-asyncio, 343 existing tests as regression baseline
**Target Platform**: Linux/macOS, CLI + library API
**Project Type**: Library (with CLI entry points)
**Performance Goals**: Pipeline throughput unchanged (no new overhead from abstraction)
**Constraints**: FileBackend must produce byte-identical output to current implementation
**Scale/Scope**: 5 source adapters, ~8,800 entities, 13 ontologies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Protocol is minimal (3 sub-protocols). FileBackend wraps existing code. No speculative abstractions. |
| II. Test-Driven Development | PASS | 343 existing tests are the primary regression gate. New protocol tests written before implementation. |
| III. API-First Design | PASS | StorageBackend protocol defined in contracts/storage-protocol.md before implementation. |
| IV. Observability | PASS | Pipeline logging unchanged. Backend operations log at DEBUG level. |
| V. No Deprecation, No Migration | PASS | No backwards compatibility needed. Path-based signatures replaced directly. |
| VI. Environment Isolation | PASS | All work in uv-managed venv. No new system dependencies. |
| VII. Developer Experience | PASS | CLI behavior unchanged. `uv run pytest` validates everything. |
| Git Commit Discipline | PASS | Commit per task phase. |
| CI Green Before Merge | PASS | All library tests must pass in remote CI before merging to main. |
| Evaluation Record | PASS | Entity counts recorded after pipeline reorder for baseline comparison. |

## Project Structure

### Documentation (this feature)

```text
specs/028-storage-abstraction/
├── plan.md              # This file
├── research.md          # Phase 0: design decisions
├── data-model.md        # Phase 1: protocol and entity model
├── quickstart.md        # Phase 1: validation scenarios
├── contracts/
│   └── storage-protocol.md  # Phase 1: protocol contract
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
library/src/undata_library/
├── storage/                  # NEW: storage abstraction module
│   ├── __init__.py           # Exports StorageBackend, FileBackend
│   ├── protocol.py           # StorageBackend, EntityStore, FlagStore, RunStore protocols
│   ├── file_backend.py       # FileBackend implementation (wraps current YAML I/O)
│   └── mock_backend.py       # MockBackend for testing (in-memory dict)
├── adapters/
│   ├── base.py               # MODIFIED: to_linkml() replaces extract()
│   ├── extractor.py          # NEW: standard LinkML → ClassifiedEntity extractor
│   ├── bids.py               # MODIFIED: to_linkml() only
│   ├── nwb.py                # MODIFIED: to_linkml() only
│   ├── dandi.py              # MODIFIED: to_linkml() only
│   ├── openminds.py          # MODIFIED: to_linkml() only
│   ├── aind.py               # MODIFIED: to_linkml() only
│   └── linkml.py             # MODIFIED: becomes the extractor reference
├── ingest.py                 # MODIFIED: accepts StorageBackend
├── enrich.py                 # MODIFIED: accepts StorageBackend
├── commit.py                 # MODIFIED: accepts staging + output backends
├── align.py                  # MODIFIED: accepts StorageBackend
├── cross_align.py            # MODIFIED: accepts StorageBackend
├── transform.py              # MODIFIED: accepts StorageBackend
├── curation.py               # MODIFIED: uses FlagStore
├── run_summary.py            # MODIFIED: uses RunStore
├── cli.py                    # MODIFIED: creates FileBackend, passes to functions
└── staging.py                # MODIFIED: creates staging StorageBackend

library/tests/
├── test_storage_protocol.py  # NEW: protocol conformance tests
├── test_file_backend.py      # NEW: FileBackend-specific tests
├── test_mock_backend.py      # NEW: MockBackend tests
├── test_pipeline_with_backend.py  # NEW: pipeline functions with explicit backend
└── [existing 343 tests]      # UNCHANGED
```

**Structure Decision**: New `storage/` subpackage within the library. All changes are to the library — no backend or frontend changes in this feature.

## Implementation Approach

### Phase 1: Protocol + FileBackend (US1 + US2)

1. Define `StorageBackend`, `EntityStore`, `FlagStore`, `RunStore` protocols in `storage/protocol.py`
2. Implement `FileBackend` in `storage/file_backend.py` by wrapping existing `utils.safe_load_yaml`, `utils.write_yaml`, and glob patterns
3. Implement `MockBackend` in `storage/mock_backend.py` (in-memory dict for testing)
4. Write protocol conformance tests (round-trip, list, exists, merge_provenance, find_by_hash, filters, flag lifecycle, run lifecycle)
5. Verify: all 343 existing tests still pass

### Phase 2: Pipeline Refactor (US3)

1. Refactor `ingest.py` — replace `library_path: Path` with `staging: StorageBackend`
2. Refactor `enrich.py` — replace `staging_dir: Path` with `staging: StorageBackend`
3. Refactor `commit.py` — replace `staging_dir: Path, output_dir: Path` with `staging: StorageBackend, output: StorageBackend`
4. Refactor `align.py` — replace `elements_dir: Path` with `backend: StorageBackend`
5. Refactor `cross_align.py` — replace `registry_dir: Path` with `backend: StorageBackend`
6. Refactor `transform.py` — replace paths with `backend: StorageBackend`
7. Refactor `curation.py` — use `FlagStore` from backend
8. Refactor `run_summary.py` — use `RunStore` from backend
9. Refactor `cli.py` — create `FileBackend(output_dir)` and pass to all functions
10. Verify: all 343 existing tests still pass
11. Add new tests: pipeline functions with MockBackend

### Phase 3: Adapter Cleanup (US4)

1. Create `adapters/extractor.py` with standard `extract_from_schema_definition(SchemaDefinition) → [ClassifiedEntity]`
2. Rename `BaseAdapter.extract()` to `BaseAdapter.to_linkml()` returning `SchemaDefinition`
3. Update each adapter (BIDS, NWB, DANDI, openMINDS, AIND) to pure `to_linkml()`
4. Update `ingest.py` to call `adapter.to_linkml()` then `extractor.extract()`
5. Verify: entity counts within 5% of baseline

### Phase 4: Pipeline Reorder (US5)

1. Change pipeline command order: extract → enrich → align → commit → transform
2. Modify align to work on staging (not committed) entities
3. Modify cross_source_align to work on staging
4. Verify: annotation transfers happen before commit
5. Record entity counts in eval-record.md

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| StorageBackend has 3 sub-protocols | Entity, flag, and run I/O have distinct patterns | Single generic CRUD loses type-specific semantics (find_by_hash, resolve_flag, load_previous) |
| StagingArea separate from StorageBackend | Staging has different lifecycle (UUID names, cleanup) | Single backend with staged flag mixes concerns and complicates queries |
