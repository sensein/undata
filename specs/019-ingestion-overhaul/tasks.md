# Tasks: Ingestion Overhaul

**Feature**: `019-ingestion-overhaul` | **Branch**: `019-ingestion-overhaul`

**User Stories** (mapped from spec):
- US1 — Rigorous Schema Classification (P1, FR-001 to FR-005)
- US2 — Extensible Source Adapters (P1, FR-006 to FR-009)
- US3 — LLM-Assisted Classification (P2, FR-010 to FR-014)
- US4 — Docker-Based Code Inspection (P2, FR-015 to FR-019)
- US5 — Parameterizable Workflow + Output Validation (P2, FR-020 to FR-025)
- US6 — Precise Source Tracking (P1, FR-026 to FR-030)
- US7 — Schema Provenance Alignment (P3, FR-031 to FR-032)

---

## Phase 1: Setup

- [X] T001 Add `litellm` to `[llm]` optional extra and `docker` to `[docker]` optional extra in `library/pyproject.toml`
- [X] T002 [P] Create `library/src/undata_library/adapters/` directory with `__init__.py`
- [X] T003 [P] Create `library/src/undata_library/adapters/docker_scripts/` directory with `__init__.py`

---

## Phase 2: Foundational — Models + BaseAdapter

**Goal**: New entity types, extended models, adapter interface — prerequisites for all user stories.

- [X] T004 Add `ValueSetIdentity` and `ValueSetRecord` models to `library/src/undata_library/models.py` with `semantic: ValueSetIdentity` + `provenance: list[ProvenanceEntry]`
- [X] T005 [P] Add `EntityType` enum (class, attribute, enum_value, valueset) to `library/src/undata_library/models.py`
- [X] T006 [P] Add `type_ref: str | None` field to `SemanticIdentity` in `library/src/undata_library/models.py`; update `_EXCLUDED_FROM_HASH` — type_ref IS in hash
- [X] T007 [P] Extend `SchemaProvenance` with `generated_at`, `attributed_to`, `activity`, `derived_from`, `source_ref` fields in `library/src/undata_library/models.py`
- [X] T008 Add `build_valueset_uri(name, key)` to `library/src/undata_library/hashing.py`; include `type_ref` in `canonical_json` when present
- [X] T009 Add `IngestionReport` and `WorkflowSpec` Pydantic models to `library/src/undata_library/models.py`
- [X] T010 Create `library/src/undata_library/adapters/base.py`: `BaseAdapter` ABC with `extract(source_path, **options) -> list[ClassifiedEntity]`, `name` property, `supported_formats` property; `ClassifiedEntity` dataclass with `source_ref: SourceRef` (repo, committish, file, checksum, package_version); `SourceRef` dataclass
- [X] T011 Create `library/src/undata_library/adapters/classifier.py`: `classify_entity(name, type_info, parent, siblings) -> tuple[EntityType, float]` — rule-based classification with structural signal detection (properties/slots → class; leaf type → attribute; enum/oneOf → enum_value; named enum collection → valueset)
- [X] T012 Write tests in `library/tests/test_classifier.py`: (a) JSON Schema with properties → class; (b) leaf string field → attribute; (c) enum with literals → enum_value; (d) named enum collection → valueset; (e) attribute referencing class → attribute with type_ref; (f) confidence scores in expected ranges
- [X] T013 Lint + run all tests; commit Phase 2

---

## Phase 3: US1+US2 — Adapter Refactoring + Classification Rigor

**Goal**: Rewrite 5 existing extractors as BaseAdapter subclasses with 4-way classification.

- [X] T014 [US1] [US2] [US6] Create `library/src/undata_library/adapters/bids.py`: `BIDSAdapter(BaseAdapter)` — rewrite `extractors/bids.py` logic; classify classes vs attributes vs enums vs valuesets; emit `ClassifiedEntity` with confidence scores and `source_ref` (repo URL, committish from git, file path, SHA-256 checksum of source file)
- [X] T015 [P] [US1] [US2] [US6] Create `library/src/undata_library/adapters/nwb.py`: `NWBAdapter(BaseAdapter)` — rewrite `extractors/nwb.py`; classify NWB namespace entities; populate `source_ref` with repo/committish/file/checksum
- [X] T016 [P] [US1] [US2] [US6] Create `library/src/undata_library/adapters/dandi.py`: `DANDIAdapter(BaseAdapter)` — rewrite `extractors/dandi.py`; classify Pydantic models and PropertyValue variants; populate `source_ref`
- [X] T017 [P] [US1] [US2] [US6] Create `library/src/undata_library/adapters/openminds.py`: `OpenMINDSAdapter(BaseAdapter)` — rewrite `extractors/openminds.py`; classify linked-data entities; populate `source_ref`
- [X] T018 [P] [US1] [US2] [US6] Create `library/src/undata_library/adapters/aind.py`: `AINDAdapter(BaseAdapter)` — rewrite `extractors/aind.py`; classify JSON Schema $defs; underscore entries → ValueConcept; named enum collections → ValueSet; populate `source_ref`
- [X] T019 [US1] [US2] Delete `library/src/undata_library/extractors/` directory entirely
- [X] T020 [US1] [US2] Refactor `library/src/undata_library/ingest.py`: replace `_extract()` dispatcher with adapter registry lookup; consume `list[ClassifiedEntity]`; route by `EntityType` to elements/, schemas/, values/, valuesets/ directories; write sha256 to all output files
- [X] T020b [US1] Add `classification_confidence` field to provenance entries in `library/src/undata_library/ingest.py`: for each ClassifiedEntity, store `confidence` in the provenance dict; verify every output YAML contains a numeric confidence value
- [X] T021 [US1] [US2] Create `library/src/undata_library/adapters/registry.py`: `AdapterRegistry` with `register(adapter_class)`, `get(name) -> BaseAdapter`, `auto_detect(path) -> BaseAdapter`; auto-detect by file extension; discover entry points via `importlib.metadata.entry_points(group="undata.adapters")`
- [X] T022 [US1] Write tests in `library/tests/test_classification.py`: (a) BIDS "units" classified as valueset not schema; (b) BIDS participant fields classified as attributes; (c) AIND underscore entries classified as enum_value; (d) class with properties classified as class; (e) all 5 sources produce 0 misclassification violations; (f) every output provenance entry contains classification_confidence
- [X] T023 [US2] [US6] Write tests in `library/tests/test_adapters.py`: (a) adapter registry discovers built-in adapters; (b) auto-detect returns correct adapter for .json/.yaml/.csv; (c) BaseAdapter.extract returns list[ClassifiedEntity]; (d) all ClassifiedEntity have valid EntityType + confidence; (e) mock entry point adapter discovered via importlib.metadata; (f) every ClassifiedEntity has non-null source_ref with file + checksum; (g) git-sourced adapters populate repo + committish; (h) non-git adapters have null repo/committish
- [X] T024 Update `library/src/undata_library/cli.py`: add `--adapter` and `--adapter-module` flags to `ingest` command; use adapter registry for dispatch
- [X] T025 Lint + run all tests; commit Phase 3

---

## Phase 4: US2 (cont.) — Generic Source Adapters

**Goal**: JSONSchemaAdapter, LinkMLAdapter, CSVDictionaryAdapter for arbitrary sources.

- [X] T026 [US2] [US6] Create `library/src/undata_library/adapters/json_schema.py`: `JSONSchemaAdapter(BaseAdapter)` — generic JSON Schema (draft-07/2019/2020-12) parser; detect $defs, properties, enums, anyOf; classify each; handle circular $ref with visited set; populate `source_ref` with file path + SHA-256 checksum (repo/committish null for standalone files)
- [X] T027 [P] [US2] [US6] Create `library/src/undata_library/adapters/linkml.py`: `LinkMLAdapter(BaseAdapter)` — parse LinkML YAML; classes → CLASS, slots → ATTRIBUTE, enums → VALUESET with member ValueConcepts; populate `source_ref`
- [X] T028 [P] [US2] [US6] Create `library/src/undata_library/adapters/csv_dictionary.py`: `CSVDictionaryAdapter(BaseAdapter)` — parse CSV/TSV data dictionaries; configurable column names (name_column, type_column, description_column, values_column); one row → one ElementRecord; allowed_values → response_options or ValueSet; populate `source_ref` with file path + SHA-256 checksum
- [X] T029 [US2] Write tests in `library/tests/test_generic_adapters.py`: (a) JSON Schema with mixed defs → correct classification; (b) circular $ref → warning + partial extraction; (c) LinkML with classes/slots/enums → correct types; (d) CSV with 10 rows → 10 elements with correct data_type; (e) CSV without type column → defaults to string
- [X] T030 Register all generic adapters in `library/src/undata_library/adapters/registry.py`; update auto-detection logic
- [X] T031 Lint + run all tests; commit Phase 4

---

## Phase 5: US3 — LLM-Assisted Classification

**Goal**: Optional LLM fallback when rule-based confidence < threshold.

- [X] T032 [US3] Create `library/src/undata_library/adapters/llm_classifier.py`: `LLMClassifier` class with `classify(entity_name, type_info, description, parent_context, siblings) -> tuple[EntityType, float, str]`; uses litellm `completion()` with structured JSON prompt; validates response against EntityType enum; returns (type, confidence, reasoning)
- [X] T033 [US3] Integrate LLM fallback into `library/src/undata_library/adapters/classifier.py`: when rule-based confidence < threshold and LLM is configured, invoke `LLMClassifier`; record LLM decision in provenance with `attributed_to: urn:llm:{model_name}` and `activity: classification`
- [X] T034 [US3] Update `library/src/undata_library/cli.py`: add `--llm-model MODEL` and `--llm-threshold FLOAT` flags to `ingest` and `pipeline` commands; pass to adapter registry/classifier
- [X] T035 [US3] Write tests in `library/tests/test_llm_classifier.py`: (a) mock litellm returns valid classification → accepted; (b) mock litellm returns invalid type → fallback to rule-based; (c) LLM disabled (no --llm-model) → rule-based only; (d) provenance includes attributed_to with model name
- [X] T036 Lint + run all tests; commit Phase 5

---

## Phase 6: US4 — Docker-Based Code Inspection

**Goal**: Launch containers to introspect code-defined schemas.

- [X] T037 [US4] Create `library/src/undata_library/adapters/docker_scripts/python_inspect.py`: standalone script that imports a Python package, introspects Pydantic/dataclass models, and writes `result.json` (list of ClassifiedEntity JSON) to stdout
- [X] T038 [P] [US4] Create `library/src/undata_library/adapters/docker_scripts/ts_inspect.js`: standalone script that parses TypeScript AST for interfaces/types and writes ClassifiedEntity JSON to stdout
- [X] T039 [US4] [US6] Create `library/src/undata_library/adapters/code_repo.py`: `CodeRepoAdapter(BaseAdapter)` — detect language from pyproject.toml/package.json; build Docker run command; mount repo read-only; copy inspection script; execute with timeout; parse JSON output into list[ClassifiedEntity]; populate `source_ref` with repo URL, committish, file, checksum, and `package_version` from pip/npm; fallback to file-based extraction on failure
- [X] T040 [US4] Update `library/src/undata_library/cli.py`: add `--docker`, `--docker-image IMAGE`, `--docker-timeout SECONDS` flags to `ingest` and `pipeline` commands
- [X] T041 [US4] Write tests in `library/tests/test_code_repo.py`: (a) language detection from pyproject.toml → python; (b) language detection from package.json → typescript; (c) Docker command construction includes correct image, mounts, timeout; (d) JSON output parsing into ClassifiedEntity; (e) timeout/failure → fallback logged
- [X] T042 Lint + run all tests; commit Phase 6

---

## Phase 7: US5 — Workflow + Output Validation

**Goal**: YAML workflow spec + ingestion-report.yaml validation.

- [X] T043 [US5] Create `library/src/undata_library/workflow.py`: `WorkflowSpec` Pydantic model (including docker sub-block); `run_workflow(spec, library_path) -> IngestionReport`; orchestrate: load spec → resolve adapters → run extraction → route entities → validate output → write report; record each step's start_time and end_time in provenance (FR-022)
- [X] T044 [US5] Add `validate_ingestion_output(library_path) -> list[dict]` to `library/src/undata_library/validation.py`: checks — (a) data_type valid on all elements; (b) sha256 matches recomputed hash; (c) no duplicate URIs across elements/schemas/values/valuesets; (d) schema property URIs resolve; (e) response_options ValueConcept URIs resolve; (f) ValueSet member URIs resolve (warn only); (g) every schema has ≥1 property
- [X] T045 [US5] Update `library/src/undata_library/cli.py`: add `--workflow YAML`, `--strict`, `--skip-validation` flags to `ingest`/`pipeline`; add `validate-ingestion` standalone command
- [X] T046 [US5] Update `library/src/undata_library/ingest.py`: after ingestion, run `validate_ingestion_output()` unless `--skip-validation`; write `ingestion-report.yaml`; exit 1 if `--strict` and violations found
- [X] T047 [US5] Write tests in `library/tests/test_workflow.py`: (a) workflow YAML parsed into WorkflowSpec; (b) workflow with classification overrides forces entity type; (c) validation catches wrong data_type; (d) validation catches sha256 mismatch; (e) validation catches duplicate URI; (f) strict mode exits 1 on violation; (g) skip-validation skips checks
- [X] T048 Lint + run all tests; commit Phase 7

---

## Phase 8: US7 — Schema Provenance Alignment

**Goal**: SchemaRecord gets full PROV-O provenance + source_ref + sha256 (FR-031, FR-032).

- [X] T049 [US7] Update schema writing in `library/src/undata_library/ingest.py`: populate `generated_at`, `attributed_to`, `activity`, `source_ref` on SchemaProvenance entries; write sha256 to schema YAML files
- [X] T050 [US7] Update `library/src/undata_library/adapters/bids.py` (and other adapters as needed): emit SchemaRecord ClassifiedEntity with full PROV-O provenance fields + source_ref
- [X] T051 [US7] Write tests in `library/tests/test_schema_provenance.py`: (a) schema YAML has generated_at, attributed_to, activity, source_ref fields; (b) schema YAML has sha256 field; (c) sha256 matches recomputed hash; (d) same schema from two sources has same URI with two provenance entries; (e) source_ref contains repo, committish, file, checksum
- [X] T052 Lint + run all tests; commit Phase 8

---

## Phase 9: Polish + Re-ingest

- [X] T053 Re-ingest all 5 sources with new adapter framework: `undata-library ingest --source bids` (repeat for nwb, dandi, aind, openminds)
- [X] T053b Time the BIDS pipeline run (`undata-library ingest --source bids`); assert < 60 seconds (SC-008)
- [X] T054 [P] Verify 0 misclassification violations: no enum collections (units, modalities) as schemas
- [X] T055 [P] Verify `valuesets/` directory created with correct ValueSetRecord files
- [X] T056 [P] Verify `ingestion-report.yaml` produced with validation passed
- [X] T057 [P] Verify SchemaRecord files have PROV-O provenance + sha256
- [X] T058 Run all library tests: `uv run pytest tests/ -v`
- [X] T059 Lint all code: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- [X] T060 Final commit and push

---

## Dependencies

```
Phase 1 (T001-T003): Setup — no deps
Phase 2 (T004-T013): Models + BaseAdapter — depends on Phase 1
Phase 3 (T014-T025): Adapter refactoring — depends on Phase 2
Phase 4 (T026-T031): Generic adapters — depends on Phase 2 (can parallel with Phase 3)
Phase 5 (T032-T036): LLM — depends on Phase 2
Phase 6 (T037-T042): Docker — depends on Phase 2
Phase 7 (T043-T048): Workflow + validation — depends on Phase 3
Phase 8 (T049-T052): Schema provenance — depends on Phase 3
Phase 9 (T053-T060): Polish — depends on all phases

Parallelizable phases: 3 ‖ 4 ‖ 5 ‖ 6 (all depend only on Phase 2)
```

## Implementation Strategy

1. **Phase 1-2** (T001-T013): Foundation — models, BaseAdapter, classifier. **Suggested MVP.**
2. **Phase 3** (T014-T025): Core refactoring — rewrite 5 adapters, delete extractors/. This is the highest-risk phase.
3. **Phases 4-6** (T026-T042): Can be developed in parallel — generic adapters, LLM, Docker.
4. **Phase 7-8** (T043-T052): Workflow orchestration + schema alignment.
5. **Phase 9** (T053-T060): Full re-ingest, verification, polish.

**Suggested MVP**: Phases 1-3 (T001-T025) — BaseAdapter + 5 refactored adapters + classification rigor. Delivers SC-001 (0 misclassifications).
