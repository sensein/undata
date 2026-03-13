# Tasks: Metamodel, Provenance & LinkML I/O

**Input**: Design documents from `specs/011-metamodel-provenance/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 per spec.md user stories
- All paths are relative to repo root

---

## Phase 1: Setup (Code Generation & Tooling)

**Purpose**: Generate PROV-O Pydantic models from OWL→LinkML conversion. These files
are committed and used by all subsequent phases.

- [ ] T001 Add `linkml-owl` to `[dependency-groups] dev` in `backend/pyproject.toml` and run `uv sync` in `backend/`
- [ ] T002 Run `uv run linkml-owl-to-linkml --input https://www.w3.org/ns/prov-o --output backend/data/prov-o-raw.linkml.yaml` in `backend/`; prune to 6 classes (Entity, Activity, Agent, Generation, Usage, Bundle) and save as `backend/data/prov-o.linkml.yaml`
- [ ] T003 Run `uv run gen-pydantic backend/data/prov-o.linkml.yaml --output backend/src/models/prov_o.py` in `backend/`; verify file contains `class Entity`, `class Activity`, `class Agent`, `class Bundle`
- [ ] T004 Commit generated files: `backend/data/prov-o.linkml.yaml`, `backend/data/prov-o-raw.linkml.yaml`, `backend/src/models/prov_o.py`, updated `backend/pyproject.toml`

---

## Phase 2: Foundational (Database Migration & ORM)

**Purpose**: DB schema changes that MUST be in place before any endpoint work.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Write Alembic migration `backend/db/migrations/versions/0010_schema_ref.py`: add `schema_ref UUID FK → dynamic_schema(id) ON DELETE SET NULL` on `data_element`; add `status VARCHAR(32) NOT NULL DEFAULT 'active'`, `attributed_to TEXT`, `confidence_score FLOAT` on `mapping_function`
- [ ] T006 Update `DataElement` ORM in `backend/src/models/db.py`: add `schema_ref: Mapped[Optional[UUID]]` with `ForeignKey("dynamic_schema.id", ondelete="SET NULL")` and `schema_ref_rel` relationship
- [ ] T007 Update `MappingFunction` ORM in `backend/src/models/db.py`: add `status: Mapped[str]` (server_default `"active"`), `attributed_to: Mapped[Optional[str]]`, `confidence_score: Mapped[Optional[float]]`
- [ ] T008 Update `DataElementCreate` / `DataElementRead` Pydantic schemas in `backend/src/models/schemas.py`: add `schema_ref: Optional[UUID]`; add validation that `schema_ref` is required when `value_type == "object"`
- [ ] T009 Update `MappingFunctionRead` / `MappingFunctionCreate` Pydantic schemas in `backend/src/models/schemas.py`: add `status`, `attributed_to`, `confidence_score` fields
- [ ] T010 Run `docker compose run --rm backend alembic upgrade head` inside `backend/` to verify migration applies cleanly; commit migration and ORM changes
- [ ] T011 Write contract tests for `schema_ref` validation in `backend/tests/contract/test_elements_schema_ref.py`: verify (a) creating an `object`-typed element without `schema_ref` returns HTTP 422; (b) creating with valid `schema_ref` returns HTTP 201 with `schema_ref` in response

**Checkpoint**: Migration applied; ORM updated; object-typed element validation active.

---

## Phase 3: User Story 1 — Element Provenance (P1)

**Goal**: `GET /elements/{id}/provenance` returns a valid PROV-O JSON-LD bundle
assembled from `AuditLog` rows.

**Independent Test**: `GET /elements/{id}/provenance` → HTTP 200, `Content-Type: application/ld+json`,
`@context == "https://www.w3.org/ns/prov.jsonld"`, `@graph` contains Entity + Activity + Agent.

- [ ] T012 [US1] Implement `audit_log_to_bundle(records: list[AuditLog], resource_uri: str) -> dict` in `backend/src/services/provenance.py`: build `prov:Entity`, `prov:Activity`, `prov:Agent` dicts using imported `prov_o.py` models, inject `@context` = `"https://www.w3.org/ns/prov.jsonld"`
- [ ] T013 [US1] Implement `get_element_provenance(element_id: UUID, session: AsyncSession) -> dict` in `backend/src/services/provenance.py`: load `AuditLog` rows filtered by `resource_id == element_id`, verify element exists (raise 404), call `audit_log_to_bundle()`
- [ ] T014 [US1] Create FastAPI router `backend/src/api/v1/provenance.py` with route `GET /elements/{element_id}/provenance` returning `Response(content=json.dumps(bundle), media_type="application/ld+json")`
- [ ] T015 [US1] Register `provenance` router in `backend/src/main.py` under prefix `/api/v1`
- [ ] T016 [US1] Write contract tests in `backend/tests/contract/test_provenance_api.py`: (a) 200 with valid PROV-O structure; (b) 3 audit entries → 3 Activity nodes; (c) invalid UUID → 404
- [ ] T017 [US1] Commit all Phase 3 files: `provenance.py` (service), `api/v1/provenance.py` (router), `main.py` (registration), test file

**Checkpoint**: `GET /elements/{id}/provenance` returns valid PROV-O JSON-LD.

---

## Phase 4: User Story 2 — Schema Provenance (P1)

**Goal**: `GET /schemas/{id}/provenance` returns a PROV-O JSON-LD bundle with
`prov:wasDerivedFrom` chain from `SchemaChangeLog` entries.

**Independent Test**: `GET /schemas/{id}/provenance` → HTTP 200, `application/ld+json`,
`@graph` contains Entity nodes linked by `prov:wasDerivedFrom`.

- [ ] T018 [US2] Add `changelog_to_bundle(records: list[SchemaChangeLog], resource_uri: str) -> dict` to `backend/src/services/provenance.py`: builds Entity nodes with `prov:wasDerivedFrom` links; reuses system Agent `urn:undata:system` for system-generated changes
- [ ] T019 [US2] Add `get_schema_provenance(schema_id: UUID, session: AsyncSession) -> dict` to `backend/src/services/provenance.py`: load `SchemaChangeLog` rows, verify schema exists (404), call `changelog_to_bundle()`
- [ ] T020 [US2] Add route `GET /schemas/{schema_id}/provenance` to `backend/src/api/v1/provenance.py`
- [ ] T021 [US2] Extend contract tests in `backend/tests/contract/test_provenance_api.py`: (a) schema with 2 changelog entries → `prov:wasDerivedFrom` present; (b) new-URI change → two distinct Entity `@id` values; (c) invalid schema id → 404
- [ ] T022 [US2] Commit Phase 4 changes

**Checkpoint**: Both provenance endpoints functional. PROV-O bundle validated.

---

## Phase 5: User Story 3 — LinkML Schema Export (P1)

**Goal**: `GET /schemas/{id}/linkml` returns valid LinkML YAML with
`X-Roundtrip-Fidelity` header.

**Independent Test**: `GET /schemas/{id}/linkml` → HTTP 200, `Content-Type: application/yaml`,
`X-Roundtrip-Fidelity` header present and parseable as float.

- [ ] T023 [US3] Define `RoundtripResult(BaseModel)` in `backend/src/services/linkml_io.py`: fields `fidelity_score: float`, `loss_points: list[str]`, `schema_id: Optional[UUID] = None`
- [ ] T024 [US3] Implement `export_schema(schema_id: UUID, session: AsyncSession) -> tuple[str, RoundtripResult]` in `backend/src/services/linkml_io.py`: load `DynamicSchema` + elements via `selectinload`; build LinkML YAML dict (prefixes, imports, classes, slots); serialize with `yaml.dump`; compute fidelity score; populate `loss_points` for each known loss (schema_ref inline, alias groups, PROV metadata, slot_uri missing)
- [ ] T025 [US3] Add route `GET /schemas/{schema_id}/linkml` to `backend/src/api/v1/schemas.py`: call `export_schema()`; return `Response(content=yaml_str, media_type="application/yaml", headers={"X-Roundtrip-Fidelity": str(result.fidelity_score)})`
- [ ] T026 [US3] Write contract tests in `backend/tests/contract/test_linkml_io_api.py`: (a) valid schema → 200 + YAML with `classes:` + fidelity header; (b) schema with alias group → slot has `aliases:` list in YAML; (c) schema with `schema_ref` element → referenced class appears in YAML; (d) invalid id → 404
- [ ] T027 [US3] Commit Phase 5 changes

**Checkpoint**: LinkML export endpoint functional and producing valid YAML.

---

## Phase 6: User Story 4 — LinkML Schema Import + Mapping Accept (P2)

**Goal**: `POST /schemas/import/linkml` creates a `DynamicSchema` from LinkML YAML
and returns `RoundtripResult`. `PUT /mappings/{id}/accept` transitions
`pending_curation` mappings to `active`.

**Independent Test**: `POST /schemas/import/linkml` with minimal valid YAML → HTTP 201,
body has `schema_id` + `fidelity_score`.

- [ ] T028 [US4] Implement `import_schema(yaml_str: str, session: AsyncSession) -> RoundtripResult` in `backend/src/services/linkml_io.py`: parse YAML with `yaml.safe_load`; validate required keys (`id`, `name`, `classes`); check URI uniqueness (409 on conflict); create `DynamicSchema` + `DataElement` rows; score fidelity; return `RoundtripResult` with `schema_id`
- [ ] T029 [US4] Add route `POST /schemas/import/linkml` to `backend/src/api/v1/schemas.py`: parse `application/yaml` body; call `import_schema()`; return HTTP 201 with `RoundtripResult`
- [ ] T030 [US4] Add `accept_mapping(mapping_id: UUID, confidence_threshold: Optional[float], session: AsyncSession)` to `backend/src/services/mappings.py`: load mapping; verify status is `pending_curation`; if `confidence_threshold` provided and `confidence_score < threshold` raise HTTP 422; else set `status = "active"` and commit
- [ ] T031 [US4] Add route `PUT /mappings/{mapping_id}/accept` to `backend/src/api/v1/mappings.py` with optional `confidence_threshold: Optional[float] = Query(None)`
- [ ] T032 [US4] Extend contract tests in `backend/tests/contract/test_linkml_io_api.py`: (a) valid YAML → 201 + RoundtripResult; (b) duplicate URI → 409; (c) invalid YAML → 422; (d) unknown slot_uri → 201 with loss_point entry
- [ ] T033 [US4] Write contract tests for `PUT /mappings/{id}/accept` in `backend/tests/contract/test_mappings_accept.py`: (a) accept pending mapping → 200 + status=active; (b) confidence below threshold → 422; (c) already active mapping → 422; (d) unknown mapping → 404
- [ ] T034 [US4] Commit Phase 6 changes

**Checkpoint**: Import endpoint and mapping accept endpoint functional.

---

## Phase 7: User Story 5 — Meta-model YAML & GitHub Actions (P2)

**Goal**: `docs/undata-metamodel.yaml` is a valid self-describing LinkML YAML;
`gen-doc` runs without error; GitHub Actions workflow publishes to GitHub Pages.

**Independent Test**: `uv run gen-doc docs/undata-metamodel.yaml -d /tmp/metamodel-test/ && ls /tmp/metamodel-test/index.md` exits 0.

- [ ] T035 [US5] Create `docs/undata-metamodel.yaml` with the full meta-model defined in `specs/011-metamodel-provenance/data-model.md` (DataElement, DynamicSchema, SemanticGraph, MappingFunction, ProvenanceRecord, DataElementVersion with class_uri/slot_uri anchors)
- [ ] T036 [US5] Validate `docs/undata-metamodel.yaml` runs cleanly: `uv run --with linkml gen-doc docs/undata-metamodel.yaml -d /tmp/mm-test/`; fix any validation errors
- [ ] T037 [US5] Create `.github/workflows/metamodel-docs.yml`: trigger on push to `main`; steps: checkout, install uv, `uv run --with "linkml mkdocs" gen-doc docs/undata-metamodel.yaml -d docs/site/metamodel/`; deploy to `gh-pages` alongside JupyterBook HTML
- [ ] T038 [US5] Add `docs/mkdocs.yml` with `site_name: undata Meta-model` and nav pointing to `metamodel/index.md`
- [ ] T039 [US5] Add `docs/site/` to `.gitignore`; commit `docs/undata-metamodel.yaml`, `docs/mkdocs.yml`, `.github/workflows/metamodel-docs.yml`

**Checkpoint**: `gen-doc` exits 0 locally; workflow file validated with `act` or pushed to verify CI.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T040 [P] Run quickstart.md Scenarios 1–6 against live backend; fix any failures found
- [ ] T041 [P] Verify no regression: run full existing test suite `docker compose run --rm test pytest /app/tests/ -v --tb=short` in `backend/`; all 39 pre-existing tests MUST pass
- [ ] T042 Update `CLAUDE.md` via `.specify/scripts/zsh/update-agent-context.sh` to document new endpoints and packages
- [ ] T043 Final git push to `origin 011-metamodel-provenance`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (ORM uses `prov_o.py` models)
- **Phase 3 (US1)**: Depends on Phase 2 (needs AuditLog + migration)
- **Phase 4 (US2)**: Depends on Phase 3 (extends same `provenance.py` service)
- **Phase 5 (US3)**: Depends on Phase 2 only — can run in parallel with Phase 3/4
- **Phase 6 (US4)**: Depends on Phase 5 (extends `linkml_io.py` + `mappings.py` from Phase 2)
- **Phase 7 (US5)**: Depends on Phase 1 only (uses `gen-doc` tooling) — fully parallel
- **Phase 8 (Polish)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no US dependencies
- **US2 (P1)**: After US1 (shares `provenance.py` service)
- **US3 (P1)**: After Phase 2 — independent of US1/US2
- **US4 (P2)**: After US3 (extends `linkml_io.py`)
- **US5 (P2)**: After Phase 1 — fully independent

### Parallel Opportunities

- T001–T004 (Phase 1): sequential (each depends on previous)
- T005–T009 (Phase 2 DB+ORM): T006, T007, T008, T009 can run in parallel after T005
- T012, T018 (provenance service fns): T012 first, T018 extends same file
- T023, T035, T037 (US3 service, US5 YAML, US5 workflow): fully parallel after Phase 1
- T040, T041 (Polish validation): parallel

---

## Parallel Example: Phase 2

```bash
# After T005 (migration file written), these can run in parallel:
Task T006: Update DataElement ORM in backend/src/models/db.py
Task T007: Update MappingFunction ORM in backend/src/models/db.py
Task T008: Update DataElementCreate schemas in backend/src/models/schemas.py
Task T009: Update MappingFunctionRead schemas in backend/src/models/schemas.py
```

## Parallel Example: Phase 5 + Phase 7

```bash
# After Phase 2 completes, these two phases are fully independent:
Phase 5 (US3): LinkML export — backend/src/services/linkml_io.py, backend/src/api/v1/schemas.py
Phase 7 (US5): Meta-model YAML — docs/undata-metamodel.yaml, .github/workflows/metamodel-docs.yml
```

---

## Implementation Strategy

### MVP First (US1 + US2 — Provenance)

1. Phase 1: Setup (T001–T004) — generate PROV-O Pydantic models
2. Phase 2: Foundational (T005–T011) — migration + ORM
3. Phase 3: US1 — element provenance (T012–T017)
4. Phase 4: US2 — schema provenance (T018–T022)
5. **STOP and VALIDATE**: both provenance endpoints return valid PROV-O JSON-LD

### Incremental Delivery

1. MVP: Phases 1–4 → provenance endpoints live
2. Add US3 (Phase 5) → LinkML export
3. Add US4 (Phase 6) → LinkML import + mapping accept
4. Add US5 (Phase 7) → meta-model docs published

### Single Developer Order

T001 → T002 → T003 → T004 → T005 → [T006 T007 T008 T009] → T010 → T011 →
T012 → T013 → T014 → T015 → T016 → T017 →
T018 → T019 → T020 → T021 → T022 →
[T023 T035] → T024 → T025 → T026 → T027 →
[T036 T037 T038] → T028 → T029 → T030 → T031 → T032 → T033 → T034 →
T039 → T040 → T041 → T042 → T043

---

## Notes

- `[P]` tasks touch different files and have no incomplete-task dependencies
- All PROV-O JSON-LD is hand-constructed via Pydantic models (no `prov` package)
- `backend/src/models/prov_o.py` is generated code — regenerate via `gen-pydantic` if `prov-o.linkml.yaml` changes
- Commit after each phase (T004, T010, T017, T022, T027, T034, T039, T043)
- Run `docker compose build test && docker compose run --rm test pytest` after T011 and T043
