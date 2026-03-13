# Feature Specification: Dual-Path Schema Adapters

**Feature Branch**: `006-dual-path-adapters`
**Created**: 2026-03-10
**Status**: Draft
**Input**: "dandi is not the only code inspection adapter. i would say all github repos are
even if they have schemas. in fact dandi-schema releases are at
https://github.com/dandi/schema/tree/master/releases. so each of these sources should have
both code inspection (varies by repo) and json/jsonld/turtle schema pathways."

---

## Context

The current ingestion system (001-neuro-schema-integration) assigns a **single**
`extraction_path` per adapter:
- BIDS → `"yaml"` (bidsschematools YAML parsing)
- DANDI → `"code"` (dandischema Pydantic introspection)
- NWB → `"yaml"` (hdmf YAML GroupSpec)
- openMINDS → `"jsonld"` (JSON-LD file parsing)
- AIND → `"json"` (pre-exported JSON Schema fixtures)

This is architecturally incomplete. Every adapter's source publishes **both** a Python
library AND schema files (JSON / JSON-LD / YAML / Turtle). The goal of this feature is
to give each adapter a dual-path architecture — the caller decides whether to use the
code-inspection path, the schema-file path, or both.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — File-based extraction for version-pinned reproducibility (Priority: P1)

A data curator wants to ingest the DANDI schema at a **specific released version** (e.g.,
v0.6.7), not just the version installed via pip. They invoke the DANDI adapter with a
file-path pointing to the GitHub release JSON Schema files and receive the same normalized
elements they would from the code path, tagged with the explicit schema version.

**Why this priority**: Version-pinned ingestion is essential for provenance — knowing
*which version* of a schema a dataset was validated against. The current code-only path
cannot pin to a specific published schema version.

**Independent Test**: Given a local directory or URL containing a DANDI schema release,
a user can call `DANDIAdapter.load_file(path)` and receive the same structure of
`NormalizedElement` objects as `DANDIAdapter.load_code()`, with `version_info` reporting
the file-based version tag.

**Acceptance Scenarios**:

1. **Given** a path to a DANDI schema release directory (JSON files), **When** a user
   calls `ingest dandi --extraction-mode file --source-path ./releases/0.6.7/`, **Then**
   the adapter parses the JSON Schema files and returns `NormalizedElement` objects
   with `source_local_id` matching those from the code path.

2. **Given** the BIDS schema GitHub repository (or local clone), **When** a user calls
   `ingest bids --extraction-mode file --source-path ./bids-spec/src/schema/`, **Then**
   the BIDS adapter parses the YAML objects directory and returns all metadata fields,
   without needing bidsschematools installed.

3. **Given** the NWB schema YAML files, **When** a user calls
   `ingest nwb --extraction-mode file --source-path ./nwb-schema/core/`, **Then** the
   NWB adapter parses GroupSpec YAML and returns `NormalizedElement` objects equivalent
   to the code-introspection path.

4. **Given** openMINDS JSON-LD schema files, **When** a user calls
   `ingest openminds --extraction-mode file --source-path ./openminds-schema/`, **Then**
   the openMINDS adapter parses the JSON-LD files and returns elements equivalent to
   those from openminds-python introspection.

5. **Given** AIND JSON Schema files (either bundled fixtures or aind-data-schema
   releases), **When** a user calls `ingest aind --extraction-mode file --source-path
   ./aind-schemas/`, **Then** the AIND adapter parses the JSON Schema files as before.

---

### User Story 2 — Code-introspection path for all adapters (Priority: P2)

A developer wants to use the Python library code-inspection path for BIDS (via
bidsschematools), NWB (via hdmf), and openMINDS (via openminds-python) — mirroring
how DANDI currently works. Each adapter can enumerate its schema types directly from the
installed library without needing local schema files.

**Why this priority**: The code path is self-updating with library upgrades and avoids
file management. It completes the architectural symmetry across all five adapters.

**Independent Test**: Given only the adapter's Python library installed (`bidsschematools`,
`hdmf`, `openminds-python`, `aind-data-schema` or `dandischema`), calling
`adapter.load_code()` + `adapter.extract_elements()` returns a complete element list
without requiring any local schema files.

**Acceptance Scenarios**:

1. **Given** `bidsschematools` installed, **When** a user calls `BIDSAdapter.load_code()`,
   **Then** the adapter uses `bidsschematools.schema.load_schema()` and returns all
   metadata fields with `extraction_path="code"`.

2. **Given** `hdmf` + `pynwb` installed, **When** a user calls `NWBAdapter.load_code()`,
   **Then** the adapter enumerates NWB neurodata types from the loaded namespace registry
   with `extraction_path="code"`.

3. **Given** `openminds-python` installed, **When** a user calls
   `OpenMINDSAdapter.load_code()`, **Then** the adapter introspects openminds module
   types and returns elements with `extraction_path="code"`.

4. **Given** `aind-data-schema` installed (Python 3.12 compat layer or future 3.14
   support), **When** a user calls `AINDAdapter.load_code()`, **Then** the adapter
   introspects Pydantic models exactly as the DANDI adapter does.

---

### User Story 3 — Dual-path merge with deduplication (Priority: P3)

A pipeline operator wants to use **both** extraction paths for a single adapter run and
receive a merged, deduplicated element list annotated with which path sourced each
element. This enables cross-validation: the code path and file path should agree on
`source_local_id` and `data_type`.

**Why this priority**: Running both paths provides a quality gate — discrepancies between
code and file outputs signal schema evolution or adapter bugs.

**Independent Test**: Given both paths available, calling `adapter.extract_both()` returns
a merged element list where elements present in only one path are flagged, and elements
present in both are deduplicated by `source_local_id`.

**Acceptance Scenarios**:

1. **Given** both `dandischema` installed and a DANDI release directory, **When** the
   DANDI adapter runs in `--extraction-mode both`, **Then** the result lists all elements
   from both paths, with `extraction_path` field containing `"code"`, `"file"`, or
   `"both"` (deduped).

2. **Given** elements that exist in both code and file paths with compatible types,
   **When** the merge is run, **Then** the `source_local_id` is deduplicated and the
   element is tagged `extraction_path="both"`.

3. **Given** elements that exist only in the code path (e.g., a field added in a library
   update not yet reflected in the release file), **When** the merge is run, **Then**
   the element is tagged `extraction_path="code"` and a `WARN` log is emitted.

4. **Given** elements that exist only in the file path (e.g., deprecated fields still
   in the release schema), **When** the merge is run, **Then** the element is tagged
   `extraction_path="file"` and a `WARN` log is emitted.

---

### Edge Cases

- **Library not installed**: If `load_code()` is called but the required library is not
  installed, the adapter MUST raise `ImportError` with a clear message naming the missing
  package; it MUST NOT silently fall back to the file path (silent fallback obscures intent).
- **File path not provided**: If `load_file()` is called without a path, the adapter MUST
  raise `ValueError` with a clear message; it MUST NOT attempt to fetch from the internet
  without explicit URL configuration. **Exception**: `AINDAdapter` has a well-known default
  fixture location bundled with the package; calling `load_file("")` on AIND uses this
  default and MUST NOT raise `ValueError`. All other adapters (BIDS, NWB, openMINDS, DANDI)
  MUST raise `ValueError` on an empty path.
- **Version mismatch between paths**: When running in `both` mode, if a `source_local_id`
  appears in both paths with **incompatible types**, it MUST be logged as `ERROR` and
  both versions preserved with disambiguating suffixes (`id.code` / `id.file`).
- **Turtle/RDF sources**: Some sources (openMINDS, QUDT) publish schemas as Turtle (`.ttl`)
  or N-Triples. The file-path extractor MUST support rdflib parsing for these formats.

---

## Requirements *(mandatory)*

### Functional Requirements

**Dual-path adapter protocol**

- **FR-001**: Every adapter MUST expose `load_code()` (library introspection) and
  `load_file(path_or_url: str)` methods alongside the existing `load(path_or_url)`.
- **FR-002**: The `extraction_mode` parameter (`"code"` | `"file"` | `"both"`) MUST
  be passable to the CLI `ingest` command and IngestionPipeline.
- **FR-003**: `SchemaClassPayload.extraction_path` MUST be updated from a fixed
  per-adapter constant to a per-element value reflecting the actual extraction source.
- **FR-004**: The `SchemaAdapter` Protocol MUST be versioned upward to include
  `load_code()`, `load_file()`, and `extract_classes(mode)` signatures.

**Per-adapter file-path support**

- **FR-005**: `DANDIAdapter.load_file()` MUST parse the JSON Schema files from
  https://github.com/dandi/schema releases. Each release contains versioned JSON Schema
  documents; the adapter MUST handle `$defs` resolution identically to the Pydantic
  code-path output.
- **FR-006**: `BIDSAdapter.load_file()` MUST parse the BIDS YAML schema directory
  structure (objects/metadata.yaml, objects/entities.yaml, etc.) without requiring
  bidsschematools installed.
- **FR-007**: `NWBAdapter.load_file()` MUST parse NWB GroupSpec YAML files from a local
  directory or URL (e.g., nwb-schema GitHub raw content).
- **FR-008**: `OpenMINDSAdapter.load_file()` MUST parse JSON-LD schema template files
  (`.schema.omi.json`, single file or directory glob). Turtle (`.ttl`) format is
  supported via a separate `load_turtle(path)` method, not via `load_file()` (see
  plan.md AD-005 for rationale; this keeps `load_file()` format-predictable).
- **FR-009**: `AINDAdapter.load_file()` MUST continue reading JSON Schema files as
  currently implemented. `AINDAdapter.load_code()` is gated on `aind-data-schema`
  being importable via the bridge venv; if unavailable it MUST raise `ImportError`
  (see FR-013).

**Per-adapter code-path support**

- **FR-010**: `BIDSAdapter.load_code()` MUST call `bidsschematools.schema.load_schema()`
  and enumerate all metadata fields, tagging them `extraction_path="code"`.
- **FR-011**: `NWBAdapter.load_code()` MUST enumerate NWB neurodata types from the hdmf
  namespace registry (pynwb loads the NWB core namespace at import time).
- **FR-012**: `OpenMINDSAdapter.load_code()` MUST introspect openminds-python module
  classes to enumerate schema types.
- **FR-013**: `AINDAdapter.load_code()` MUST introspect `aind-data-schema` Pydantic
  models; if the package is unavailable it MUST raise `ImportError`.
- **FR-014**: `DANDIAdapter.load_code()` remains the existing Pydantic introspection path.

**Merge & deduplication**

- **FR-015**: `extract_elements(mode="both")` MUST merge code-path and file-path results,
  deduplicating by `source_local_id`. The winner is configurable; default is `"code"`.
- **FR-016**: Elements unique to one path MUST be emitted with a `WARN` log entry
  identifying the element and which path it was exclusive to.
- **FR-017**: Type conflicts (same `source_local_id`, different `data_type`) MUST be
  logged as `ERROR` and both preserved with disambiguated `source_local_id`.

**CLI**

- **FR-018**: The `undata ingest` CLI MUST accept `--extraction-mode [code|file|both]`
  (default: `"code"` for backward compatibility).
- **FR-019**: When `--extraction-mode file` is chosen, `--source-path` MUST be required
  unless the adapter has a well-known default file location. The following adapters have
  defined defaults and MAY omit `--source-path`: `aind` (bundled JSON Schema fixtures
  shipped with `aind-data-schema`). All other adapters (bids, nwb, openminds, dandi)
  MUST receive an explicit `--source-path`.

### Key Entities (updated)

- **ExtractionMode**: `Literal["code", "file", "both"]` — selects which extraction
  path(s) an adapter uses.
- **ExtractedElement**: Extended `NormalizedElement` with `extraction_path: str` field
  (value: `"code"`, `"file"`, or `"both"` after merge).
- **SchemaClassPayload** (updated): `extraction_path` is now per-element, not a
  per-adapter constant.
- **AdapterResult**: New dataclass wrapping `list[NormalizedElement]` plus metadata
  about which extraction mode was used and any conflicts detected.

---

## Assumptions

- `bidsschematools.schema.load_schema()` returns the full BIDS schema object regardless
  of path — the code path doesn't require a local checkout.
- `hdmf` / `pynwb` register the NWB core namespace at import time via
  `pynwb.load_namespaces()`; iterating `pynwb.get_type_map().get_container_classes()`
  or similar gives access to all registered NWB types.
- openminds-python exposes a module-level enumeration of all schema classes that can be
  introspected without reading JSON-LD files directly.
- DANDI JSON Schema releases (https://github.com/dandi/schema/releases) use standard
  JSON Schema draft vocabulary with `$defs` for shared definitions.
- `aind-data-schema` will remain Python-3.12-only for the foreseeable future; its
  code-introspection path MUST gracefully degrade when Python 3.14 is used.
- The `extraction_path` values used in `SchemaClassPayload` (and stored via the backend
  schema class API) remain informational — the backend does not enforce or validate them.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five adapters pass `extract_elements(mode="file")` tests using their
  respective fixture formats (JSON, YAML, JSON-LD) with 0% element loss vs. baseline.
- **SC-002**: All five adapters pass `extract_elements(mode="code")` tests; AIND
  code-path returns a clear `ImportError` on Python 3.14 (graceful degradation).
- **SC-003**: Running `extract_elements(mode="both")` on all five adapters returns ≥ 95%
  overlap between code-path and file-path element sets (by `source_local_id`). DANDI and
  BIDS are the primary validation targets; NWB, openMINDS, and AIND MUST also pass both-mode
  overlap tests (tasks T042–T044).
- **SC-004**: Conflict detection logs `ERROR` entries for every type-mismatched element
  in the both-mode merge; zero silent conflicts.
- **SC-005**: `undata ingest dandi --extraction-mode file --source-path <path>` completes
  successfully and produces valid IngestionResult with `elements_succeeded > 0`.
- **SC-006**: All existing 68 ingestion element-extraction tests continue to pass after
  adapter refactoring without modification (they call `load()` which is preserved as a
  shim). Class-extraction test assertion values in `test_adapter_class_extraction.py` are
  separately updated by task T035 to reflect the `extraction_path` semantics change
  (`"file"` replaces format-specific values like `"yaml"`/`"json"`/`"jsonld"`); these
  updates are expected and do not constitute behavioral regressions.
