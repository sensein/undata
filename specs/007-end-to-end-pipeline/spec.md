# Feature Specification: End-to-End Schema Ingestion and LinkML Export

**Feature Branch**: `007-end-to-end-pipeline`
**Created**: 2026-03-11
**Status**: Draft
**Input**: "Using a local install import all schemas and data elements from the sources in the plan into a clean database and then export it out as linkml schemas with inheritance and mixins"

---

## Context

The five neuroscience data standards (BIDS, DANDI, NWB, openMINDS, AIND) each contain
far more schema data than the minimal unit-test fixtures currently bundled with the
ingestion package. The real schema sizes are:

| Source | Real Schema Size | Code-path Library | Python 3.14? |
|--------|----------------|-------------------|--------------|
| BIDS | 1,012 vocabulary entries (metadata 449, columns 101, entities 35, suffixes 118, enums 218, formats 18, datatypes 16, extensions 44, files 13); 22 modality-based classes from `rules/sidecars/` | `bidsschematools` | ✅ installed |
| DANDI | 728 fields across 4 release files (122 top-level + 606 in `$defs`); 43 Pydantic models via code-path; 2 models silently dropped by `$ref` recursion bug | `dandischema` | ✅ installed |
| NWB | 80 neurodata_type_def entries (13 YAML files) | `pynwb` + `hdmf` | needs pynwb install |
| openMINDS | 292 `.schema.omi.json` schemas (across core, controlledTerms, SANDS, ephys, etc.) | `openMINDS` PyPI | likely ✅ (>=3.9) |
| AIND | 9 Pydantic model files in `core/` (5 covered by bundled fixtures, 4 new: metadata, model, processing, quality_control) | `aind-data-schema` | ❌ pyo3-ffi block |

This feature delivers: (1) full ingestion of all five real schemas into a clean
database; (2) an extended LinkML generator that emits schema inheritance (`is_a`)
and mixin composition; (3) a reproducible one-command pipeline runbook.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Full Schema Ingestion from Real Sources (Priority: P1)

A schema engineer wants to populate a fresh undata database with the complete real
schema data from all five neuroscience data standards. They run the ingestion pipeline
and confirm all five sources appear in the backend with realistic element counts
(hundreds per source, not just the handful in the test fixtures).

**Why this priority**: A fully-populated database is the prerequisite for meaningful
LinkML export. The test fixtures are intentionally minimal; this story delivers real
data.

**Independent Test**: Run `undata ingest bids dandi nwb openminds aind` against a
live backend; confirm `GET /api/v1/elements?limit=1` returns `total ≥ 1000` and all
five sources appear in `GET /api/v1/sources`.

**Acceptance Scenarios**:

1. **Given** a clean database (migrations applied, ProvenanceMixin seeded),
   **When** `undata ingest bids --extraction-mode code` runs, **Then** BIDS source
   has ≥ 900 elements (full vocabulary: metadata, columns, entities, suffixes,
   enums, formats, datatypes, extensions, files — all 1,012 vocabulary objects)
   and ≥ 20 classes reflecting modality-based sidecar groups from `rules/sidecars/`.

2. **Given** a clean database, **When** `undata ingest dandi --extraction-mode code`
   runs, **Then** DANDI source has ≥ 370 elements (all 43 Pydantic models including
   self-referencing models previously silently dropped). **When** `--extraction-mode
   file` is used with the DANDI 0.7.0 release files, **Then** ≥ 200 unique elements
   are extracted from `$defs` entity definitions (Participant, BioSample, Organization,
   Person, Resource, etc.) in addition to top-level properties.

3. **Given** a clean database, **When** `undata ingest nwb --extraction-mode code`
   runs with pynwb installed, **Then** NWB source has ≥ 200 elements (80+ neurodata
   types × multiple fields each).

4. **Given** a clean database and the openMINDS repo cloned (or openMINDS package
   installed), **When** `undata ingest openminds --extraction-mode file
   --source-path ./schemas/openminds/` (or `--extraction-mode code`) runs, **Then**
   openMINDS source has ≥ 500 elements (from 292 `.schema.omi.json` files across
   all modules: core, controlledTerms, SANDS, computation, publications, ephys, etc.).

5. **Given** a clean database, **When** `undata ingest aind --extraction-mode file`
   runs with extended AIND fixtures (all 10 core schema files), **Then** AIND source
   has ≥ 100 elements.

6. **Given** all five sources ingested, **When** `GET /api/v1/elements?limit=1` is
   called, **Then** `total ≥ 1000` across all sources.

---

### User Story 2 — LinkML Export with Inheritance and Mixins (Priority: P2)

A data architect wants to export the unified neuroscience schema from the populated
backend as a valid LinkML YAML that captures: per-source class hierarchy (`is_a`),
DynamicSchema inheritance chains (from `parent_id`), the ProvenanceMixin as a proper
LinkML mixin class (`mixin: true`), and all schema-level mixin compositions
(`mixins: [...]`). The exported file is valid according to `linkml-validate`.

**Why this priority**: The LinkML export is the primary shareable artefact. Without
inheritance and mixin information, the schema is a flat list of fields with no
structural relationships.

**Independent Test**: Run `undata generate-schema --output unified.yaml`; run
`linkml-validate --schema unified.yaml`; inspect YAML to confirm `mixin: true`,
`is_a:`, and `mixins: [...]` are present for the appropriate classes.

**Acceptance Scenarios**:

1. **Given** a populated backend with 5 sources, **When** `undata generate-schema`
   runs, **Then** the output YAML contains one class per source
   (`BIDSDataset`, `DANDIDataset`, `NWBFile`, `openMINDSDataset`, `AINDDataset`)
   each with `is_a: NeuroscienceDataset`.

2. **Given** the ProvenanceMixin system schema is seeded in the backend, **When**
   the generator runs, **Then** the YAML contains a `ProvenanceMixin` class with
   `mixin: true` and all ProvenanceMixin element slots.

3. **Given** a DynamicSchema with attached ProvenanceMixin, **When** the generator
   runs, **Then** the corresponding LinkML class contains `mixins: [ProvenanceMixin]`.

4. **Given** a DynamicSchema with `parent_id` set, **When** the generator runs,
   **Then** the corresponding LinkML class contains `is_a: <ParentSchemaName>`.

5. **Given** the generator output YAML, **When** `linkml-validate` runs, **Then**
   it exits with code 0 and reports zero errors.

6. **Given** per-source class hierarchies stored in `SchemaClassInheritance`
   (e.g., `openMINDSSubject is_a openMINDSDataset`), **When** the generator runs,
   **Then** those `is_a` relationships appear in the YAML class definitions.

---

### User Story 3 — Reproducible Pipeline Runbook (Priority: P3)

A new contributor or CI operator wants to go from a fresh checkout to a fully-
populated, exported, and validated LinkML schema in one command. The runbook handles:
starting the backend, installing missing libraries, downloading full schema fixtures,
ingesting all five sources, generating the schema, and validating the output.

**Why this priority**: Reproducibility ensures this pipeline can be re-run after schema
library updates and forms the basis for future CI integration.

**Independent Test**: On a machine with Docker, uv, git, and curl, run `make pipeline`
from the repo root. Confirm exit code 0 and `unified.yaml` contains all five source
classes and the ProvenanceMixin mixin.

**Acceptance Scenarios**:

1. **Given** a fresh checkout with Docker running, **When** `make pipeline` runs,
   **Then** all steps complete without manual intervention and exit code is 0.

2. **Given** the pipeline has already run, **When** it is re-run, **Then** it handles
   409 Duplicate Source errors gracefully and exits 0 (idempotent).

3. **Given** the pipeline completes, **When** `unified.yaml` is inspected, **Then**
   it contains all five source classes, `NeuroscienceDataset` base class,
   `ProvenanceMixin` mixin class, and ≥ 100 slots.

---

### Edge Cases

- **NWB pynwb absent**: `undata ingest nwb --extraction-mode code` raises ImportError
  with a clear message; runbook MUST provide an alternative file-path command using
  downloaded NWB YAML files.
- **openMINDS absent**: If the openMINDS package is not installed and no file path
  is provided, `load_code()` raises ImportError and `load_file("")` raises ValueError;
  the runbook MUST install the package or clone the repo.
- **AIND Python 3.14 block**: `load_code()` always fails with ImportError on Python
  3.14; `load_file("")` uses bundled fixtures. Extended fixture download MUST be
  available via a script.
- **Duplicate source on re-run**: The ingestion pipeline MUST handle 409 from the
  backend gracefully — log WARN and skip the source rather than aborting.
- **Empty schema export**: If the database has no DynamicSchemas with mixins or
  inheritance, the generator MUST still produce a valid (if minimal) LinkML YAML.
- **NWB multi-file namespace**: The NWB schema distributes types across 13 YAML files
  linked via `nwb.namespace.yaml`. The adapter MUST traverse the namespace manifest
  to load all domain files rather than expecting a single flat YAML.

---

## Requirements *(mandatory)*

### Functional Requirements

**Dependencies and Setup**

- **FR-001**: `pynwb` MUST be added to `ingestion/pyproject.toml` dependencies so
  `NWBAdapter.load_code()` works without a separate install step.
- **FR-002**: `openMINDS` (PyPI package name `openMINDS`, import `openminds`) MUST
  be added to `ingestion/pyproject.toml` dependencies so `OpenMINDSAdapter.load_code()`
  works. If it does not install on Python 3.14, a bridge venv approach MUST be
  documented and the runbook MUST use `--extraction-mode file` with the cloned repo.
- **FR-003**: A download/setup script (`ingestion/scripts/fetch-schemas.sh`) MUST:
  - Clone or sparse-checkout the openMINDS GitHub repo to `ingestion/schemas/openminds/`
    to obtain all 292 `.schema.omi.json` files
  - Download the 13 NWB core YAML files from the nwb-schema GitHub repo to
    `ingestion/schemas/nwb/`
  - Download the extended AIND JSON Schema files (all 10 core modules) to
    `ingestion/schemas/aind/`
  - Download the DANDI schema release files (latest version) to `ingestion/schemas/dandi/`
  - Be idempotent (skip if already downloaded)

**BIDSAdapter Enhancement**

- **FR-017**: `BIDSAdapter.load_code()` MUST load ALL vocabulary object types from
  `bidsschematools`, not just `schema.objects.metadata`. The full vocabulary includes:
  `metadata` (449), `columns` (101), `entities` (35), `suffixes` (118), `enums` (218),
  `formats` (18), `datatypes` (16), `extensions` (44), `files` (13) — totaling 1,012
  entries. Each entry type MUST be tagged with a `vocabulary_type` annotation in
  `raw_metadata` to distinguish metadata fields from column/entity/suffix definitions.
- **FR-018**: `BIDSAdapter.extract_classes()` MUST produce modality-based class
  groupings by reading `schema.rules.sidecars` from bidsschematools. Each sidecar
  YAML group (e.g., `MRIHardwareFields`, `EEGHardwareFields`, `PETFields`) becomes
  one `SchemaClassPayload` with its member fields as `element_source_local_ids`.
  The broken `_` name-split heuristic MUST be replaced.

**DANDIAdapter Enhancement**

- **FR-019**: `DANDIAdapter.load_file()` MUST extract elements from `$defs` in each
  JSON Schema release file in addition to top-level `properties`. Each `$defs` entry
  that has a `properties` dict MUST produce its own `SchemaClassPayload` (nested entity
  type) with its properties as elements. Top-level `$defs` entries represent entity
  types: `Participant`, `BioSample`, `Organization`, `Person`, `Resource`, etc.
- **FR-020**: `DANDIAdapter.load_code()` MUST handle Pydantic v2 self-referencing
  models (`BioSample`, `PropertyValue`) that return 0 properties from
  `model_json_schema()` by falling back to `model.model_fields` for field introspection.

**NWBAdapter Enhancement**

- **FR-004**: `NWBAdapter.load_file(path_or_url)` MUST be enhanced to handle the
  NWB multi-file namespace structure: when given a directory, it MUST detect
  `*.namespace.yaml` and load all referenced domain YAML files; when given a direct
  URL to `nwb.namespace.yaml`, it MUST fetch and traverse all referenced files.
- **FR-005**: `NWBAdapter.extract_classes()` MUST emit one `SchemaClassPayload` per
  `neurodata_type_def` entry, using `neurodata_type_inc` as the `parent_class_name`
  to preserve the NWB type hierarchy.

**Ingestion Pipeline**

- **FR-006**: The ingestion pipeline MUST handle `DuplicateSourceError` (409 from
  backend) gracefully: log WARN and continue rather than aborting the entire run.
- **FR-007**: All five sources MUST be ingested in a single `undata ingest bids dandi
  nwb openminds aind` invocation with appropriate `--extraction-mode` per source;
  OR separate per-source invocations are acceptable in the runbook.

**LinkML Generator Enhancement**

- **FR-008**: `LinkMLSchemaGenerator.generate()` MUST fetch DynamicSchema records from
  `GET /schemas` and include their inheritance structure in the output YAML.
- **FR-009**: Schemas with `is_mixin=True` MUST appear as LinkML classes with
  `mixin: true`.
- **FR-010**: Schemas with attached mixin schemas (from the
  `GET /schemas/{id}/inheritance-tree` edges of type `"mixin"`) MUST include
  `mixins: [<MixinName>, ...]` in their LinkML class, ordered by mixin position.
- **FR-011**: Schemas with `parent_id` MUST include `is_a: <ParentSchemaName>` in
  their LinkML class.
- **FR-012**: Per-source subclasses (`BIDSDataset`, `DANDIDataset`, etc.) with
  `is_a: NeuroscienceDataset` MUST continue to be emitted (existing behavior
  preserved).
- **FR-013**: Slots already inherited via a mixin MUST NOT be duplicated on classes
  that use the mixin (deduplication by slot name post-MRO resolution, using
  `GET /schemas/{id}/resolved` response).
- **FR-014**: The output YAML MUST be valid according to `linkml-validate` with zero
  errors.

**Runbook**

- **FR-015**: A `Makefile` at the repo root or `ingestion/Makefile` MUST define
  targets: `setup` (start backend + run migrations), `fetch-schemas` (download full
  fixtures), `ingest` (run all five adapters), `generate` (run generate-schema),
  `validate` (run linkml-validate), and `pipeline` (all steps in order).
- **FR-016**: The Makefile MUST document which targets require Docker, which require
  the backend to be running, and which are pure Python.

### Key Entities (new/extended)

- **DynamicSchemaNode**: Internal generator representation of a DynamicSchema fetched
  from the backend — holds `id`, `name`, `parent_id`, `is_mixin`, and ordered
  `mixin_ids` list; used to build the LinkML class hierarchy in one pass.
- **NWBNamespaceManifest**: Internal NWBAdapter representation of `nwb.namespace.yaml`
  containing the list of per-domain YAML file paths to load.

---

## Assumptions

- `pynwb` and `openMINDS` support Python 3.14 (both require `>=3.9`); if either fails
  to install, the runbook falls back to `--extraction-mode file` with downloaded files.
- `aind-data-schema` remains Python 3.12-only; all AIND ingestion uses
  `--extraction-mode file` with downloaded fixture files.
- The backend is reachable at `http://localhost:8002/api/v1` (or `UNDATA_BACKEND_URL`).
- The ProvenanceMixin system schema is seeded by migration 0009.
- The backend 409 on duplicate source names is the expected behaviour for idempotent
  re-runs; the pipeline does not need to delete and recreate sources.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `GET /api/v1/elements?limit=1` returns `total ≥ 2500` after full
  pipeline run (BIDS ≥ 900 + DANDI ≥ 370 + NWB ≥ 200 + openMINDS ≥ 500 + AIND ≥ 100).
- **SC-002**: Per-source element counts: BIDS ≥ 900 (full vocabulary), DANDI ≥ 370
  (all 43 models), NWB ≥ 200, openMINDS ≥ 500, AIND ≥ 100.
- **SC-003**: `undata generate-schema --output unified.yaml` completes in < 60s.
- **SC-004**: `linkml-validate --schema unified.yaml` exits with code 0.
- **SC-005**: `unified.yaml` contains `mixin: true` for at least one class and
  `is_a: NeuroscienceDataset` for all five source classes.
- **SC-006**: `make pipeline` exits 0 on first run and on re-run (idempotent).
- **SC-007**: All 132 existing ingestion unit tests continue to pass after
  adapter and generator changes (`uv run pytest tests/ -q`).
