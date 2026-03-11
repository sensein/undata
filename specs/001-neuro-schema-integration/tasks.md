# Tasks: Neuroscience Schema Integration

**Feature**: `001-neuro-schema-integration` | **Branch**: `001-neuro-schema-integration`
**Input**: Design documents from `/specs/001-neuro-schema-integration/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli-interface.md ✅, quickstart.md ✅

**Tests**: TDD approach — test tasks are marked ⚠️ and MUST FAIL before their corresponding implementation tasks.

**User Stories**:
- US1 P1 — Schema Ingestion (ingest BIDS, DANDI, openMINDS, NWB into backend)
- US2 P2 — LinkML Generation (generate unified LinkML YAML schema)
- US3 P3 — Alias Detection & Mapping (semantic dedup + identity mapping registration)
- US4 P4 — Validation (validate data files against unified LinkML schema)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create ingestion/ project scaffold: src/undata/, tests/unit/, tests/integration/, tests/contract/, tests/fixtures/
- [x] T002 Write ingestion/pyproject.toml: `requires-python = ">=3.14"`, `[tool.uv]` section, all dependencies (bidsschematools, dandischema, openminds-python, hdmf, linkml-runtime>=1.8, sentence-transformers>=3, httpx>=0.27, typer>=0.12, pydantic>=2, python-json-logger>=3, respx, pytest, pytest-asyncio), entry point `undata = undata.cli:app`
- [x] T003 [P] Create ingestion/.gitignore and verify root .gitignore covers __pycache__/, *.pyc, .venv/, dist/, *.egg-info/, uv.lock
- [x] T038 Create uv-managed venv for ingestion package: run `uv venv ingestion/.venv --python 3.14` and `uv pip install -e "ingestion/[all]"` inside ingestion/; verify `uv run python --version` reports 3.14.x

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures and shared infrastructure required by all user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create NormalizedElement, IngestionResult, AliasCandidate dataclasses in ingestion/src/undata/models.py
- [x] T005 [P] Implement SchemaAdapter Protocol (load, extract_elements, get_version_info) in ingestion/src/undata/adapters/base.py
- [x] T006 [P] Create sample fixture files: ingestion/tests/fixtures/bids_schema_sample.yaml, dandi_schema_sample.json, openminds_sample.json, nwb_schema_sample.yaml
- [x] T007 Create typer CLI skeleton in ingestion/src/undata/cli.py with stub commands: ingest, detect-aliases, generate-schema, validate (all raise NotImplementedError)
- [x] T008 [P] Create ingestion/src/undata/__init__.py exporting SchemaAdapter, NormalizedElement, IngestionResult, AliasCandidate
- [x] T039 Create ingestion/src/undata/logging.py: `get_logger(name: str)` returning a `logging.Logger` with `python-json-logger` JsonFormatter emitting JSON to stderr; import and use in cli.py and ingestion.py (Principle IV — structured logs required on all runtime paths)

**Checkpoint**: Foundation ready — data structures, adapter protocol, CLI skeleton, and logging are in place

---

## Phase 3: User Story 1 — Schema Ingestion (Priority: P1) 🎯 MVP

**Goal**: Ingest BIDS, DANDI, openMINDS, and NWB schemas, normalize elements to NormalizedElement, and bulk-POST to backend `/api/v1/elements/bulk`.

**Independent Test**: `undata ingest bids --dry-run` reports > 0 elements with 0 failures; full ingest stores elements retrievable via `GET /elements`.

### Tests for User Story 1 ⚠️ Write FIRST — must FAIL before implementation

- [x] T009 [P] [US1] Unit test for BIDSAdapter: verify extract_elements() returns NormalizedElement list with correct name/data_type/description in ingestion/tests/unit/test_bids_adapter.py
- [x] T010 [P] [US1] Unit test for DANDIAdapter: verify Pydantic model introspection produces correct NormalizedElements in ingestion/tests/unit/test_dandi_adapter.py
- [x] T011 [P] [US1] Unit test for OpenMINDSAdapter: verify JSON-LD template parsing produces NormalizedElements in ingestion/tests/unit/test_openminds_adapter.py
- [x] T012 [P] [US1] Unit test for NWBAdapter: verify hdmf YAML spec loading produces NormalizedElements in ingestion/tests/unit/test_nwb_adapter.py
- [x] T013 [US1] Integration test for IngestionPipeline: uses respx to mock POST /api/v1/sources and POST /api/v1/elements/bulk; verifies IngestionResult counts in ingestion/tests/integration/test_ingest_pipeline.py
- [x] T014 [US1] CLI contract test for `undata ingest bids --dry-run`: verifies stdout format, exit code 0, and no backend calls in ingestion/tests/contract/test_cli_ingest.py

### Implementation for User Story 1

- [x] T015 [P] [US1] Implement BIDSAdapter using bidsschematools.schema.load_schema(); map schema.objects.metadata fields to NormalizedElement in ingestion/src/undata/adapters/bids.py
- [x] T016 [P] [US1] Implement DANDIAdapter: introspect dandischema.models BaseModel subclasses via model.model_fields and model.model_json_schema(); map to NormalizedElement in ingestion/src/undata/adapters/dandi.py
- [x] T017 [P] [US1] Implement OpenMINDSAdapter: parse JSON-LD template files from openminds-python or bundled schemas; extract properties with @type/label/description; map to NormalizedElement in ingestion/src/undata/adapters/openminds.py
- [x] T018 [P] [US1] Implement NWBAdapter: use hdmf spec loader on bundled/fetched YAML; iterate attributes and datasets; map to NormalizedElement in ingestion/src/undata/adapters/nwb.py
- [x] T019 [US1] Implement IngestionPipeline in ingestion/src/undata/ingestion.py: async httpx client, POST /api/v1/sources (upsert), POST /api/v1/elements/bulk (chunked), --dry-run mode (skip writes), returns IngestionResult
- [x] T020 [US1] Wire `undata ingest` CLI command in ingestion/src/undata/cli.py: SOURCE args, --backend-url, --token/UNDATA_TOKEN, --version-tag, --dry-run, --output-format text/json, --log-level; emit text/json to stdout; exit codes 0/1/2

**Checkpoint**: `undata ingest bids --dry-run` and full ingest work end-to-end

---

## Phase 3.5: AIND Adapter (5th Schema Source)

**Goal**: Add Allen Institute for Neural Dynamics (AIND) schema as a 5th ingestion source.
AIND uses `aind-data-schema` 2.x which requires a Rust extension (pyo3-ffi) incompatible with Python 3.14.
Solution: parse pre-exported JSON Schema files bundled in tests/fixtures/aind/.

### Tests for AIND Adapter ⚠️ Write FIRST — must FAIL before implementation

- [x] T040 [P] [US1] Copy AIND JSON schema files from /tmp/aind-data-schema/schemas/ to ingestion/tests/fixtures/aind/: subject_schema.json, acquisition_schema.json, data_description_schema.json, procedures_schema.json, instrument_schema.json
- [x] T041 [P] [US1] Unit test for AINDAdapter: verify extract_elements() returns NormalizedElements from bundled JSON Schema files; verify content_hash is stable; verify "aind" source_name in ingestion/tests/unit/test_aind_adapter.py

### Implementation for AIND Adapter

- [x] T042 [P] [US1] Implement AINDAdapter in ingestion/src/undata/adapters/aind.py: load JSON Schema files from fixtures/aind/ dir (or path arg); resolve $defs references; map properties to NormalizedElement; handle required array; compute content_hash from combined schema text
- [x] T043 [US1] Wire "aind" source into CLI _get_adapter() in ingestion/src/undata/cli.py and add "aind" to _KNOWN_SOURCES
- [x] T044 [P] [US1] Update ingestion/src/undata/__init__.py to export AINDAdapter; add aind source class to linkml_gen.py _SOURCE_CLASSES if applicable

**Checkpoint**: `undata ingest aind --dry-run` reports > 0 AIND elements with 0 failures

---

## Phase 4: User Story 2 — LinkML Schema Generation (Priority: P2)

**Goal**: Fetch all DataElements from backend and generate a unified LinkML YAML schema with source-specific subclasses, slots, and enumerations.

**Independent Test**: `undata generate-schema --output unified.yaml` produces valid YAML that passes `linkml-validate` schema lint with 0 errors.

### Tests for User Story 2 ⚠️ Write FIRST — must FAIL before implementation

- [x] T021 [US2] Integration test for LinkMLSchemaGenerator: uses respx to mock GET /api/v1/elements; verifies schema has NeuroscienceDataset class, slots, and enums; verifies YAML serialization in ingestion/tests/integration/test_linkml_gen.py
- [x] T022 [US2] CLI contract test for `undata generate-schema`: verifies output is valid YAML with expected top-level keys; verifies --format json-ld switch in ingestion/tests/contract/test_cli_generate.py

### Implementation for User Story 2

- [x] T023 [US2] Implement LinkMLSchemaGenerator in ingestion/src/undata/linkml_gen.py: async httpx GET /api/v1/elements (paginated), build SchemaDefinition with NeuroscienceDataset + BIDSDataset/DANDIDataset/NWBFile/openMINDSDataset subclasses, SlotDefinition per deduplicated element, EnumDefinition for allowed_values fields, YAMLDumper serialization
- [x] T024 [US2] Wire `undata generate-schema` CLI command in ingestion/src/undata/cli.py: --backend-url, --output FILE, --schema-id, --schema-name, --version, --include-sources, --format yaml/json-ld; write to file or stdout

**Checkpoint**: `undata generate-schema --output unified.yaml` produces valid LinkML YAML

---

## Phase 5: User Story 3 — Alias Detection & Mapping (Priority: P3)

> **Scope note**: This phase implements **identity mapping detection only** (FR-013, FR-014).
> Non-identity mapping functions (FR-011, FR-012, FR-015, FR-016, FR-017 — user-defined
> `target = f(inputs, params)`, apply-mapping, cycle detection, unmapped-element reporting)
> are **deferred to 004-migration-api**, which owns transformation execution. The spec's US3
> acceptance scenarios 1, 2, 5, and 6 are out of scope for this feature.

**Goal**: Run three-phase alias detection (exact name → type gate → embedding cosine) over backend elements and register identity mappings via `/api/v1/mappings`.

**Independent Test**: `undata detect-aliases --dry-run` identifies at least one `skos:exactMatch` pair (e.g., subject_age / participant_age) when BIDS + DANDI elements are present.

### Tests for User Story 3 ⚠️ Write FIRST — must FAIL before implementation

- [x] T025 [P] [US3] Unit test for AliasDetector: verify exact name normalization (synonym table), type gate filtering, and cosine similarity thresholds (0.92 exactMatch, 0.80–0.92 closeMatch) in ingestion/tests/unit/test_alias_detection.py
- [x] T026 [US3] Integration test for AliasDetector end-to-end: uses respx to mock GET /api/v1/elements and POST /api/v1/mappings; verifies AliasCandidate output and mapping registration in ingestion/tests/integration/test_alias_pipeline.py
- [x] T027 [US3] CLI contract test for `undata detect-aliases`: verifies text/json/sssom-tsv output formats; verifies --dry-run skips POST /mappings in ingestion/tests/contract/test_cli_aliases.py

### Implementation for User Story 3

- [x] T028 [US3] Implement AliasDetector in ingestion/src/undata/alias_detection.py: async httpx GET /api/v1/elements, three-phase pipeline (exact name normalization with hardcoded synonym table, type+cardinality gate, sentence-transformers all-MiniLM-L6-v2 embedding cosine), POST /api/v1/mappings for each pair, --dry-run mode, SSSOM TSV serialization
- [x] T029 [US3] Wire `undata detect-aliases` CLI command in ingestion/src/undata/cli.py: --backend-url, --token, --threshold, --dry-run, --output-format text/json/sssom-tsv, --source-filter; emit to stdout

**Checkpoint**: `undata detect-aliases --dry-run --output-format sssom-tsv` produces correct SSSOM output

---

## Phase 6: User Story 4 — Validation (Priority: P4)

**Goal**: Validate JSON/YAML data files against the unified LinkML schema using linkml-runtime.

**Independent Test**: A conformant sample JSON passes; a JSON with a missing required field fails with a clear error message; exit codes are 0 (PASS) and 1 (FAIL).

### Tests for User Story 4 ⚠️ Write FIRST — must FAIL before implementation

- [x] T030 [US4] Unit test for ValidationService: verify pass/fail outcomes for conformant and non-conformant data dicts against a minimal LinkML schema fixture in ingestion/tests/unit/test_validation.py
- [x] T031 [US4] CLI contract test for `undata validate`: verifies exit code 0 for PASS, exit code 1 for FAIL with structured error output, --target-class switch in ingestion/tests/contract/test_cli_validate.py

### Implementation for User Story 4

- [x] T032 [US4] Implement ValidationService in ingestion/src/undata/validation.py: load LinkML schema from --schema file or fetch generated schema from backend; use linkml-runtime JsonSchemaDataValidator or equivalent; collect all violations; structured text/json error report
- [x] T033 [US4] Wire `undata validate` CLI command in ingestion/src/undata/cli.py: DATA_FILE arg, --schema FILE, --target-class, --output-format text/json; exit 0 (PASS), 1 (FAIL), 2 (tool error)

**Checkpoint**: All four user stories are independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, library API surface, and quickstart verification

- [x] T034 [P] Expose Python library API in ingestion/src/undata/__init__.py: export IngestionPipeline, LinkMLSchemaGenerator, AliasDetector, ValidationService, all four adapters
- [x] T035 Run quickstart.md validation checklist: `undata ingest bids --dry-run`, full 5-source ingest (bids dandi openminds nwb aind), `detect-aliases --dry-run`, `generate-schema --output unified.yaml`, `undata validate sample.json` PASS and FAIL cases
- [x] T036 [P] Verify performance targets: 5-source ingest < 5 min on developer workstation; alias detection over 1k elements < 30s
- [x] T037 [P] Write ingestion/tests/fixtures/sample_conformant.json and sample_nonconformant.json for quickstart validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2; no dependency on US2/US3/US4
- **US2 (Phase 4)**: Depends on Phase 2; independent of US3/US4; benefits from US1 elements in backend for integration tests
- **US3 (Phase 5)**: Depends on Phase 2; independent of US2/US4; requires elements in backend (US1) for integration tests with real data
- **US4 (Phase 6)**: Depends on Phase 2; independent of US3; uses schema from US2 (can stub for unit tests)
- **Polish (Phase 7)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Can start immediately after Phase 2 — no story dependencies
- **US2 (P2)**: Can start after Phase 2 — no story dependencies (integration tests stub backend)
- **US3 (P3)**: Can start after Phase 2 — no story dependencies (integration tests stub backend)
- **US4 (P4)**: Can start after Phase 2 — no story dependencies (unit tests use inline schema fixture)

### Within Each User Story

- ⚠️ Test tasks MUST be written first and MUST FAIL before implementation
- Models/dataclasses before services
- Services before CLI wiring
- Core implementation before integration

### Parallel Opportunities

- T009–T012 (adapter unit tests) — all parallel, different files
- T015–T018 (adapter implementations) — all parallel, different files
- T025 and T028 are independent within US3
- US2 and US3 can be worked in parallel after US1 checkpoint
- US4 can start as soon as US2 is done (or use inline schema fixture)

---

## Parallel Example: User Story 1

```bash
# Parallel: all four adapter tests (different files, no deps):
Task: "T009 Unit test for BIDSAdapter in tests/unit/test_bids_adapter.py"
Task: "T010 Unit test for DANDIAdapter in tests/unit/test_dandi_adapter.py"
Task: "T011 Unit test for OpenMINDSAdapter in tests/unit/test_openminds_adapter.py"
Task: "T012 Unit test for NWBAdapter in tests/unit/test_nwb_adapter.py"

# Parallel: all four adapter implementations (after tests fail):
Task: "T015 Implement BIDSAdapter in adapters/bids.py"
Task: "T016 Implement DANDIAdapter in adapters/dandi.py"
Task: "T017 Implement OpenMINDSAdapter in adapters/openminds.py"
Task: "T018 Implement NWBAdapter in adapters/nwb.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 Schema Ingestion
4. **STOP and VALIDATE**: `undata ingest bids --dry-run` passes; backend shows ingested elements
5. Continue to US2, US3, US4 in priority order

### Incremental Delivery

1. Phase 1 + Phase 2 → Scaffold and data structures ready
2. US1 → Test independently → Ingest pipeline works (MVP!)
3. US2 → Test independently → LinkML generation works
4. US3 → Test independently → Alias detection works
5. US4 → Test independently → Validation works
6. Phase 7 → Quickstart checklist + performance targets verified

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps each task to a specific user story for traceability
- ⚠️ Write tests FIRST — they must fail before implementation begins (Principle II)
- All Python invocations via `uv run` or explicit venv binary — never system Python (Principle VI)
- `requires-python = ">=3.14"` — Python 3.14 required per Constitution §VI (T002, T038)
- Backend (002-schema-backend) must be running for integration tests; unit tests use respx mocks
- **Deferred to 004-migration-api**: FR-011/012/015/016/017 (non-identity mapping functions, apply-mapping, cycle detection, unmapped-element report)
- Total tasks: 39 (T001–T039, with T038–T039 inserted into Phase 1/2)
