# Research: Cross-Source Alignment

**Date**: 2026-04-03 | **Feature**: 041-cross-source-alignment

## R1: LinkML SchemaView for Slot Deduplication

**Decision**: Use `linkml_runtime.utils.schemaview.SchemaView` to traverse and deduplicate slots across classes within each source's SchemaDefinition before entity extraction.

**Rationale**: SchemaView provides `all_slots()`, `get_slot()`, `slot_usage_for_class()`, and `get_classes_by_slot()` — exactly the APIs needed to identify shared slots across classes and resolve aliases. Currently the codebase builds SchemaDefinitions but never constructs a SchemaView from them. The existing `add_slot()` dedup check (`if name in schema.slots: return`) is a basic guard but doesn't handle aliases or cross-class slot reuse analysis.

**Alternatives considered**:
- Manual dict-based dedup (current approach) — works for exact name matches but misses alias resolution
- Post-extraction dedup in alignment — too late; entities already have separate sha256 hashes

## R2: Adapter Conversion Strategy (ReproSchema, NDA, OpenNeuro)

**Decision**: Convert all 3 non-LinkML adapters to produce SchemaDefinitions using the existing `linkml_builder` helpers.

**Rationale**: The existing builder functions (`build_schema()`, `add_slot()`, `add_class()`, `add_enum()`) handle the common patterns. Each adapter's domain maps naturally to LinkML:
- **ReproSchema**: Activities → classes, items → slots, response options → enums
- **NDA**: Structures → classes, fields → slots, coded values → enums, aliases → slot aliases
- **OpenNeuro**: Each TSV file type → class, columns → slots, categorical values → enums

**Complexity assessment**:
- ReproSchema: Medium — well-structured JSON-LD, clean mapping
- NDA: Medium-High — must preserve existing dedup logic as pre-LinkML consolidation
- OpenNeuro: High — TSV type inference is heuristic; needs careful handling of datasets-as-classes

**Alternatives considered**:
- Keep direct extraction for NDA/OpenNeuro, use alignment for dedup — loses SchemaView benefits
- Build separate SchemaView per dataset (OpenNeuro) — too granular, defeats the purpose

## R3: Cross-Source Candidate Generation

**Decision**: Two-phase blocking strategy: (1) name normalization blocking, (2) embedding k-NN search.

**Rationale**: With 370K+ entities post-dedup, O(n²) pairwise comparison is infeasible (~137 billion pairs). Name blocking reduces to O(n) for exact matches. Embedding k-NN with a vector index (e.g., numpy dot product on pre-computed embeddings, or hnswlib) reduces semantic matching to O(n·k) where k is a small constant (e.g., 10).

**Performance estimate**: 370K entities × 384 dimensions × 10 neighbors = ~15 seconds with numpy matrix multiply. Acceptable within the 30-minute budget.

**Alternatives considered**:
- Name blocking only — misses cross-name equivalences (age ↔ interview_age)
- Full vector index (HNSW) — adds a dependency; numpy matrix ops are sufficient at this scale

## R4: Alignment Group Persistence

**Decision**: Store `aligned_to` and `aligned_members` fields on entities in the semantic JSON, using sha256 hashes as graph edges.

**Rationale**: This avoids a separate alignment table and makes alignment relations queryable through the existing entity query paths. The graph structure (canonical → members, member → canonical) enables both directions of traversal. Storing in semantic JSON means ParquetStore schema doesn't need new columns — the fields are part of the JSON blob.

**Alternatives considered**:
- Separate Parquet table for alignment groups — adds complexity, requires joins
- Relational DB-only (PostgreSQL foreign keys) — doesn't persist in library pipeline output

## R5: Search-Driven Alignment Feedback

**Decision**: When semantic search returns 2+ unaligned entities with similarity > 0.8, record them as alignment candidates in a `alignment_candidates.parquet` file for the next pipeline run.

**Rationale**: User search behavior is a strong signal for missed alignments. Recording candidates is cheap (append-only Parquet) and the feedback loop improves alignment quality over time without requiring manual curation.

**Alternatives considered**:
- Real-time alignment during search — too expensive, blocks search response
- Manual curator flagging only — doesn't scale, misses patterns

## R6: Canonical Entity Selection

**Decision**: For identical entities (same semantic content), designate the one with the earliest `created_at` timestamp as canonical. For entities requiring content merge (e.g., combining annotations from multiple sources), create a new entity only when the merged content differs from all existing members.

**Rationale**: Earliest-first is deterministic and stable across runs. Avoiding unnecessary new entities keeps the registry lean and preserves content-addressed identity — if the content hasn't changed, the sha256 shouldn't change.

**Alternatives considered**:
- Random selection — non-deterministic, changes across runs
- Most-annotated entity — unstable as annotations evolve
- Always create new merged entity — wasteful when entities are identical
