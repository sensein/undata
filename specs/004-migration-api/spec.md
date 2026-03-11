# Feature Specification: Dynamic Schema Construction and Migration API

**Feature Branch**: `004-migration-api`
**Created**: 2026-03-07
**Status**: Draft
**Input**: An API that allows clients to dynamically construct schemas and classes
from data elements, and to define and execute migration pathways for forward and
backward data transformation between schema versions or between source schemas.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Dynamic Schema and Class Construction (Priority: P1)

A tool developer needs to assemble a schema tailored to a specific research use case —
selecting a subset of data elements from the unified store, grouping them into classes,
and exporting the result as a valid, self-contained LinkML schema. They do this
programmatically through the API without writing LinkML by hand.

**Why this priority**: Dynamic schema construction is the foundational capability of
this API. Migration pathways operate on schemas; without the ability to construct
schemas programmatically, migration is limited to pre-ingested schema pairs.

**Independent Test**: Call the schema construction endpoint with a list of element
identifiers and class groupings. Receive a valid LinkML schema as output. Validate
it with the official LinkML toolchain independently of the migration subsystem.

**Acceptance Scenarios**:

1. **Given** a set of data element identifiers from the element store, **When** a
   client sends a construction request specifying which elements belong to which
   classes, **Then** the API returns a valid LinkML schema containing the requested
   slots organized into the specified classes.

2. **Given** a construction request that references a non-existent element identifier,
   **When** submitted, **Then** the API returns an error identifying the unknown
   identifier(s); the request is not partially fulfilled.

3. **Given** a dynamically constructed schema, **When** a client requests it, **Then**
   it is available in LinkML YAML and JSON-LD formats.

4. **Given** a dynamically constructed schema, **When** a client saves it with a name
   and version, **Then** it is stored durably and retrievable by name and version in
   future requests.

5. **Given** a saved schema, **When** a client requests an updated version with additional
   or removed elements, **Then** the new version is saved alongside the previous version;
   no version is deleted.

6. **Given** a construction request that includes elements with name collisions (same
   name, incompatible types from different sources), **Then** the API MUST surface the
   conflict and require the client to explicitly resolve it (by aliasing or renaming)
   before construction succeeds.

---

### User Story 2 — Migration Pathway Definition (Priority: P2)

A data steward needs to define a migration pathway that transforms data conforming to
schema version 1.0 into data conforming to schema version 2.0 (or from BIDS to DANDI).
They describe the pathway as an ordered sequence of mapping functions — forward
direction (old → new) and backward direction (new → old, where invertible). The pathway
is stored and reusable.

**Why this priority**: Migration pathways are the governance artifacts that make data
transformation safe and reproducible. They must be defined before data can be migrated.

**Independent Test**: Register a migration pathway with two mapping steps. Retrieve it.
Confirm the step order, function references, and direction flags are preserved exactly.

**Acceptance Scenarios**:

1. **Given** two schemas (source and target) and an ordered list of mapping function
   references, **When** a client registers a migration pathway, **Then** it is stored
   with a unique identifier, directional metadata (forward/backward/bidirectional), and
   references to all constituent mapping functions.

2. **Given** a registered migration pathway, **When** a client queries it, **Then** the
   full ordered sequence of mapping functions is returned with step indices and
   directionality flags.

3. **Given** a pathway where all constituent mapping functions have declared inverse
   functions, **When** the pathway is registered, **Then** the API automatically derives
   and stores the inverse (backward) pathway.

4. **Given** a pathway where some steps are not invertible, **When** a client requests
   the inverse pathway, **Then** the API returns the pathway with those steps marked as
   non-invertible; the pathway is still usable for the forward direction.

5. **Given** two registered pathways that together form a chain (A→B and B→C), **When**
   a client requests a composite pathway A→C, **Then** the API composes them into a
   single pathway and returns it (without requiring re-registration of each step).

6. **Given** an update to a mapping function that is part of a registered pathway,
   **When** the pathway is retrieved, **Then** it reflects the updated function and its
   version history records the change.

---

### User Story 3 — Data Migration Execution (Priority: P3)

A data engineer has a dataset conforming to BIDS schema v1.8 and needs to transform
it to conform to DANDI schema v0.6. They invoke the migration execution endpoint with
the dataset, the source schema identifier, and the target schema identifier. The API
applies the registered pathway, returns the transformed dataset, and provides a
migration report detailing every transformation step applied, any fields that could
not be mapped, and the validation status of the output.

**Why this priority**: Execution is the primary user-facing value of the migration
system — the moment schema knowledge becomes actionable on real data.

**Independent Test**: Provide a conformant test dataset and a registered migration
pathway. Call the execution endpoint. Verify the output conforms to the target schema
and the migration report accounts for every input field.

**Acceptance Scenarios**:

1. **Given** a data record conforming to a source schema and a registered forward
   migration pathway to a target schema, **When** a client invokes the migration
   endpoint, **Then** the API returns a transformed data record and a migration report.

2. **Given** a successful migration, **When** the migration report is inspected,
   **Then** it lists: each mapping function applied (with input values, output values,
   and function identifier), any input fields with no mapping to the target schema
   (unmapped fields), and a validation result for the output record.

3. **Given** an input field with a registered mapping, **When** the mapping function
   raises an error (e.g., out-of-range input), **Then** the migration halts at that
   step, the report captures the failure with full context, and the output record is
   NOT returned as valid.

4. **Given** a registered backward migration pathway, **When** a client applies it to
   a record conforming to the target schema, **Then** the API returns a record
   conforming to the source schema (within the limits of non-invertible steps).

5. **Given** a migration involving multiple intermediate schemas (A → B → C), **When**
   executed, **Then** the migration report shows all intermediate states and the
   validation result at each hop.

6. **Given** a batch of data records, **When** submitted for migration together, **Then**
   each record is migrated independently; a failure on one record MUST NOT prevent
   migration of other records.

---

### User Story 4 — Schema Diff and Compatibility Analysis (Priority: P4)

Before committing to a migration pathway, an architect wants to understand exactly
how two schemas differ — which elements were added, removed, renamed, or had their
types changed — and whether a direct migration is possible or if gaps exist. They
call the schema diff endpoint and receive a structured compatibility report.

**Why this priority**: Proactive compatibility analysis prevents migration failures at
execution time and helps teams plan schema evolution safely.

**Independent Test**: Call the diff endpoint on two schemas with known differences.
Verify the report correctly identifies all added, removed, renamed (aliased), and
type-changed elements without any false positives or negatives.

**Acceptance Scenarios**:

1. **Given** two schema identifiers, **When** a client calls the diff endpoint, **Then**
   the API returns a structured report listing: elements added in the target, elements
   removed from source, elements present in both (with change details), and elements
   that are aliases (same concept, different name).

2. **Given** a diff report, **When** the client reviews it, **Then** each difference
   is classified as: ADDED, REMOVED, RENAMED (alias), TYPE_CHANGED, CONSTRAINT_CHANGED,
   or DESCRIPTION_CHANGED.

3. **Given** a diff report showing that all source elements have a registered mapping
   to the target, **When** compatibility is assessed, **Then** the report indicates
   FULL_COVERAGE (a migration pathway can be automatically assembled).

4. **Given** a diff report showing some source elements have no registered mapping,
   **Then** the report indicates PARTIAL_COVERAGE and lists the unmapped elements.

5. **Given** a diff report, **When** the client requests a migration pathway, **Then**
   the API assembles and returns a draft pathway from existing mappings for the covered
   elements, leaving gaps explicitly marked for the unmapped ones.

---

### Edge Cases

- What happens when a migration pathway references a mapping function that has been
  deleted? The pathway MUST be marked as BROKEN and execution MUST be refused until
  the broken step is replaced; existing migration reports produced before the deletion
  remain valid.
- What happens when the input data record contains fields not present in the source
  schema? Those fields MUST be passed through unchanged (with a WARNING in the report)
  unless the pathway explicitly drops them.
- What happens when a dynamic schema construction request is very large (thousands of
  elements)? The API MUST handle it asynchronously if it exceeds a documented size
  threshold, returning a job identifier for polling.
- What happens when a backward migration is requested for a pathway that has no
  inverse? The API MUST return a clear error identifying which steps are not invertible,
  rather than returning a silently incomplete result.
- What happens when two migration pathways exist between the same source and target
  schemas? Both MUST be returned in pathway queries; the client MUST explicitly choose
  which to use for execution; the API MUST NOT silently choose one.

---

## Requirements *(mandatory)*

### Functional Requirements

**Dynamic Schema Construction**

- **FR-001**: API MUST accept a schema construction request specifying: a list of
  data element identifiers, class groupings, and an optional schema name and version.
- **FR-002**: API MUST return a valid LinkML schema (YAML and JSON-LD) for any valid
  construction request.
- **FR-003**: API MUST reject requests referencing unknown element identifiers and
  return a list of unresolved identifiers.
- **FR-004**: API MUST detect and surface name collisions in construction requests
  and require explicit resolution before proceeding.
- **FR-005**: API MUST durably store saved schemas with versioning; all versions MUST
  be retrievable by name and version identifier.
- **FR-006**: API MUST support asynchronous construction for requests exceeding a
  documented element count threshold, returning a job identifier for status polling.

**Migration Pathway Definition**

- **FR-007**: API MUST accept pathway registration requests specifying: source schema,
  target schema, direction (forward/backward/bidirectional), and an ordered list of
  mapping function references.
- **FR-008**: API MUST validate that all referenced mapping functions exist at
  registration time; missing references MUST cause rejection.
- **FR-009**: API MUST automatically derive and store the inverse pathway when all
  constituent functions declare inverses.
- **FR-010**: API MUST support pathway composition: given two pathways A→B and B→C,
  produce a composed pathway A→C without re-registering individual steps.
- **FR-011**: API MUST mark pathways as BROKEN when any constituent mapping function
  is deleted, and MUST refuse execution of broken pathways.

**Migration Execution**

- **FR-012**: API MUST accept a migration execution request specifying: input data
  record(s), source schema identifier, target schema identifier (or explicit pathway
  identifier), and direction.
- **FR-013**: API MUST return a migration report for every execution containing: list
  of applied mapping steps with input/output values, unmapped fields, and validation
  result of the output record.
- **FR-014**: API MUST validate the output record against the target schema after
  migration and include the validation result in the report.
- **FR-015**: API MUST support batch execution; individual record failures MUST NOT
  prevent processing of other records in the batch.
- **FR-016**: When multiple pathways exist between source and target, API MUST require
  the client to specify which pathway to use.

**Schema Diff and Compatibility**

- **FR-017**: API MUST provide a diff endpoint that compares two schemas and returns
  a structured report classifying all element-level differences.
- **FR-018**: Diff report MUST classify each difference as: ADDED, REMOVED, RENAMED,
  TYPE_CHANGED, CONSTRAINT_CHANGED, or DESCRIPTION_CHANGED.
- **FR-019**: Diff report MUST include a coverage assessment (FULL, PARTIAL, or NONE)
  based on whether registered mappings exist for all differing elements.
- **FR-020**: API MUST assemble a draft migration pathway from existing mappings for
  elements with FULL or PARTIAL coverage, explicitly marking gaps.

### Key Entities

- **DynamicSchema**: A client-assembled LinkML schema, versioned, composed of
  DataElements from the store.
- **MigrationPathway**: An ordered, directional sequence of MappingFunction references
  linking a source schema to a target schema. Can be ACTIVE or BROKEN.
- **MigrationExecution**: A single run of a MigrationPathway against one or more
  data records, producing a MigrationReport.
- **MigrationReport**: A structured record of an execution: steps applied, values
  transformed, unmapped fields, and validation result.
- **SchemaDiff**: A structured comparison between two schemas, classifying all
  element-level differences and assessing mapping coverage.
- **MigrationJob**: An asynchronous task handle for long-running construction or
  migration operations, exposing status and result retrieval.

---

## Assumptions

- The API operates on schemas and data elements stored by the backend (spec 002);
  it does not maintain its own data store.
- Mapping function execution is performed by the API service; the function expression
  stored in the backend is interpreted or invoked at execution time.
- "Backward migration" is only fully supported when all steps in the pathway have
  declared inverse functions; partial inverses produce partial results with clear
  gap reporting.
- Input data for migration is supplied as JSON or YAML; other formats are out of
  scope for this specification.
- Asynchronous job execution for large requests is polled by the client; push
  notification (webhooks) is a future enhancement.
- Schema versioning uses CalVer (YYYY.MM.MICRO) as established in the project
  constitution.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of valid construction requests produce a LinkML schema that passes
  the official LinkML validator with zero errors.
- **SC-002**: 100% of migration execution requests produce a migration report; no
  execution completes silently without a report.
- **SC-003**: The migration report accounts for 100% of input fields — every field
  is either mapped, explicitly listed as unmapped, or passed through with a warning.
- **SC-004**: Schema diff correctly classifies all element differences (ADDED, REMOVED,
  RENAMED, TYPE_CHANGED, etc.) with ≥ 99% accuracy against a manually labelled
  diff test suite.
- **SC-005**: Batch migration of 1,000 records completes with per-record failure
  isolation — a failure in any one record does not prevent the remaining 999 from
  being processed.
- **SC-006**: Broken pathway detection is immediate: any pathway referencing a deleted
  mapping function is marked BROKEN before any subsequent execution attempt.
- **SC-007**: Pathway composition (A→B + B→C = A→C) produces a valid, executable
  pathway in 100% of test cases where both constituent pathways are ACTIVE.
