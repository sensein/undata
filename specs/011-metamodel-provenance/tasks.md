# Tasks: Metamodel, Provenance & LinkML I/O

**Input**: Design documents from `specs/011-metamodel-provenance/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Organization**: Tasks grouped by user story for independent implementation and testing.
**TDD**: Test tasks appear BEFORE implementation tasks within each phase (Constitution II).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependencies)
- **[Story]**: US1–US5 per spec.md user stories
- All paths are relative to repo root

---

## Phase 1: Setup (Code Generation & Tooling)

**Purpose**: Generate PROV-O Pydantic models from OWL→LinkML conversion.
All generated files are committed and used by subsequent phases.

- [X] T001 Add `linkml-owl` to `[dependency-groups] dev` in `backend/pyproject.toml`; run `uv sync` in `backend/`; verify `uv run linkml-owl-to-linkml --help` exits 0 (if CLI unavailable, document in `backend/data/prov-o.linkml.yaml` header and write YAML manually per data-model.md)
- [X] T002 Fetch PROV-O OWL and produce `backend/data/prov-o.linkml.yaml`: run `uv run linkml-owl-to-linkml --input https://www.w3.org/ns/prov-o --output backend/data/prov-o-raw.linkml.yaml` then prune to 6 classes (Entity, Activity, Agent, Generation, Usage, Bundle) with correct `class_uri` values; save final as `backend/data/prov-o.linkml.yaml`
- [X] T003 Generate Pydantic v2 models: run `uv run gen-pydantic backend/data/prov-o.linkml.yaml --output backend/src/models/prov_o.py`; verify output contains `class Entity`, `class Activity`, `class Agent`, `class Bundle`
- [X] T004 Commit generated files: `backend/data/prov-o.linkml.yaml`, `backend/data/prov-o-raw.linkml.yaml`, `backend/src/models/prov_o.py`, `backend/pyproject.toml`

---

## Phase 2: Foundational (Database Migration & ORM)

**Purpose**: All DB schema changes in one flattened migration. Must complete before any endpoint work.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.
**Note**: All 10 prior migrations have been replaced by `2026_03_12_0001_initial_schema.py`,
which includes all tables plus new 011 columns (`data_element.schema_ref`,
`mapping_function.attributed_to`, `mapping_function.confidence_score`).

- [X] T005 [P] Verify ORM additions already applied to `backend/src/models/db.py`: `DataElement.schema_ref` (UUID FK → dynamic_schema), `MappingFunction.attributed_to` (Text), `MappingFunction.confidence_score` (Float), `MappingFunction.status` (already present); confirm columns present and correct types
- [X] T006 [P] Update `DataElementCreate` / `DataElementRead` Pydantic schemas in `backend/src/models/schemas.py`: add `schema_ref: Optional[UUID] = None`; add `@model_validator` or `@field_validator` that raises 422 when `value_type == "object"` and `schema_ref is None`
- [X] T007 Update `MappingFunctionRead` Pydantic schema in `backend/src/models/schemas.py`: add `status: str = "active"`, `attributed_to: Optional[str] = None`, `confidence_score: Optional[float] = None` (after T006; both modify `schemas.py`)
- [X] T008 Run migration against the test database: `cd backend && docker compose build test && docker compose run --rm --entrypoint="" -e TEST_DATABASE_URL=postgresql+asyncpg://undata:undata@db:5432/undata_test test sh -c "uv run alembic -x url=postgresql+asyncpg://undata:undata@db:5432/undata_test upgrade head"`; verify exits 0
- [X] T009 Write contract tests for `schema_ref` enforcement in `backend/tests/contract/test_elements_schema_ref.py`: (a) `POST /elements` with `value_type="object"` and no `schema_ref` → HTTP 422; (b) `POST /elements` with valid `schema_ref` UUID → HTTP 201 with `schema_ref` in response body; (c) `POST /elements/children` when parent element has `schema_ref` set → HTTP 422 (FR-003); ensure tests **FAIL** before T006 is complete
- [X] T010a Add FR-003 guard to `backend/src/services/elements.py`: in `create_child()` (or equivalent), if the parent `DataElement.schema_ref` is not null, raise HTTP 422 with `detail: "use schema_ref for named types, not DataElementChild"`; run contract test (c) from T009 and confirm it passes
- [X] T010 Commit Phase 2 files: `backend/src/models/schemas.py`, `backend/src/services/elements.py`, `backend/tests/contract/test_elements_schema_ref.py`

**Checkpoint**: Migration applied; schema_ref validation active; DataElementChild guard active (FR-003); contract tests passing.

---

## Phase 3: User Story 1 — Element Provenance Upgrade (P1)

**Goal**: Upgrade the **existing** `GET /elements/{id}/provenance` endpoint (currently in
`backend/src/api/v1/elements.py:651`) to use generated Pydantic PROV-O models and the
correct `@context` URL (`https://www.w3.org/ns/prov.jsonld`).

**Current state**: Endpoint exists; uses `schema_changelog_svc.to_element_prov_jsonld()`
which hand-builds dicts and returns `@context: "http://www.w3.org/ns/prov"` (wrong URL).

**Independent Test**: `GET /elements/{id}/provenance` → HTTP 200, `Content-Type: application/ld+json`,
`@context == "https://www.w3.org/ns/prov.jsonld"`, `@graph` contains Entity + Activity + Agent nodes.

- [X] T011 [US1] Write contract tests for the upgraded endpoint in `backend/tests/contract/test_provenance_api.py`: (a) 200 with `@context == "https://www.w3.org/ns/prov.jsonld"`; (b) 3 audit entries → 3 Activity nodes with `prov:startedAtTime`; (c) invalid UUID → 404; run and confirm they **FAIL** against current implementation (wrong context URL)
- [X] T012 [US1] Refactor `to_element_prov_jsonld()` in `backend/src/services/schema_changelog.py`: replace manual dict construction with imported Pydantic `Entity`, `Activity`, `Agent` models from `src.models.prov_o`; update `@context` constant to `"https://www.w3.org/ns/prov.jsonld"`
- [X] T013 [US1] Verify `GET /elements/{id}/provenance` in `backend/src/api/v1/elements.py` still returns `media_type="application/ld+json"` (no route change needed; verify response header present)
- [X] T014 [US1] Run contract tests from T011; confirm all pass; commit: `backend/src/services/schema_changelog.py`, `backend/tests/contract/test_provenance_api.py`

**Checkpoint**: `GET /elements/{id}/provenance` returns valid PROV-O JSON-LD with correct context.

---

## Phase 4: User Story 2 — Schema Provenance Upgrade (P1)

**Goal**: Upgrade the **existing** `GET /schemas/{id}/provenance` endpoint
(currently in `backend/src/api/v1/schemas.py:558`) to use Pydantic PROV-O models,
the correct `@context` URL, and `prov:wasDerivedFrom` chain from `SchemaChangeLog`.

**Independent Test**: `GET /schemas/{id}/provenance` → HTTP 200, `application/ld+json`,
`@graph` contains Entity nodes linked by `prov:wasDerivedFrom`.

- [ ] T015 [US2] Extend contract tests in `backend/tests/contract/test_provenance_api.py`: (a) schema with 2 changelog entries → `prov:wasDerivedFrom` present in `@graph`; (b) new-URI change (semantic_boundary_crossed=True) → two Entity nodes with distinct `@id`; (c) invalid schema id → 404; run and confirm they **FAIL** before T016
- [ ] T016 [US2] Refactor `to_prov_jsonld()` in `backend/src/services/schema_changelog.py`: replace manual dict construction with Pydantic PROV-O models; update `@context` to `"https://www.w3.org/ns/prov.jsonld"`; ensure `prov:wasDerivedFrom` is set when `SchemaChangeLog.semantic_boundary_crossed` is True
- [ ] T017 [US2] Run all contract tests; confirm T011 tests still pass (no regression); commit `backend/src/services/schema_changelog.py` (updated), `backend/tests/contract/test_provenance_api.py` (extended)

**Checkpoint**: Both provenance endpoints return valid PROV-O JSON-LD with correct context URL.

---

## Phase 5: User Story 3 — LinkML Schema Export (P1)

**Goal**: `GET /schemas/{id}/linkml` returns valid LinkML YAML with `X-Roundtrip-Fidelity` header.

**Independent Test**: `GET /schemas/{id}/linkml` → HTTP 200, `Content-Type: application/yaml`,
`X-Roundtrip-Fidelity` header present and parseable as float.

- [ ] T018 [US3] Write contract tests in `backend/tests/contract/test_linkml_io_api.py`: (a) valid schema → 200 + YAML body containing `classes:` + `X-Roundtrip-Fidelity` header ∈ [0.0, 1.0]; (b) schema with alias group → slot `aliases:` list in YAML; (c) schema with `schema_ref` element → referenced class present in YAML; (d) invalid id → 404; run and confirm they **FAIL** (route does not exist yet)
- [ ] T019 [US3] Define `RoundtripResult(BaseModel)` in `backend/src/services/linkml_io.py`: `fidelity_score: float`, `loss_points: list[str]`, `schema_id: Optional[UUID] = None`
- [ ] T020 [US3] Implement `export_schema(schema_id: UUID, session: AsyncSession) -> tuple[str, RoundtripResult]` in `backend/src/services/linkml_io.py`: load `DynamicSchema` + elements via `selectinload`; build LinkML YAML dict (prefixes, imports, classes, slots); serialize with `yaml.dump`; compute fidelity score from loss_points list (schema_ref inline, alias groups, PROV metadata, unknown slot_uri)
- [ ] T021 [US3] Add route `GET /schemas/{schema_id}/linkml` to `backend/src/api/v1/schemas.py`: call `export_schema()`; return `Response(content=yaml_str, media_type="application/yaml", headers={"X-Roundtrip-Fidelity": str(result.fidelity_score)})`
- [ ] T022 [US3] Run contract tests from T018; confirm all pass; commit `backend/src/services/linkml_io.py`, `backend/src/api/v1/schemas.py`, `backend/tests/contract/test_linkml_io_api.py`

**Checkpoint**: LinkML export endpoint functional and producing valid YAML.

---

## Phase 6: User Story 4 — LinkML Schema Import + Mapping Accept (P2)

**Goal**: `POST /schemas/import/linkml` creates a `DynamicSchema` from LinkML YAML.
`PUT /mappings/{id}/accept` gates curation of system-inferred mappings by confidence.

**Independent Test**: `POST /schemas/import/linkml` with minimal valid YAML → HTTP 201,
body has `schema_id` + `fidelity_score`.

- [ ] T023 [US4] Extend contract tests in `backend/tests/contract/test_linkml_io_api.py`: (a) valid YAML → 201 + `RoundtripResult` JSON; (b) duplicate URI → 409; (c) invalid YAML → 422; (d) unknown `slot_uri` → 201 with `loss_points` entry; run and confirm FAIL before T024
- [ ] T024a [US4] Add a test fixture helper in `backend/tests/contract/test_mappings_accept.py` that seeds a `MappingFunction` row with `status="pending_curation"`, `attributed_to="urn:undata:system"`, `confidence_score=0.85` — this satisfies FR-013 (system-inferred mappings have these values) without requiring a live inference engine; document in a comment that the inference trigger (semantic graph similarity) is deferred to a future feature
- [ ] T024 [US4] Write contract tests for `PUT /mappings/{id}/accept` in `backend/tests/contract/test_mappings_accept.py`: (a) `pending_curation` mapping → 200 + `status="active"`; (b) confidence below threshold → 422; (c) already `active` mapping → 422; (d) unknown mapping → 404; run and confirm FAIL before T026
- [ ] T025 [US4] Implement `import_schema(yaml_str: str, session: AsyncSession) -> RoundtripResult` in `backend/src/services/linkml_io.py`: `yaml.safe_load`; validate required keys; check URI uniqueness (409); create `DynamicSchema` + `DataElement` rows; score fidelity; return `RoundtripResult` with `schema_id`
- [ ] T026 [US4] Add route `POST /schemas/import/linkml` to `backend/src/api/v1/schemas.py`: parse `application/yaml` request body; call `import_schema()`; return HTTP 201
- [ ] T027 [US4] Add `accept_mapping(mapping_id, confidence_threshold, session)` to `backend/src/services/mappings.py`: verify `status == "pending_curation"`; if threshold provided and `confidence_score < threshold` raise 422; else set `status = "active"` and commit
- [ ] T028 [US4] Add route `PUT /mappings/{mapping_id}/accept` to `backend/src/api/v1/mappings.py` with `confidence_threshold: Optional[float] = Query(None)`
- [ ] T029 [US4] Run all contract tests from T023 + T024; confirm all pass; commit `backend/src/services/linkml_io.py` (extended), `backend/src/services/mappings.py`, `backend/src/api/v1/schemas.py` (extended), `backend/src/api/v1/mappings.py`, `backend/tests/contract/test_linkml_io_api.py` (extended), `backend/tests/contract/test_mappings_accept.py`

**Checkpoint**: Import endpoint and mapping accept endpoint functional.

---

## Phase 7: User Story 5 — Meta-model YAML & GitHub Actions (P2)

**Goal**: `docs/undata-metamodel.yaml` is valid LinkML; `gen-doc` exits 0;
GitHub Actions publishes to GitHub Pages.

**Independent Test**: `uv run --with linkml gen-doc docs/undata-metamodel.yaml -d /tmp/metamodel-test/` exits 0 and produces at least one `.md` file.

- [ ] T030 [US5] Create `docs/undata-metamodel.yaml` with the full meta-model from `specs/011-metamodel-provenance/data-model.md`: classes DataElement, DynamicSchema, SemanticGraph, MappingFunction, ProvenanceRecord with `class_uri` / `slot_uri` anchors; enums ValueType, MappingFunctionType, MappingStatus
- [ ] T031 [US5] Validate: `uv run --with linkml gen-doc docs/undata-metamodel.yaml -d /tmp/mm-test/ && ls /tmp/mm-test/`; fix any validation errors; confirm at least one `.md` file produced
- [ ] T032 [US5] Create `docs/mkdocs.yml`: `site_name: undata Meta-model`, nav pointing to generated Markdown; add `docs/site/` to root `.gitignore`
- [ ] T033 [US5] Create `.github/workflows/metamodel-docs.yml`: trigger on push to `main`; steps: checkout, install uv + linkml + mkdocs-material, run `gen-doc`, run `mkdocs build`, deploy to `gh-pages` branch
- [ ] T034 [US5] Commit `docs/undata-metamodel.yaml`, `docs/mkdocs.yml`, `.github/workflows/metamodel-docs.yml`, updated `.gitignore`

**Checkpoint**: `gen-doc` exits 0 locally; workflow syntax valid (`actionlint` or push to verify CI).

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T035 [P] Run quickstart.md Scenarios 1–6 against live backend; fix any failures
- [ ] T036 [P] Run full regression test suite: `cd backend && docker compose build test && docker compose run --rm --entrypoint="" -e TEST_DATABASE_URL=postgresql+asyncpg://undata:undata@db:5432/undata_test test sh -c "pytest /app/tests/ -v --tb=short"`; all pre-existing 39 tests MUST pass
- [ ] T037 Write unit tests for `provenance.py` helper functions in `backend/tests/unit/test_provenance_svc.py`: test `audit_log_to_bundle()` and `changelog_to_bundle()` offline (no DB, pass mock record objects)
- [ ] T038 Update `CLAUDE.md` via `.specify/scripts/zsh/update-agent-context.sh`
- [ ] T039 Final commit and git push to `origin 011-metamodel-provenance`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (`prov_o.py` used by services)
- **Phase 3 (US1)**: Depends on Phase 2 (migration + prov_o models)
- **Phase 4 (US2)**: Depends on Phase 3 (same `schema_changelog.py` service file)
- **Phase 5 (US3)**: Depends on Phase 2 only — independent of US1/US2
- **Phase 6 (US4)**: Depends on Phase 5 (extends `linkml_io.py`)
- **Phase 7 (US5)**: Depends on Phase 1 only (uses gen-doc tooling) — fully parallel
- **Phase 8 (Polish)**: Depends on all user story phases

### Parallel Opportunities

- T005, T006 (Phase 2 ORM verify + DataElement schema): parallel after T004; T007 must follow T006 (same file)
- T018, T030 (US3 tests, US5 YAML): parallel after Phase 2
- T035, T036 (Polish validation): parallel

### Single Developer Order

T001 → T002 → T003 → T004 →
[T005 T006] → T007 → T008 → T009 → T010a → T010 →
T011 → T012 → T013 → T014 →
T015 → T016 → T017 →
T018 → T019 → T020 → T021 → T022 →
T023 → T024a → T024 → T025 → T026 → T027 → T028 → T029 →
[T030 T031] → T032 → T033 → T034 →
[T035 T036 T037] → T038 → T039

---

## Implementation Strategy

### MVP First (US1 + US2 — Provenance Upgrade)

1. Phase 1: Setup (T001–T004) — generate PROV-O models
2. Phase 2: Foundational (T005–T010) — migration + ORM validation
3. Phase 3: US1 upgrade (T011–T014) — element provenance with correct context
4. Phase 4: US2 upgrade (T015–T017) — schema provenance
5. **STOP and VALIDATE**: both endpoints return `@context: "https://www.w3.org/ns/prov.jsonld"`

### Incremental Delivery

1. MVP: Phases 1–4 → provenance endpoints upgraded
2. Phase 5 (US3) → LinkML export
3. Phase 6 (US4) → LinkML import + mapping accept
4. Phase 7 (US5) → meta-model docs

---

## Notes

- Tests MUST be written before implementation in each phase (Constitution II)
- `GET /elements/{id}/provenance` and `GET /schemas/{id}/provenance` already exist; Phases 3–4 are upgrades, not new implementations
- Migration history is now a single file: `backend/src/db/migrations/versions/2026_03_12_0001_initial_schema.py`
- When adding new columns in future features: update `db.py` ORM + update the single migration file (no new migration file needed until the service is deployed to production)
- `backend/src/models/prov_o.py` is generated — regenerate via `gen-pydantic backend/data/prov-o.linkml.yaml --output backend/src/models/prov_o.py` if `prov-o.linkml.yaml` changes
- Commit after each phase completion (T004, T010, T014, T017, T022, T029, T034, T039)
