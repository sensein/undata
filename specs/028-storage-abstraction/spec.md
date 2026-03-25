# Feature Specification: Library Storage Abstraction

**Feature Branch**: `028-storage-abstraction`
**Created**: 2026-03-24
**Status**: Draft
**Input**: Phase 1 of iteration 2 — introduce StorageBackend protocol and FileBackend to decouple pipeline functions from file system, enabling future database backends.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Storage Protocol Definition (Priority: P1)

As a library maintainer, I need a formal interface describing how entities are stored and retrieved so that pipeline functions can work against any storage implementation without knowing the details.

**Why this priority**: This is the foundational abstraction that everything else builds on. Without it, the pipeline remains hardcoded to files and the backend cannot reuse library logic.

**Independent Test**: Import the protocol, verify it defines all required methods, and confirm that the existing file-based behavior can satisfy the interface.

**Acceptance Scenarios**:

1. **Given** the library is imported, **When** a developer inspects the storage protocol, **Then** it exposes methods for reading, writing, listing, checking existence, deleting, and merging provenance for all entity types (elements, schemas, values, valuesets, curation flags, run summaries).
2. **Given** the protocol is defined, **When** a type checker validates the FileBackend against the protocol, **Then** it confirms the FileBackend satisfies the interface with no missing methods.
3. **Given** the protocol is defined, **When** a developer writes a mock implementation for testing, **Then** the mock can be used in place of the file backend with no changes to pipeline code.

---

### User Story 2 — File Backend Wrapping Current Behavior (Priority: P1)

As a CLI user, I need the existing file-based pipeline to work exactly as before — same commands, same output, same file layout — after the storage abstraction is introduced.

**Why this priority**: 343 tests validate the current behavior. Any regression means the abstraction was introduced incorrectly. This story is a pure refactor with zero behavioral change.

**Independent Test**: Run the full library test suite. All 343 tests pass without modification.

**Acceptance Scenarios**:

1. **Given** the library with the new file backend, **When** a user runs `undata-library pipeline --source bids`, **Then** the output directory structure, file contents, and entity counts are identical to the current implementation.
2. **Given** the full test suite, **When** all 343 tests are executed, **Then** every test passes without any test code changes.
3. **Given** a pipeline run that writes entities, **When** the output files are compared byte-for-byte with the previous implementation's output, **Then** the files are identical (same YAML content, same filenames, same directory layout).

---

### User Story 3 — Pipeline Functions Accept Storage Backend (Priority: P1)

As a backend developer, I need pipeline functions to accept a storage backend parameter so I can pass a database-backed implementation instead of file paths when calling the library from the web service.

**Why this priority**: This is the integration point that makes the abstraction useful. Without it, the protocol and file backend exist but nothing uses them.

**Independent Test**: Call each pipeline function (ingest, enrich, align, commit, transform) with an explicit file backend parameter and verify the output matches the default behavior.

**Acceptance Scenarios**:

1. **Given** a pipeline function that previously accepted a directory path, **When** it is called with a file backend wrapping that same path, **Then** the output is identical.
2. **Given** the CLI, **When** a user runs any pipeline command, **Then** the CLI internally creates a file backend from the output directory and passes it to the pipeline function (transparent to the user).
3. **Given** a pipeline function, **When** it is called with a minimal mock backend that records operations, **Then** the function issues the expected sequence of read/write/list calls without assuming file system access.

---

### User Story 4 — Adapter Cleanup (Priority: P2)

As a library maintainer, I need all source adapters to follow the same pattern — produce an intermediate schema representation, then a standard extractor classifies entities — so that adding new sources requires only writing the conversion, not reimplementing classification logic.

**Why this priority**: Brainstorm v1 found 51 misclassification issues across 5 adapters due to inconsistent classification. While adapters were partially converted, some still have ad-hoc classification code that should be removed. This is P2 because the storage abstraction (P1) is the blocking dependency for the backend; adapter cleanup improves quality but doesn't gate other work.

**Independent Test**: Run extraction for each source and verify entity counts and types match expected values.

**Acceptance Scenarios**:

1. **Given** any of the 5 source adapters, **When** extraction is run, **Then** the adapter produces an intermediate schema representation and a standard extractor produces classified entities — no adapter directly assigns entity types.
2. **Given** the adapter interface, **When** a developer adds a new source, **Then** they only need to implement the schema conversion method; classification, provenance stamping, and routing are handled by the standard extractor.
3. **Given** extraction from all 5 sources, **When** entity counts are compared to the brainstorm v1 baseline (2,191 elements, 915 schemas, 5,500 values, 214 valuesets), **Then** counts are within 5% (minor changes from classification fixes are expected and documented).

---

### User Story 5 — Pipeline Stage Reordering (Priority: P2)

As a data engineer, I need alignment to run before commit so that cross-source annotation transfers improve entity identity before content-addressing, producing better deduplication.

**Why this priority**: Currently commit runs before alignment, so annotation transfers discovered during alignment don't influence the content hash. Reordering means openMINDS annotations (70% enriched) can transfer to NWB entities (1% enriched) *before* hashing, causing NWB entities with transferred annotations to merge with equivalent entities from other sources. This is P2 because it's an optimization — the pipeline works correctly either way.

**Independent Test**: Run the full pipeline with the new ordering and verify that annotation transfer happens before commit and entity counts reflect improved deduplication.

**Acceptance Scenarios**:

1. **Given** a multi-source pipeline run, **When** alignment runs before commit, **Then** cross-source annotation transfers are reflected in the committed entities' ontology annotations.
2. **Given** a source with low enrichment (e.g., NWB at 1%), **When** alignment transfers annotations from a highly enriched source (e.g., openMINDS at 70%), **Then** the transferred annotations are present at commit time and influence the content hash.
3. **Given** the pipeline with the new ordering, **When** entity counts are compared to the old ordering, **Then** the new ordering produces equal or fewer committed entities (better deduplication from richer annotations at commit time).

---

### Edge Cases

- What happens when a storage backend method is called with an entity type it doesn't recognize? It raises a clear error indicating the unsupported type.
- What happens when write_entity is called for an entity that already exists? The behavior depends on the backend: file backend overwrites (current behavior), future database backend may merge or reject.
- What happens when list_entities is called on an empty backend? It returns an empty iterator, not an error.
- What happens when the pipeline is run with the old stage order (commit before align)? It still works correctly — the reorder is an optimization, not a correctness fix.
- What happens when an adapter produces zero entities? The pipeline continues with the next stage, producing a run summary with zero counts for that source.
- What happens when a mock backend is used for testing but doesn't implement all optional methods? The protocol defines all methods as required; incomplete implementations fail type checking.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define a storage protocol with methods for reading, writing, listing, checking existence, deleting, and counting entities across all entity types.
- **FR-002**: System MUST provide a merge_provenance operation that adds provenance entries to an existing entity without overwriting other fields.
- **FR-003**: System MUST implement a file-based backend that preserves the exact current behavior: YAML files in entity-type subdirectories with content-addressed filenames.
- **FR-004**: All existing library tests (343+) MUST pass without modification after the file backend is introduced.
- **FR-005**: Pipeline functions (ingest, enrich, align, commit, transform) MUST accept a storage backend parameter.
- **FR-006**: Pipeline functions MUST default to file-based behavior when no backend is explicitly provided (backward compatible CLI usage).
- **FR-007**: The CLI MUST transparently create a file backend from the output directory and pass it to pipeline functions.
- **FR-008**: All source adapters MUST produce an intermediate schema representation as their output; a standard extractor MUST handle entity classification.
- **FR-009**: The pipeline MUST execute stages in the order: extract → enrich → align → commit → transform.
- **FR-010**: Cross-source annotation transfers from the align stage MUST be reflected in entities before the commit stage computes content hashes.
- **FR-011**: The storage protocol MUST support filtering when listing entities (e.g., by source, by entity type, by curation status).
- **FR-012**: The storage protocol MUST NOT depend on any database library — it is a pure interface with no implementation dependencies.
- **FR-013**: The file backend MUST handle concurrent reads safely (multiple processes reading the same registry).
- **FR-014**: Entity counts from a full pipeline run MUST be recorded in an evaluation report for comparison with the brainstorm v1 baseline.

### Key Entities

- **StorageBackend**: The central abstraction — a protocol defining how entities are persisted and queried. Has no implementation; defines the contract.
- **FileBackend**: An implementation of StorageBackend that reads and writes YAML files in a directory tree. Wraps the current library behavior.
- **Entity types**: Element, Schema, Value, ValueSet — the four core types managed by the storage protocol.
- **Supporting types**: CurationFlag, RunSummary — also managed through the storage protocol.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 343+ existing library tests pass with zero modifications after the storage abstraction is introduced.
- **SC-002**: A full pipeline run (all 5 sources) produces entity counts within 5% of the brainstorm v1 baseline (2,191 elements, 915 schemas, 5,500 values, 214 valuesets).
- **SC-003**: Pipeline functions can be called with a mock storage backend (no file system) and execute without errors, demonstrating decoupling from the file system.
- **SC-004**: All 5 source adapters produce entities through the standard extractor — no adapter directly assigns entity types.
- **SC-005**: Cross-source annotation transfer (align stage) occurs before content addressing (commit stage), resulting in equal or improved deduplication compared to the old pipeline order.
- **SC-006**: The storage protocol is a pure interface with zero runtime dependencies beyond the standard library.
- **SC-007**: A developer can implement a new storage backend by satisfying the protocol — no subclassing or framework coupling required.

## Scope Boundaries

### In Scope

- StorageBackend protocol definition
- FileBackend implementation wrapping current YAML behavior
- Refactoring pipeline functions to accept backend parameter
- Adapter cleanup to consistent pattern
- Pipeline stage reordering (align before commit)
- Full test suite validation (zero regressions)

### Out of Scope

- Database backend implementation (Phase 2)
- Backend service changes (Phase 2)
- Frontend changes (Phase 3)
- New source adapters or ontology expansion
- Embedding storage abstraction (covered by storage protocol but implementation deferred)
- Authentication or authorization

## Assumptions

- The library's test suite (343 tests) is the definitive regression check for the file backend
- The file backend preserves the exact directory layout: `{base}/elements/*.yaml`, `{base}/schemas/*.yaml`, etc.
- Pipeline functions currently accept Path or str arguments for directories — these are replaced with StorageBackend parameters while maintaining backward compatibility through the CLI layer
- The standard extractor for adapters is the existing LinkML extraction path validated in brainstorm v1
- Concurrent writes to the same file backend are not guaranteed safe (current behavior); this is documented, not fixed

## Dependencies

- Brainstorm v1 library codebase (343 tests, 5 adapters, pipeline functions)
- VISION.md blueprint for the StorageBackend protocol design
