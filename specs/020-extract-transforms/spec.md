# Feature Specification: Extract & Transform Pipeline

**Feature Branch**: `020-extract-transforms`
**Created**: 2026-03-20
**Status**: Draft
**Input**: Re-extract all outputs using the new adapter framework (019) and ensure transforms are created between overlapping data elements. Transforms should be represented as functions. Outputs should contain data elements, schemas, valuesets, transforms, and an ontology inverse map.

## User Scenarios & Testing

### User Story 1 — Complete Re-extraction with New Adapter Framework (Priority: P1)

A data curator runs the full ingestion pipeline for all 5 sources using the new adapter framework (019) and receives a complete library output containing: elements, schemas, valuesets, values, transforms, and an ontology inverse map. The output is validated and the curator can verify the registry is complete.

**Why this priority**: The 019 adapter framework is in place but the library hasn't been re-extracted with it. The existing element/schema/value files use the old extractor output. Re-extraction is the prerequisite for all other work.

**Independent Test**: Run `undata-library pipeline --source bids` (and each other source) and verify elements/, schemas/, valuesets/, transforms/, and ontology-index.yaml are all populated.

**Acceptance Scenarios**:

1. **Given** the new adapter framework is installed, **When** all 5 sources are ingested, **Then** the library contains elements, schemas, valuesets (new), values, transforms, and ontology-index.yaml.
2. **Given** re-extraction completes, **When** `validate-ingestion` runs, **Then** 0 violations are reported: all sha256 match, no duplicate URIs, all schemas have properties, all entity types are correct.
3. **Given** the old library output exists, **When** re-extraction runs, **Then** old files are replaced (content-addressed: same semantic = same file updated with merged provenance).

---

### User Story 2 — Transform Generation Between Overlapping Elements (Priority: P1)

When two data elements represent the same concept but differ in type, unit, or representation (e.g., BIDS `age` as float/years vs NWB `age` as string/ISO8601), the system automatically generates a transform record that describes the function to convert between them. Transforms are bidirectional and represented as callable function specifications.

**Why this priority**: Transforms are the core value proposition of undata — without them, cross-source data migration is manual. They enable automated data conversion pipelines.

**Independent Test**: After ingesting BIDS and NWB, verify that a transform exists between BIDS `age` (float/years) and NWB `age` (string/ISO8601) with a function specification describing the conversion.

**Acceptance Scenarios**:

1. **Given** two elements share the same ontology_term but differ in data_type or unit, **When** transforms are generated, **Then** a bidirectional transform pair is created linking the two element URIs with a function specification.
2. **Given** two elements share the same name and class but no ontology_term, **When** the enrichment pipeline has assigned ontology_terms, **Then** transforms are generated based on the shared ontology alignment.
3. **Given** a transform between element A (integer/years) and element B (string/ISO8601), **When** the transform is read, **Then** it contains: source_element, target_element, function_type, a function expression (e.g., `str(timedelta(days=value*365))` or a named converter), parameter types, and provenance.
4. **Given** two elements with identical semantic hash, **When** transforms are generated, **Then** no transform is created (they are the same element — identity, not conversion).

---

### User Story 3 — Transform Function Model (Priority: P1)

Transforms are represented as function specifications with typed inputs and outputs, not just labels. Each transform describes what function converts source data to target data, enabling downstream consumers to execute or validate the conversion.

**Why this priority**: The current MappingRecord has `expression` as a free-text string and `function_type` as a coarse enum. This is insufficient for automated migration. Transforms need typed, structured function definitions.

**Independent Test**: Read a transform YAML file and verify it contains a function specification with input type, output type, function body or reference, and parameter descriptions.

**Acceptance Scenarios**:

1. **Given** a unit conversion transform (years → months), **When** read, **Then** it contains: `function_type: unit_conversion`, `input_type: float`, `output_type: float`, `expression: value * 12`, `expression_type: arithmetic`.
2. **Given** a type conversion transform (float → ISO8601 string), **When** read, **Then** it contains: `function_type: type_conversion`, `input_type: float`, `output_type: string`, `expression: iso8601_duration_from_years`, `expression_type: named_function`.
3. **Given** a structural transform (flat field → nested PropertyValue), **When** read, **Then** it contains: `function_type: structural`, `expression_type: template`, and a template describing the structural mapping.
4. **Given** an identity mapping (same type, same unit, different source name), **When** read, **Then** it contains: `function_type: identity`, no expression needed.

---

### User Story 4 — Ontology Inverse Map (Priority: P2)

After extraction, the system produces an ontology inverse map: a lookup from ontology term URI to all elements, schemas, and valuesets that reference it. This enables discovery of all entities related to a concept across all sources.

**Why this priority**: The ontology-index already exists (built by `ontology-index` CLI command). This story formalizes it as a standard pipeline output and extends it to include schemas and valuesets, not just elements.

**Independent Test**: Run the pipeline and verify `ontology-index.yaml` contains entries for schemas and valuesets in addition to elements.

**Acceptance Scenarios**:

1. **Given** elements, schemas, and valuesets with ontology_term fields, **When** the ontology index is built, **Then** each ontology term maps to all entity types (elements, schemas, valuesets) that reference it.
2. **Given** the pipeline runs, **When** complete, **Then** `ontology-index.yaml` is automatically produced as a standard output alongside elements/, schemas/, transforms/, and valuesets/.

---

### Edge Cases

- What happens when two elements share ontology_term but have incompatible types (e.g., boolean vs array)? No transform is generated; a warning is logged.
- What happens when an element has no ontology_term? No cross-source transform is generated for that element (transforms require shared semantic identity or ontology alignment).
- What happens when a transform expression references a named function that doesn't exist? Validation warns; the transform is still stored as a specification (the function is a reference, not executable code).
- What happens when re-extraction changes an element's hash? New element is created (content-addressed); old element retained; transforms pointing to the old URI are preserved; new transforms generated for the new URI.

## Requirements

### Functional Requirements

**Re-extraction**

- **FR-001**: The system MUST re-extract all 5 sources (BIDS, NWB, DANDI, openMINDS, AIND) using the 019 adapter framework, producing a complete set of elements, schemas, valuesets, values, transforms, and ontology-index.yaml.
- **FR-002**: Re-extraction MUST use the content-addressed identity model: same semantic = same file; provenance entries are merged for cross-source elements.
- **FR-003**: The pipeline output directories MUST include: `elements/`, `schemas/`, `values/`, `valuesets/`, `transforms/`, plus `ontology-index.yaml`, `hash-registry.yaml`, and `ingestion-report.yaml`.

**Transform Generation**

- **FR-004**: After ingestion + enrichment, the system MUST automatically generate transforms between elements that share an ontology_term but differ in data_type, unit, or structural representation.
- **FR-005**: Transforms MUST be bidirectional: if A→B exists, B→A MUST also be generated.
- **FR-006**: Transforms MUST NOT be generated between elements with identical semantic hash (same element = identity, handled by content-addressing).
- **FR-007**: Transform generation MUST be a distinct pipeline step: `ingest → enrich → align → transform → validate`.
- **FR-008**: Each transform MUST be stored as a content-addressed YAML file in `transforms/` with its own sha256.

**Transform Function Model**

- **FR-009**: Each transform MUST include a typed function specification: `input_type` (data_type of source element), `output_type` (data_type of target element), `function_type` (identity, unit_conversion, type_conversion, scaling, structural, value_mapping, unknown), `expression` (function body, formula, named function reference, or template), and `expression_type` (arithmetic, named_function, template, lookup_table, none).
- **FR-010**: The `MappingFunctionType` enum MUST be extended with `type_conversion` and `value_mapping` variants.
- **FR-011**: Transform provenance MUST include `generated_at`, `attributed_to`, `activity: transform`, and `source_ref` for both source and target elements.
- **FR-012**: Common transform patterns MUST be auto-detected: years↔months (unit_conversion, `value * 12`), float↔string ISO8601 (type_conversion, `iso8601_duration_from_years`), enum value mapping (value_mapping, lookup table).

**Ontology Inverse Map**

- **FR-013**: `ontology-index.yaml` MUST index all entity types: elements, schemas, and valuesets (not just elements as currently).
- **FR-014**: Each ontology term entry MUST include: term URI, list of referencing entities with their URI, entity type, file path, and source list.
- **FR-015**: The ontology index MUST be regenerated as a standard step in the pipeline (after transform generation).

**Pipeline Integration**

- **FR-016**: The `pipeline` CLI command MUST be extended to include the `transform` step: `ingest → enrich → align → transform → validate`.
- **FR-017**: A standalone `undata-library transform [PATH]` CLI command MUST generate transforms from existing library output without re-ingesting.
- **FR-018**: The `validate-ingestion` command MUST verify transforms: source/target element URIs resolve, function_type is valid, expression is present for non-identity transforms.

### Key Entities

- **TransformRecord** (replaces/extends MappingRecord): Content-addressed transform with typed function specification, bidirectional, sha256, provenance with source_ref.
- **FunctionSpec**: Typed function definition within a transform — input_type, output_type, expression, expression_type, parameters.
- **OntologyIndexEntry**: Extended to include entity_type (element/schema/valueset) alongside URI, file, and sources.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Re-extraction of all 5 sources produces a complete library with 0 validation violations.
- **SC-002**: Every pair of elements sharing an ontology_term with different data_type/unit has a bidirectional transform pair.
- **SC-003**: Transforms for known conversions (age years↔months, float↔ISO8601) contain correct, typed function specifications — not just "unknown" function_type.
- **SC-004**: `ontology-index.yaml` includes entries for schemas and valuesets, not just elements.
- **SC-005**: Full pipeline (ingest + enrich + align + transform + validate) for all 5 sources completes in under 5 minutes.
- **SC-006**: `undata-library transform` can be run standalone on existing library output and produces correct transforms without re-ingestion.

### Assumptions

- The 019 adapter framework is complete and produces ClassifiedEntity output for all 5 sources.
- Transform expressions are specifications (not executable code) — they describe the conversion but are not eval'd at ingestion time.
- Named function references (e.g., `iso8601_duration_from_years`) point to a registry of known conversion functions that downstream consumers implement.
- The transform directory uses content-addressed filenames: `{source_name}_{target_name}_{12-hex-key}.yaml`.
