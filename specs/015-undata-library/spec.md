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

## Clarifications

### Session 2026-03-16

- Q: How should undata represent element identity given class scoping and inheritance? → A: RDF property model in LinkML. Element = property URI. Library stores properties + class shapes + subClassOf + equivalentProperty. Use LinkML's native RDF support.
- Q: What should the property URI scheme be? → A: Content-addressed via SHA-256 of the semantic graph. Hash is stored in a mapping table; a 6-char alphanumeric short key is derived. The universal element name is `{attribute}_{6-char-id}` (e.g., `age_x7k2m9`).
- Q: How to handle elements with incomplete semantic graphs? → A: Underspecification is acceptable. Only essential disambiguators (ontology_term, data_type, unit, constraints) form the identity hash. Provenance (name, description, source, class) is stored separately and is NOT part of identity.
- Q: How should class/schema shapes be represented? → A: Separate `schemas/` directory with content-hashed URIs. A schema's identity is its set of property URIs + inheritance chain. Same property set from different sources → same schema hash → automatic equivalence.
- Q: What hash format for URIs? → A: SHA-256 truncated to 6-char alphanumeric key via mapping table. Element filenames and URIs use `{attribute}_{6-char-id}` format. Full SHA-256 stored in `hash-registry.yaml`. Collision check at generation time.

### Design Principles (from clarifications)

**Identity vs Provenance separation**: An element's identity is its semantic graph (what concept, what type, what unit, what constraints). Everything else — name, description, source, class membership — is provenance. Two elements with identical semantic graphs ARE the same element, regardless of source.

**RDF-native model**: Elements are `rdf:Property` instances. Schemas are `sh:NodeShape` instances. Class-property membership is a triple (`sh:property`). Inheritance is `rdfs:subClassOf`. Cross-source equivalence is automatic via content-addressing (same hash = same thing).

**Universal name format**: `{attribute}_{6-char-id}` — human-readable attribute name + unique semantic fingerprint. Parseable: grep `name_*` finds all "name" properties; same suffix = same semantics.

**Three-directory structure**:
- `elements/` — properties (identity = semantic graph hash)
- `schemas/` — class shapes (identity = property set hash)
- `mappings/` — transformations between non-identical properties

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

**Element Identity Model (RDF property semantics)**

- **FR-001**: Each element (property) MUST have a content-addressed URI derived from its
  semantic graph: `https://schema.undata.live/elements/{attribute}_{6-char-id}`.
- **FR-002**: The semantic graph (identity hash input) MUST include ONLY essential
  disambiguators: `ontology_term`, `data_type`, `unit`, `constraints`/`allowed_values`.
- **FR-003**: Provenance (name, description, source, defining_class, required, multivalued)
  MUST be stored separately from identity and MUST NOT affect the content hash.
- **FR-004**: An element file MUST contain one `semantic` block (identity) and one or more
  `provenance` entries (one per source that defines this property).
- **FR-005**: Two elements with identical semantic graphs MUST produce the same content hash
  and be represented as a single element file with multiple provenance entries.

**Schema/Class Model (SHACL shape semantics)**

- **FR-006**: Each schema (class shape) MUST have a content-addressed URI derived from its
  set of property URIs + inheritance chain.
- **FR-007**: Schema files in `schemas/` MUST list property URIs, `subclass_of` references,
  and `mixins` references. Provenance (source name, description) stored separately.
- **FR-008**: Class inheritance (`rdfs:subClassOf`) MUST be tracked — subclasses reference
  parent properties, not duplicate them.

**Hash Registry**

- **FR-009**: `hash-registry.yaml` MUST map each 6-char alphanumeric key to its full
  SHA-256 hash, attribute name, and URI.
- **FR-010**: 6-char keys MUST be checked for collisions at generation time; collisions
  MUST be resolved by extending to 7+ chars.

**Data Format**

- **FR-011**: `DataType` enum MUST include: string, integer, float, boolean, array, object.
- **FR-012**: `MappingFunctionType` enum MUST include: identity, unit_conversion, scaling,
  structural, unknown.

**CLI Commands**

- **FR-013**: `validate` MUST validate YAML files against the LinkML schema and report
  structured violations.
- **FR-014**: `export` MUST fetch elements/mappings/schemas from backend API and write
  content-addressed YAML files with provenance.
- **FR-015**: `import` MUST read YAML files and POST to backend API, skipping duplicates.
- **FR-016**: `diff` MUST compare versions within an element file.
- **FR-017**: `index` MUST produce `index.yaml` listing all records.
- **FR-018**: `hash` (new) MUST compute and display the content hash for a given element
  or schema YAML file.

**Packaging**

- **FR-019**: Library MUST be installable via `pip install undata-library`.
- **FR-020**: Library MUST work as a git submodule in the main undata repo at `library/`.

### Non-Functional Requirements

- **NFR-001**: Validation of 1000 element files MUST complete in under 30 seconds.
- **NFR-002**: No runtime dependency on the backend — validation and diff work offline.
- **NFR-003**: Python 3.12+ compatible (broader than the backend's 3.14 requirement).

### Key Entities

- `library-schema.linkml.yaml` — LinkML meta-schema (RDF property + SHACL shape model)
- `hash-registry.yaml` — 6-char key → SHA-256 → URI mapping table
- `elements/` — Property files: `{attribute}_{6-char-id}.yaml` (identity + provenance)
- `schemas/` — Class shape files: content-addressed (property URIs + inheritance)
- `mappings/` — Transformation files (non-identity mappings between properties)
- `index.yaml` — Machine-readable registry
- `src/undata_library/models.py` — Pydantic dataclasses
- `src/undata_library/hashing.py` — Content-addressed hash + 6-char key generation
- `src/undata_library/validation.py` — Schema validation
- `src/undata_library/export.py` — Backend → content-addressed YAML export
- `src/undata_library/import_lib.py` — YAML → Backend import
- `src/undata_library/diff.py` — Version diff
- `src/undata_library/cli.py` — CLI entry points

---

## Assumptions

- The library is a **canonical, source-independent property registry**. The backend is one
  consumer; external tools, notebooks, and pipelines can use the library directly.
- Element identity is determined by semantic content (ontology_term, data_type, unit,
  constraints), NOT by source name, class, or description.
- Underspecification is acceptable — elements without ontology_term have partial identity
  that may merge with other elements when enriched later.
- The library repo can be used independently — no dependency on the backend at runtime.
- Element filenames use `{attribute}_{6-char-id}.yaml` format.
- Schema filenames use content-addressed hashes.
- Inspired by reproschema's content-addressed item model and RDF property semantics.

---

## Success Criteria

- **SC-001**: `uv run undata-library validate elements/` exits 0 for valid fixtures.
- **SC-002**: `uv run undata-library validate` exits 1 for invalid fixtures with errors.
- **SC-003**: Export from backend produces valid YAML with version history.
- **SC-004**: Import to backend creates elements without errors.
- **SC-005**: Diff shows correct field changes between versions.
- **SC-006**: `pip install undata-library` works from the repo.
- **SC-007**: Library works as git submodule in main undata repo.
