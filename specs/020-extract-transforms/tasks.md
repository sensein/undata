# Tasks: Extract & Transform Pipeline

**Feature**: `020-extract-transforms` | **Branch**: `020-extract-transforms`

**User Stories** (mapped from spec):
- US1 — Complete Re-extraction with New Adapter Framework (P1, FR-001 to FR-003)
- US2 — Transform Generation Between Overlapping Elements (P1, FR-004 to FR-008)
- US3 — Transform Function Model (P1, FR-009 to FR-012)
- US4 — Ontology Inverse Map (P2, FR-013 to FR-015)

---

## Phase 1: Setup

- [X] T001 Create `library/transforms/` directory (empty, will be populated during re-extraction)
- [X] T002 [P] Delete old `library/mappings/` directory if it exists (replaced by transforms/)

---

## Phase 2: Foundational — Transform Model + Hashing

**Goal**: TransformRecord, FunctionSpec models, extended MappingFunctionType, hashing.

- [X] T003 Add `type_conversion` and `value_mapping` to `MappingFunctionType` enum in `library/src/undata_library/models.py`
- [X] T004 Add `FunctionSpec` Pydantic model to `library/src/undata_library/models.py`: fields — `function_type: str`, `input_type: str`, `output_type: str`, `expression: str | None`, `expression_type: str` (arithmetic|named_function|template|lookup_table|none), `parameters: dict | None`
- [X] T005 Add `TransformRecord` Pydantic model to `library/src/undata_library/models.py`: fields — `source_element: str`, `target_element: str`, `function: FunctionSpec`, `confidence: float | None`, `sssom_predicate: str | None`, `provenance: list[ProvenanceEntry]`
- [X] T006 Add `build_transform_uri(source_name, target_name, key)` to `library/src/undata_library/hashing.py`
- [X] T007 Write tests in `library/tests/test_transform_model.py`: (a) FunctionSpec validates all expression_types; (b) TransformRecord round-trips to/from dict; (c) MappingFunctionType includes type_conversion and value_mapping; (d) build_transform_uri produces correct URI format
- [X] T008 Lint + run all tests; commit Phase 2

---

## Phase 3: US2+US3 — Transform Generation Engine

**Goal**: Auto-detect conversion patterns and generate typed bidirectional transforms.

- [X] T009 [US2] [US3] Create `library/src/undata_library/transform.py`: `generate_transforms(elements_dir, library_path, threshold) -> dict` — scans elements, groups by ontology_term, generates bidirectional transform pairs, writes to transforms/
- [X] T010 [US2] [US3] Implement pattern detection in `library/src/undata_library/transform.py`: `_detect_pattern(elem_a, elem_b) -> FunctionSpec` — rule-based matching for identity, unit_conversion (years↔months), type_conversion (float↔ISO8601 string), value_mapping (enum overlap), structural (object↔flat), unknown
- [X] T011 [P] [US3] Implement unit conversion detection in `transform.py`: `_detect_unit_conversion(unit_a, unit_b) -> FunctionSpec | None` — known unit pairs (year↔month factor=12, meter↔centimeter factor=100, etc.) with arithmetic expression
- [X] T012 [P] [US3] Implement type conversion detection in `transform.py`: `_detect_type_conversion(type_a, type_b, unit_a, unit_b) -> FunctionSpec | None` — float↔string ISO8601, integer↔string, enum value_mapping
- [X] T013 [US2] Implement bidirectional transform writing in `transform.py`: `_write_transform(source_uri, target_uri, func_spec, library_path) -> Path` — compute sha256 of canonical({source_element, target_element, function}), write content-addressed YAML to transforms/, generate both forward and reverse
- [X] T014 [US2] Implement transform provenance: each transform gets `generated_at`, `attributed_to: urn:undata:transform-pipeline`, `activity: transform`
- [X] T015 [US2] [US3] Write tests in `library/tests/test_transform.py`: (a) same ontology_term + different type → transform created; (b) same hash → no transform; (c) identity pattern detected for same type+unit; (d) unit_conversion pattern for years→months with expression `value * 12`; (e) type_conversion for float→string ISO8601; (f) value_mapping for overlapping enums; (g) unknown pattern for incompatible types; (h) bidirectional: both forward and reverse files written; (i) sha256 in transform YAML matches recomputed hash
- [X] T016 Lint + run all tests; commit Phase 3

---

## Phase 4: US4 — Ontology Inverse Map Extension

**Goal**: Include schemas and valuesets in ontology-index.yaml.

- [X] T017 [US4] Modify `build_ontology_index()` in `library/src/undata_library/index.py`: scan `schemas/` and `valuesets/` directories in addition to `elements/`; each entry includes `entity_type` field (element, schema, or valueset)
- [X] T018 [US4] Write tests in `library/tests/test_ontology_index.py`: (a) element with ontology_term appears in index; (b) schema with ontology_term appears with entity_type=schema; (c) valueset with ontology_term appears with entity_type=valueset; (d) entity without ontology_term does not appear
- [X] T019 Lint + run all tests; commit Phase 4

---

## Phase 5: US1 — Pipeline Integration + CLI

**Goal**: Transform step in pipeline, standalone CLI, validation extension.

- [X] T020 [US1] Add `transform` CLI command to `library/src/undata_library/cli.py`: `undata-library transform [PATH] [--threshold FLOAT] [--output-dir DIR]` — calls `generate_transforms()` and reports stats
- [X] T021 [US1] Extend `pipeline` CLI command in `library/src/undata_library/cli.py`: add transform step after align and before validate; add `--skip-transform` flag
- [X] T022 [US1] Extend `validate_ingestion_output()` in `library/src/undata_library/validation.py`: add transform checks — (a) source_element URI resolves; (b) target_element URI resolves; (c) function_type is valid MappingFunctionType; (d) expression present for non-identity transforms; (e) sha256 matches recomputed hash
- [X] T023 [US1] Update `run_workflow()` in `library/src/undata_library/workflow.py`: add transform step between align and validate; record timing
- [X] T024 [US1] Update `build_ontology_index()` call in pipeline to run after transforms (include all entity types)
- [X] T025 [US1] Write tests in `library/tests/test_pipeline_transforms.py`: (a) pipeline produces transforms/ directory; (b) pipeline --skip-transform skips transform step; (c) validate-ingestion checks transform integrity; (d) standalone `transform` command produces correct output
- [X] T026 Lint + run all tests; commit Phase 5

---

## Phase 6: Re-extraction + Polish

- [X] T027 Delete old library output: `rm -rf library/elements/ library/schemas/ library/values/ library/valuesets/ library/mappings/ library/transforms/`
- [X] T028 Re-extract all 5 sources: run `undata-library pipeline --source bids`, then nwb, dandi, aind, openminds (with appropriate --path flags)
- [X] T029 [P] Verify transforms/ populated with bidirectional TransformRecord YAML files
- [X] T030 [P] Verify ontology-index.yaml includes entity_type for schemas and valuesets
- [X] T031 [P] Verify ingestion-report.yaml shows 0 violations
- [X] T032 [P] Verify known transform patterns: age years↔months has unit_conversion, age float↔ISO8601 has type_conversion
- [X] T033 Run all library tests: `uv run pytest tests/ -v`
- [X] T034 Lint all code: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- [X] T035 Final commit and push

---

## Dependencies

```
Phase 1 (T001-T002): Setup — no deps
Phase 2 (T003-T008): Transform model — depends on Phase 1
Phase 3 (T009-T016): Transform engine — depends on Phase 2
Phase 4 (T017-T019): Ontology extension — depends on Phase 1 (can parallel with Phase 3)
Phase 5 (T020-T026): CLI + pipeline — depends on Phase 3 + Phase 4
Phase 6 (T027-T035): Re-extraction — depends on all

Parallelizable: Phase 3 ‖ Phase 4
```

## Implementation Strategy

1. **Phase 1-2** (T001-T008): Foundation — models + hashing. **Suggested MVP.**
2. **Phase 3** (T009-T016): Transform engine — core value. Detects patterns and generates bidirectional transforms.
3. **Phase 4** (T017-T019): Ontology extension — quick win, can parallel with Phase 3.
4. **Phase 5** (T020-T026): Pipeline integration — CLI and workflow.
5. **Phase 6** (T027-T035): Full re-extraction with all 5 sources.

**Suggested MVP**: Phases 1-3 (T001-T016) — Transform model + generation engine with pattern detection.
