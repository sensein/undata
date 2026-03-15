# Feature Specification: undata-library

**Feature Branch**: `015-undata-library`
**Created**: 2026-03-15
**Status**: Draft
**Input**: Standalone library that stores exported elements, mappings, and schemas in
LinkML YAML format with validation and versioning — reusable outside the infrastructure.

---

## Overview

Create a standalone Python package (`undata-library`) that:

1. **Defines a LinkML schema** for storing data elements, mappings, and schemas as flat
   YAML files with embedded version history
2. **Validates** YAML files against the schema using linkml-runtime
3. **Exports** from the backend database to the library format
4. **Imports** from the library format back to the backend
5. **Diffs** element versions to show what changed between versions

The library lives in its own git repository (`sensein/undata-library`) and is added as a
git submodule to the main undata repo at `library/`. This decouples the core schema data
from the infrastructure, enabling reuse by external tools, notebooks, and pipelines.

---

## User Scenarios & Testing

### User Story 1 — Validate Library YAML (Priority: P1)

A contributor edits an element YAML file and wants to verify it conforms to the schema.

**Independent Test**: `uv run undata-library validate elements/` exits 0 when all files
are valid; exits 1 with descriptive errors when a file is malformed.

**Acceptance Scenarios**:

1. **Given** a valid element YAML, **When** `undata-library validate` runs, **Then** it
   reports "valid" with zero violations.
2. **Given** a YAML missing `element.source_local_id`, **When** validated, **Then** it
   reports an ERROR violation with the field path and message.
3. **Given** a YAML with `data_type: "invalid"`, **When** validated, **Then** it reports
   an ERROR for enum violation on `data_type`.
4. **Given** a directory of mixed valid/invalid files, **When** validated with `--strict`,
   **Then** exit code is 1 and all violations are listed.

### User Story 2 — Export from Backend (Priority: P1)

A maintainer wants to snapshot the current backend state into the library.

**Acceptance Scenarios**:

1. **Given** a running backend with elements, **When** `undata-library export --backend-url
   http://localhost:8002 --output ./elements/`, **Then** one YAML file per element is
   created with all version history.
2. **Given** export completes, **When** `undata-library validate elements/` runs, **Then**
   all exported files pass validation.
3. **Given** an element with 3 versions, **When** exported, **Then** the YAML file contains
   3 entries in `versions:` with correct `version_num`, `created_at`, and `created_by`.

### User Story 3 — Import to Backend (Priority: P2)

A contributor wants to load library YAML files into a backend instance.

**Acceptance Scenarios**:

1. **Given** valid element YAML files, **When** `undata-library import --backend-url
   http://localhost:8002 --path elements/`, **Then** elements are created via the API.
2. **Given** an element that already exists (same source_local_id), **When** imported,
   **Then** it is skipped with a warning (no duplicate error).

### User Story 4 — Diff Element Versions (Priority: P2)

A contributor wants to see what changed between element versions.

**Acceptance Scenarios**:

1. **Given** an element with 2 versions, **When** `undata-library diff elements/el.yaml`,
   **Then** output shows which fields changed between v1 and v2.
2. **Given** `--format json`, **When** diff runs, **Then** output is a JSON array of
   `{field, old_value, new_value, breaking}` objects.

### User Story 5 — Build Index (Priority: P3)

A consumer wants a machine-readable registry of all elements and mappings.

**Acceptance Scenarios**:

1. **Given** elements and mappings directories, **When** `undata-library index`, **Then**
   `index.yaml` is created listing all element IDs, names, and current versions.

---

## Requirements

### Functional Requirements

- **FR-001**: `library-schema.linkml.yaml` MUST define `ElementRecord`, `ElementVersion`,
  `MappingRecord`, `MappingVersion`, `SemanticGraph`, `ChangeEntry` classes with proper
  `class_uri` and `slot_uri` anchors.
- **FR-002**: `ElementVersion` MUST include: `version_num`, `name`, `data_type`, `description`,
  `required`, `multivalued`, `constraints`, `semantic_graph`, `created_at`, `created_by`,
  `changelog` (list of `ChangeEntry`).
- **FR-003**: `MappingVersion` MUST include: `version_num`, `function_type`, `expression`,
  `expression_type`, `input_element_ids`, `created_at`, `created_by`.
- **FR-004**: `DataType` enum MUST include: string, integer, float, boolean, array, object.
- **FR-005**: `MappingFunctionType` enum MUST include: identity, unit_conversion, scaling,
  structural, unknown.
- **FR-006**: `MappingStatus` enum MUST include: active, pending_curation.
- **FR-007**: `validate` CLI command MUST validate YAML files against the LinkML schema
  using `linkml-runtime` and report structured violations.
- **FR-008**: `export` CLI command MUST fetch all elements/mappings from backend API and
  write one YAML file per record with all version history.
- **FR-009**: `import` CLI command MUST read YAML files and POST to backend API, skipping
  duplicates.
- **FR-010**: `diff` CLI command MUST compare consecutive versions within an element file.
- **FR-011**: `index` CLI command MUST produce `index.yaml` listing all records.
- **FR-012**: Library MUST be installable via `pip install undata-library` (or `uv add`).
- **FR-013**: Library MUST work as a git submodule in the main undata repo at `library/`.

### Non-Functional Requirements

- **NFR-001**: Validation of 1000 element files MUST complete in under 30 seconds.
- **NFR-002**: No runtime dependency on the backend — validation and diff work offline.
- **NFR-003**: Python 3.12+ compatible (broader than the backend's 3.14 requirement).

### Key Entities

- `library-schema.linkml.yaml` — LinkML meta-schema for the library format
- `src/undata_library/models.py` — Pydantic dataclasses
- `src/undata_library/validation.py` — Schema validation
- `src/undata_library/export.py` — Backend → YAML export
- `src/undata_library/import_lib.py` — YAML → Backend import
- `src/undata_library/diff.py` — Version diff
- `src/undata_library/cli.py` — CLI entry points
- `elements/` — Element YAML files (one per element)
- `mappings/` — Mapping YAML files (one per mapping)
- `index.yaml` — Machine-readable registry

---

## Assumptions

- The backend API is the source of truth; the library is a snapshot/mirror.
- Version history in the library captures the full DataElementVersion chain, not just
  the current version.
- The library repo can be used independently — no dependency on the backend at runtime
  for validation, diff, or browsing.
- Element and mapping YAML files use the element's UUID as the filename
  (`element-{uuid}.yaml`).

---

## Success Criteria

- **SC-001**: `uv run undata-library validate elements/` exits 0 for valid fixtures.
- **SC-002**: `uv run undata-library validate` exits 1 for invalid fixtures with errors.
- **SC-003**: Export from backend produces valid YAML with version history.
- **SC-004**: Import to backend creates elements without errors.
- **SC-005**: Diff shows correct field changes between versions.
- **SC-006**: `pip install undata-library` works from the repo.
- **SC-007**: Library works as git submodule in main undata repo.
