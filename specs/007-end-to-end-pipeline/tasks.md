---
description: "Task list for End-to-End Schema Ingestion and LinkML Export"
---

# Tasks: End-to-End Schema Ingestion and LinkML Export

**Branch**: `007-end-to-end-pipeline` | **Date**: 2026-03-11
**Input**: Design documents from `/specs/007-end-to-end-pipeline/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**Tests**: TDD approach — test tasks are included per plan.md specification.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: US1 = Full Schema Ingestion, US2 = LinkML Export with Inheritance, US3 = Reproducible Pipeline

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependencies and create test fixtures needed across all stories.

- [X] T001 Add `pynwb` and `openMINDS` to `[project.dependencies]` in `ingestion/pyproject.toml`
- [X] T002 Add `linkml` to `[dependency-groups]` dev section via `uv add --dev linkml` in `ingestion/pyproject.toml` (required for `make validate` / FR-014 / SC-004)
- [X] T003 Bump version to `2026.03.2` in `ingestion/pyproject.toml`
- [X] T004 Run `uv lock` to update the lock file in `ingestion/`; then run `uv run python -c "import openminds; import pynwb"` to verify both packages import — if either fails, pause and document bridge-venv fallback per FR-002 before proceeding to T021/T019
- [X] T005 [P] Create multi-file NWB namespace test fixture directory `ingestion/tests/fixtures/nwb_namespace_sample/` with `test.namespace.yaml` (using `namespaces[].doc[].source` key per NWB format) and `test.types.yaml` (one `neurodata_type_def` with `neurodata_type_inc` set)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Verify baseline is green before any story work begins.

**⚠️ CRITICAL**: All 132 existing tests must pass after Phase 1 dep changes before US implementation.

- [X] T006 Run `uv run pytest tests/ -q` in `ingestion/` and confirm all existing tests still pass after pyproject.toml dependency additions (pre-implementation baseline; SC-007)

**Checkpoint**: Foundation ready — existing test suite green, new fixtures available.

---

## Phase 3: User Story 1 — Full Schema Ingestion from Real Sources (Priority: P1) 🎯 MVP

**Goal**: Ingest the complete real-world schema data from all five neuroscience standards into a clean database — BIDS ≥ 900 elements, DANDI ≥ 370, NWB ≥ 200, openMINDS ≥ 500, AIND ≥ 100.

**Independent Test**: Run `uv run pytest tests/unit/test_bids_adapter.py tests/unit/test_dandi_adapter.py tests/unit/test_nwb_adapter.py -q` — all tests pass with correct element counts.

### BIDSAdapter — Full Vocabulary + Sidecar Class Grouping (TDD)

- [X] T007 [P] [US1] Write failing tests for `BIDSAdapter.load_code()` loading all 9 vocabulary types (`metadata`, `columns`, `entities`, `suffixes`, `enums`, `formats`, `datatypes`, `extensions`, `files`) with ≥ 900 total elements and `vocabulary_type` in `raw_metadata` in `ingestion/tests/unit/test_bids_adapter.py`
- [X] T008 [P] [US1] Write failing test for `BIDSAdapter.extract_classes()` returning ≥ 20 modality-based sidecar groups (not the `_`-split singleton heuristic) in `ingestion/tests/unit/test_bids_adapter.py`
- [X] T009 [US1] Extend `BIDSAdapter.load_code()` to iterate all `schema.objects.*` attributes and tag each entry with `raw_metadata["vocabulary_type"]` in `ingestion/src/undata/adapters/bids.py` (makes T007 pass)
- [X] T010 [US1] Replace `_`-split heuristic in `BIDSAdapter.extract_classes()` with `schema.rules.sidecars` modality-group reading in `ingestion/src/undata/adapters/bids.py` (makes T008 pass)

### DANDIAdapter — `$defs` Extraction + Self-Ref Fix (TDD)

- [X] T011 [P] [US1] Write failing tests for `DANDIAdapter._elements_from_json_schema()` extracting `$defs` entries with `properties` as separate `SchemaClassPayload` instances in `ingestion/tests/unit/test_dandi_adapter.py`
- [X] T012 [P] [US1] Write failing test for `DANDIAdapter.load_code()` handling self-referencing Pydantic models (mock `model_json_schema()` returning 0 properties, assert fallback to `model.model_fields`) in `ingestion/tests/unit/test_dandi_adapter.py`
- [X] T013 [US1] Extend `DANDIAdapter._elements_from_json_schema()` to iterate `schema.get("$defs", {})` and produce `SchemaClassPayload` + `NormalizedElement` instances per `$defs` entry in `ingestion/src/undata/adapters/dandi.py` (makes T011 pass)
- [X] T014 [US1] Add `model.model_fields` fallback in `DANDIAdapter.load_code()` for models where `model_json_schema()` returns 0 properties in `ingestion/src/undata/adapters/dandi.py` (makes T012 pass)

### NWBAdapter — Multi-File Namespace Traversal (TDD)

- [X] T015 [P] [US1] Write failing test for `NWBAdapter.load_file(directory)` detecting `*.namespace.yaml` and loading all referenced domain YAML files (using `nwb_namespace_sample/` fixture) in `ingestion/tests/unit/test_nwb_adapter.py`
- [X] T016 [P] [US1] Write failing test for `NWBAdapter.load_file(namespace_yaml_path)` traversing `namespaces[].doc[].source` relative paths (NOT `catalog`) in `ingestion/tests/unit/test_nwb_adapter.py`
- [X] T017 [P] [US1] Write failing test for `NWBAdapter.extract_classes()` emitting `parent_class_name` from `neurodata_type_inc` in `ingestion/tests/unit/test_nwb_adapter.py`
- [X] T018 [US1] Add `NWBNamespaceManifest` dataclass (`namespace_name`, `version`, `doc_files`, `base_dir`, `base_url`) in `ingestion/src/undata/adapters/nwb.py`
- [X] T019 [US1] Enhance `NWBAdapter.load_file()` with three-path detection: (1) `groups:` key → existing behavior; (2) `namespaces:` key → parse `namespaces[].doc[].source` and load referenced files; (3) directory → glob `*.namespace.yaml` then load all sources in `ingestion/src/undata/adapters/nwb.py` (makes T015, T016 pass)
- [X] T020 [US1] Extend `NWBAdapter._elements_from_nwb_yaml()` and `extract_classes()` to preserve `neurodata_type_inc` as `parent_class_name` in `SchemaClassPayload` in `ingestion/src/undata/adapters/nwb.py` (makes T017 pass)

### openMINDS — Verify Full Load (TDD)

- [X] T021 [P] [US1] Write unit test using mock `openminds.registry["types"]["latest"]` (same mock pattern as existing `test_openminds_load_code_raises_import_error` in `test_openminds_adapter.py`) confirming ≥ 200 elements from 292 mocked schema types; note: live-backend SC-002 threshold is ≥ 500 (validated in T041) in `ingestion/tests/unit/test_openminds_adapter.py`

### AIND — Extended Fixtures (TDD)

- [X] T022 [P] [US1] Write test confirming `AINDAdapter.load_file(path)` loads ≥ 20 elements from extended AIND JSON Schema files in `ingestion/schemas/aind/`; mark `pytest.mark.skipif` if directory absent with message "run `bash scripts/fetch-schemas.sh` first" in `ingestion/tests/unit/test_aind_adapter.py`

**Checkpoint**: All US1 tests pass. BIDS, DANDI, NWB adapter enhancements complete. openMINDS + AIND verified.

---

## Phase 4: User Story 2 — LinkML Export with Inheritance and Mixins (Priority: P2)

**Goal**: `undata generate-schema` emits `is_a`, `mixin: true`, and `mixins: [...]` from DynamicSchema backend data, passes `linkml-validate` with zero errors.

**Independent Test**: Run `uv run pytest tests/unit/test_linkml_gen.py -q` — all tests pass; inspect mock output YAML for `mixin: true`, `is_a:`, and `mixins:` fields.

### LinkML Generator — Inheritance + Mixin Emission (TDD)

- [X] T023 [P] [US2] Write failing test: mock `GET /schemas` returning a DynamicSchema with `is_mixin=True`, assert output YAML class has `mixin: true` in `ingestion/tests/unit/test_linkml_gen.py`
- [X] T024 [P] [US2] Write failing test: mock DynamicSchema with `parent_id` set, assert output YAML class has `is_a: <ParentName>` in `ingestion/tests/unit/test_linkml_gen.py`
- [X] T025 [P] [US2] Write failing test: mock DynamicSchema with mixin edges from `GET /schemas/{id}/inheritance-tree`, assert output YAML class has `mixins: [MixinName]` in `ingestion/tests/unit/test_linkml_gen.py`
- [X] T026 [P] [US2] Write failing test: mixin-contributed slots are NOT duplicated on child classes (dedup via `GET /schemas/{id}/resolved`) in `ingestion/tests/unit/test_linkml_gen.py`
- [X] T027 [US2] Add `DynamicSchemaNode` and `LinkMLExportContext` dataclasses in `ingestion/src/undata/linkml_gen.py`
- [X] T028 [US2] Implement `LinkMLSchemaGenerator._fetch_dynamic_schemas()` calling `GET /schemas?limit=500` and `GET /schemas/{id}/inheritance-tree` to build `LinkMLExportContext` in `ingestion/src/undata/linkml_gen.py` (makes T023, T024, T025 pass)
- [X] T029 [US2] Integrate Pass 2 into `LinkMLSchemaGenerator.generate()`: iterate `LinkMLExportContext.nodes`, emit `ClassDefinition` with `is_a`, `mixin=True`, and `mixins=[...]`; add classes to `schema.classes` additively in `ingestion/src/undata/linkml_gen.py`
- [X] T030 [US2] Implement mixin slot deduplication: fetch `GET /schemas/{id}/resolved` for each schema, build `mixin_slot_sets`, exclude mixin-contributed slots from child class slot lists in `ingestion/src/undata/linkml_gen.py` (makes T026 pass)
- [X] T031 [US2] Bump `linkml_gen.py` module version constant after generator changes in `ingestion/src/undata/linkml_gen.py`

**Checkpoint**: All US2 tests pass. Generator emits inheritance, mixin flags, and mixins list.

---

## Phase 5: User Story 3 — Reproducible Pipeline Runbook (Priority: P3)

**Goal**: `make pipeline` goes from clean checkout to fully-populated, exported, and validated LinkML schema in one command. Idempotent on re-run.

**Independent Test**: `bash ingestion/scripts/fetch-schemas.sh` completes without error; `make -n pipeline` shows all targets without error.

### Fetch Script

- [X] T032 [P] [US3] Write `ingestion/scripts/fetch-schemas.sh` — download 13 NWB core YAML files from `https://raw.githubusercontent.com/NeurodataWithoutBorders/nwb-schema/dev/core/` to `ingestion/schemas/nwb/` (idempotent: skip if file exists)
- [X] T033 [P] [US3] Extend `ingestion/scripts/fetch-schemas.sh` with openMINDS sparse-checkout: `git clone --depth 1 --filter=blob:none --sparse https://github.com/openMetadataInitiative/openMINDS.git ingestion/schemas/openminds-repo` then `git sparse-checkout set schemas/latest/` (idempotent: skip if directory exists)
- [X] T034 [P] [US3] Extend `ingestion/scripts/fetch-schemas.sh` with AIND extended JSON Schema files download from `https://raw.githubusercontent.com/AllenNeuralDynamics/aind-data-schema/main/` to `ingestion/schemas/aind/` (idempotent: skip if files exist)
- [X] T035 [P] [US3] Extend `ingestion/scripts/fetch-schemas.sh` with DANDI schema release files (v0.7.0: `asset.json`, `dandiset.json`, `published-asset.json`, `published-dandiset.json`, `context.json`) to `ingestion/schemas/dandi/` (idempotent: skip if files exist)

### Makefile

- [X] T036 [US3] Write `ingestion/Makefile` with targets: `backend-up` (docker compose up), `backend-wait` (poll `/health` with timeout), `fetch-schemas` (run fetch-schemas.sh), `ingest-code` (bids dandi nwb openminds --extraction-mode code; satisfies FR-007), `ingest-aind` (aind --extraction-mode file), `ingest` (ingest-code + ingest-aind), `generate` (generate-schema --output unified.yaml), `validate` (linkml-validate --schema unified.yaml), `pipeline` (all in order); document Docker/backend requirements per target in `ingestion/Makefile`

### 409 Duplicate Source Handling

- [X] T037 [US3] Verify `DuplicateSourceError` (HTTP 409) is caught and logged as WARN in `ingestion/src/undata/cli.py` — log WARN and continue rather than raising, so `make pipeline` is idempotent
- [X] T038 [P] [US3] Verify `ingestion/scripts/fetch-schemas.sh` idempotency: run the script twice back-to-back and assert the second run exits 0 and produces the same file counts (skip-if-exists guard working for NWB, openMINDS, AIND, DANDI sections)

**Checkpoint**: All US3 artifacts complete. `make pipeline` dry-run works.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, linting, gitignore, and documentation.

- [X] T039 [P] Add `ingestion/schemas/`, `ingestion/schemas/openminds-repo/`, and `ingestion/unified.yaml` to `.gitignore` (downloaded artifacts must not be committed)
- [X] T040 Run full test suite `uv run pytest tests/ -q` in `ingestion/` and confirm ≥ 132 tests pass, 0 failures (SC-007 final regression check — distinct from pre-impl baseline T006)
- [X] T041 [P] Run `uv run ruff check ingestion/src/ ingestion/tests/` and `uv run ruff format --check ingestion/src/ ingestion/tests/` — fix any violations in modified files (constitution linting requirement)
- [X] T042 [P] Run QS-005 through QS-007 live validation from `quickstart.md` against a running backend: confirm SC-001 (`GET /elements total ≥ 2500`), SC-002 (per-source counts), SC-004 (`linkml-validate` exits 0) — document results in a comment in `specs/007-end-to-end-pipeline/quickstart.md`
- [X] T043 Update `CLAUDE.md` at repo root — add `007-end-to-end-pipeline: IN PROGRESS` entry noting pynwb/openMINDS added to pyproject.toml and LinkML generator inheritance pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 complete — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2; BIDS/DANDI/NWB/openMINDS/AIND adapter tracks are independent of each other
- **US2 (Phase 4)**: Depends on Phase 2 only; independent of US1 (generator tests use mocked backend)
- **US3 (Phase 5)**: Depends on Phase 2; independent of US1/US2 (shell scripts + Makefile)
- **Polish (Phase 6)**: Depends on US1 + US2 + US3 complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — BIDS/DANDI/NWB/openMINDS/AIND adapter tasks can proceed in parallel
- **US2 (P2)**: After Foundational — independent of US1 (generator tests use mocked backend)
- **US3 (P3)**: After Foundational — independent of US1/US2 (fetch scripts and Makefile are standalone)

### Within Each User Story

- TDD order: Write failing test → implement → verify test passes
- Within US1: BIDS (T007–T010), DANDI (T011–T014), NWB (T015–T020), openMINDS (T021), AIND (T022) are independent parallel adapter tracks
- Within US2: Test tasks (T023–T026) → Dataclasses (T027) → Generator methods (T028–T030) → Version bump (T031)
- Within US3: Fetch script sections (T032–T035) can be written in parallel → Makefile (T036) → 409 check (T037) → idempotency check (T038)

### Parallel Opportunities

- T007, T011, T015 — BIDS, DANDI, NWB first test files can be written simultaneously
- T009/T010 (BIDS impl), T013/T014 (DANDI impl), T018/T019/T020 (NWB impl) — parallel adapter implementation tracks
- T021 (openMINDS), T022 (AIND) — parallel after T006
- T023, T024, T025, T026 — all LinkML generator test cases are independent
- T032, T033, T034, T035 — all fetch-schemas.sh sections are independent (different URLs/repos)
- T039, T041, T042 — Polish tasks affecting different files

---

## Parallel Example: User Story 1

```bash
# Three independent adapter tracks can run concurrently after T006:

# Track A — BIDS
T007 Write failing BIDS tests (full vocab)
T008 Write failing BIDS sidecar test
T009 Implement BIDSAdapter.load_code() full vocabulary
T010 Fix BIDSAdapter.extract_classes() sidecar groups

# Track B — DANDI (parallel with Track A)
T011 Write failing DANDI $defs tests
T012 Write failing DANDI self-ref test
T013 Implement DANDIAdapter $defs extraction
T014 Implement DANDIAdapter self-ref fallback

# Track C — NWB (parallel with Tracks A and B)
T015 Write failing NWB directory test
T016 Write failing NWB namespace YAML test (namespaces[].doc[].source)
T017 Write failing NWB parent_class_name test
T018 Add NWBNamespaceManifest dataclass
T019 Enhance NWBAdapter.load_file() namespace traversal
T020 Extend extract_classes() with parent_class_name
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Add deps + uv lock
2. Complete Phase 2: Verify 132 tests green
3. Complete Phase 3 (US1): Run adapter tracks in parallel
4. **STOP and VALIDATE**: Run `uv run python -c "from undata.adapters.bids import BIDSAdapter; b=BIDSAdapter(); b.load_code(); print(len(b.extract_elements('code')))"`
5. Deploy / demo if ready

### Incremental Delivery

1. Setup + Foundational → baseline green
2. US1 (adapter enhancements) → real schema data ingestible
3. US2 (LinkML inheritance) → richly structured export possible
4. US3 (Makefile + fetch-schemas) → one-command reproducibility
5. Polish → ruff clean, gitignore, live SC-001 validation

### Adapter-Parallel Team Strategy

With multiple developers on US1 after T006:
- Dev A: BIDS adapter (T007–T010)
- Dev B: DANDI adapter (T011–T014)
- Dev C: NWB adapter (T015–T020)
- Dev D: openMINDS verification (T021) + AIND test (T022)

All tracks merge before T039 (final test sweep).

---

## Notes

- [P] tasks = different files or independent concerns, no blocking dependencies
- TDD: write test → confirm FAIL → implement → confirm PASS
- Backward compatibility: `nwb_schema_sample.yaml` uses `groups:` key — must still pass (case 1 in T019)
- NWB YAML key is `namespaces[].doc[].source` (NOT `catalog`) — see I03 fix in plan.md AD-001
- `ingestion/schemas/` contains downloaded artifacts; must not be committed (T038)
- T022 AIND test uses `skipif` (not xfail) since the file-absence is expected in CI without fetch step
- T021 openMINDS unit test threshold ≥ 200 (mock); live-backend SC-002 threshold ≥ 500 (validated in T041)
- All 132 existing tests must remain green after every implementation task (SC-007)
- Total tasks: **43**
