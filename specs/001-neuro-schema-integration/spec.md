# Feature Specification: Neuroscience Schema Integration System

**Feature Branch**: `001-neuro-schema-integration`
**Created**: 2026-03-07
**Status**: Draft
**Input**: User description: "create a system that can integrate different neuroscience schemas
(BIDS, DANDI, openMINDS, NWB). preference to generate a LinkML schema to represent this
neuroscience information space. tools that map data elements (linkml slots) as functions
of the form dataelement_y = function(dataelement_a, dataelement_b, ..., other_parameters).
where two data elements only differ in name an identity function should be used and such
aliases should be noted. specifications for approaching this problem including ingestion
and validation."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Schema Ingestion and Exploration (Priority: P1)

A neuroscience data curator needs to understand what data elements exist across BIDS,
DANDI, openMINDS, and NWB schemas without having to read each schema's native format
separately. They load all four schemas into the system and receive a normalized,
browsable inventory of every data element — its name, type, description, allowed values,
and which source schema it came from.

**Why this priority**: All downstream capabilities (LinkML generation, mapping, validation)
depend on having a consistent, normalized view of source schema content. This is the
foundational data acquisition step.

**Independent Test**: Given access to the four schema sources, a user can invoke the
ingestion workflow and receive a unified inventory listing every data element with its
provenance. No other system component is required.

**Acceptance Scenarios**:

1. **Given** the BIDS schema repository, **When** a user runs schema ingestion for BIDS,
   **Then** all BIDS data elements (fields, objects, enumerations) are loaded, normalized,
   and stored with their full metadata (name, type, description, constraints, source version).

2. **Given** the DANDI schema, **When** a user runs ingestion for DANDI, **Then** all
   DANDI data elements are extracted and represented as normalized data elements with
   their types and validation rules preserved.

3. **Given** the openMINDS schema, **When** a user runs ingestion for openMINDS, **Then**
   all openMINDS type properties are extracted as normalized data elements with their
   linked-data context preserved.

4. **Given** the NWB schema, **When** a user runs ingestion for NWB, **Then** all NWB
   neurodata types and their attributes/datasets are extracted as normalized data elements.

5. **Given** all four schemas have been ingested, **When** a user queries the inventory,
   **Then** results can be filtered by source schema, data type, or keyword, and each
   element includes its source provenance.

6. **Given** a source schema is updated to a new version, **When** the user re-runs
   ingestion, **Then** the system detects changed, added, and removed elements and updates
   the inventory without discarding provenance of the previous version.

---

### User Story 2 — Unified LinkML Schema Generation (Priority: P2)

A tool developer needs a single authoritative LinkML schema that represents the full
neuroscience information space covered by BIDS, DANDI, openMINDS, and NWB. They invoke
the schema generation workflow and receive a valid, self-consistent LinkML schema where
every source data element is represented as a slot (or class), with cross-schema
relationships captured.

**Why this priority**: The LinkML schema is the canonical artifact that enables
interoperability tooling, documentation generation, and downstream validation. It must
exist before mapping and validation features can be fully exercised.

**Independent Test**: The generated LinkML schema can be validated by the official LinkML
toolchain (linter, schema loader) independently of the mapping or validation subsystems.

**Acceptance Scenarios**:

1. **Given** a fully ingested schema inventory, **When** a user generates the unified
   LinkML schema, **Then** the output is a valid LinkML YAML document that passes the
   official LinkML schema validator without errors.

2. **Given** the unified LinkML schema, **When** a user inspects any data element, **Then**
   it is represented as a LinkML slot with: name, range (type), description, multivalued
   flag, required flag, and a `source` annotation recording the originating schema(s).

3. **Given** a data element that appears in multiple source schemas, **When** the LinkML
   schema is generated, **Then** the element is deduplicated and its slot definition
   lists all source schemas in its provenance annotation.

4. **Given** enumeration types in any source schema, **When** the LinkML schema is
   generated, **Then** the allowed values are represented as LinkML permissible values
   within an enum definition.

5. **Given** the generated LinkML schema, **When** a user exports it, **Then** it is
   available as both a YAML file and as a machine-readable JSON-LD context.

---

### User Story 3 — Data Element Mapping Functions (Priority: P3) *(Identity alias detection in scope; non-identity transformation execution deferred to 004-migration-api)*

A data integration engineer needs to transform data records from one neuroscience schema
into another (e.g., BIDS → DANDI). They use the mapping function registry to declare
transformations of the form `dataelement_y = f(dataelement_a, dataelement_b, ..., params)`,
apply those functions to a record, and receive a transformed record conforming to the
target schema.

**Why this priority**: Mapping functions are the operational core of schema integration.
They operationalize the relationships discovered during ingestion and encode domain
knowledge about how elements correspond.

**Independent Test**: Given two data elements and a defined mapping function, applying
the function to input values produces correct output values independently of ingestion
or validation subsystems.

**Acceptance Scenarios**:

1. **Given** two data elements from different schemas, **When** a user registers a mapping
   function of the form `target_element = f(source_element_a, source_element_b, params)`,
   **Then** the function is stored in the mapping registry linked to its input and output
   slot definitions in the unified LinkML schema.

2. **Given** a registered mapping function, **When** the user applies it to a source data
   record, **Then** the target data element is produced with the correct value, and the
   transformation is recorded in a provenance log.

3. **Given** two data elements that differ only in name (identical type, description, and
   allowed values), **When** the system analyzes the schema inventory, **Then** an identity
   mapping function `dataelement_y = identity(dataelement_a)` is automatically generated
   and the pair is recorded as an alias in the alias registry.

4. **Given** the alias registry, **When** a user queries it, **Then** each alias group
   lists all equivalent element names, their source schemas, and references the identity
   mapping function.

5. **Given** a source data record, **When** a user applies a full mapping chain from
   schema A to schema B, **Then** all mappable elements are transformed and a report
   identifies unmapped elements (those with no registered function).

6. **Given** a mapping function that requires additional parameters beyond source elements,
   **When** the function is invoked, **Then** those parameters must be explicitly supplied
   or have documented defaults; missing required parameters result in a clear error.

---

### User Story 4 — Schema Validation (Priority: P4)

A researcher wants to verify that a neuroscience dataset (e.g., a DANDI metadata record
or a BIDS dataset description) conforms to the unified schema. They submit the dataset
to the validation service and receive a structured report identifying conformance issues,
missing required fields, type violations, and constraint failures.

**Why this priority**: Validation is the quality-assurance layer that makes the unified
schema actionable for data producers. It depends on the LinkML schema and mapping layer
being in place.

**Independent Test**: Given a known-valid data record and the unified LinkML schema, the
validator returns a pass result. Given a known-invalid record, it returns a structured
error report identifying each violation.

**Acceptance Scenarios**:

1. **Given** a data record in any supported source schema format, **When** a user submits
   it for validation against the unified schema, **Then** the system returns a structured
   report with: overall pass/fail status, list of violations with field names and
   descriptions, and a severity level (error/warning/info) for each.

2. **Given** a data record missing a required field, **When** validated, **Then** the
   report includes a violation of severity ERROR identifying the missing field name and
   the requirement source.

3. **Given** a data record with a value outside the allowed enumeration, **When** validated,
   **Then** the report lists the field name, the invalid value, and the set of permitted
   values.

4. **Given** a data record that is fully conformant, **When** validated, **Then** the
   report returns overall status PASS with zero ERROR-level violations.

5. **Given** a validation report, **When** exported, **Then** it is available in both
   human-readable text and machine-readable JSON formats.

---

### Edge Cases

- What happens when a source schema is unavailable (network failure, missing file)
  during ingestion? The system MUST report the failure clearly and continue ingesting
  available schemas without silent data loss.
- How does the system handle data elements with the same name but incompatible types
  across schemas (name collision, semantic conflict)? These MUST be flagged as conflicts
  in the inventory and NOT silently merged; resolution requires explicit user action.
- What happens when a mapping function produces an output value outside the allowed
  range of the target element's constraints? The mapping result MUST fail validation
  and the violation MUST be traceable back to the specific function.
- How does the system handle circular mapping dependencies (A → B → A)? Cycles MUST
  be detected at registration time and rejected with a clear error.
- What happens when a source schema has no stable versioning? The system MUST record
  the ingestion timestamp and content hash as a surrogate version.

---

## Requirements *(mandatory)*

### Functional Requirements

**Ingestion**

- **FR-001**: System MUST ingest schema definitions from BIDS (YAML-based), DANDI
  (JSON Schema/JSON), openMINDS (JSON-LD), and NWB (YAML-based) source formats.
- **FR-002**: System MUST extract and normalize data elements from each source, capturing:
  name, data type, description, cardinality, allowed values, and source provenance.
- **FR-003**: System MUST support ingestion from local filesystem paths and from versioned
  remote repositories (via URL or git reference).
  > **Scope (001)**: Local filesystem paths only. Remote URL / git reference fetch is
  > deferred to a future feature increment.
- **FR-004**: System MUST detect and record schema version information for each source;
  where no explicit version exists, content hash and ingestion timestamp MUST be recorded.
- **FR-005**: System MUST detect changes between ingestion runs (added, modified, removed
  elements) and produce a diff report.
  > **Scope (001)**: Deferred. The backend already records provenance per ingestion run;
  > CLI-level diff reporting is deferred to a future increment. SC-007 is similarly deferred.

**LinkML Schema Generation**

- **FR-006**: System MUST generate a unified LinkML schema (YAML) from the normalized
  inventory that is valid according to the official LinkML specification.
- **FR-007**: Every data element MUST be represented as a LinkML slot with name, range,
  description, multivalued, required, and a `source` annotation listing originating schemas.
- **FR-008**: Data elements appearing in multiple schemas MUST be deduplicated; the merged
  slot MUST reference all source schemas in its provenance.
- **FR-009**: Enumeration types MUST be represented as LinkML enum definitions with
  permissible values.
- **FR-010**: The generated schema MUST export as both YAML and JSON-LD.

**Mapping Functions**

- **FR-011**: System MUST provide a mapping registry where users can register functions
  of the form `target_slot = f(source_slot_a, source_slot_b, ..., params)`.
  > **Scope (001)**: Deferred to `004-migration-api`. This feature implements identity
  > mapping detection only (FR-013, FR-014).
- **FR-012**: Each registered mapping function MUST be linked to slot definitions in the
  unified LinkML schema for both inputs and outputs.
  > **Scope (001)**: Deferred to `004-migration-api`.
- **FR-013**: System MUST automatically detect alias pairs (elements differing only in
  name with equivalent type, description, and constraints) and register identity mappings.
- **FR-014**: All alias relationships MUST be recorded in a queryable alias registry with
  source schema provenance.
- **FR-015**: System MUST support applying a registered mapping function to a data record
  and returning the transformed output with a provenance trace.
  > **Scope (001)**: Deferred to `004-migration-api`.
- **FR-016**: System MUST detect and reject circular mapping dependencies at registration
  time.
  > **Scope (001)**: Deferred to `004-migration-api`. Backend (002) enforces cycle detection
  > at the storage layer.
- **FR-017**: System MUST report unmapped elements when applying a full schema-to-schema
  transformation.
  > **Scope (001)**: Deferred to `004-migration-api`.

**Validation**

- **FR-018**: System MUST validate data records against the unified LinkML schema and
  return a structured report.
- **FR-019**: Validation reports MUST include: overall status (PASS/FAIL), per-violation
  details (field name, violation type, severity, description), and export in JSON and
  human-readable text.
- **FR-020**: System MUST distinguish violation severities: ERROR (schema non-conformance),
  WARNING (best-practice deviation), INFO (informational annotation).
- **FR-021**: Validation MUST check: required field presence, data type conformance,
  enumeration membership, cardinality constraints.

### Key Entities

- **SchemaSource**: A versioned neuroscience schema origin (BIDS, DANDI, openMINDS, NWB),
  with format, version/hash, and ingestion timestamp.
- **DataElement**: A normalized representation of a single data field extracted from a
  source schema. Attributes: name, data type, description, cardinality, allowed values,
  source provenance list.
- **UnifiedSlot**: A LinkML slot definition in the generated unified schema, derived from
  one or more DataElements. Carries full provenance.
- **AliasGroup**: A set of DataElements across schemas that are semantically equivalent
  (identical except for name), linked by an identity mapping function.
- **MappingFunction**: A declared transformation `target = f(inputs..., params)` linking
  source and target UnifiedSlots. Includes function signature, parameter schema, and
  a reference implementation or expression. *(Non-identity functions deferred to 004-migration-api.)*
- **MappingRegistry**: The queryable store of all registered MappingFunctions and
  AliasGroups. *(Implemented by 002-schema-backend via `/api/v1/mappings`; this feature
  is a client of that API.)*
- **ValidationReport**: The output of a validation run — overall status, list of
  Violations, export formats.
- **Violation**: A single conformance failure with field reference, violation type,
  severity, and human-readable description.

---

## Assumptions

- Source schemas are publicly accessible and their licenses permit programmatic
  ingestion for integration purposes.
- "Two data elements differ only in name" is operationally defined as: same normalized
  data type, same cardinality, same set of allowed values (if enumerated), and a
  semantic similarity score above a configurable threshold on their descriptions.
  The threshold and similarity method are configuration parameters.
- Mapping functions are declared by users or generated automatically (identity case);
  the system does not automatically infer non-trivial transformation logic.
- The unified schema targets LinkML 1.x. Compatibility with earlier LinkML versions
  is not required.
- Data records submitted for validation are provided in JSON or YAML format.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All data elements from the four source schemas are represented in the
  unified inventory after a single ingestion run (0% silent data loss).
- **SC-002**: The generated LinkML schema passes the official LinkML validator with
  zero errors for all four source schemas combined.
- **SC-003**: Known alias pairs (manually verified synonym list) are correctly detected
  with ≥ 95% recall by the automated alias detection workflow.
- **SC-004**: Applying a registered mapping function to a conformant source record
  produces an output record that passes validation against the target schema in ≥ 99%
  of test cases.
- **SC-005**: Validation reports correctly identify all violations in a set of
  pre-labeled test records with ≥ 99% precision and ≥ 99% recall on ERROR-level issues.
- **SC-006**: A full ingestion, schema generation, and validation workflow for all four
  schemas completes within 5 minutes on a standard developer workstation (baseline to be
  refined during planning once schema sizes are characterized).
- **SC-007**: Schema updates (new source version) are detected and reflected in the
  unified schema without requiring a full re-ingestion of unchanged schemas.
