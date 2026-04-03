# Feature Specification: Robust Ingestion Pipeline v2

**Feature Branch**: `039-robust-ingestion-pipeline`
**Created**: 2026-04-03
**Status**: Draft
**Input**: Scale the pipeline to handle millions of entities from 8+ sources without filesystem bottlenecks, ensure all adapters route through the standard pipeline, preserve source-native aliasing, and surface element range information in the UI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Scalable Entity Storage (Priority: P1)

As a data engineer running the pipeline on large sources (NDA: 2.7M entities, OpenNeuro: 257K entities), I need the system to store and retrieve entities efficiently without per-entity file I/O — so that ingestion completes in minutes, not hours, and the filesystem isn't overwhelmed by millions of small files.

**Why this priority**: Current approach writes one YAML file per entity. At NDA scale (2.7M entities), file I/O dominates runtime and filesystem metadata wastes space. This blocks production use.

**Independent Test**: Ingest all 6,086 NDA structures → 2.7M entities stored in a single container per entity type → pipeline completes without creating millions of individual files.

**Acceptance Scenarios**:

1. **Given** a source producing more than 10,000 entities, **When** the pipeline runs, **Then** entities are stored in a binary container format (not individual files) during staging and after commit.
2. **Given** a source producing fewer than 100 entities, **When** the pipeline runs, **Then** entities MAY be stored as individual YAML files for human readability.
3. **Given** entities stored in binary format, **When** a developer queries the registry via CLI, **Then** individual entities are retrievable by sha256 or name with the same interface as the file-based backend.
4. **Given** the binary container, **When** the pipeline re-runs for the same source, **Then** existing entities are deduplicated correctly (same content hash → merge provenance, not duplicate).

---

### User Story 2 — All Adapters Through the Pipeline (Priority: P1)

As a system operator, I need every source ingestion (including batch OpenNeuro and full NDA) to flow through the standard pipeline stages (extract → enrich → align → commit → transform) — so that all entities are enriched, content-addressed, and deduplicated consistently regardless of source.

**Why this priority**: The batch OpenNeuro and NDA scripts currently bypass the pipeline, writing directly to the registry without enrichment, alignment, or proper content-addressed commit. This produces un-enriched, un-deduplicated entities.

**Independent Test**: Run `undata-library pipeline --source nda --all` → all 6,086 NDA structures extracted, enriched, committed with sha256 hashes, transforms generated.

**Acceptance Scenarios**:

1. **Given** the pipeline CLI, **When** a user runs `--source openneuro --batch 100`, **Then** 100 datasets are cloned via git+datalad, extracted, enriched, committed, and transforms generated — all through the standard pipeline.
2. **Given** the pipeline CLI, **When** a user runs `--source nda --all`, **Then** all NDA structures are fetched from the API, extracted, enriched, committed — through the standard pipeline.
3. **Given** any adapter, **When** it produces entities, **Then** those entities pass through enrichment (ontology matching) before being committed to the registry.
4. **Given** a batch source, **When** the pipeline completes, **Then** a run summary is recorded with entity counts, enrichment rates, timing, and any errors.

---

### User Story 3 — NDA Alias Preservation (Priority: P1)

As a data analyst, I need the NDA adapter to preserve cross-structure aliasing information (elements that appear in multiple NDA data dictionaries with the same semantics) — so that the alignment step can use NDA's own cross-referencing as ground truth.

**Why this priority**: NDA maintains relationships between data structures. Discarding this means the system must rediscover connections that NDA already knows, and may miss some.

**Independent Test**: Ingest two NDA structures sharing the same element name → alias information preserved in provenance → alignment step uses it to link them.

**Acceptance Scenarios**:

1. **Given** an NDA element that appears in multiple data structures, **When** the adapter extracts it, **Then** the element's provenance records all structures it belongs to.
2. **Given** NDA's alias/cross-reference metadata, **When** ingestion completes, **Then** the alignment step can access these as pre-verified alias hints.
3. **Given** two NDA elements with the same name and compatible types across structures, **When** alignment runs, **Then** they are grouped as aliases with higher confidence than embedding-only matches.

---

### User Story 4 — Element Range Information (Priority: P1)

As a researcher browsing elements, I need to see the full range/constraint information for each element — value set references, min/max bounds, patterns, array element types, and object type references — so I can understand what valid values an element accepts.

**Why this priority**: Range information is critical metadata that's currently extracted by adapters but not consistently populated or displayed. Without it, the registry describes elements without their constraints.

**Independent Test**: Browse an element with response_options → see linked valueset. Browse an element with min/max → see constraint range. Browse an element with type_ref → see linked schema.

**Acceptance Scenarios**:

1. **Given** an element with response_options, **When** viewed in the UI, **Then** the options are displayed and link to their corresponding ValueSet entity.
2. **Given** an element with min_value and max_value, **When** viewed in the UI, **Then** the range is displayed prominently (e.g., "Range: 0–100").
3. **Given** an element with a pattern constraint, **When** viewed in the UI, **Then** the pattern is displayed (e.g., "Pattern: ^[A-Z]{3}$").
4. **Given** an element with type_ref pointing to a schema, **When** viewed in the UI, **Then** the type reference links to the schema detail page.
5. **Given** all 8 adapters, **When** extracting elements, **Then** each adapter populates range fields (response_options, min_value, max_value, pattern, type_ref) whenever the source provides this information.

---

### User Story 5 — Batch Pipeline CLI (Priority: P2)

As a data engineer, I need the pipeline CLI to support batch ingestion from multi-dataset sources — so I can ingest 100 OpenNeuro datasets or all NDA structures with a single command.

**Why this priority**: Currently requires custom scripts outside the pipeline. A CLI integration makes batch ingestion reproducible and auditable.

**Independent Test**: `undata-library pipeline --source openneuro --batch 10` → 10 datasets ingested through full pipeline with progress reporting.

**Acceptance Scenarios**:

1. **Given** the CLI with `--source openneuro --batch N`, **When** run, **Then** N datasets are fetched, extracted, and processed through the full pipeline with progress output.
2. **Given** the CLI with `--source nda --all`, **When** run, **Then** all NDA structures are fetched and processed.
3. **Given** a batch run, **When** individual datasets fail, **Then** the pipeline continues with remaining datasets and reports failures in the run summary.
4. **Given** a batch run, **When** it completes, **Then** a consolidated run summary reports total datasets attempted, successful, failed, skipped, total entities, and elapsed time.

---

### User Story 6 — Enrichment at Scale (Priority: P2)

As a system operator, I need enrichment to work efficiently with the expanded NCBITaxon species filter (~90 taxa including BBQS species) and handle 200K+ elements — so that ontology matching completes in reasonable time without memory issues.

**Why this priority**: The embedding index grew from 20 to 90 NCBITaxon taxa, and the element count jumped from 7K to 220K+. Enrichment must scale.

**Independent Test**: Run enrichment on the full 220K element registry → completes within 30 minutes → species-level NCBITaxon matches are more precise than genus-level.

**Acceptance Scenarios**:

1. **Given** the full registry (220K+ elements), **When** enrichment runs, **Then** it completes without out-of-memory errors.
2. **Given** an element describing a mouse experiment, **When** enriched against NCBITaxon, **Then** the primary match is "Mus musculus" (species) not "Mus" (genus) — most precise match preferred.
3. **Given** the BBQS species list (gerbil, cowbird, cichlids, panther worm, capuchin), **When** enrichment runs, **Then** these species are available as annotation targets.

---

### Edge Cases

- What happens when a binary container is corrupted? The pipeline detects checksum mismatch and rebuilds from staging.
- What happens when NDA API is rate-limited? Adapter retries with exponential backoff; failed structures are logged and skippable.
- What happens when an OpenNeuro dataset has no metadata files? Adapter reports zero entities; pipeline skips to next dataset.
- What happens when enrichment runs out of memory on 200K+ elements? Batch processing with configurable chunk size; memory-mapped embedding index.
- What happens when two adapters produce entities with the same sha256? Provenance is merged (not duplicated), per existing content-addressing design.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST support a binary container format for staging and committed entities when entity count exceeds a configurable threshold (default: 1,000).
- **FR-002**: Individual YAML files MUST remain available as a fallback for debugging and small sources.
- **FR-003**: All source adapters (BIDS, NWB, DANDI, openMINDS, AIND, OpenNeuro, ReproSchema, NDA) MUST route through the standard pipeline stages (extract → enrich → align → commit → transform).
- **FR-004**: No adapter or script MAY write directly to the registry directory, bypassing the pipeline.
- **FR-005**: The NDA adapter MUST extract and preserve cross-structure aliasing information in element provenance.
- **FR-006**: The alignment step MUST use NDA alias information as high-confidence hints when grouping cross-source elements.
- **FR-007**: All adapters MUST populate element range fields (response_options, min_value, max_value, pattern, type_ref) when the source provides this information. Range fields are part of the semantic identity hash — elements with different ranges are distinct entities.
- **FR-008**: The frontend element detail page MUST display range/constraint information prominently: linked valueset for response_options, numeric range for min/max, regex for pattern, linked schema for type_ref. Range MUST be visible in both browse and detail views.
- **FR-009**: The pipeline CLI MUST support `--batch N` for multi-dataset sources and `--all` for API-backed sources.
- **FR-010**: Batch pipeline runs MUST report progress, handle individual dataset failures gracefully, and produce consolidated run summaries.
- **FR-011**: Enrichment MUST work efficiently on 200K+ elements with the expanded NCBITaxon filter (~90 taxa).
- **FR-012**: Species-level ontology matches MUST be preferred over genus-level when both are available.
- **FR-013**: OpenNeuro dataset cloning MUST use git clone followed by datalad get for proper annex content retrieval.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Full NDA ingestion (6,086 structures, 2.7M entities) completes through the pipeline in under 30 minutes.
- **SC-002**: Full OpenNeuro batch (100 datasets) completes through the pipeline in under 20 minutes.
- **SC-003**: Registry storage for 1M+ entities uses less than 5GB disk space (vs 50GB+ for individual YAML files).
- **SC-004**: All 8 adapters produce entities that pass through enrichment with at least 20% annotation rate overall.
- **SC-005**: Element detail pages display range information for at least 50% of elements that have constraints.
- **SC-006**: NDA cross-structure aliases are preserved and used during alignment, increasing alias detection accuracy by 30%+ over embedding-only matching.
- **SC-007**: Enrichment on 220K elements completes within 30 minutes with peak memory under 8GB.

## Clarifications

### Session 2026-04-03

- Q: How should element ranges be represented when sources provide different constraints? → A: Elements with different ranges (min/max, response_options) produce different content hashes and are therefore distinct entities. Each element contains the range from its source. The UI must display range information in both browse and detail views.

## Scope Boundaries

### In Scope

- Binary container format for entity storage (staging + committed registry)
- Pipeline CLI batch mode for OpenNeuro and NDA
- NDA alias extraction and alignment integration
- Element range display in frontend
- Adapter audit for range field population
- Enrichment scaling and species precision
- OpenNeuro git+datalad clone pattern

### Out of Scope

- Real-time streaming ingestion (batch is sufficient)
- Custom adapter SDK for third-party developers
- Multi-node distributed pipeline execution
- Automated adapter discovery (manual registration is fine)
- Frontend editing of range constraints

## Assumptions

- The binary container format (Parquet or SQLite) is read/write compatible with the existing StorageBackend protocol
- NDA API remains publicly accessible without authentication for data dictionary queries
- OpenNeuro datasets are accessible via GitHub + git-annex without authentication
- The existing embedding model (all-MiniLM-L6-v2) scales to 200K+ elements with chunked processing
- Docker compose development setup continues to work with the new storage format

## Dependencies

- Feature 038 (System Hardening) — provides adapters, NCBITaxon filter, evidence chains, audit trail
- StorageBackend protocol — must be extended to support binary container read/write
- pyoxigraph ontology store — must be loaded before enrichment
- datalad + git-annex — required for OpenNeuro dataset cloning
