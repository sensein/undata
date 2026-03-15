# Tasks: undata-library

**Feature**: `015-undata-library` | **Branch**: `015-undata-library`
**Input**: Design documents from `/specs/015-undata-library/`

**User Stories**:
- US1 P1 — Validate library YAML
- US2 P1 — Export from backend
- US3 P2 — Import to backend
- US4 P2 — Diff element versions
- US5 P3 — Build index

---

## Phase 1: Scaffold + LinkML Schema + Models

- [X] T001 Create `library/` directory at repo root; init with `pyproject.toml` (name: undata-library, requires-python >=3.12, deps: linkml-runtime>=1.8, pydantic>=2.0, pyyaml, httpx, click); add `src/undata_library/__init__.py`
- [X] T002 [P] Create `library/library-schema.linkml.yaml`: LinkML schema with ElementRecord, ElementMetadata, ElementVersion, SemanticGraph, ChangeEntry, MappingRecord, MappingMetadata, MappingVersion classes + DataType, MappingFunctionType, MappingStatus enums; validate with `gen-doc`
- [X] T003 [P] Create `library/src/undata_library/models.py`: Pydantic v2 dataclasses matching LinkML schema (ElementRecord, ElementVersion, MappingRecord, MappingVersion, SemanticGraph, ChangeEntry)
- [X] T004 [P] Create test fixtures in `library/tests/fixtures/`: valid-element.yaml, invalid-element-missing-field.yaml, invalid-element-bad-enum.yaml, valid-mapping.yaml, multi-version-element.yaml
- [X] T005 Create `library/elements/.gitkeep`, `library/mappings/.gitkeep`, `library/schemas/.gitkeep`
- [X] T006 Commit Phase 1

## Phase 2: Validation + CLI (US1)

- [X] T007 Write tests in `library/tests/test_validation.py`: valid fixture passes, missing-field fixture fails with ERROR, bad-enum fixture fails, directory scan finds all violations
- [X] T008 Create `library/src/undata_library/validation.py`: load YAML, validate against Pydantic models, return ValidationReport with violations list
- [X] T009 Create `library/src/undata_library/cli.py`: Click group with `validate` subcommand; exit 0 on valid, exit 1 on violations
- [X] T010 Add `[project.scripts] undata-library = "undata_library.cli:main"` to pyproject.toml
- [X] T011 Run tests; verify `uv run undata-library validate tests/fixtures/valid-element.yaml` exits 0
- [X] T012 Commit Phase 2

## Phase 3: Export (US2)

- [X] T013 Write tests in `library/tests/test_export.py`: mock httpx responses, verify exported YAML matches ElementRecord schema, multi-version element has all versions
- [X] T014 Create `library/src/undata_library/export.py`: fetch elements from backend API (paginated), convert to ElementRecord, write YAML per element; fetch mappings similarly
- [X] T015 Add `export` subcommand to CLI: `--backend-url`, `--output`, `--token` options
- [X] T016 Run tests; commit Phase 3

## Phase 4: Import (US3)

- [X] T017 Write tests in `library/tests/test_import.py`: mock httpx POST, verify element creation call, verify duplicate skip on 409
- [X] T018 Create `library/src/undata_library/import_lib.py`: read YAML files, POST to backend API, skip on 409 DuplicateElementError
- [X] T019 Add `import` subcommand to CLI: `--backend-url`, `--path`, `--token` options
- [X] T020 Run tests; commit Phase 4

## Phase 5: Diff (US4)

- [X] T021 Write tests in `library/tests/test_diff.py`: two-version element shows changed fields, unchanged fields omitted, `--format json` produces valid JSON
- [X] T022 Create `library/src/undata_library/diff.py`: load ElementRecord, compare consecutive versions, return list of FieldDiff
- [X] T023 Add `diff` subcommand to CLI: FILE arg, `--from`, `--to`, `--format text|json`
- [X] T024 Run tests; commit Phase 5

## Phase 6: Index (US5)

- [X] T025 Write tests in `library/tests/test_index.py`: scan elements/ and mappings/, produce index.yaml with correct counts
- [X] T026 Create `library/src/undata_library/index.py`: walk directories, extract id+name+current_version from each YAML, write index.yaml
- [X] T027 Add `index` subcommand to CLI: `--output` option
- [X] T028 Run tests; commit Phase 6

## Phase 7: Integration + Polish

- [X] T029 Add `library/` as git submodule placeholder (document in README how to init standalone repo)
- [X] T030 Run full test suite; verify all tests pass
- [X] T031 Update CLAUDE.md via update-agent-context script
- [X] T032 Final commit and push

---

## Dependencies

T001 → T002, T003, T004, T005 (parallel) → T006
T007 → T008 → T009 → T010 → T011 → T012
T013 → T014 → T015 → T016
T017 → T018 → T019 → T020
T021 → T022 → T023 → T024
T025 → T026 → T027 → T028
T029, T030 → T031 → T032
