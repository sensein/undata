# Feature Specification: Unified Embedding & Storage

**Feature Branch**: `040-unified-embedding-storage`
**Created**: 2026-04-03
**Status**: Draft
**Input**: Eliminate YAML files from the pipeline entirely. Make Parquet the single storage format. Compute entity embeddings once during pipeline commit (not during backend import). Recompute embeddings on entity update. Trigger re-alignment when embeddings are missing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Parquet-Only Pipeline (Priority: P1)

As a data engineer, I need the entire pipeline (extract → enrich → align → commit → transform) to use Parquet as the sole storage format — so that there are no individual YAML files created at any stage, and the system handles millions of entities without filesystem bottlenecks.

**Why this priority**: The current pipeline writes individual YAML files during extraction and commit, then has a separate Parquet path. This dual-format approach causes confusion, slow I/O at scale, and inconsistencies between what's in YAML vs Parquet.

**Independent Test**: Run the full pipeline for any source → no .yaml files created in staging or registry directories → all entities stored in Parquet files only.

**Acceptance Scenarios**:

1. **Given** the pipeline running for any source, **When** extraction completes, **Then** staged entities are written to Parquet (not individual YAML files).
2. **Given** the pipeline running enrichment, **When** enrichment completes, **Then** enriched entities are written back to the same Parquet store (no YAML intermediaries).
3. **Given** the pipeline running commit, **When** commit completes, **Then** committed entities are in Parquet files in the registry (not individual YAML files).
4. **Given** the backend importing a registry, **When** import runs, **Then** it reads from Parquet files and does not require or expect YAML files.
5. **Given** a developer debugging, **When** they need to inspect an entity, **Then** the CLI `inspect` command reads from Parquet and displays the entity.

---

### User Story 2 — Embeddings Computed Once at Commit (Priority: P1)

As a system operator, I need entity embeddings to be computed exactly once — during the pipeline commit step — and stored alongside the entity data. The backend MUST NOT recompute embeddings during import. If an entity already has an embedding, it is used as-is.

**Why this priority**: Currently the backend recomputes embeddings for every entity during database import, which takes 10+ minutes for 7K entities in Docker. Embeddings should travel with the entity through the pipeline.

**Independent Test**: Run pipeline → commit stores entities with embeddings → import to database takes <30 seconds for 7K entities (no model loading).

**Acceptance Scenarios**:

1. **Given** the pipeline commit step, **When** an entity is committed, **Then** its embedding is computed from all entity information (name, description, type, unit, provenance, annotations) and stored in the entity record.
2. **Given** all entity types (elements, schemas, values, valuesets), **When** committed, **Then** each has an embedding vector stored alongside it.
3. **Given** the backend importing entities, **When** an entity has a pre-computed embedding, **Then** the backend stores it directly without recomputation.
4. **Given** the backend importing entities, **When** an entity is missing an embedding (legacy data), **Then** the backend computes it on demand and flags the entity for re-alignment.
5. **Given** the embedding computation, **When** building the embedding text, **Then** it uses all available information: provenance names, descriptions, semantic fields, ontology annotation labels — not just a single field.

---

### User Story 3 — Embedding Recomputation on Update (Priority: P1)

As a curator updating an entity, I need the embedding to be automatically recomputed when the entity's content changes — so that semantic search and alignment always reflect the current state.

**Why this priority**: Stale embeddings cause incorrect search results and alignment groupings.

**Independent Test**: Update an element's description via GraphQL mutation → embedding changes → semantic search reflects the new content.

**Acceptance Scenarios**:

1. **Given** a curator updating an element (description, unit, annotations), **When** the mutation completes, **Then** the entity's embedding is recomputed from the updated content.
2. **Given** a curator approving an annotation, **When** the annotation is added, **Then** the embedding is recomputed to include the annotation label.
3. **Given** the versioning mutation (creating a new version of an element), **When** the new version is committed, **Then** it gets a fresh embedding computed from its content.

---

### User Story 4 — Re-alignment on Missing Embeddings (Priority: P2)

As a system operator, I need the backend to detect entities with missing embeddings and trigger re-alignment for them — so that all entities participate in semantic search and cross-source alias detection.

**Why this priority**: Legacy entities imported before embedding computation may lack embeddings. These should be caught and processed.

**Independent Test**: Import an entity without an embedding → system detects it → computes embedding → triggers alignment check.

**Acceptance Scenarios**:

1. **Given** an entity imported without an embedding, **When** the backend detects this, **Then** it computes the embedding and stores it.
2. **Given** a newly embedded entity, **When** it has no alignment group, **Then** the system queues it for alignment comparison against entities from other sources.
3. **Given** the system processing a batch of unembedded entities, **When** embeddings are computed, **Then** the alignment check runs efficiently (not pairwise against all entities).

---

### User Story 5 — Unified Store Interface (Priority: P1)

As a developer working on any part of the system (library, backend, CLI), I need a single store abstraction that reads/writes Parquet — so that there is one way to access entities, not multiple paths depending on format.

**Why this priority**: Currently there are multiple code paths: FileEntityStore (YAML), ParquetStore, DatabaseBackend, and iter_staged. This causes bugs where one path is updated but another isn't.

**Independent Test**: All entity access (read, write, list, count, search) goes through a single store interface regardless of whether the caller is the pipeline, CLI, or backend.

**Acceptance Scenarios**:

1. **Given** the pipeline, **When** any stage reads or writes entities, **Then** it uses the unified store interface (not raw file I/O).
2. **Given** the CLI, **When** inspecting, listing, or counting entities, **Then** it uses the same store interface.
3. **Given** the alignment module, **When** loading entities for comparison, **Then** it uses the same store interface.
4. **Given** the enrichment module, **When** reading and writing entities, **Then** it uses the same store interface.

---

### Edge Cases

- What happens when a Parquet file is corrupted? The store detects read failure and reports it; the pipeline can re-extract from source.
- What happens when an entity has an embedding from a different model version? The system checks model compatibility and recomputes if mismatched.
- What happens when the embedding model is not available (no sentence-transformers)? Entities are stored without embeddings; a warning is logged; alignment is skipped for those entities.
- What happens when a batch of 1M entities needs embeddings? Chunked computation (10K at a time) to control memory.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST use Parquet as the sole storage format for all stages (staging, enrichment, commit, registry). No individual YAML files MUST be created during normal pipeline operation.
- **FR-002**: Every entity (element, schema, value, valueset) MUST have an embedding vector computed and stored at commit time.
- **FR-003**: The embedding MUST be computed from all available entity information: provenance names and descriptions, semantic fields (data_type, unit, pattern, description), and ontology annotation labels.
- **FR-004**: The backend MUST use pre-computed embeddings from the entity record when importing. It MUST NOT load the embedding model or recompute embeddings for entities that already have them.
- **FR-005**: When the backend encounters an entity without an embedding, it MUST compute one and flag the entity for re-alignment.
- **FR-006**: When an entity is updated via any mutation (update, approve annotation, version), the embedding MUST be recomputed from the updated content.
- **FR-007**: All entity access across pipeline, CLI, backend, enrichment, and alignment MUST go through a unified store interface.
- **FR-008**: The store interface MUST support: read, write, write_batch, list, count, exists, find_by_hash — all operating on Parquet.
- **FR-009**: Cross-reference resolution (schema properties → element sha256, valueset members → value sha256, element type_ref → schema sha256) MUST work with Parquet storage.
- **FR-010**: The ontology embedding index MUST be built from the pyoxigraph store directly, not from YAML cache files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero YAML files created during a full pipeline run (any source).
- **SC-002**: Backend import of 7K entities completes in under 30 seconds (no embedding model loading).
- **SC-003**: Every entity in the registry has an embedding vector (100% coverage).
- **SC-004**: Entity update via GraphQL results in embedding recomputation within the same request.
- **SC-005**: Registry storage for 1M+ entities uses less than 2GB (Parquet compression).
- **SC-006**: All pipeline stages, CLI commands, and backend operations use the same store interface (zero direct file I/O for entities).

## Scope Boundaries

### In Scope

- Parquet-only pipeline (extract, enrich, align, commit, transform)
- Embedding computation at commit for all entity types
- Embedding recomputation on entity update mutations
- Backend import using pre-computed embeddings
- Missing embedding detection and re-alignment trigger
- Unified store interface replacing FileEntityStore + ParquetStore + iter_staged
- Cross-reference resolution on Parquet
- Ontology index from pyoxigraph (already done in 039)

### Out of Scope

- Migrating existing YAML registries to Parquet (manual re-ingest is fine)
- Changing the PostgreSQL/pgvector backend storage (stays as-is)
- Distributed/parallel embedding computation
- Custom embedding models (all-MiniLM-L6-v2 remains the default)

## Assumptions

- Parquet read/write via pyarrow is faster than YAML for any batch size
- The existing embedding model (all-MiniLM-L6-v2, 384-dim) is sufficient
- Cross-reference resolution can work with in-memory Parquet DataFrames
- The Docker backend image includes the library with ParquetStore

## Dependencies

- Feature 039 (Robust Ingestion Pipeline) — provides ParquetStore, batch CLI, enrichment restructure
- pyarrow — already a library dependency
- sentence-transformers — for embedding computation (already available)
- pyoxigraph — for ontology index (already loaded)
