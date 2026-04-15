# Feature Specification: Cross-Source Alignment

**Feature Branch**: `041-cross-source-alignment`
**Created**: 2026-04-03
**Status**: Draft
**Input**: Improve ingest alignment so that duplicate elements across sources and datasets merge into single undata elements. Currently elements like roi_name appear separately for each OpenNeuro dataset instead of being aligned into one canonical element. The alignment pipeline should detect semantically equivalent elements, merge provenance, handle cross-source alignment, preserve source-specific metadata, and produce visible alignment groups.

## Clarifications

### Session 2026-04-03

- Q: Should all 8 adapters produce LinkML SchemaDefinitions so a unified SchemaView can be built for pre-alignment dedup? → A: Yes — all 8 adapters MUST produce LinkML SchemaDefinitions; build unified SchemaView per source for pre-serialization dedup.
- Q: Should intra-source dedup happen only at SchemaView level or also during post-commit alignment? → A: Both layers — SchemaView dedup during extraction (primary) + lightweight verification during alignment (safety net).
- Q: Should alignment create new merged entities or designate an existing source entity as canonical? → A: Entities with different ranges are different entities (separate sha256). For truly identical entities, designate one as canonical representative (Option B) — do not create unnecessary new entities. Only create a new merged entity when content must actually change (e.g., combining annotations from multiple sources).
- Q: How should alignment group membership be persisted? → A: Fields on each entity using sha256 hashes with graph-like relations. Canonical entities store `aligned_members` (list of member sha256 hashes). Member entities store `aligned_to` (canonical sha256 hash). Relations form a graph of edges between aligned entities.
- Q: How should candidate pairs be generated for cross-source alignment? → A: Both name blocking (normalized exact match) and embedding k-NN (vector similarity). Additionally, semantic/both search queries from users should be used to evaluate alignment — when search results reveal unaligned entities that appear related, flag them as alignment candidates for the next pipeline run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Intra-Source Deduplication (Priority: P1)

As a data engineer running the pipeline, I need elements that appear in multiple datasets within the same source (e.g., `roi_name` across 100 OpenNeuro datasets) to be merged into a single canonical element with combined provenance — so that the registry reflects true unique concepts, not per-dataset copies.

**Why this priority**: This is the most common and visible duplication problem. OpenNeuro alone produces thousands of duplicate elements because each dataset extracts the same column names independently. Fixing this has the highest impact on reducing element count.

**Independent Test**: Run pipeline for OpenNeuro → elements like `roi_name`, `participant_id`, and `age` each appear exactly once → provenance lists all contributing datasets → element count drops by 50%+ compared to current output.

**Acceptance Scenarios**:

1. **Given** elements extracted from 100 OpenNeuro datasets, **When** alignment runs, **Then** elements with identical names, data types, and compatible ranges are merged into a single element.
2. **Given** a merged element, **When** a user views it in the UI, **Then** the provenance section shows all contributing datasets (e.g., "openneuro/ds001, openneuro/ds002, ...").
3. **Given** elements with the same name but different data types or different ranges, **When** alignment runs, **Then** they remain separate entities (different identity) and are placed in related but distinct alignment groups, with a cross-reference noting the relationship.
4. **Given** elements with the same name, same data type, and same range (or no range), **When** alignment runs, **Then** they are merged by designating one as canonical and combining provenance from all contributing datasets.

---

### User Story 2 — Cross-Source Alignment (Priority: P1)

As a researcher browsing the registry, I need semantically equivalent elements from different sources (e.g., BIDS `age` and NDA `interview_age`) to be recognized as the same concept — so that I can see how a concept is represented across the neuroscience ecosystem.

**Why this priority**: Cross-source alignment is the core value proposition of the undata registry. Without it, researchers must manually discover that different sources use different names for the same concept.

**Independent Test**: Run pipeline for BIDS + NDA → `age` and `interview_age` appear in the same alignment group → the canonical element references both source representations → searching for "age" returns one unified result with cross-source provenance.

**Acceptance Scenarios**:

1. **Given** elements from different sources with different names but the same meaning, **When** alignment runs using name matching, embedding similarity, and shared ontology annotations, **Then** they are grouped into the same alignment group with a confidence score.
2. **Given** NDA elements with alias hints (e.g., `sex` aliased to `gender`), **When** alignment runs, **Then** alias hints boost similarity scores, increasing the chance of cross-source matches.
3. **Given** an alignment group containing elements from multiple sources, **When** a canonical element is produced, **Then** it preserves the ontology annotations from all contributing elements (union of annotations).
4. **Given** two elements that share an ontology annotation (e.g., both mapped to the same NCIT term), **When** alignment runs, **Then** their similarity score is boosted above the threshold.
5. **Given** elements with conflicting metadata (e.g., different units: "years" vs "months"), **When** alignment detects the conflict, **Then** the system flags the conflict in the alignment report rather than silently merging.

---

### User Story 3 — Alignment Visibility in UI (Priority: P2)

As a curator reviewing the registry, I need to see which source-level elements were merged into each canonical element — so that I can verify alignment quality and correct mistakes.

**Why this priority**: Alignment is an automated process that will make mistakes. Curators need visibility to verify and override decisions.

**Independent Test**: Browse any element in the UI → see an "Alignment" section showing the contributing source elements, their similarity scores, and the merge rationale.

**Acceptance Scenarios**:

1. **Given** a canonical element in the UI, **When** a curator views its detail page, **Then** an "Aligned From" section shows each contributing source element with its source, original name, and alignment confidence.
2. **Given** the alignment groups in the backend, **When** the browse page loads, **Then** element count reflects canonical (merged) elements, not raw source-level duplicates.
3. **Given** a curator who disagrees with an alignment, **When** they search for the element, **Then** they can see the full alignment group and identify which sources contributed.

---

### User Story 4 — All Entity Types Aligned (Priority: P2)

As a data engineer, I need alignment to work across all entity types (elements, schemas, values, valuesets) — not just elements — so that duplicate schemas, values, and valuesets from different sources are also merged.

**Why this priority**: Duplicate values and valuesets are common across sources (e.g., sex/gender valuesets in BIDS, NDA, and openMINDS contain overlapping members). Schemas also repeat across sources.

**Independent Test**: Run pipeline → duplicate values (e.g., "Male"/"Female" from multiple sources) are merged → duplicate schemas are merged → alignment report covers all entity types.

**Acceptance Scenarios**:

1. **Given** values extracted from multiple sources with the same label and value type, **When** alignment runs, **Then** they are merged into a single canonical value.
2. **Given** valuesets from different sources with overlapping members, **When** alignment runs, **Then** the system identifies them as related and merges them if member overlap exceeds 80%.
3. **Given** schemas from different sources with the same property structure, **When** alignment runs, **Then** they are merged into a canonical schema with combined provenance.

---

### User Story 5 — LinkML-First Adapter Uniformity (Priority: P1)

As a data engineer, I need all 8 adapters (BIDS, NWB, DANDI, openMINDS, AIND, ReproSchema, NDA, OpenNeuro) to produce LinkML SchemaDefinitions — so that a unified SchemaView can be built per source to deduplicate slots and aliases before entities are serialized to Parquet.

**Why this priority**: Currently 3 adapters (ReproSchema, NDA, OpenNeuro) bypass LinkML entirely, producing raw entities without the structural dedup that LinkML SchemaView provides. Slots with the same name across datasets within a source should be unified in SchemaView (which resolves aliases, slot_usage inheritance, and name collisions) before being classified into entities. This is the most effective place to catch intra-source duplicates — before they ever enter the pipeline.

**Independent Test**: Run each of the 8 adapters → each produces a valid LinkML SchemaDefinition → SchemaView can be constructed from it → duplicate slots across datasets within a source are unified in the SchemaView → entity count per source is lower than current output.

**Acceptance Scenarios**:

1. **Given** the ReproSchema adapter processing multiple instruments, **When** extraction runs, **Then** it produces a LinkML SchemaDefinition with instruments as classes and items as slots, and SchemaView unifies shared slots across instruments.
2. **Given** the NDA adapter processing multiple data structures, **When** extraction runs, **Then** it produces a LinkML SchemaDefinition with structures as classes and fields as slots, and SchemaView unifies fields that appear across structures (including alias-linked fields like sex/gender).
3. **Given** the OpenNeuro adapter processing multiple datasets, **When** extraction runs, **Then** it produces a LinkML SchemaDefinition with TSV columns as slots, and SchemaView unifies common columns (participant_id, age, sex) across datasets.
4. **Given** any adapter's SchemaDefinition, **When** SchemaView is built in memory, **Then** slot aliases are resolved so that aliased names point to the same canonical slot.
5. **Given** the unified SchemaView for a source, **When** entities are extracted from it, **Then** duplicate slots produce a single element with combined provenance from all classes/datasets that use that slot.

---

### Edge Cases

- What happens when two elements have identical names but fundamentally different semantics (e.g., `status` in clinical data vs `status` in imaging metadata)? The system should require ontology annotation agreement or high embedding similarity, not just name matching, to merge them.
- How does the system handle elements that were previously aligned but diverge after an update? Re-alignment should be triggered when entities are modified.
- What happens when alignment runs incrementally (new source added to existing registry)? New entities should be aligned against existing canonical entities without disrupting previous alignments.
- What happens when an alignment group grows very large (100+ contributing sources)? The provenance display should be paginated or summarized.
- How are alignment conflicts resolved when embedding similarity is high but ontology annotations disagree? The system should flag these as "uncertain" alignments for curator review.
- What happens when SchemaView dedup and post-commit alignment produce different groupings for the same entities? The alignment step treats SchemaView-unified entities as authoritative; it only adds new groupings, never splits what SchemaView already unified.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect duplicate elements within the same source using two layers: (a) primary dedup via LinkML SchemaView slot unification during extraction, and (b) a lightweight verification pass during post-commit alignment that catches any duplicates that escaped SchemaView resolution (e.g., slight naming variations not captured as aliases).
- **FR-002**: System MUST detect semantically equivalent elements across different sources using a multi-signal scoring approach: exact name match (highest weight), embedding cosine similarity, shared ontology annotations, and alias hint overlap.
- **FR-003**: System MUST produce a composite similarity score for each candidate pair, with configurable weights for each signal (name, embedding, ontology, alias).
- **FR-004**: System MUST merge provenance from all contributing source elements into the canonical element, preserving source identity, dataset path, and original element name.
- **FR-005**: System MUST preserve source-specific metadata (alias hints, descriptions, units, ranges) during merging, using a union strategy for list-type fields and selecting the most informative value for scalar fields.
- **FR-006**: System MUST produce an alignment report listing all alignment groups, their member elements, composite scores, and merge rationale.
- **FR-007**: System MUST support alignment across all entity types: elements, schemas, values, and valuesets.
- **FR-008**: System MUST handle incremental alignment — when new entities are added, they are aligned against existing canonical entities without re-processing the entire registry.
- **FR-009**: System MUST flag conflicting metadata (e.g., different units or incompatible ranges) as alignment conflicts for curator review rather than silently merging.
- **FR-010**: System MUST persist alignment group membership as sha256 hash-based graph relations on each entity: canonical entities store an `aligned_members` list of member sha256 hashes, and member entities store an `aligned_to` sha256 hash pointing to their canonical. The query interface MUST expose these relations so the UI can traverse the alignment graph.
- **FR-011**: System MUST support a configurable similarity threshold (default 0.7) below which entities are not aligned.
- **FR-012**: Elements with different ranges (different min/max or different valuesets) MUST remain separate entities — different ranges mean different identity. Alignment groups only contain entities with compatible (identical or absent) ranges. Provenance from identical entities is combined onto the designated canonical representative without creating a new entity.
- **FR-013**: System MUST re-align entities whose embeddings have been recomputed (due to content updates) in subsequent pipeline runs.
- **FR-014**: All 8 adapters (BIDS, NWB, DANDI, openMINDS, AIND, ReproSchema, NDA, OpenNeuro) MUST produce LinkML SchemaDefinitions as their output, ensuring a uniform extraction path through the shared LinkML extractor.
- **FR-015**: System MUST build a LinkML SchemaView in memory per source from the adapter's SchemaDefinition before extracting entities — leveraging SchemaView's slot resolution, alias unification, and inheritance traversal to deduplicate slots at the schema level.
- **FR-016**: Slots that appear in multiple classes within the same SchemaView (e.g., `participant_id` used by multiple OpenNeuro dataset classes) MUST be unified into a single slot definition, with all using classes recorded as provenance.
- **FR-017**: Slot aliases defined in the SchemaDefinition (e.g., NDA's sex→gender) MUST be resolved by SchemaView so that aliased slots map to the same canonical entity.
- **FR-018**: Cross-source alignment candidate generation MUST use two strategies: (a) name blocking — normalize names (lowercase, strip underscores/hyphens) and match exact, and (b) embedding k-nearest-neighbor — use pre-computed entity embeddings to find top-k most similar entities across sources.
- **FR-019**: When a user performs a semantic or combined search that returns multiple unaligned entities with high similarity scores, the system MUST flag those entities as alignment candidates for evaluation in the next pipeline run. This creates a feedback loop where search usage improves alignment over time.

### Key Entities

- **Alignment Group**: A graph of source-level entities that represent the same concept, stored as sha256-based edges on the entities themselves. The canonical entity holds `aligned_members` (list of member sha256 hashes); each member entity holds `aligned_to` (canonical sha256 hash). These hash-based relations form a traversable graph.
- **Canonical Entity**: The representative entity of an alignment group. For groups where all members are semantically identical (same name, type, range, annotations), one existing source entity is designated canonical — no new entity is created. For groups where members differ in annotations or provenance but share identity, a new merged entity is created only when content must change. Entities with different ranges remain separate entities and are NOT merged.
- **Alignment Score**: A composite score (0.0–1.0) computed from name similarity, embedding cosine similarity, ontology annotation overlap, and alias hint match. Each component has a configurable weight.
- **Alignment Conflict**: A flagged disagreement between source entities in an alignment group (e.g., different units, incompatible types) requiring curator review.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Total element count in the registry is significantly reduced compared to the unaligned state (currently ~926K elements) by merging truly identical elements and deduplicating via SchemaView. Target: at least 50% reduction for intra-source duplicates (OpenNeuro, NDA) while preserving elements that differ in range or type as separate entities.
- **SC-002**: Elements that exist in multiple OpenNeuro datasets (e.g., `roi_name`, `participant_id`) appear exactly once as a canonical element with provenance referencing all contributing datasets.
- **SC-003**: Known cross-source equivalences (e.g., BIDS `age` ↔ NDA `interview_age`, BIDS `sex` ↔ NDA `gender`) are correctly aligned with confidence scores above 0.7.
- **SC-004**: Alignment processing time for the full registry (926K entities) completes within 30 minutes on a standard workstation.
- **SC-005**: The UI displays alignment group membership for any entity within 2 seconds of page load.
- **SC-006**: Zero false merges for entities with different ontology annotations — entities are only merged when at least one additional signal (name, embedding, alias) agrees.
- **SC-007**: All entity types (elements, schemas, values, valuesets) have alignment groups, not just elements.

## Assumptions

- Entity embeddings are pre-computed during pipeline commit (Feature 040) and available for similarity comparison.
- Ontology annotations from the enrichment step are available for annotation-based matching.
- NDA alias hints are extracted during ingestion (Feature 039) and stored in semantic fields.
- The existing ParquetStore infrastructure supports reading and writing alignment group metadata.
- A "canonical" entity is an existing source entity designated as the group representative when all members are identical. A new entity is created only when merging requires content changes (e.g., combining annotations). Entities with different ranges are never merged — they remain separate.
- Alignment is a pipeline step that runs after commit and before transform.

## Scope Boundaries

**In scope**:
- Converting ReproSchema, NDA, and OpenNeuro adapters to produce LinkML SchemaDefinitions
- Building LinkML SchemaView per source for pre-serialization slot/alias deduplication
- Intra-source deduplication (same name + type within one source)
- Cross-source semantic alignment (different names, same concept across sources)
- Multi-signal scoring (name, embedding, ontology, alias)
- Provenance merging and range broadening
- Alignment report generation
- UI display of alignment group membership
- Search-driven alignment feedback (semantic search results flag alignment candidates)
- All entity types (elements, schemas, values, valuesets)

**Out of scope**:
- Manual curator override of alignment decisions (future curation feature)
- Automated alignment of transforms
- Machine learning model training for alignment improvement
- Alignment across different entity types (e.g., aligning an element to a value)
