# Feature Specification: Unit Standardization with QUDT

**Feature Branch**: `033-unit-standardization`
**Created**: 2026-03-28
**Status**: Draft
**Input**: Standardize unit handling across the pipeline — resolve raw unit strings to canonical QUDT URIs, validate with cmixf, normalize before hashing, and generate transforms using QUDT conversion factors.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — QUDT Unit Resolution (Priority: P1)

As a data engineer, I need raw unit strings (e.g., "kg", "years", "mV") resolved to canonical QUDT URIs so I can programmatically determine that two elements with different unit spellings refer to the same physical quantity.

**Why this priority**: Without canonical unit URIs, the system cannot determine that `kg` and `kilogram` refer to the same unit, or that `years` and `yr` are equivalent. This breaks deduplication and transform generation.

**Independent Test**: Call the unit resolver with "kg" — it returns `qudt:KiloGM` with the QUDT URI. Call with "years" — returns `qudt:YR`.

**Acceptance Scenarios**:

1. **Given** a raw unit string "kg", **When** the resolver processes it, **Then** it returns the canonical QUDT URI (`http://qudt.org/vocab/unit/KiloGM`), the standard label ("Kilogram"), and the QUDT dimension.
2. **Given** a variant spelling "kilogram", **When** the resolver processes it, **Then** it returns the same QUDT URI as "kg".
3. **Given** an unrecognized unit string "wobbles", **When** the resolver processes it, **Then** it marks the unit as unresolved and generates a curation flag.
4. **Given** a unit-less element (unit is None), **When** the resolver processes it, **Then** it is skipped without error.

---

### User Story 2 — Unit Normalization Before Hashing (Priority: P1)

As a library maintainer, I need units normalized to their canonical form before the content hash is computed so that `age(unit="years")` and `age(unit="yr")` produce the same identity hash.

**Why this priority**: Currently these produce different hashes and create duplicate entities. Normalization before hashing is essential for correct cross-source deduplication.

**Independent Test**: Two elements identical except one has `unit: "years"` and the other `unit: "yr"` — after normalization, they produce the same content hash.

**Acceptance Scenarios**:

1. **Given** two elements differing only in unit spelling ("kg" vs "kilogram"), **When** both are committed, **Then** they resolve to a single entity with merged provenance.
2. **Given** an element with a resolved QUDT URI, **When** the hash is computed, **Then** the canonical QUDT symbol (not the raw string) is used in the hash input.
3. **Given** an element with an unresolved unit, **When** the hash is computed, **Then** the raw unit string is used as fallback (preserving current behavior).

---

### User Story 3 — Adapter Unit Extraction (Priority: P1)

As a library maintainer, I need all source adapters to extract unit information when it's available in the source schema, so the registry captures unit data from all ecosystems.

**Why this priority**: Currently only BIDS extracts units. NWB, DANDI, openMINDS, and AIND have unit information in their schemas that is being ignored.

**Independent Test**: Run extraction from NWB — elements that have units in the source schema have `unit` populated.

**Acceptance Scenarios**:

1. **Given** the BIDS source, **When** extraction runs, **Then** elements with defined units (e.g., age→years, weight→kg) have `unit` populated (current behavior, preserved).
2. **Given** the NWB source, **When** extraction runs, **Then** elements with `quantity` or `dtype` that imply units have `unit` populated.
3. **Given** any source adapter, **When** it produces a LinkML SchemaDefinition, **Then** slot annotations for units are preserved and extracted by the standard extractor.

---

### User Story 4 — QUDT-Based Transform Generation (Priority: P2)

As a data engineer, I need transforms between elements with compatible units to include QUDT-derived conversion factors so I can automate unit conversion in data pipelines.

**Why this priority**: The current 8 hardcoded conversions are incomplete. QUDT contains thousands of unit relationships with precise conversion factors. P2 because the resolution (P1) must work first.

**Independent Test**: Elements `age_years` and `age_months` generate a transform with `factor: 12.0` sourced from QUDT, not the hardcoded table.

**Acceptance Scenarios**:

1. **Given** two elements with compatible QUDT units (years and months), **When** transforms are generated, **Then** the transform includes a conversion factor from QUDT.
2. **Given** two elements with the same QUDT dimension but no known conversion, **When** transforms are generated, **Then** the transform is flagged as `needs_review`.
3. **Given** the QUDT vocabulary, **When** conversion factors are looked up, **Then** at least 50 unit pairs have computable conversion factors.

---

### User Story 5 — Unit Validation with cmixf (Priority: P2)

As a curator, I need unit strings validated against the cmixf grammar so typos and non-standard unit expressions are caught early.

**Why this priority**: cmixf validates unit symbol syntax (e.g., "kg" is valid, "kgs" is not). P2 because QUDT resolution handles most cases; cmixf adds an extra validation layer.

**Independent Test**: Validate "kg/m^2" — passes. Validate "kgs per meter" — fails with descriptive error.

**Acceptance Scenarios**:

1. **Given** a valid cmixf expression "kg", **When** validated, **Then** it passes with `cmixf_valid: true`.
2. **Given** an invalid expression "kgs", **When** validated, **Then** it fails with `cmixf_valid: false` and an error message.
3. **Given** a compound expression "kg/m^2", **When** validated, **Then** it passes and resolves to `qudt:KiloGM-PER-M2`.

---

### Edge Cases

- What happens when the QUDT vocabulary cannot be loaded? Unit resolution is skipped; raw strings are used as fallback. A warning is logged.
- What happens when a unit maps to multiple QUDT entries? The most specific match is chosen (e.g., "meter" → qudt:M, not qudt:M_Length).
- What happens when the same element is extracted from two sources with different unit spellings? After normalization they resolve to the same QUDT URI and merge at commit.
- What happens when an adapter returns a unit not in QUDT? The raw string is preserved and a curation flag is generated.
- What happens when a field has `allowed_units: ["kg", "lb", "g"]`? Three separate elements are created, each with one unit, linked by unit_conversion transforms.
- What happens when a schema has `age` (float) + `age_unit` (enum: years/months/days)? The pair is recognized; transforms are generated linking `age_in_years`, `age_in_months`, `age_in_days` to the generic `T(age, age_unit)`.
- What happens when a string field contains "120 mmHg"? A curation flag is generated with type `unit_encoded_string` suggesting decomposition into numeric value + unit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST resolve raw unit strings to canonical QUDT URIs using the bundled QUDT vocabulary.
- **FR-002**: System MUST support common unit aliases (e.g., "kg" = "kilogram" = "KG" all resolve to the same QUDT URI).
- **FR-003**: Unresolvable units MUST be flagged as curation items with flag type `unresolved_unit`.
- **FR-004**: Unit normalization MUST occur before content hash computation so equivalent units produce identical hashes.
- **FR-005**: All source adapters MUST extract unit information when available in the source schema.
- **FR-006**: Transform generation MUST use QUDT conversion factors when available instead of hardcoded tables.
- **FR-007**: Unit validation with cmixf MUST be available as an optional validation step.
- **FR-008**: The QUDT vocabulary MUST be loadable from the bundled TTL file without external network access.
- **FR-009**: Resolved QUDT URIs MUST be stored in the entity's semantic block as `unit_uri` alongside the raw `unit` string.
- **FR-010**: The system MUST work correctly when QUDT is unavailable — falling back to raw unit strings.
- **FR-011**: When an element has no explicit `unit` field but its description mentions a unit (e.g., "Age in years"), the system MUST use LLM to extract the unit and resolve it via QUDT.
- **FR-012**: When a source schema allows multiple units for the same field (e.g., `allowed_units: ["kg", "lb"]`), the system MUST create one element per unit variant, each with its own content hash, linked by unit_conversion transforms.
- **FR-013**: When a source schema has paired value+unit fields (e.g., `age` + `age_unit`), the system MUST recognize the pair as a single semantic concept with runtime unit selection. A transform MUST be generated: `age_in_{unit} = T(age, age_unit)` linking the generic pair to each unit-specific variant.
- **FR-014**: String values with embedded units (e.g., `"5.2 kg"`) MUST generate a curation flag suggesting decomposition into a numeric value + canonical unit element.

### Key Entities

- **UnitResolver**: Service that maps raw unit strings to QUDT URIs. Loads from bundled TTL file.
- **SemanticIdentity.unit**: Raw unit string from source (unchanged).
- **SemanticIdentity.unit_uri**: NEW — canonical QUDT URI (e.g., `http://qudt.org/vocab/unit/KiloGM`).
- **CurationFlag(unresolved_unit)**: NEW flag type for units that cannot be resolved.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The unit resolver correctly maps at least 50 common neuroscience unit strings to QUDT URIs.
- **SC-002**: Elements with equivalent units ("kg" vs "kilogram") produce the same content hash after normalization.
- **SC-003**: All 5 source adapters extract units when available in the source schema.
- **SC-004**: Transform generation uses QUDT conversion factors for at least 20 unit pairs (replacing hardcoded 8).
- **SC-005**: All existing library tests (400+) continue to pass.
- **SC-006**: Unresolvable units generate curation flags.

## Scope Boundaries

### In Scope

- QUDT unit resolution from bundled TTL vocabulary
- Unit alias table (common spellings → QUDT URIs)
- Unit normalization integrated into enrichment pipeline
- Hash computation using normalized units
- Adapter updates to extract units from all sources
- QUDT-based transform generation
- cmixf validation (optional)
- `unit_uri` field on SemanticIdentity
- `unresolved_unit` curation flag type

### Out of Scope

- Custom unit definition by users
- Dimensional analysis (checking unit compatibility beyond QUDT)
- Unit conversion execution (only factor generation, not runtime conversion)
- Backend/frontend changes (this is library-only)

## Clarifications

### Session 2026-03-28

- Q: Should QUDT be a separate resolver or integrated into the existing ontology service? → A: Load QUDT into the existing OntologyStore (pyoxigraph) as another ontology alongside NCIT, PATO, etc. Reuse the same search_terms/lookup_term patterns. Unit resolution is ontology enrichment for the `unit` field, following the same approach as entity ontology enrichment.
- Q: Should LLM extract units from descriptions when no explicit unit field is set? → A: Yes — use LLM to extract units from descriptions when `unit` field is empty. Add as an enrichment step after QUDT symbol resolution. Reuses existing LLM infrastructure (litellm/ollama).
- Q: How should multi-unit elements and unit-encoded strings be handled? → A: One element per unit variant (split). `age(kg)` and `age(lb)` are separate elements linked by unit_conversion transforms. String-encoded values flagged for decomposition. Also: schemas with paired fields (age, age_unit) should generate transforms: `age_in_years = T(age, age_unit)` — recognizing that the pair represents a single semantic concept with runtime unit selection.

## Assumptions

- The QUDT TTL file at `backend/data/qudt/VOCAB_QUDT-UNITS-ALL.ttl` is the authoritative vocabulary
- QUDT loads into the existing OntologyStore (pyoxigraph) alongside other ontologies
- The enrichment pipeline's existing pattern (embedding similarity + lookup) is reused for unit resolution
- cmixf 0.2.x is available for symbol validation
- Unit strings from sources are typically simple symbols ("kg", "mV", "years") not complex expressions
- The `unit_uri` field is new and will not conflict with existing data

## Dependencies

- Feature 028 (storage abstraction) — enrichment pipeline accepts StorageBackend
- QUDT TTL vocabulary file (already in repo)
- pyoxigraph (already in library dependencies — used by OntologyStore)
- cmixf 0.2.x (needs to be added back to library dependencies)
