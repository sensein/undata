# Tasks: System Tutorials

**Branch**: `009-tutorials`
**Input**: Design documents from `/specs/009-tutorials/`
**Prerequisites**: spec.md ✅ plan.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Tests**: Tutorials ARE the tests — each notebook is an executable integration test run via
`pytest --nbmake`. No separate TDD gate tasks needed (notebooks are end-to-end tests by
nature, not unit tests). Each notebook creation task includes an explicit pytest run step.

**Organization**: Tasks grouped by user story. Phase 1 creates shared infrastructure (mandatory
before any notebook can run). Phases 3–9 create one notebook per user story. All notebook files
are independent — they can be written in parallel after Phase 1 completes.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the `tutorials/` project scaffold that all notebooks depend on.
Must be complete before any notebook can be run with `pytest --nbmake`.

- [X] T001 Create `tutorials/pyproject.toml` declaring: `name="undata-tutorials"`, `requires-python=">=3.14"`, `dependencies=["httpx>=0.27"]`; `[dependency-groups] dev=["nbmake>=1.5","ipykernel","jupyter","pytest"]`; `[tool.pytest.ini_options] addopts=["--nbmake","--nbmake-timeout=60"] testpaths=["."]`; `[tool.ruff] line-length=100 target-version="py314"`
- [X] T002 Create `tutorials/conftest.py` with session-scoped pytest fixtures: `backend_url` (from `BACKEND_URL` env, default `http://localhost:8002`), `migration_url` (from `MIGRATION_URL`, default `http://localhost:8004`), `api_key` (from `API_KEY`, default 64-char dev key `a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2`), `api_headers` (dict `{"X-API-Key": api_key}`), `backend_available` (bool via `httpx.get(url + "/health", timeout=2.0)`), `migration_available` (same pattern for migration URL) — fixtures are for native pytest tests; notebooks read env vars directly
- [X] T003 [P] Create `tutorials/README.md` with: overview paragraph; prerequisites (Docker, uv); "Quick Start" section with `uv sync` + `pytest --nbmake -v`; env vars table (`BACKEND_URL`, `MIGRATION_URL`, `API_KEY`, `INGESTION_DIR`); per-tutorial table showing notebook filename, services required, est. run time, and offline flag; instructions for running a single notebook (`pytest --nbmake tutorials/01_getting_started.ipynb -v`); instructions for interactive Jupyter use (`uv run jupyter lab`)
- [X] T004 Verify `tutorials/` environment: `cd tutorials && uv sync` completes without error and `uv run pytest --collect-only 2>&1` shows zero errors

**Checkpoint**: `tutorials/` directory has pyproject.toml, conftest.py, README.md; `uv sync`
passes; `pytest --collect-only` completes. Notebook implementation can begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No new infrastructure needed beyond Phase 1. All service-side APIs
(backend, migration-api, ingestion CLI) are already implemented. This phase is
satisfied by Phase 1 completion.

**⚠️ NOTE**: All user story notebook phases can begin in parallel once Phase 1 is complete.

---

## Phase 3: User Story 1 — Getting Started (Priority: P1) 🎯 MVP

**Goal**: A new developer starts the backend, confirms health, authenticates, and makes
their first API calls — all documented step-by-step in a single executable notebook.

**Independent Test**: `cd tutorials && uv run pytest --nbmake 01_getting_started.ipynb -v`
— passes with backend running; skips when backend unreachable.

- [X] T005 [US1] Create `tutorials/01_getting_started.ipynb` with the following cells in order:
  - **Cell 1 (markdown)**: `# T01: Getting Started` — goal paragraph, "Services required: backend", "Est. time: 5 min"
  - **Cell 2 (code)**: Standard service skip cell per `contracts/notebook-structure.md` — reads `BACKEND_URL` + `API_KEY` from env (with defaults); calls `httpx.get(f"{BACKEND_URL}/health", timeout=2.0).raise_for_status()`; prints `✓ Backend available`; calls `pytest.skip()` on exception
  - **Cell 3 (markdown)**: `## 1. Health Check` section
  - **Cell 4 (code)**: `GET {BACKEND_URL}/health` — assert `response.status_code == 200`; assert `response.json()["status"] == "ok"`; print full response
  - **Cell 5 (markdown)**: `## 2. List Schema Sources` section explaining what sources are
  - **Cell 6 (code)**: `GET {BACKEND_URL}/api/v1/sources/` with HEADERS — assert 200; print `f"Found {len(data['items'])} sources"`; print each source name and format
  - **Cell 7 (markdown)**: `## 3. List Elements (first 5)` section
  - **Cell 8 (code)**: `GET {BACKEND_URL}/api/v1/elements/?limit=5` — assert 200; print `f"Total elements: {data['total']}"`; for each item print name, data_type, source_name
  - **Cell 9 (markdown)**: `## 4. Authenticate — About API Keys` explaining the auth model and how to create a key via the API; note that we use the pre-seeded dev key by default
  - **Cell 10 (code)**: Verify auth works: `GET {BACKEND_URL}/api/v1/users/me` with HEADERS — assert 200; print user info
  - **Cell 11 (markdown)**: `## Next Steps` pointing to `02_ingest_schemas.ipynb`

- [X] T006 [US1] Verify `tutorials/01_getting_started.ipynb` runs: start backend (`cd backend && docker compose up -d`); `cd tutorials && uv run pytest --nbmake 01_getting_started.ipynb -v` — confirm PASSED; also verify skip: `BACKEND_URL=http://localhost:9999 uv run pytest --nbmake 01_getting_started.ipynb -v` — confirm SKIPPED not FAILED

**Checkpoint**: `pytest --nbmake 01_getting_started.ipynb` → PASSED with backend running;
SKIPPED (not FAILED) with backend unreachable. US1 done.

---

## Phase 4: User Story 2 — Schema Ingestion via CLI (Priority: P1)

**Goal**: Push BIDS and DANDI schemas from the ingestion CLI into the backend and confirm
elements are queryable.

**Independent Test**: `cd tutorials && uv run pytest --nbmake 02_ingest_schemas.ipynb -v`

- [X] T007 [P] [US2] Create `tutorials/02_ingest_schemas.ipynb` with the following cells:
  - **Cell 1 (markdown)**: `# T02: Ingest Schemas via CLI` — goal; "Services required: backend"; "Requires: undata CLI (`cd ../ingestion && uv sync`)"; "Est. time: 10 min"
  - **Cell 2 (code)**: Standard skip cell (backend health check); also set `INGESTION_DIR = os.getenv("INGESTION_DIR", str(Path(__file__).parent.parent / "ingestion"))`
  - **Cell 3 (markdown)**: `## 1. Install ingestion CLI` — one-time setup note
  - **Cell 4 (code)**: `subprocess.run(["uv", "sync"], cwd=INGESTION_DIR, check=True)`; print `✓ Ingestion CLI ready`
  - **Cell 5 (markdown)**: `## 2. Ingest BIDS Schema` explaining what BIDS is
  - **Cell 6 (code)**: `subprocess.run(["uv", "run", "undata", "ingest", "bids", "--extraction-mode", "code", "--backend-url", BACKEND_URL, "--token", API_KEY], cwd=INGESTION_DIR, check=True, capture_output=True)`; decode and print stdout/stderr; assert return code == 0
  - **Cell 7 (markdown)**: `## 3. Ingest DANDI Schema`
  - **Cell 8 (code)**: Same pattern for `undata ingest dandi --extraction-mode code`
  - **Cell 9 (markdown)**: `## 4. Verify Ingested Data`
  - **Cell 10 (code)**: `GET /api/v1/sources/` — find BIDS and DANDI sources; assert both present; print source IDs and element counts
  - **Cell 11 (code)**: `GET /api/v1/elements/?limit=10` with `source_name=BIDS` filter — assert ≥1 element; print first 5 element names
  - **Cell 12 (markdown)**: `## Next Steps` pointing to `03_browse_elements.ipynb`

- [X] T008 [US2] Verify `tutorials/02_ingest_schemas.ipynb` runs: `cd tutorials && uv run pytest --nbmake 02_ingest_schemas.ipynb -v` — confirm PASSED (ingestion completes, elements returned)

**Checkpoint**: T02 notebook PASSED. BIDS and DANDI elements queryable in backend.

---

## Phase 5: User Story 3 — Browse and Search Elements (Priority: P1)

**Goal**: Demonstrate the full element query API — pagination, filtering, detail view,
version history, and semantic alias detection.

**Independent Test**: `cd tutorials && uv run pytest --nbmake 03_browse_elements.ipynb -v`

- [X] T009 [P] [US3] Create `tutorials/03_browse_elements.ipynb` with the following cells:
  - **Cell 1 (markdown)**: `# T03: Browse and Search Elements` — goal; "Services required: backend (with ingested data from T02)"; "Est. time: 5 min"
  - **Cell 2 (code)**: Standard skip cell; assert `GET /api/v1/elements/` returns `total > 0` or skip with "No elements found — run T02 first"
  - **Cell 3 (markdown)**: `## 1. Paginate Elements`
  - **Cell 4 (code)**: Page 1: `GET /api/v1/elements/?limit=10&offset=0`; page 2: `GET /api/v1/elements/?limit=10&offset=10`; print total, current page count; assert `len(page1["items"]) <= 10`
  - **Cell 5 (markdown)**: `## 2. Filter by Source`
  - **Cell 6 (code)**: `GET /api/v1/elements/?source_name=BIDS&limit=5` — print names; `GET /api/v1/elements/?source_name=DANDI&limit=5` — print names; compare counts
  - **Cell 7 (markdown)**: `## 3. Element Detail View`
  - **Cell 8 (code)**: Take first element ID from prior results; `GET /api/v1/elements/{element_id}` — assert 200; print full element JSON (name, data_type, description, required, source_local_id, constraints)
  - **Cell 9 (markdown)**: `## 4. Version History`
  - **Cell 10 (code)**: `GET /api/v1/elements/{element_id}/history` — assert 200; print `f"Versions: {len(history)}"`; print first version fields
  - **Cell 11 (markdown)**: `## 5. Detect Alias Candidates`
  - **Cell 12 (code)**: `POST /api/v1/aliases/detect` with body `{"threshold": 0.85, "limit": 5}` — assert 200; print top 3 pairs with similarity scores; note "These are candidates — not yet approved aliases"
  - **Cell 13 (markdown)**: `## Next Steps` pointing to `04_mappings_aliases.ipynb`

- [X] T010 [US3] Verify `tutorials/03_browse_elements.ipynb` runs: `cd tutorials && uv run pytest --nbmake 03_browse_elements.ipynb -v` — confirm PASSED

**Checkpoint**: T03 notebook PASSED. Element browsing and alias detection demonstrated.

---

## Phase 6: User Story 4 — Schema Classes and Element Mappings (Priority: P2)

**Goal**: Create cross-source element mappings and alias groups; run the detect-aliases CLI.

**Independent Test**: `cd tutorials && uv run pytest --nbmake 04_mappings_aliases.ipynb -v`

- [X] T011 [P] [US4] Create `tutorials/04_mappings_aliases.ipynb` with the following cells:
  - **Cell 1 (markdown)**: `# T04: Schema Classes and Element Mappings` — goal; "Services required: backend"; "Est. time: 10 min"
  - **Cell 2 (code)**: Standard skip cell + fetch two elements from different sources to use as mapping targets; store as `elem_a_id`, `elem_b_id`; skip if fewer than 2 elements exist
  - **Cell 3 (markdown)**: `## 1. Create an Element Mapping`
  - **Cell 4 (code)**: `POST /api/v1/mappings/` with body `{"source_element_id": elem_a_id, "target_element_id": elem_b_id, "function_type": "identity", "expression": null, "description": "Tutorial identity mapping"}`; assert 201; store `mapping_id`; print mapping JSON
  - **Cell 5 (markdown)**: `## 2. Inspect the Mapping`
  - **Cell 6 (code)**: `GET /api/v1/mappings/{mapping_id}` — assert 200; print source and target element names; `GET /api/v1/mappings/{mapping_id}/history` — print version count
  - **Cell 7 (markdown)**: `## 3. Create an Alias Group`
  - **Cell 8 (code)**: `POST /api/v1/aliases/` with body `{"label": "tutorial-alias-group", "predicate": "skos:exactMatch"}`; store `alias_group_id`; `PUT /api/v1/aliases/{alias_group_id}` to add `elem_a_id` as member; assert 200; print group JSON
  - **Cell 9 (markdown)**: `## 4. Run detect-aliases CLI`
  - **Cell 10 (code)**: `subprocess.run(["uv", "run", "undata", "detect-aliases", "--dry-run", "--backend-url", BACKEND_URL, "--token", API_KEY], cwd=INGESTION_DIR, capture_output=True)`; print output; assert return code == 0
  - **Cell 11 (markdown)**: `## Cleanup`
  - **Cell 12 (code)**: `DELETE /api/v1/mappings/{mapping_id}`; `DELETE /api/v1/aliases/{alias_group_id}`; print `✓ Cleanup complete`
  - **Cell 13 (markdown)**: `## Next Steps` pointing to `05_linkml_export.ipynb`

- [X] T012 [US4] Verify `tutorials/04_mappings_aliases.ipynb` runs: `cd tutorials && uv run pytest --nbmake 04_mappings_aliases.ipynb -v` — confirm PASSED; confirm cleanup removed created resources

**Checkpoint**: T04 notebook PASSED. Mappings and alias groups created and cleaned up.

---

## Phase 7: User Story 5 — LinkML Schema Export (Priority: P2)

**Goal**: Generate a unified LinkML YAML schema from all ingested backend elements and
verify it is importable via `LinkMLAdapter`.

**Independent Test**: `cd tutorials && uv run pytest --nbmake 05_linkml_export.ipynb -v`

- [X] T013 [P] [US5] Create `tutorials/05_linkml_export.ipynb` with the following cells:
  - **Cell 1 (markdown)**: `# T05: LinkML Schema Export` — goal; "Services required: backend"; "Requires: undata CLI"; "Est. time: 5 min"
  - **Cell 2 (code)**: Standard skip cell + set `OUTPUT_PATH = "/tmp/undata-tutorial-schema.yaml"` + import `sys; sys.path.insert(0, str(Path(INGESTION_DIR) / "src"))`
  - **Cell 3 (markdown)**: `## 1. Generate Unified Schema via CLI`
  - **Cell 4 (code)**: `subprocess.run(["uv", "run", "undata", "generate-schema", "--output", OUTPUT_PATH, "--backend-url", BACKEND_URL], cwd=INGESTION_DIR, check=True, capture_output=True)`; assert `Path(OUTPUT_PATH).exists()`; print `f"Schema written to {OUTPUT_PATH} ({Path(OUTPUT_PATH).stat().st_size} bytes)"`
  - **Cell 5 (markdown)**: `## 2. Inspect the Generated Schema`
  - **Cell 6 (code)**: `from undata.adapters.linkml_adapter import LinkMLAdapter`; `la = LinkMLAdapter(); la.load_file(OUTPUT_PATH)`; `elements = la.extract_elements()`; `classes = la.extract_classes()`; print `f"Elements: {len(elements)}, Classes: {len(classes)}"`; print first 5 slot names
  - **Cell 7 (markdown)**: `## 3. View Schema Metadata via API`
  - **Cell 8 (code)**: `GET /api/v1/schemas/?limit=5` — print schema names and creation dates
  - **Cell 9 (markdown)**: `## Cleanup`
  - **Cell 10 (code)**: `import os; os.unlink(OUTPUT_PATH)`; print `✓ Cleanup complete`
  - **Cell 11 (markdown)**: `## Next Steps` pointing to `06_schema_roundtrip.ipynb`

- [X] T014 [US5] Verify `tutorials/05_linkml_export.ipynb` runs: `cd tutorials && uv run pytest --nbmake 05_linkml_export.ipynb -v` — confirm PASSED; confirm `/tmp/undata-tutorial-schema.yaml` removed

**Checkpoint**: T05 notebook PASSED. LinkML export and re-import demonstrated.

---

## Phase 8: User Story 6 — Schema Roundtrip Validation (Priority: P2)

**Goal**: Demonstrate offline roundtrip validation of custom schemas using the ingestion
library and CLI — no backend needed.

**Independent Test**: `cd tutorials && uv run pytest --nbmake 06_schema_roundtrip.ipynb -v`
— MUST pass with NO services running (SC-002).

- [X] T015 [P] [US6] Create `tutorials/06_schema_roundtrip.ipynb` with the following cells:
  - **Cell 1 (markdown)**: `# T06: Schema Roundtrip Validation` — goal; **"Services required: NONE (fully offline)"**; "Requires: undata library (`cd ../ingestion && uv sync`)"; "Est. time: 3 min"
  - **Cell 2 (code)**: Set up path only (NO service skip cell): `import sys; from pathlib import Path; INGESTION_DIR = Path(os.getenv("INGESTION_DIR", "../ingestion")).resolve(); FIXTURES = INGESTION_DIR / "tests" / "fixtures"; sys.path.insert(0, str(INGESTION_DIR / "src"))`; assert `FIXTURES.exists()`, f"Fixtures not found at {FIXTURES} — run `cd ../ingestion && uv sync` first"
  - **Cell 3 (markdown)**: `## 1. Import a JSON Schema`
  - **Cell 4 (code)**: `from undata.adapters.json_schema import GenericJSONSchemaAdapter`; `adapter = GenericJSONSchemaAdapter()`; `adapter.load_file(str(FIXTURES / "generic_schema_sample.json"))`; `elements = adapter.extract_elements()`; `classes = adapter.extract_classes()`; print `f"Extracted {len(elements)} elements, {len(classes)} classes"`; print each element name and data_type
  - **Cell 5 (markdown)**: `## 2. Roundtrip: JSON Schema → LinkML → Re-import`
  - **Cell 6 (code)**: `from undata.roundtrip import roundtrip_json_schema`; `result = roundtrip_json_schema(str(FIXTURES / "generic_schema_sample.json"))`; print `f"Fidelity score: {result.fidelity_score:.2f}"`; print `f"Missing elements: {result.missing_elements}"`; print `f"Missing classes: {result.missing_classes}"`; `assert result.fidelity_score == 1.0, f"Expected perfect fidelity, got {result.fidelity_score}"`
  - **Cell 7 (markdown)**: `## 3. Import a LinkML YAML Schema`
  - **Cell 8 (code)**: `from undata.adapters.linkml_adapter import LinkMLAdapter`; `la = LinkMLAdapter(); la.load_file(str(FIXTURES / "linkml_sample.yaml"))`; `elements = la.extract_elements(); classes = la.extract_classes()`; print slot names and ranges
  - **Cell 9 (markdown)**: `## 4. Roundtrip: LinkML → Re-serialize → Re-import`
  - **Cell 10 (code)**: `from undata.roundtrip import roundtrip_linkml`; `result = roundtrip_linkml(str(FIXTURES / "linkml_sample.yaml"))`; print fidelity; `assert result.fidelity_score >= 0.8`
  - **Cell 11 (markdown)**: `## 5. Using the CLI`
  - **Cell 12 (code)**: `subprocess.run(["uv", "run", "undata", "roundtrip", str(FIXTURES / "generic_schema_sample.json")], cwd=str(INGESTION_DIR), capture_output=True)`; print stdout; assert return code == 0
  - **Cell 13 (markdown)**: `## Next Steps` pointing to `07_data_migration.ipynb`; note "This tutorial required no running services — all processing was offline."

- [X] T016 [US6] Verify `tutorials/06_schema_roundtrip.ipynb` runs offline (SC-002): confirm backend is NOT running; `cd tutorials && uv run pytest --nbmake 06_schema_roundtrip.ipynb -v` — confirm PASSED with no services

**Checkpoint**: T06 notebook PASSED with no services. Fidelity score 1.0 for sample fixtures.

---

## Phase 9: User Story 7 — Data Migration (Priority: P3)

**Goal**: Diff two schema sources, create a migration pathway, submit a batch migration job,
and poll for completion.

**Independent Test**: `cd tutorials && uv run pytest --nbmake 07_data_migration.ipynb -v`
— requires backend + migration-api + Redis; skips if either service unavailable.

- [X] T017 [P] [US7] Create `tutorials/07_data_migration.ipynb` with the following cells:
  - **Cell 1 (markdown)**: `# T07: Data Migration` — goal; "Services required: backend + migration-api"; "Est. time: 15 min"
  - **Cell 2 (code)**: Skip cell for BOTH services: check `BACKEND_URL/health` AND `MIGRATION_URL/health`; `pytest.skip()` if either unavailable; set `MIGRATION_URL = os.getenv("MIGRATION_URL", "http://localhost:8004")`; set `MIGRATION_HEADERS = {"X-API-Key": API_KEY}`
  - **Cell 3 (markdown)**: `## 1. Schema Diff — What Changed?`
  - **Cell 4 (code)**: Fetch first two source IDs from `GET /api/v1/sources/`; `POST {MIGRATION_URL}/api/v1/diff` with body `{"source_schema_id": src_a_id, "target_schema_id": src_b_id}`; assert 200; print `f"Added: {len(diff['added'])}, Removed: {len(diff['removed'])}, Changed: {len(diff['changed'])}"`
  - **Cell 5 (markdown)**: `## 2. Create a Migration Pathway`
  - **Cell 6 (code)**: `POST {MIGRATION_URL}/api/v1/pathways` with body `{"name": "tutorial-pathway", "source_schema_id": src_a_id, "target_schema_id": src_b_id, "steps": []}`; assert 201; store `pathway_id`; print pathway JSON
  - **Cell 7 (markdown)**: `## 3. Submit a Batch Migration Job`
  - **Cell 8 (code)**: `POST {MIGRATION_URL}/api/v1/migrate` with body `{"pathway_id": pathway_id, "records": [{"id": "test-001", "subject_name": "test"}]}`; assert 200; store `job_id` if returned; print job status
  - **Cell 9 (markdown)**: `## 4. Query Job Status`
  - **Cell 10 (code)**: `GET {MIGRATION_URL}/api/v1/jobs/{job_id}` — print status; if async, poll up to 3 times with 2s sleep
  - **Cell 11 (markdown)**: `## Cleanup`
  - **Cell 12 (code)**: `DELETE {MIGRATION_URL}/api/v1/pathways/{pathway_id}`; print `✓ Cleanup complete`
  - **Cell 13 (markdown)**: `## Congratulations!` — you've completed all 7 tutorials; link back to T01

- [X] T018 [US7] Verify `tutorials/07_data_migration.ipynb` skips gracefully when migration-api is down: `MIGRATION_URL=http://localhost:9999 uv run pytest --nbmake 07_data_migration.ipynb -v` — confirm SKIPPED; also verify PASSED when full stack is running

**Checkpoint**: T07 notebook PASSED with full stack; SKIPPED (not FAILED) when migration-api
unreachable. All 7 user stories complete.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Ruff validation, regression smoke test, documentation update.

- [X] T019 [P] Extract Python code from all notebooks and run `ruff check` (SC-005): `for nb in tutorials/*.ipynb; do uv run jupyter nbconvert --to script $nb --stdout | uv run ruff check --stdin-filename ${nb%.ipynb}.py -; done` — fix any violations in notebook code cells
- [X] T020 [P] Run full offline tutorial smoke test (SC-002, QS-002): `cd tutorials && uv run pytest --nbmake 06_schema_roundtrip.ipynb -v` with no services — confirm PASSED; confirm execution time < 10s
- [X] T021 Run full tutorial suite smoke test with backend (SC-001, QS-001): start backend; `cd tutorials && uv run pytest --nbmake 01_getting_started.ipynb 02_ingest_schemas.ipynb 03_browse_elements.ipynb -v` — confirm all 3 P1 notebooks PASS
- [X] T022 Update `CLAUDE.md` to mark `009-tutorials` as `COMPLETE` and record: "7 notebooks in tutorials/; nbmake for pytest execution; offline T06; auto-skip via in-notebook pytest.skip()"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Satisfied by Phase 1 — no new infrastructure needed
- **Phase 3 (US1)**: Depends on Phase 1 (conftest.py). Can proceed once T004 passes.
- **Phase 4 (US2)**: Depends on Phase 1. Can run in parallel with Phase 3 (different file).
- **Phase 5 (US3)**: Depends on Phase 1. Logically benefits from US2 data; notebook handles empty state gracefully.
- **Phase 6 (US4)**: Depends on Phase 1. Logically benefits from US2 data.
- **Phase 7 (US5)**: Depends on Phase 1. Logically benefits from US2 data.
- **Phase 8 (US6)**: Depends on Phase 1 only — fully offline.
- **Phase 9 (US7)**: Depends on Phase 1. Requires migration-api stack.
- **Phase 10 (Polish)**: Depends on all notebooks created (T005–T018).

### User Story Dependencies

- **US1 (P1)**: Needs conftest.py (T002) and pyproject.toml (T001). No data dependency.
- **US2 (P1)**: Needs conftest.py. Backend must be running. Ingestion CLI must work.
- **US3 (P1)**: Needs conftest.py. Logically runs after US2 to have data to browse.
- **US4 (P2)**: Needs conftest.py + elements from US2. Self-contained with cleanup.
- **US5 (P2)**: Needs conftest.py + elements from US2. Self-contained with cleanup.
- **US6 (P2)**: Needs conftest.py. Fully offline — depends only on ingestion fixtures.
- **US7 (P3)**: Needs conftest.py. Requires migration-api stack + backend.

### Notebook Creation Parallelism

All notebook creation tasks (T005, T007, T009, T011, T013, T015, T017) are marked [P]
because they target different files and have no content dependencies on each other.
They can be written simultaneously once Phase 1 is complete.

---

## Parallel Example: After Phase 1 completes

```bash
# All notebook creation tasks can run simultaneously:
Task: "Create 01_getting_started.ipynb"   # T005
Task: "Create 02_ingest_schemas.ipynb"    # T007
Task: "Create 03_browse_elements.ipynb"   # T009
Task: "Create 04_mappings_aliases.ipynb"  # T011
Task: "Create 05_linkml_export.ipynb"     # T013
Task: "Create 06_schema_roundtrip.ipynb"  # T015
Task: "Create 07_data_migration.ipynb"    # T017
```

---

## Implementation Strategy

### MVP First (P1 Stories Only)

1. Complete Phase 1 (T001–T004) — infrastructure
2. Create T01 + T02 + T03 notebooks (T005–T010) — these cover getting started + ingestion + browse
3. **STOP and VALIDATE**: `pytest --nbmake 01_getting_started.ipynb 02_ingest_schemas.ipynb 03_browse_elements.ipynb -v`
4. All P1 workflows documented and runnable

### Incremental Delivery

1. Phase 1 → infrastructure ready
2. US1–US3 (T005–T010) → P1 tutorials pass → users can get started and ingest
3. US4–US6 (T011–T016) → P2 tutorials pass → mappings, export, and offline roundtrip
4. US7 (T017–T018) → P3 tutorial pass → full migration workflow
5. Phase 10 (T019–T022) → ruff clean, smoke tests, CLAUDE.md updated

---

## Notes

- All notebooks use `pytest.skip()` (not `raise`) for service unavailability — this ensures
  CI reports SKIPPED not FAILED when optional services are not running.
- Tutorial 06 (roundtrip) is the only fully offline notebook; it MUST pass in CI without
  any services started.
- Notebooks reference fixtures from `../ingestion/tests/fixtures/` — the relative path
  must work from the `tutorials/` directory.
- Use `subprocess.run(..., check=True)` for CLI calls; capture stdout/stderr and print
  them so pytest output shows what happened.
- Each notebook's cleanup cell uses DELETE endpoints; soft-delete is acceptable (elements
  remain in history but are no longer active).
- `ruff check` is run on extracted Python (via `nbconvert --to script`) — not on the raw
  `.ipynb` JSON.
