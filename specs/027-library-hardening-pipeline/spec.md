# Feature Specification: Library Hardening, Pipeline Optimization, and UI/DB Rebuild

**Feature Branch**: `027-library-hardening-pipeline`
**Created**: 2026-03-22
**Status**: Draft
**Input**: Full review of library code, pipeline optimization with source-aware validation, human curation flags, and UI/DB layer rebuild

## User Scenarios & Testing

### User Story 1 - Library Code Review and Cleanup (Priority: P1)

A developer reviews the complete undata-library codebase to consolidate requirements from features 001-026 into a coherent set, identify and fix code quality issues, create shared utilities, enforce encapsulation (underscore-prefixed internals not exposed), and ensure comprehensive test coverage with edge cases.

**Why this priority**: The library has evolved through 26 feature iterations with meandering requirements. Before optimizing or rebuilding dependent layers, the foundation must be solid — inconsistencies and dead code from earlier iterations must be resolved.

**Independent Test**: Run the full test suite after cleanup. Every public function has a corresponding test. No internal (`_`-prefixed) symbol is imported from outside its module. All removed dead code paths are verified as unreachable.

**Acceptance Scenarios**:

1. **Given** the library codebase from features 001-026, **When** a developer audits all modules, **Then** a consolidated requirements document lists every active user story and functional requirement with status (implemented, partially implemented, outdated)
2. **Given** modules with inconsistent patterns (e.g., some using hash-registry, others not), **When** shared utilities are extracted, **Then** common operations (YAML I/O, provenance dedup, filename sanitization) use a single shared utility
3. **Given** internal functions prefixed with underscore, **When** all imports across the codebase are audited, **Then** no underscore-prefixed function is imported from outside its defining module or class
4. **Given** dead code branches from removed features (ontology_term, Constraints, SchemaProvenance), **When** a full code audit is performed, **Then** all dead branches, unreachable conditions, and obsolete comments are removed
5. **Given** the test suite (221 tests), **When** coverage is analyzed, **Then** every public function has at least one test, and edge cases (empty inputs, malformed YAML, missing fields, Unicode names) are covered
6. **Given** any code path skipped during review, **When** the review concludes, **Then** that path is documented with a "REVIEW-TODO" marker and a brief reason for deferral

---

### User Story 2 - Pipeline Optimization and Source-Aware Validation (Priority: P1)

A data engineer optimizes each pipeline step (extract, enrich, commit, align, transform) to be maximally accurate and sensitive to upstream source material. Each adapter deeply understands its source schema format so that when sources evolve (new BIDS version, updated DANDI models), extraction routines detect and handle changes. Human curation flags are introduced for ambiguous cases that automated processing cannot resolve with confidence.

**Why this priority**: Equally critical to US1 — the pipeline is the core product. Inaccurate extraction or insensitivity to source changes undermines the entire registry's value. Human curation flags are foundational for the UI/DB rebuild.

**Independent Test**: Re-extract all 5 sources, compare element/schema/value counts and ontology annotation rates against the 026 baseline. Verify that flagged items appear in a machine-readable curation queue. Run against a modified source (e.g., simulated BIDS schema update) and verify the pipeline detects the change.

**Acceptance Scenarios**:

1. **Given** a source schema (BIDS, DANDI, NWB, openMINDS, AIND), **When** extraction runs, **Then** every data element, vocabulary type, and class definition present in the source is captured (no silent omissions)
2. **Given** a source schema with a new or changed field compared to the previous version, **When** re-extraction runs, **Then** the pipeline detects new, modified, and removed elements and reports them in the extraction summary
3. **Given** an element where ontology matching confidence is below the enrichment threshold, **When** enrichment runs, **Then** the element is flagged for human curation with the reason (low confidence, ambiguous match, multiple candidates)
4. **Given** a transform between two elements where the conversion function cannot be automatically determined, **When** transform generation runs, **Then** the transform is flagged as "needs-review" with the ambiguity described
5. **Given** the enrichment step, **When** it processes values like "male" against ontology terms, **Then** clear matches (cosine similarity >= 0.95) are assigned automatically and borderline matches (0.7-0.95) are flagged for review
6. **Given** a complete pipeline run, **When** the run finishes, **Then** a summary report lists: counts per entity type, enrichment rates, number of curation flags, and comparison to previous run

---

### User Story 3 - UI/DB Layer Rebuild with Efficiency Optimization (Priority: P2)

A platform operator rebuilds the web UI and database layers to consume the library's content-addressed registry, display elements with provenance and ontology annotations, support human curation workflows (review flagged items, approve/reject annotations), and optimize for efficiency at all levels (query performance, rendering, caching).

**Why this priority**: Depends on US1 (clean library) and US2 (accurate pipeline with curation flags). Cannot meaningfully build a UI for curation without the underlying data quality and flag infrastructure.

**Independent Test**: Deploy the UI against a populated registry. A curator can browse elements, review flagged items, and approve/reject ontology annotations. Page load times meet performance targets.

**Acceptance Scenarios**:

1. **Given** a populated registry with 7,000+ elements, **When** a curator opens the element browser, **Then** elements load with pagination and the page is interactive within 2 seconds
2. **Given** elements flagged for curation, **When** a curator views the curation queue, **Then** flagged items are grouped by type (low confidence, ambiguous match, needs-review transform) with supporting context
3. **Given** a flagged ontology annotation, **When** a curator approves or rejects it, **Then** the decision is recorded with the curator's identity and timestamp, and the element is updated accordingly
4. **Given** the database layer, **When** elements are imported from the flat-file registry, **Then** content-addressed identities, provenance chains, and ontology annotations are preserved without loss
5. **Given** the full stack (UI + DB + library), **When** a new pipeline run produces updated elements, **Then** the database reflects changes incrementally (new elements added, merged elements updated, no full reimport required)

---

### Edge Cases

- What happens when a source schema file is malformed or partially downloaded?
- How does the pipeline handle a source that was previously available but is now unreachable?
- What happens when two curators flag the same element simultaneously?
- How does the system handle elements with no provenance (orphaned during cleanup)?
- What happens when an ontology term referenced by an annotation is deprecated or removed in a newer ontology version?
- How does re-extraction handle renamed fields (same concept, different attribute name)?

## Requirements

### Functional Requirements

**Workstream 1: Library Code Review**

- **FR-001**: System MUST have a consolidated requirements document mapping every active user story from features 001-026 to its implementation status
- **FR-002**: System MUST extract shared utilities for common operations: YAML read/write with error handling, provenance deduplication, filename sanitization, URI building
- **FR-003**: System MUST NOT expose underscore-prefixed internal functions in any public import path (no cross-module imports of `_private` functions)
- **FR-004**: System MUST remove all dead code paths, obsolete comments, and references to removed models (ontology_term on elements, Constraints, SchemaProvenance, ValueProvenance, source_attribute, source_class)
- **FR-005**: System MUST have test coverage for every public function, including edge cases for empty inputs, malformed data, missing required fields, and Unicode/special character handling
- **FR-006**: System MUST document any code paths deferred during review with machine-searchable markers (e.g., "REVIEW-TODO")

**Workstream 2: Pipeline Optimization**

- **FR-007**: Each adapter MUST extract all entity types present in its source (elements, schemas, values, valuesets) with zero silent omissions
- **FR-008**: Each adapter MUST document the source schema structure it expects and the mapping from source fields to undata entities
- **FR-009**: The pipeline MUST detect new, modified, and removed entities when re-extracting a source that has been previously extracted
- **FR-010**: The enrichment step MUST flag entities for human curation when: (a) best ontology match confidence is between 0.7 and 0.95, (b) multiple candidate matches are within 0.05 of each other, (c) value_domain cannot be determined
- **FR-011**: The transform step MUST flag transforms as "needs-review" when the conversion function type is "unknown"
- **FR-012**: The pipeline MUST produce a machine-readable run summary with entity counts, enrichment rates, curation flag counts, and delta from previous run
- **FR-013**: Each adapter MUST be sensitive to source schema version changes and report when the source format has changed from what was previously extracted

**Workstream 3: UI/DB Rebuild**

- **FR-014**: The database layer MUST import elements, schemas, values, and valuesets from the flat-file registry preserving content-addressed identities and full provenance
- **FR-015**: The UI MUST provide a browsable element catalog with search, filtering by source/data_type/ontology, and pagination
- **FR-016**: The UI MUST provide a curation queue showing all flagged items grouped by flag type with supporting context (match candidates, scores, source provenance)
- **FR-017**: The UI MUST allow curators to approve, reject, or defer flagged items with recorded identity and timestamp
- **FR-018**: The database MUST support incremental updates from new pipeline runs without requiring full reimport
- **FR-019**: All layers (library, database, UI) MUST be optimized for efficiency: batch operations for import, indexed queries for search, lazy loading for large result sets

### Key Entities

- **CurationFlag**: Represents a machine-generated flag on an entity requiring human review — includes flag type (low_confidence, ambiguous_match, needs_review, unknown_transform), entity reference, context (candidate matches, scores), status (pending, approved, rejected, deferred), reviewer identity, timestamp
- **RunSummary**: Per-pipeline-run report with source, entity counts by type, enrichment rate, flag counts, delta from previous run, timing
- **CurationDecision**: A curator's resolution of a flag — action taken, justification, resulting entity update

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero underscore-prefixed internal functions imported across module boundaries after cleanup
- **SC-002**: Test coverage reaches every public function with at least one positive and one negative/edge-case test
- **SC-003**: Re-extraction of all 5 sources produces element counts within 1% of the 026 baseline (7,745 elements), with equal or higher enrichment rates
- **SC-004**: At least 80% of all "clear match" ontology annotations (score >= 0.95) are assigned automatically; remaining annotations are flagged for curation
- **SC-005**: Pipeline run summary report is produced for every run, machine-readable, and includes delta comparison
- **SC-006**: Curation queue displays flagged items within 2 seconds for a registry of 7,000+ elements
- **SC-007**: A curator can review and resolve a flagged item in under 30 seconds on average
- **SC-008**: Database incremental import processes a new pipeline run (delta only) in under 60 seconds for typical source updates

## Assumptions

- The library codebase at the end of feature 026 is the baseline for all review and optimization work
- Source schemas (BIDS, DANDI, NWB, openMINDS, AIND) remain accessible at their current locations
- The existing ontology store (268K embedded terms from 13 ontologies) is sufficient for enrichment; no new ontologies need to be added in this feature
- The UI/DB rebuild will reuse the existing backend architecture (002-schema-backend) as a starting point, not start from scratch
- Human curation decisions feed back into the enrichment pipeline (approved annotations become ground truth for future runs)

## Scope Boundaries

**In scope**:
- Full code audit and cleanup of library/src/undata_library/
- Full test review and gap analysis of library/tests/
- Pipeline accuracy optimization for all 5 adapters
- Human curation flag infrastructure in the library
- Database import from flat-file registry
- UI for element browsing and curation
- Performance optimization across all layers

**Out of scope**:
- Adding new source schemas beyond the existing 5
- Adding new ontologies beyond the existing 13
- Multi-user collaboration features (concurrent curation by teams)
- Automated retraining of embedding models
- Mobile UI support
