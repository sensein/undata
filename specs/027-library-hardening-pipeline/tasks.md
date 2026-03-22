# Tasks: Library Hardening, Pipeline Optimization, UI/DB Rebuild

**Input**: Design documents from `/specs/027-library-hardening-pipeline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**User Stories**:
- US1 — Library Code Review and Cleanup (P1)
- US2 — Pipeline Optimization and Source-Aware Validation (P1)
- US3 — UI/DB Layer Rebuild Inspired by CivicDB (P2)

---

## Phase 1: Setup

**Purpose**: Shared infrastructure and tooling

- [ ] T001 Create `library/src/undata_library/utils.py` with shared utilities: `safe_load_yaml(path) -> dict | None`, `write_yaml(path, data)`, `sanitize_filename(name, max_length=60) -> str`, `BASE_URI` constant
- [ ] T002 [P] Create `library/tests/test_utils.py` with tests for all utility functions (valid YAML, malformed YAML, empty file, Unicode filenames, long names)
- [ ] T003 Lint + run all tests; commit Phase 1

---

## Phase 2: Foundational

**Purpose**: Core infrastructure needed by all user stories

- [ ] T004 Add `CurationFlag` and `RunSummary` Pydantic models to `library/src/undata_library/models.py` per data-model.md
- [ ] T005 [P] Create `library/src/undata_library/curation.py`: `write_flag(output_dir, flag)`, `read_flags(output_dir, status=None) -> list[CurationFlag]`, `resolve_flag(output_dir, flag_id, action, resolved_by, note)`
- [ ] T006 [P] Create `library/src/undata_library/run_summary.py`: `generate_summary(run_id, source, counts, flags, timing) -> RunSummary`, `save_summary(output_dir, summary)`, `load_previous_summary(output_dir, source) -> RunSummary | None`, `compute_delta(current, previous) -> dict`
- [ ] T007 [P] Create `library/tests/test_curation.py` with tests for flag write/read/resolve lifecycle
- [ ] T008 [P] Create `library/tests/test_run_summary.py` with tests for summary generation, delta computation, save/load
- [ ] T009 Lint + run all tests; commit Phase 2

**Checkpoint**: CurationFlag + RunSummary models ready; shared utilities available

---

## Phase 3: US1 — Library Code Review and Cleanup (P1)

**Goal**: Clean, consistent, well-tested library codebase

**Independent Test**: `uv run pytest tests/ -v` passes with no private imports across modules, no dead code, and every public function tested

### Requirements Audit

- [ ] T010 [US1] Read all specs 001-026 and create `specs/027-library-hardening-pipeline/requirements-audit.md` mapping every user story to status (implemented, partial, outdated)
- [ ] T011 [US1] Identify and document outdated requirements that no longer apply after 026 identity model changes

### Shared Utilities Integration

- [ ] T012 [US1] Replace all unguarded `yaml.safe_load()` calls in `library/src/undata_library/ingest.py` with `safe_load_yaml()` from utils.py (~8 occurrences)
- [ ] T013 [P] [US1] Replace all unguarded `yaml.safe_load()` calls in `library/src/undata_library/commit.py`, `align.py`, `transform.py` with `safe_load_yaml()`
- [ ] T014 [P] [US1] Replace all filename sanitization patterns in `library/src/undata_library/ingest.py`, `commit.py`, `transform.py` with `sanitize_filename()` from utils.py
- [ ] T015 [P] [US1] Replace all hardcoded `https://schema.undata.live/...` URIs in `library/src/undata_library/enrich.py`, `validation.py`, `index.py`, `alias_detection.py` with `BASE_URI` constant + builder functions from hashing.py
- [ ] T016 [P] [US1] Extract duplicate export pagination loop in `library/src/undata_library/export.py` into shared helper function

### Encapsulation + Dead Code

- [ ] T017 [US1] Fix `_download_obo` import in `library/src/undata_library/cli.py` — make public or create wrapper in `ontology_fetch.py`
- [ ] T018 [US1] Audit ALL cross-module imports and accesses of underscore-prefixed functions and variables across `library/src/undata_library/` — fix each violation
- [ ] T019 [P] [US1] Remove all dead code branches, obsolete comments, and unreachable conditions across the entire `library/src/undata_library/` directory
- [ ] T020 [P] [US1] Verify no remaining references to removed models: `ontology_term` (on SemanticIdentity), `Constraints`, `SchemaProvenance`, `ValueProvenance`, `source_attribute`, `source_class`

### Test Coverage

- [ ] T021 [P] [US1] Add tests for `acquire_source()` and `build_source_ref_from_cache()` in `library/tests/test_acquisition.py`
- [ ] T022 [P] [US1] Add tests for `ontology_search()` and `map_to_skos()` in `library/tests/test_ontology_store.py`
- [ ] T023 [P] [US1] Add tests for `run_workflow()` and `load_workflow()` in `library/tests/test_workflow.py`
- [ ] T024 [P] [US1] Add edge-case tests across all modules: empty inputs, malformed YAML, missing required fields, Unicode names in `library/tests/test_edge_cases.py`
- [ ] T025 [US1] Create `library/tests/test_pipeline_e2e.py` — full end-to-end pipeline test: extract BIDS → enrich → commit → align → transform, verify counts match baseline

### Validation

- [ ] T026 [US1] Run full pipeline for all 5 sources, compare against 026 baseline (7,745 elements, 642 schemas, 1,000 values, 86 valuesets)
- [ ] T027 [US1] Add a new synthetic element, verify it flows through the entire pipeline (extract → enrich → commit → align → transform)
- [ ] T028 [US1] Update `eval-record.md` with post-cleanup extraction results
- [ ] T029 [US1] Lint + run all tests; commit US1

**Checkpoint**: Library is clean, consistent, well-tested. All 026 extraction counts preserved.

---

## Phase 4: US2 — Pipeline Optimization (P1)

**Goal**: Maximum accuracy enrichment with LLM verification, curation flags, run summaries, source-aware validation

**Independent Test**: Full pipeline produces curation flags, LLM verification results, and run summaries. Enrichment rate equals or exceeds 026 baseline.

### LLM-Assisted Enrichment

- [ ] T030 [US2] Create `library/src/undata_library/llm_enrich.py`: `verify_borderline_match(element_desc, ontology_term_def, source_context, model="claude-haiku") -> LLMVerification` using litellm
- [ ] T031 [P] [US2] Create `library/tests/test_llm_enrich.py` with tests (mock LLM responses: confirm, reject, error handling, timeout)
- [ ] T032 [US2] Integrate LLM verification into `library/src/undata_library/enrich.py`: for matches with 0.7-0.95 cosine similarity, call `verify_borderline_match()` before assigning or flagging

### Curation Flag Integration

- [ ] T033 [US2] Update `library/src/undata_library/enrich.py` to generate CurationFlags: `low_confidence` for matches < 0.7, `ambiguous_match` for multiple candidates within 0.05, `needs_review` for LLM-rejected matches
- [ ] T034 [P] [US2] Update `library/src/undata_library/transform.py` to flag transforms with `unknown` function type as `unknown_transform`
- [ ] T035 [US2] Write curation flags to `{output_dir}/curation-flags/` directory during pipeline run

### Run Summary + Delta Detection

- [ ] T036 [US2] Integrate `run_summary.py` into pipeline CLI: generate and save `RunSummary` after each pipeline run to `{output_dir}/runs/{timestamp}-{source}.yaml`
- [ ] T037 [US2] Implement delta detection: compare current run entity counts/hashes against previous run, report added/removed/modified per entity type
- [ ] T038 [P] [US2] Add source version tracking: compare `_resolved_committish` files between runs to detect source schema changes

### Adapter Accuracy Review

- [ ] T039 [US2] Read BIDS schema format docs, verify `library/src/undata_library/adapters/bids.py` + `docker_scripts/bids_extract.py` capture all entity types; document mapping in adapter docstring
- [ ] T040 [P] [US2] Read DANDI model docs, verify `library/src/undata_library/adapters/dandi.py` + `docker_scripts/dandi_extract.py` capture all entity types; document mapping
- [ ] T041 [P] [US2] Read NWB namespace format, verify `library/src/undata_library/adapters/nwb.py` captures all entity types; document mapping
- [ ] T042 [P] [US2] Read openMINDS JSON-LD format, verify `library/src/undata_library/adapters/openminds.py` captures all entity types; document mapping
- [ ] T043 [P] [US2] Read AIND JSON Schema format, verify `library/src/undata_library/adapters/aind.py` captures all entity types; document mapping

### CLI Updates

- [ ] T044 [US2] Add `curation-queue` CLI command to `library/src/undata_library/cli.py`: list pending flags with filtering by type/status
- [ ] T045 [P] [US2] Add `resolve-flag` CLI command to `library/src/undata_library/cli.py`: resolve a flag by ID with action + note

### Validation

- [ ] T046 [US2] Run full pipeline for all 5 sources with LLM enrichment + curation flags; verify flag counts > 0
- [ ] T047 [US2] Verify run summary produced for each source with entity counts + delta + timing
- [ ] T048 [US2] Add a new synthetic element, verify it flows through the full pipeline and appears in run summary delta
- [ ] T049 [US2] Compare enrichment rates against 026 baseline (equal or higher)
- [ ] T050 [US2] Update `eval-record.md` with pipeline optimization results
- [ ] T051 [US2] Lint + run all tests; commit US2

**Checkpoint**: Pipeline produces accurate enrichment with LLM verification, curation flags, and run summaries.

---

## Phase 5: US3 — UI/DB Layer Rebuild (P2)

**Goal**: CivicDB-inspired web UI with GraphQL API, social curation, connected entity navigation

**Independent Test**: Deploy UI + DB, import registry, browse elements, resolve flags, submit contributions. Playwright visual tests pass.

### CivicDB Study

- [ ] T052 [US3] Run Playwright exploration of civicdb.org: capture screenshots and document browse, search, curate, and evidence panel flows in `specs/027-library-hardening-pipeline/civicdb-study.md`
- [ ] T053 [P] [US3] Review griffithlab/civic-v2 codebase: document GraphQL schema patterns, revision workflow, polymorphic concerns (Commentable, Flaggable, Subscribable) in civicdb-study.md

### Backend — Database + GraphQL

- [ ] T054 [US3] Create `backend/` project structure: FastAPI + Strawberry + SQLAlchemy + Alembic + PostgreSQL per plan.md
- [ ] T055 [US3] Create SQLAlchemy models in `backend/src/models/`: Element, Schema, Value, ValueSet, Transform, CurationFlag, Contribution, User per data-model.md
- [ ] T056 [US3] Create Alembic migration for initial database schema in `backend/migrations/`
- [ ] T057 [US3] Create registry import service in `backend/src/services/import_service.py`: read flat-file YAML registry → batch insert to PostgreSQL preserving sha256 + provenance
- [ ] T058 [US3] Create Strawberry GraphQL schema in `backend/src/schema.py`: types for all entities per `contracts/graphql-schema.md`
- [ ] T059 [P] [US3] Create query resolvers in `backend/src/resolvers/queries.py`: `element`, `browseElements`, `schema`, `browseSchemas`, `curationQueue`, `runSummaries`
- [ ] T060 [P] [US3] Create mutation resolvers in `backend/src/resolvers/mutations.py`: `resolveFlag`, `submitContribution`, `reviewContribution`, `importRegistry`
- [ ] T061 [US3] Add DataLoader batching for all relationships (element → ontology_annotations, element → transforms, element → schemas)
- [ ] T062 [US3] Add query depth limiting and cost analysis to prevent fan-out attacks
- [ ] T063 [P] [US3] Create backend tests in `backend/tests/`: GraphQL query tests, mutation tests, import service tests
- [ ] T064 [US3] Add OmniAuth integration (GitHub/ORCID) for user authentication in `backend/src/auth.py`

### Frontend — Element Browser

- [ ] T065 [US3] Create `frontend/` project structure: Next.js 15 + Vite + Apollo Client + Tailwind CSS
- [ ] T066 [US3] Create Apollo Client provider with GraphQL connection in `frontend/src/lib/apollo.ts`
- [ ] T067 [US3] Create element browse page in `frontend/src/app/elements/page.tsx`: faceted search (source, data_type, ontology, curation status) with cursor pagination
- [ ] T068 [P] [US3] Create element detail page in `frontend/src/app/elements/[sha256]/page.tsx`: semantic identity, provenance, ontology annotations, related transforms, schemas
- [ ] T069 [P] [US3] Create connected entity navigation component in `frontend/src/components/EntityGraph.tsx`: visualize element → transforms → target elements → schemas
- [ ] T070 [P] [US3] Create search component in `frontend/src/components/Search.tsx`: full-text search across all entity types

### Frontend — Curation Workflows

- [ ] T071 [US3] Create curation queue page in `frontend/src/app/curation/page.tsx`: pending flags grouped by type with evidence panels (match candidates, scores, provenance)
- [ ] T072 [US3] Create flag resolution UI in `frontend/src/components/FlagResolver.tsx`: approve/reject/defer with justification text
- [ ] T073 [P] [US3] Create contribution submission form in `frontend/src/components/ContributionForm.tsx`: suggest annotation, comment, flag issue
- [ ] T074 [P] [US3] Create user profile page in `frontend/src/app/profile/page.tsx`: role display, contribution history
- [ ] T075 [US3] Implement contributor/curator role-based access in frontend routing and UI components

### Frontend — Visual Tests

- [ ] T076 [US3] Create Playwright visual tests for element browser in `frontend/tests/elements.spec.ts`
- [ ] T077 [P] [US3] Create Playwright visual tests for curation queue in `frontend/tests/curation.spec.ts`
- [ ] T078 [P] [US3] Create Playwright visual tests for flag resolution flow in `frontend/tests/flag-resolution.spec.ts`
- [ ] T079 [P] [US3] Create Playwright visual tests for search + entity navigation in `frontend/tests/navigation.spec.ts`

### Integration + Validation

- [ ] T080 [US3] Run full pipeline → import to DB → browse in UI → resolve a flag → verify end-to-end flow
- [ ] T081 [US3] Performance test: GraphQL queries < 500ms p95, curation queue < 2s load with 7,000+ elements
- [ ] T082 [US3] Update `eval-record.md` with UI/DB rebuild results
- [ ] T083 [US3] Lint + run all tests (library + backend + frontend + Playwright); commit US3

**Checkpoint**: Full stack working: library → pipeline → DB → GraphQL → UI with curation workflows

---

## Phase 6: Polish & Cross-Cutting

- [ ] T084 Run quickstart.md validation (QS-001 through QS-010)
- [ ] T085 [P] Final code review: remove REVIEW-TODO markers where resolved, document remaining
- [ ] T086 [P] Update CLAUDE.md with new technology entries (Strawberry, Next.js, Apollo, Playwright)
- [ ] T087 Final full pipeline re-extraction for all 5 sources → import → verify in UI
- [ ] T088 Update eval-record.md with final comprehensive results
- [ ] T089 Lint all code (library + backend + frontend); commit final

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundational)**: Depends on Phase 1 (utils.py)
- **Phase 3 (US1)**: Depends on Phase 2 (models + utils)
- **Phase 4 (US2)**: Depends on Phase 3 (clean library) + Phase 2 (CurationFlag model)
- **Phase 5 (US3)**: Depends on Phase 4 (curation flags in pipeline)
- **Phase 6 (Polish)**: Depends on all above

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (P1)**: Depends on US1 (clean codebase to optimize)
- **US3 (P2)**: Depends on US2 (curation flags + run summaries to display)

### Within Each User Story

- Audit/research before code changes
- Models before services
- Services before CLI/UI
- Core implementation before integration
- Tests alongside implementation
- Validation at end of each story

### Parallel Opportunities

- T002 ‖ T001 (test file independent of implementation)
- T005 ‖ T006 ‖ T007 ‖ T008 (independent new files)
- T012 ‖ T013 ‖ T014 ‖ T015 ‖ T016 (different files, same utility replacement)
- T021 ‖ T022 ‖ T023 ‖ T024 (independent test files)
- T039 ‖ T040 ‖ T041 ‖ T042 ‖ T043 (independent adapter reviews)
- T059 ‖ T060 (independent resolver files)
- T067 ‖ T068 ‖ T069 ‖ T070 (independent page/component files)
- T076 ‖ T077 ‖ T078 ‖ T079 (independent test files)

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1: Setup (T001-T003)
2. Phase 2: Foundational (T004-T009)
3. Phase 3: US1 Library Cleanup (T010-T029)
4. **VALIDATE**: Full test suite passes, extraction counts match baseline

### Incremental Delivery

1. US1 → Clean library foundation
2. US2 → Accurate pipeline with curation flags
3. US3 → Full-stack UI with CivicDB-inspired curation

**Suggested MVP**: Phase 1 + 2 + 3 (US1) — clean library is the prerequisite for everything else
