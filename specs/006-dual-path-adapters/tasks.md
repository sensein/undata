# Tasks: Dual-Path Schema Adapters (006)

**Input**: Design documents from `/specs/006-dual-path-adapters/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Included per constitution Principle II (TDD is NON-NEGOTIABLE).
Tests must be written FIRST and must FAIL before any implementation task begins.

**Organization**: Tasks grouped by user story. US1 (file-path) and US2 (code-path) are
independently implementable in parallel. US3 (merge) depends on US1 + US2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 maps to user stories in spec.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Fixtures and shared model changes needed before any adapter work begins.

- [X] T001 Create DANDI JSON Schema release fixture files (dandiset.json + asset.json with $defs block, mimicking releases/0.6.7/ structure) in ingestion/tests/fixtures/dandi/releases/0.6.7/
- [X] T002 [P] Add ExtractionMode type alias, AdapterResult dataclass, update SchemaClassPayload (extraction_path default `"file"`, add optional schema_format field) in ingestion/src/undata/models.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Protocol contract and test structure that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Update SchemaAdapter Protocol in ingestion/src/undata/adapters/base.py — add `load_code()`, `load_file(path_or_url)`, update `extract_elements(mode: ExtractionMode = "file")` and `extract_classes(mode: ExtractionMode = "file")` signatures; retain `load()` shim
- [X] T004 Write failing Protocol conformance test (all 5 adapters satisfy SchemaAdapter v2 via `isinstance` check) in new ingestion/tests/contract/test_adapter_protocol.py — must FAIL before US1/US2 implementations

**Checkpoint**: Foundation ready — US1 and US2 can now proceed in parallel

---

## Phase 3: User Story 1 — File-Path Extraction (Priority: P1) 🎯 MVP

**Goal**: Every adapter exposes `load_file(path)` for version-pinned, file-based schema ingestion
without needing the Python library installed.

**Independent Test**: Given a local path to schema files for any adapter, calling
`adapter.load_file(path); adapter.extract_elements("file")` returns non-empty
`NormalizedElement` list with `extraction_path="file"` on all `SchemaClassPayload` objects.

### Tests for User Story 1 (write FIRST — must FAIL)

- [X] T005 [P] [US1] Add failing unit tests for `DANDIAdapter.load_file()`: (a) given fixture dir `tests/fixtures/dandi/releases/0.6.7/`, extract_elements("file") returns elements with schema_format="json", extract_classes("file") returns classes with extraction_path="file"; (b) assert `load_file("")` raises `ValueError` with message describing required path format in ingestion/tests/unit/test_dandi_adapter.py
- [X] T006 [P] [US1] Add failing unit tests for `BIDSAdapter.load_file()`: (a) given fixture YAML path, extract_elements("file") returns BIDS fields, extract_classes("file") returns extraction_path="file", schema_format="yaml"; (b) mock `bidsschematools` absent from `sys.modules`, assert YAML parsing still returns elements (FR-006 no-library requirement); (c) assert `load_file("")` raises `ValueError` in ingestion/tests/unit/test_bids_adapter.py
- [X] T007 [P] [US1] Add failing unit tests for `NWBAdapter.load_file()`: (a) given fixture YAML path, extract_elements("file") returns NWB attrs/datasets, extract_classes("file") returns extraction_path="file", schema_format="yaml"; (b) mock `httpx.get()` returning fixture YAML content and assert `load_file("http://example.com/nwb.yaml")` succeeds (FR-007 URL support); (c) assert `load_file("")` raises `ValueError` in ingestion/tests/unit/test_nwb_adapter.py
- [X] T008 [P] [US1] Add failing unit tests for `OpenMINDSAdapter.load_file()`: (a) single `.schema.omi.json` file; (b) directory glob of `*.schema.omi.json`; (c) `extract_classes("file")` returns extraction_path="file", schema_format="jsonld"; (d) assert `load_file("")` raises `ValueError` in ingestion/tests/unit/test_openminds_adapter.py
- [X] T009 [P] [US1] Add failing unit tests for `AINDAdapter.load_file()`: given fixture dir, extract_elements("file") returns AIND elements, extract_classes("file") returns classes with extraction_path="file", schema_format="json" (AIND has well-known default so empty path is NOT a ValueError case) in ingestion/tests/unit/test_aind_adapter.py

### Implementation for User Story 1

- [X] T010 [P] [US1] Implement `DANDIAdapter.load_file(path_or_url)`: parse JSON Schema files from releases dir, resolve `$defs`, populate `self._file_models`; add mode dispatch to `extract_elements()` and `extract_classes()` with schema_format="json" in ingestion/src/undata/adapters/dandi.py
- [X] T011 [P] [US1] Implement `BIDSAdapter.load_file(path)`: promote existing raw YAML parsing code to named method, populate `self._file_fields`; add mode dispatch to `extract_elements()` and `extract_classes()` with schema_format="yaml" in ingestion/src/undata/adapters/bids.py
- [X] T012 [P] [US1] Implement `NWBAdapter.load_file(path_or_url)`: if `path_or_url` starts with `http`, fetch content via `httpx.get(path_or_url).text` then parse with `yaml.safe_load`; otherwise open local file; promote existing YAML load code to named method, populate `self._file_groups`; raise `ValueError` if path empty; add mode dispatch with schema_format="yaml" in ingestion/src/undata/adapters/nwb.py
- [X] T013 [P] [US1] Implement `OpenMINDSAdapter.load_file(path)`: support single `.schema.omi.json` file OR glob all `*.schema.omi.json` in directory, populate `self._file_types` list; add mode dispatch with schema_format="jsonld" in ingestion/src/undata/adapters/openminds.py
- [X] T014 [P] [US1] Implement `AINDAdapter.load_file(path)`: promote existing JSON Schema dir reader to named method, populate `self._file_schemas`; add mode dispatch with schema_format="json" in ingestion/src/undata/adapters/aind.py
- [X] T035 Update ingestion/tests/unit/test_adapter_class_extraction.py — change existing `extraction_path` assertions from format-specific values ("yaml"/"json"/"jsonld") to "file" for BIDS/NWB/openMINDS/AIND; confirm "code" for DANDI unchanged (must run BEFORE Phase 4+ tests so TDD green cycle is unbroken)
- [X] T039 [P] [US1] Write failing unit test for `OpenMINDSAdapter.load_turtle(path)`: create minimal Turtle fixture `ingestion/tests/fixtures/openminds_sample.ttl` with 2–3 RDF type+property triples; assert `load_turtle(path)` then `extract_elements("file")` returns non-empty elements in ingestion/tests/unit/test_openminds_adapter.py (FR-008, edge-turtle)
- [X] T040 [P] [US1] Implement `OpenMINDSAdapter.load_turtle(path)`: parse `.ttl` via `rdflib.Graph().parse(path)`, extract subjects as types and predicate objects as properties, append to `self._file_types`; raise `ValueError` if path empty in ingestion/src/undata/adapters/openminds.py

**Checkpoint**: US1 complete — all 5 adapters support `load_file()` + `extract_elements("file")`; Turtle path via rdflib covered

---

## Phase 4: User Story 2 — Code-Introspection Path (Priority: P2)

**Goal**: Every adapter exposes `load_code()` for self-updating library introspection. BIDS, NWB,
openMINDS, and AIND gain new code paths. DANDI promotes its existing implementation.

**Independent Test**: Given only the adapter's Python library installed, calling
`adapter.load_code(); adapter.extract_elements("code")` returns elements with
`extraction_path="code"`. AIND raises `ImportError` if `aind-data-schema` unavailable.

### Tests for User Story 2 (write FIRST — must FAIL)

- [X] T015 [P] [US2] Add failing unit tests for `DANDIAdapter.load_code()`: verify extract_elements("code") returns same structure as old load() behavior; schema_format="code" in ingestion/tests/unit/test_dandi_adapter.py
- [X] T016 [P] [US2] Add failing unit tests for `BIDSAdapter.load_code()`: mock bidsschematools.schema.load_schema(); verify extract_elements("code") returns elements with schema_format="code"; verify extraction_path="code" on classes in ingestion/tests/unit/test_bids_adapter.py
- [X] T017 [P] [US2] Add failing unit tests for `NWBAdapter.load_code()`: mock pynwb.get_type_map() and hdmf namespace registry; verify extract_elements("code") returns typed NWB elements in ingestion/tests/unit/test_nwb_adapter.py
- [X] T018 [P] [US2] Add failing unit tests for `OpenMINDSAdapter.load_code()`: mock openminds.registry; verify extract_elements("code") returns elements deduped across "latest"/"v4"; schema_format="code" in ingestion/tests/unit/test_openminds_adapter.py
- [X] T019 [P] [US2] Add failing unit test for `AINDAdapter.load_code()`: assert raises `ImportError` in TWO scenarios — (a) `aind_data_schema` absent: pop from `sys.modules` via `unittest.mock.patch.dict`; (b) simulated C-extension failure: raise `ImportError("pyo3...")` to cover Python 3.14 Rust-extension path (SC-002); message must contain "aind" in both cases in ingestion/tests/unit/test_aind_adapter.py

### Implementation for User Story 2

- [X] T020 [P] [US2] Implement `DANDIAdapter.load_code()`: rename/promote existing `load()` Pydantic introspection body into `load_code()`, keep `load()` as shim; update `extract_classes()` to set schema_format="code" in ingestion/src/undata/adapters/dandi.py
- [X] T021 [P] [US2] Implement `BIDSAdapter.load_code()`: call `bidsschematools.schema.load_schema()` (no path), populate `self._code_fields`; raise `ImportError` if bidsschematools unavailable; set schema_format="code" in ingestion/src/undata/adapters/bids.py
- [X] T022 [P] [US2] Implement `NWBAdapter.load_code()`: first verify `pynwb` and `hdmf` are in `ingestion/pyproject.toml` dependencies (add under `[project.dependencies]` if missing); call `pynwb.get_type_map()`, enumerate `ns.get_registered_types()` from hdmf NamespaceCatalog, populate `self._code_groups`; raise `ImportError` if pynwb unavailable; set schema_format="code" in ingestion/src/undata/adapters/nwb.py
- [X] T023 [P] [US2] Implement `OpenMINDSAdapter.load_code()`: iterate `openminds.registry["types"]["latest"]`, deduplicate against "v4" by type URI, populate `self._code_types`; raise `ImportError` if openminds unavailable; set schema_format="code" in ingestion/src/undata/adapters/openminds.py
- [X] T024 [P] [US2] Implement `AINDAdapter.load_code()`: try-import `aind_data_schema.base.DataCoreModel`, raise `ImportError` with clear message if unavailable; enumerate `__subclasses__()` recursively; populate `self._code_models`; set schema_format="code" in ingestion/src/undata/adapters/aind.py

**Checkpoint**: US2 complete — all 5 adapters support `load_code()` + `extract_elements("code")`

---

## Phase 5: User Story 3 — Dual-Path Merge (Priority: P3)

**Goal**: `extract_elements(mode="both")` and `extract_classes(mode="both")` merge code and file
paths, deduplicate by `source_local_id`, WARN on single-path elements, ERROR on type conflicts.

**Independent Test**: Given DANDI adapter with both code and file paths loaded, calling
`extract_elements("both")` returns a merged list where ≥ 95% of elements have
`extraction_path="both"` (SC-003). Type conflicts produce `.code`/`.file` suffixed IDs.

### Tests for User Story 3 (write FIRST — must FAIL)

- [X] T025 [US3] Write failing unit tests for `_merge_elements()` and `_merge_classes()` in new ingestion/tests/unit/test_dual_path_merge.py: test dedup (same SLID → extraction_path="both"), WARN log for code-only, WARN log for file-only, ERROR log + disambiguated IDs for type conflict
- [X] T026 [P] [US3] Add failing unit test for `DANDIAdapter.extract_elements(mode="both")`: load code + fixture, verify ≥ 95% overlap in ingestion/tests/unit/test_dandi_adapter.py
- [X] T027 [P] [US3] Add failing unit test for `BIDSAdapter.extract_elements(mode="both")`: load code via bidsschematools bundled schema + load file from a **distinct** YAML fixture (e.g., `tests/fixtures/bids_schema_sample.yaml` subset) to verify genuine cross-path overlap ≥ 95% (SC-003) — do NOT use the same source for both paths; verify extraction_path values in ingestion/tests/unit/test_bids_adapter.py
- [X] T042 [P] [US3] Add failing unit test for `NWBAdapter.extract_elements(mode="both")`: load code via pynwb/hdmf + load file from fixture YAML; verify ≥ 95% overlap by source_local_id (SC-003) in ingestion/tests/unit/test_nwb_adapter.py
- [X] T043 [P] [US3] Add failing unit test for `OpenMINDSAdapter.extract_elements(mode="both")`: load code via openminds registry + load file from fixture JSON-LD dir; verify ≥ 95% overlap by source_local_id (SC-003) in ingestion/tests/unit/test_openminds_adapter.py
- [X] T044 [P] [US3] Add failing unit test for `AINDAdapter.extract_elements(mode="both")`: load code raises ImportError on Python 3.14 (bridge venv unavailable in test env) — assert both-mode gracefully falls back to file-only with WARN log; verify extraction_path="file" on all elements in ingestion/tests/unit/test_aind_adapter.py

### Implementation for User Story 3

- [X] T028 [US3] Create ingestion/src/undata/adapters/merge.py with `merge_elements(code_elements, file_elements, merge_strategy="code")` and `merge_classes(code_classes, file_classes, merge_strategy="code")`: dedup by source_local_id/class_name, WARN for single-path, ERROR + .code/.file suffixes for type conflict
- [X] T029 [P] [US3] Add `extract_elements(mode="both")` and `extract_classes(mode="both")` dispatch to `DANDIAdapter` using merge.py: auto-call `load_code()` + `load_file(self._file_path)` if not already loaded in ingestion/src/undata/adapters/dandi.py
- [X] T030 [P] [US3] Add `extract_elements(mode="both")` and `extract_classes(mode="both")` dispatch to `BIDSAdapter` in ingestion/src/undata/adapters/bids.py
- [X] T031 [P] [US3] Add `extract_elements(mode="both")` and `extract_classes(mode="both")` dispatch to `NWBAdapter` in ingestion/src/undata/adapters/nwb.py
- [X] T032 [P] [US3] Add `extract_elements(mode="both")` and `extract_classes(mode="both")` dispatch to `OpenMINDSAdapter` in ingestion/src/undata/adapters/openminds.py
- [X] T033 [P] [US3] Add `extract_elements(mode="both")` and `extract_classes(mode="both")` dispatch to `AINDAdapter` in ingestion/src/undata/adapters/aind.py

**Checkpoint**: All 3 user stories complete — all adapters support code/file/both modes

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T034 Add `--extraction-mode [code|file|both]` (default: "code") and `--source-path PATH` (required when mode=file/both and adapter has no default) flags to `ingest` command in ingestion/src/undata/cli.py; update `_get_adapter()` to call `load_code()` or `load_file(path)` based on mode
- [X] T041 Add `extraction_mode: ExtractionMode = "code"` and `source_path: str = ""` parameters to `IngestionPipeline.ingest()` in ingestion/src/undata/ingestion.py; pass mode to adapter `load_code()` or `load_file(source_path)` calls instead of hard-coded `load()` (FR-002)
- [X] T036 Run `uv run ruff check ingestion/src/ ingestion/tests/` and `uv run ruff format ingestion/src/ ingestion/tests/` from repo root; fix all lint errors
- [X] T037 Run `uv run pytest ingestion/tests/ -v` from repo root; verify all tests pass including existing element-extraction tests (SC-006)
- [X] T038 Verify Protocol conformance test T004 passes for all 5 adapters after US1+US2 implementations complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001 and T002 can start immediately and in parallel
- **Foundational (Phase 2)**: T003 depends on T002 (needs ExtractionMode type); T004 depends on T003 (tests the updated Protocol)
- **US1 (Phase 3)**: Tests (T005-T009) depend on T003 (Protocol updated), T001 (DANDI fixture exists); Implementations (T010-T014) depend on their corresponding tests failing
- **US2 (Phase 4)**: Tests (T015-T019) depend on T003; Implementations (T020-T024) depend on their tests failing; US2 is independent of US1 (different internal state)
- **US3 (Phase 5)**: T025-T027 tests depend on T003 + T002; T028 merge utility can be done before US1/US2 but dispatch tasks T029-T033 depend on US1 + US2 complete
- **Polish (Phase 6)**: T034 (CLI) depends on all US complete; T041 (IngestionPipeline) depends on T034; T036→T037→T038 are sequential post-all

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 only — file-path is independent of code-path
- **US2 (P2)**: Depends on Phase 2 only — code-path is independent of file-path
- **US3 (P3)**: Depends on US1 + US2 — merge requires both paths to be implemented

### Within Each User Story

- Tests (T005-T009 or T015-T019 or T025-T027) MUST be written FIRST and confirmed to FAIL
- All 5 adapter implementations within a story (T010-T014 or T020-T024) can be done in parallel (different files)
- T028 (merge utility) before T029-T033 (dispatch implementations)

---

## Parallel Execution Examples

### US1 — Run all file-path tests in parallel (T005-T009):

```
Task T005: Add DANDIAdapter.load_file() tests in test_dandi_adapter.py
Task T006: Add BIDSAdapter.load_file() tests in test_bids_adapter.py
Task T007: Add NWBAdapter.load_file() tests in test_nwb_adapter.py
Task T008: Add OpenMINDSAdapter.load_file() tests in test_openminds_adapter.py
Task T009: Add AINDAdapter.load_file() tests in test_aind_adapter.py
```

### US1 — Run all file-path implementations in parallel (T010-T014):

```
Task T010: Implement DANDIAdapter.load_file() in adapters/dandi.py
Task T011: Implement BIDSAdapter.load_file() in adapters/bids.py
Task T012: Implement NWBAdapter.load_file() in adapters/nwb.py
Task T013: Implement OpenMINDSAdapter.load_file() in adapters/openminds.py
Task T014: Implement AINDAdapter.load_file() in adapters/aind.py
```

### US2 — Run all code-path implementations in parallel (T020-T024):

```
Task T020: Implement DANDIAdapter.load_code() in adapters/dandi.py
Task T021: Implement BIDSAdapter.load_code() in adapters/bids.py
Task T022: Implement NWBAdapter.load_code() in adapters/nwb.py
Task T023: Implement OpenMINDSAdapter.load_code() in adapters/openminds.py
Task T024: Implement AINDAdapter.load_code() in adapters/aind.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only — file-path for all adapters)

1. Complete Phase 1: T001-T002
2. Complete Phase 2: T003-T004
3. Complete Phase 3: T005-T014 (US1 — file-path)
4. **STOP and VALIDATE**: `uv run pytest ingestion/tests/ -v`
5. US1 is independently shippable — file-based pinned ingestion works for all adapters

### Incremental Delivery

1. Setup + Foundational (T001-T004) → Protocol defined
2. US1 (T005-T014) → File-path ingestion for all 5 adapters ✓
3. US2 (T015-T024) → Code-path for BIDS/NWB/openMINDS/AIND (DANDI was already code-path)
4. US3 (T025-T033) → Dual-path merge + conflict detection
5. Polish (T034-T038) → CLI flags, lint, regression

### Total Task Count

| Phase | Tasks | Parallel Opportunities |
|-------|-------|----------------------|
| Setup | 2 | T001+T002 in parallel |
| Foundational | 2 | Sequential (T003→T004) |
| US1 (tests) | 5 | T005-T009 all parallel |
| US1 (impl+fixes) | 8 | T010-T014 parallel; T035, T039-T040 parallel |
| US2 (tests) | 5 | T015-T019 all parallel |
| US2 (impl) | 5 | T020-T024 all parallel |
| US3 (tests) | 6 | T026-T027, T042-T044 parallel |
| US3 (impl) | 6 | T029-T033 parallel after T028 |
| Polish | 5 | T034→T041→T036→T037→T038 sequential |
| **Total** | **44** | **~31 parallelizable** |

---

## Notes

- Adapters maintain SEPARATE internal state for code-loaded vs file-loaded data:
  - Code state: `_code_fields` / `_code_groups` / `_code_models` / `_code_types`
  - File state: `_file_fields` / `_file_groups` / `_file_models` / `_file_types`
  - The existing state vars (`_raw_fields`, `_raw_groups`, `_models`, `_data`, `_schemas`) remain for backward compatibility; `load()` shim populates them AND the file-state vars
- `extract_elements(mode=None)` → default "file" for backward compatibility (existing `load()` was file-based for BIDS/NWB/openMINDS/AIND; DANDI maps `load()` to `load_code()`)
- The 68 pre-existing tests must continue to pass; do NOT change their `adapter.load(path)` calls
- `test_adapter_class_extraction.py` assertions on `extraction_path` WILL need updating (T035) since format-specific values change to "file"
- SC-006: All 68 existing tests pass without modification (they call `load()` which is preserved as shim)
