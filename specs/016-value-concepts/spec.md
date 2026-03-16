# Feature Specification: Value Concepts

**Feature Branch**: `016-value-concepts`
**Created**: 2026-03-16
**Status**: Draft
**Input**: Enum/categorical values (sex, species, handedness, modality) should be
content-addressed semantic entities — not bare strings — enabling cross-source
value standardization.

---

## Overview

Extend the undata-library with a fourth entity type: **ValueConcept**. Each unique
categorical value (e.g., "male", "Mus musculus", "right") is a content-addressed
record with an ontology term and provenance showing how each source represents it.

This follows the same identity-vs-provenance pattern as elements and schemas:
- Identity = ontology_term + value_type (hashed)
- Provenance = raw string per source (NOT part of hash)

`Constraints.allowed_values` changes from `list[str]` (bare strings) to
`list[uriorcurie]` (value concept URIs).

---

## User Scenarios & Testing

### User Story 1 — Standardize Categorical Values (Priority: P1)

A harmonization expert wants to know that BIDS "male", AIND "Male", and NWB "M" all
mean the same thing.

**Acceptance Scenarios**:

1. **Given** a value concept file for "male" with ontology_term `PATO:0000384`,
   **When** validated, **Then** it passes with provenance from 3 sources.
2. **Given** BIDS uses `"male"` and NWB uses `"M"`, **When** both are ingested,
   **Then** they produce the same value concept file (same ontology_term hash).
3. **Given** a value with no ontology mapping, **When** ingested, **Then** it uses
   `raw_value` as disambiguator (same fallback as underspecified elements).

### User Story 2 — Link Values to Elements (Priority: P1)

A contributor wants element `sex` to reference standardized value URIs instead of
raw strings in `allowed_values`.

**Acceptance Scenarios**:

1. **Given** element `sex` with `allowed_values: ["male", "female"]`, **When** enriched,
   **Then** `allowed_values` becomes URIs: `[values/male_p8k3n2, values/female_q9l4o3]`.
2. **Given** `undata-library validate elements/sex_*.yaml`, **When** `allowed_values`
   contains value URIs, **Then** validation resolves URIs against `values/` directory.

### User Story 3 — Ingest Value Mappings (Priority: P2)

A maintainer wants to automatically extract enum values from source schemas during
ingestion and create value concept files.

**Acceptance Scenarios**:

1. **Given** AIND JSON Schema with `"enum": ["Male", "Female"]`, **When** ingested,
   **Then** value concept files are created for each enum value.
2. **Given** a value mapping file (`value-mappings.yaml`) that maps raw strings to
   ontology terms, **When** ingestion runs, **Then** values with mappings get
   ontology-based hashes and cross-source values merge.

---

## Requirements

### Functional Requirements

- **FR-001**: `ValueConcept` model MUST follow the identity-vs-provenance pattern:
  semantic (ontology_term, value_type) and provenance (source, raw_value).
- **FR-002**: Value files MUST be stored in `values/` directory with content-addressed
  filenames: `{label}_{6-char-hash}.yaml`.
- **FR-003**: `Constraints.allowed_values` MUST accept both raw strings (backward
  compatible) and value concept URIs.
- **FR-004**: `value-mappings.yaml` MUST map common raw strings to ontology terms for
  automatic enrichment during ingestion.
- **FR-005**: `undata-library ingest` MUST extract enum values from source schemas and
  create value concept files.
- **FR-006**: `undata-library validate` MUST validate value concept files.
- **FR-007**: `hash-registry.yaml` MUST include a `values` section.

### Non-Functional Requirements

- **NFR-001**: Initial mapping table MUST cover at minimum: sex, species, handedness,
  modality (the most common cross-source categorical fields).
- **NFR-002**: Backward compatible — existing elements with string `allowed_values`
  MUST still validate.

### Key Entities

- `values/` — Value concept YAML files (`{label}_{hash}.yaml`)
- `value-mappings.yaml` — Raw string → ontology term mapping table
- `src/undata_library/models.py` — `ValueConcept` model
- `src/undata_library/extractors/*.py` — Updated to extract enum values

### Data Format

```yaml
# values/male_p8k3n2.yaml
semantic:
  ontology_term: http://purl.obolibrary.org/obo/PATO_0000384
  value_type: categorical
  label: male

provenance:
  - source: bids
    raw_value: "male"
  - source: aind
    raw_value: "Male"
  - source: nwb
    raw_value: "M"
```

```yaml
# value-mappings.yaml (curated)
sex:
  male:
    ontology_term: http://purl.obolibrary.org/obo/PATO_0000384
    aliases: ["Male", "M", "m", "MALE"]
  female:
    ontology_term: http://purl.obolibrary.org/obo/PATO_0000383
    aliases: ["Female", "F", "f", "FEMALE"]
species:
  mus_musculus:
    ontology_term: http://purl.obolibrary.org/obo/NCBITaxon_10090
    aliases: ["Mus musculus", "mouse", "Mouse"]
  rattus_norvegicus:
    ontology_term: http://purl.obolibrary.org/obo/NCBITaxon_10116
    aliases: ["Rattus norvegicus", "rat", "Rat"]
```

---

## Success Criteria

- **SC-001**: `undata-library validate values/` exits 0 for valid value files.
- **SC-002**: Cross-source enum values with same ontology term produce one file.
- **SC-003**: `value-mappings.yaml` covers sex, species, handedness, modality.
- **SC-004**: Elements with value URI `allowed_values` pass validation.
