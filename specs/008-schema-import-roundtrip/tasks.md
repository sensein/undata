# Tasks: Generic Schema Import with Roundtrip Fidelity

**Branch**: `008-schema-import-roundtrip`
**Input**: Design documents from `/specs/008-schema-import-roundtrip/`
**Prerequisites**: spec.md ✅ plan.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Tests**: TDD is NON-NEGOTIABLE (Constitution §II). All test tasks MUST be written and
confirmed FAILING before the corresponding implementation tasks begin.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

**Purpose**: Version bump and test fixtures that all user stories depend on.

- [X] T001 Bump version to `2026.03.3` in `ingestion/pyproject.toml`
- [X] T002 [P] Create JSON Schema fixture `ingestion/tests/fixtures/generic_schema_sample.json` with: top-level `properties` (3 fields: `id:string`, `count:integer`, `active:boolean`), a `$defs.Address` entry with `properties` (`street:string`, `city:string`), a `$ref` to `$defs.Address` in a `home_address` field, an `enum` field `status` with values `["active","inactive"]`, and a `required: ["id"]` array
- [X] T003 [P] Create LinkML YAML fixture `ingestion/tests/fixtures/linkml_sample.yaml` with: `id: https://example.org/test`, `name: test_schema`, `version: 0.1.0`, 4 slots (`name:string required`, `age:integer`, `active:boolean`, `tags:string multivalued`), and 2 classes (`Person` with slots `name`/`age`/`active`, `Dataset` with slots `name`/`tags`)

**Checkpoint**: Fixtures created — unit tests can reference them immediately.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No new infrastructure needed — `NormalizedElement`, `SchemaClassPayload`,
`SchemaAdapter` protocol, `linkml_runtime`, and `logging` are all already in place.
This phase is satisfied by Phase 1 completion.

**⚠️ NOTE**: All user stories can begin immediately after Phase 1.

---

## Phase 3: User Story 1 — Generic JSON Schema Import (Priority: P1) 🎯 MVP

**Goal**: `GenericJSONSchemaAdapter` loads any draft-07/2019/2020 JSON Schema file and
extracts `NormalizedElement`s and `SchemaClassPayload`s with `source_name="generic-json"`.

**Independent Test**: `uv run pytest tests/unit/test_json_schema_adapter.py` — all pass
with no backend or Docker required.

### TDD: Write Failing Tests First (US1)

- [X] T004 [US1] Write failing unit tests in `ingestion/tests/unit/test_json_schema_adapter.py` covering:
  - `test_load_file_returns_normalized_elements` — `load_file(FIXTURE).extract_elements()` returns `len > 0` and all `isinstance(e, NormalizedElement)`
  - `test_elements_have_source_name_generic_json` — all elements have `source_name == "generic-json"`
  - `test_top_level_properties_extracted` — `id`, `count`, `active`, `home_address`, `status` all appear in element names
  - `test_data_types_correct` — `id` → `"string"`, `count` → `"number"`, `active` → `"boolean"`
  - `test_enum_field_has_allowed_values` — element for `status` has `allowed_values == ["active", "inactive"]`
  - `test_required_field_marked` — element for `id` has `required == True`
  - `test_defs_entry_creates_class_payload` — `extract_classes()` includes `SchemaClassPayload` with `class_name="Address"`
  - `test_defs_properties_extracted_as_elements` — elements for `Address.street` and `Address.city` present
  - `test_ref_resolved_no_raw_ref_string` — no element has `data_type` containing `"$ref"`
  - `test_load_file_empty_path_raises_value_error` — `load_file("")` raises `ValueError`
  - `test_load_file_nonexistent_raises` — `load_file("/nonexistent/path.json")` raises `FileNotFoundError`
  - `test_empty_schema_returns_empty_lists` — `load_file` of `{}` schema returns `extract_elements() == []`
  - `test_get_version_info_has_content_hash` — `get_version_info()["content_hash"]` is non-empty string
  - `test_load_file_emits_info_log` — (G1) use a temporary `CapturingHandler` added directly to `logging.getLogger("undata.adapters.json_schema")` (set level to INFO; restore after); assert log message contains "loaded", "generic", or "json". NOTE: `caplog` does NOT work here because `undata.logging.get_logger()` sets `propagate=False`; `capsys`/`capfd` also fail because the StreamHandler is initialized at import time before pytest capture activates. (Constitution §IV — Observability)
  - `test_load_dandi_dandiset_fixture` — (G2, SC-001) `load_file(str(DANDI_FIXTURE / "dandiset.json")).extract_elements()` returns `len > 0`; set `DANDI_FIXTURE = Path(__file__).parent.parent / "fixtures" / "dandi"`; skip with `pytest.mark.skipif(not DANDI_FIXTURE.exists(), reason="DANDI fixture not present")`

- [X] T004a [US1] **TDD gate — run `uv run pytest ingestion/tests/unit/test_json_schema_adapter.py -x` and confirm at least one test fails with `ImportError` or `ModuleNotFoundError` before proceeding to T005** (Constitution §II step 2)

### Implementation (US1)

- [X] T005 [US1] Implement `GenericJSONSchemaAdapter` in `ingestion/src/undata/adapters/json_schema.py`:
  - `source_name = "generic-json"`, `source_format = "json"`
  - `__init__`: `self._schema: dict = {}`, `self._path: str = ""`
  - `load_file(path_or_url)`: raises `ValueError` on empty; opens JSON; stores in `self._schema`; logs INFO `"Loaded generic JSON schema"` with `extra={"source": "generic-json", "property_count": N}`; raises `FileNotFoundError` propagated from `open()`
  - `_get_defs(schema)` → returns `schema.get("$defs", schema.get("definitions", {}))`
  - `_resolve_ref(ref, defs, depth=0)`: parses `#/$defs/<name>` or `#/definitions/<name>`; returns `defs.get(name, {})`; returns `{}` when `depth >= 5` (max 4 recursive resolutions) with WARN log `"Circular $ref detected at depth {depth}"`
  - `_infer_type(prop, defs)`: handles `type` (str or list[str], strip null), `$ref` → `_resolve_ref(ref, defs, depth+1)` → infer from resolved; returns one of `"string"/"number"/"boolean"/"object"/"array"`
  - `_elements_from_schema(schema, title, defs)` → `list[NormalizedElement]`: iterates `schema.get("properties", {})`; for each prop: infer type, get description, get required from schema-level `required`, get enum, build `NormalizedElement(source_local_id=f"{title}.{prop_name}", source_name="generic-json", extraction_path="file")`
  - `extract_elements(mode="file")` → calls `_elements_from_schema` for root schema (title = `schema.get("title", "Root")`) + for each `$defs`/`definitions` entry that has `properties` (title = def_name)
  - `extract_classes(mode="file")` → `SchemaClassPayload` for root (if has properties) + one per `$defs`/`definitions` entry with properties; `schema_format="json"`
  - `get_version_info()` → SHA-256 of raw file bytes; `version_tag="local"`

**Checkpoint**: `uv run pytest tests/unit/test_json_schema_adapter.py` — all 15 tests PASS.

---

## Phase 4: User Story 2 — LinkML Schema Import (Priority: P2)

**Goal**: `LinkMLAdapter` loads a LinkML YAML schema file and extracts slots as
`NormalizedElement`s and classes as `SchemaClassPayload`s with `source_name="linkml"`.

**Independent Test**: `uv run pytest tests/unit/test_linkml_adapter.py` — all pass offline.

### TDD: Write Failing Tests First (US2)

- [X] T006 [US2] Write failing unit tests in `ingestion/tests/unit/test_linkml_adapter.py` covering:
  - `test_load_file_returns_normalized_elements` — `load_file(LINKML_FIXTURE).extract_elements()` returns `len >= 4` (4 slots) and all `isinstance(e, NormalizedElement)`
  - `test_elements_have_source_name_linkml` — all elements have `source_name == "linkml"`
  - `test_slot_names_present` — `name`, `age`, `active`, `tags` all appear in element names
  - `test_range_mapped_to_data_type` — `name` → `"string"`, `age` → `"number"`, `active` → `"boolean"`, `tags` (multivalued) → `"array"`
  - `test_required_slot_marked` — element for `name` has `required == True`
  - `test_multivalued_slot_is_array` — element for `tags` has `multivalued == True` and `data_type == "array"`
  - `test_extract_classes_returns_class_payloads` — `extract_classes()` returns list with `class_name` in `{"Person", "Dataset"}`
  - `test_classes_have_schema_format_yaml` — all `SchemaClassPayload.schema_format == "yaml"`
  - `test_class_element_source_local_ids` — `Person` class has `source_local_id`s for `name`/`age`/`active`
  - `test_load_file_empty_path_raises_value_error` — `load_file("")` raises `ValueError`
  - `test_get_version_info_has_content_hash` — `get_version_info()["content_hash"]` is non-empty string
  - `test_load_file_emits_info_log` — (G1) use a temporary `CapturingHandler` added directly to `logging.getLogger("undata.adapters.linkml_adapter")` (set level to INFO; restore after); assert log message contains "loaded", "linkml", or "yaml". NOTE: same `propagate=False` constraint applies — see T004 note. (Constitution §IV)

- [X] T006a [US2] **TDD gate — run `uv run pytest ingestion/tests/unit/test_linkml_adapter.py -x` and confirm at least one test fails with `ImportError` or `ModuleNotFoundError` before proceeding to T007** (Constitution §II step 2)

### Implementation (US2)

- [X] T007 [US2] Implement `LinkMLAdapter` in `ingestion/src/undata/adapters/linkml_adapter.py`:
  - `source_name = "linkml"`, `source_format = "yaml"`
  - `__init__`: `self._linkml_schema = None`, `self._path: str = ""`
  - `load_file(path_or_url)`: raises `ValueError` on empty; uses `yaml_loader.load(path_or_url, target_class=SchemaDefinition)` from `linkml_runtime.loaders`; stores in `self._linkml_schema`; logs INFO with slot count and class count
  - `_range_to_data_type(slot)`: if `slot.multivalued` → `"array"`; else map `slot.range` → `{"string":"string","str":"string","integer":"number","int":"number","float":"number","double":"number","boolean":"boolean","bool":"boolean","Any":"object","anyuri":"object","uriorcurie":"object"}.get(range, "object")`; None range → `"string"`
  - `extract_elements(mode="file")` → iterates `self._linkml_schema.slots.items()`; for each slot: `NormalizedElement(name=slot_name, data_type=_range_to_data_type(slot), description=slot.description or "", required=bool(slot.required), multivalued=bool(slot.multivalued), source_local_id=f"{schema.name}.{slot_name}", source_name="linkml", extraction_path="file")`
  - `extract_classes(mode="file")` → iterates `self._linkml_schema.classes.items()`; for each class: `SchemaClassPayload(class_name=cls_name, description=cls.description or "", element_source_local_ids=[f"{schema.name}.{s}" for s in (cls.slots or [])], parent_class_name=cls.is_a or None, extraction_path="file", schema_format="yaml")`
  - `get_version_info()` → SHA-256 of raw file bytes; `version_tag = self._linkml_schema.version or "local"`

**Checkpoint**: `uv run pytest tests/unit/test_linkml_adapter.py` — all 11 tests PASS.

---

## Phase 5: User Story 3 — Roundtrip Validation (Priority: P3)

**Goal**: `roundtrip_json_schema()` and `roundtrip_linkml()` compute a `RoundtripResult`
with `fidelity_score == 1.0` for simple schemas; CLI `undata roundtrip` exits 0 on PASS.

**Independent Test**: `uv run pytest tests/unit/test_roundtrip.py` — all pass offline
(no backend, uses fixtures from Phase 1).

### TDD: Write Failing Tests First (US3)

- [X] T008 [US3] Write failing unit tests in `ingestion/tests/unit/test_roundtrip.py` covering:
  - `test_roundtrip_json_schema_perfect_fidelity` — `roundtrip_json_schema(GENERIC_FIXTURE).fidelity_score == 1.0`
  - `test_roundtrip_json_schema_no_missing_elements` — `result.missing_elements == []`
  - `test_roundtrip_json_schema_no_missing_classes` — `result.missing_classes == []`
  - `test_roundtrip_linkml_perfect_fidelity` — `roundtrip_linkml(LINKML_FIXTURE).fidelity_score == 1.0`
  - `test_roundtrip_linkml_no_missing_slots` — `result.missing_elements == []`
  - `test_roundtrip_result_is_dataclass` — `isinstance(result, RoundtripResult)` and has `fidelity_score`, `missing_classes`, `missing_elements`, `warnings` attributes
  - `test_roundtrip_fidelity_score_range` — `0.0 <= result.fidelity_score <= 1.0`
  - `test_roundtrip_empty_schema_full_fidelity` — schema `{}` → `fidelity_score == 1.0` (vacuously true)
  - `test_roundtrip_json_schema_raises_on_empty_path` — `roundtrip_json_schema("")` raises `ValueError`
  - `test_roundtrip_linkml_raises_on_empty_path` — `roundtrip_linkml("")` raises `ValueError`
  - `test_roundtrip_json_schema_emits_info_log` — (G1) use `caplog` with `level=logging.INFO`; assert fidelity score appears in `caplog.text` after `roundtrip_json_schema(GENERIC_FIXTURE)` (Constitution §IV)

- [X] T008a [US3] **TDD gate — run `uv run pytest ingestion/tests/unit/test_roundtrip.py -x` and confirm at least one test fails with `ImportError` or `ModuleNotFoundError` before proceeding to T009** (Constitution §II step 2)

### Implementation (US3)

- [X] T009 [US3] Implement `RoundtripResult` dataclass + `roundtrip_json_schema()` + `roundtrip_linkml()` in `ingestion/src/undata/roundtrip.py`:
  - `@dataclass class RoundtripResult`: `fidelity_score: float`, `missing_classes: list[str]`, `missing_elements: list[str]`, `warnings: list[str]`
  - `_build_schema_def(elements, classes)` → minimal `SchemaDefinition` using `linkml_runtime`; one `SlotDefinition` per element (name, description, `range` via inline reverse map: `"string"→"string"`, `"number"→"float"`, `"boolean"→"boolean"`, `"object"→"Any"`, `"array"→"string"` with `multivalued=True`; `required`); one `ClassDefinition` per `SchemaClassPayload` (name, description, slots=class.element_source_local_ids with schema prefix stripped)
  - `roundtrip_json_schema(path)`: validate non-empty path; `GenericJSONSchemaAdapter().load_file(path)`; `extract_elements()`/`extract_classes()`; `_build_schema_def()`; `yaml_dumper.dumps(schema_def)` to tempfile; `LinkMLAdapter().load_file(tmp_path)`; compare element name sets and class name sets; compute `fidelity_score = 1.0 - lost/max(total,1)`; return `RoundtripResult`
  - `roundtrip_linkml(path)`: validate non-empty path; `la = LinkMLAdapter(); la.load_file(path)`; `yaml_dumper.dumps(la._linkml_schema)` to tempfile; re-import via new `LinkMLAdapter`; compare sets; return `RoundtripResult`
  - Both functions collect warnings from adapter cycle detection and coercion issues
  - Log INFO with fidelity score on completion

- [X] T010 [US3] Add `roundtrip` Typer subcommand in `ingestion/src/undata/cli.py`:
  - Signature: `@app.command() def roundtrip(path: str, format: str | None = typer.Option(None, "--format", help="json or linkml (auto-detected from extension if omitted)"))` — use `str | None` not `Optional[str]` (Python 3.14 style)
  - Auto-detect: `.json` → `"json"`, `.yaml`/`.yml` → `"linkml"`; raise `typer.BadParameter` if extension unrecognized and `--format` not provided
  - Call `roundtrip_json_schema(path)` or `roundtrip_linkml(path)` per format
  - Print: `Roundtrip fidelity: {score:.2f} (PASS|FAIL)`, `Missing elements: {n}`, `Missing classes: {n}`; if `warnings`, print each warning
  - `raise typer.Exit(code=0)` on PASS, `raise typer.Exit(code=1)` on FAIL

**Checkpoint**: `uv run pytest tests/unit/test_roundtrip.py` — all 10 tests PASS.
`uv run undata roundtrip tests/fixtures/generic_schema_sample.json` — prints PASS, exits 0.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Ruff clean, regression check, CLAUDE.md update.

- [X] T011 [P] Run `uv run ruff check ingestion/src/undata/adapters/json_schema.py ingestion/src/undata/adapters/linkml_adapter.py ingestion/src/undata/roundtrip.py ingestion/src/undata/cli.py` and fix all violations
- [X] T012 [P] Run `uv run ruff format ingestion/src/undata/adapters/json_schema.py ingestion/src/undata/adapters/linkml_adapter.py ingestion/src/undata/roundtrip.py ingestion/src/undata/cli.py` to enforce line length ≤ 100
- [X] T013 Run `uv run pytest ingestion/tests/` and confirm all pre-existing tests still pass (SC-005 regression guard; 192 total at feature completion)
- [X] T014 Update `CLAUDE.md` to mark `008-schema-import-roundtrip` as `COMPLETE` (not `PLANNING`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Satisfied by Phase 1 (no new infra needed)
- **Phase 3 (US1)**: Depends on T002 (fixture). T004 (tests) → T004a (gate, must fail) → T005 (impl).
- **Phase 4 (US2)**: Depends on T003 (fixture). T006 (tests) → T006a (gate, must fail) → T007 (impl).
  Can run in parallel with Phase 3 once fixtures exist.
- **Phase 5 (US3)**: Depends on T005 (US1 impl) + T007 (US2 impl).
  T008 (tests) → T008a (gate, must fail) → T009+T010 (impl).
- **Phase 6 (Polish)**: Depends on all implementation tasks complete.

### User Story Dependencies

- **US1 (P1)**: Needs `generic_schema_sample.json` fixture (T002). Independent of US2/US3.
- **US2 (P2)**: Needs `linkml_sample.yaml` fixture (T003). Independent of US1/US3.
- **US3 (P3)**: Needs `GenericJSONSchemaAdapter` (T005) and `LinkMLAdapter` (T007).

### Within Each User Story

- Tests MUST be written first and confirmed FAILING before implementation begins
- Fixture creation (T002/T003) before tests that reference them
- Adapter implementation before roundtrip functions (US3 depends on US1+US2)

### Parallel Opportunities

- T002 and T003 (fixtures) can be created in parallel
- T004 (US1 tests) and T006 (US2 tests) can be written in parallel after T002/T003
- T005 (US1 impl) and T007 (US2 impl) can be implemented in parallel after their tests fail
- T011 and T012 (ruff check/format) can run in parallel

---

## Parallel Example: Setup Phase

```bash
# Both fixture tasks can run simultaneously:
Task: "Create generic_schema_sample.json in tests/fixtures/"  # T002
Task: "Create linkml_sample.yaml in tests/fixtures/"          # T003
```

## Parallel Example: US1 + US2 after fixtures

```bash
# After T002 and T003 complete, these can run in parallel:
Task: "Write failing tests for GenericJSONSchemaAdapter"      # T004
Task: "Write failing tests for LinkMLAdapter"                 # T006
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1 (T001–T003)
2. Write + fail US1 tests (T004)
3. Implement GenericJSONSchemaAdapter (T005)
4. **STOP and VALIDATE**: `pytest tests/unit/test_json_schema_adapter.py` — all green
5. Any JSON Schema file is now importable as NormalizedElements

### Incremental Delivery

1. Phase 1 → fixtures ready
2. US1 (T004–T005) → generic JSON import works
3. US2 (T006–T007) → LinkML import works
4. US3 (T008–T010) → roundtrip validation + CLI works
5. Polish (T011–T014) → ruff clean, regressions confirmed

---

## Notes

- All test files MUST import from `undata.adapters.json_schema`, `undata.adapters.linkml_adapter`,
  and `undata.roundtrip` — imports will fail before implementation (TDD red phase).
- `GenericJSONSchemaAdapter` reuses the `_elements_from_props()` pattern from `dandi.py` —
  check that file for reference but do NOT modify it.
- `LinkMLAdapter` uses `yaml_loader` which is already used in `validation.py` — same import.
- `roundtrip.py` uses `tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)` and
  cleans up with `os.unlink()` in a `finally` block.
- `ruff` max line length is 100 per constitution. Use `# noqa: E501` sparingly.
