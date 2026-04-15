# Tasks: Cross-Source Alignment

**Input**: Design documents from `specs/041-cross-source-alignment/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup

**Purpose**: Add dependencies and prepare shared infrastructure for alignment

- [X] T001 Add linkml-runtime SchemaView import capability — verify `from linkml_runtime.utils.schemaview import SchemaView` works in library/src/undata_library/adapters/extractor.py
- [X] T002 Add alias support to `add_slot()` in library/src/undata_library/adapters/linkml_builder.py — accept optional `aliases: list[str]` parameter that sets `slot.aliases` on the SlotDefinition

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: SchemaView-based extraction and multi-signal scoring — required before all user stories

- [X] T003 Rewrite `extract_from_schema_definition()` in library/src/undata_library/adapters/extractor.py to build a SchemaView from the SchemaDefinition, then use `schemaview.all_slots()` and `schemaview.get_classes_by_slot()` to produce deduplicated entities with combined provenance from all classes that use each slot
- [X] T004 Update library/src/undata_library/adapters/linkml.py `_extract_from_dict()` to resolve slot aliases via SchemaView — when SchemaView reports aliases for a slot, map all alias names to the same canonical slot entity
- [X] T005 Add `compute_alignment_score()` function in library/src/undata_library/similarity.py implementing the 4-signal weighted scoring: name_sim (0.3), embedding_sim (0.3), ontology_overlap (0.25), alias_match (0.15) — returns AlignmentScore dict per contract
- [X] T006 Add `normalize_name()` helper in library/src/undata_library/similarity.py — lowercase, strip underscores/hyphens/spaces, normalize unicode — used for name blocking in candidate generation
- [X] T007 [P] Add alignment candidate Parquet schema to library/src/undata_library/storage/parquet_store.py — `CANDIDATE_SCHEMA` with fields: entity_a, entity_b, similarity, source, created_at, resolved — and `write_candidates()` / `read_candidates()` methods

---

## Phase 3: User Story 5 — LinkML-First Adapter Uniformity (P1)

**Goal**: All 8 adapters produce LinkML SchemaDefinitions; SchemaView deduplicates slots per source

**Independent Test**: Run each adapter → each produces a valid SchemaDefinition → SchemaView unifies shared slots → entity count per source is lower than current

- [X] T008 [US5] Implement `to_linkml()` in library/src/undata_library/adapters/reproschema.py — map activities → classes, items → slots (with min/max from responseOptions), response options → enums with permissible_values; remove manual ClassifiedEntity construction from extract()
- [X] T009 [US5] Implement `to_linkml()` in library/src/undata_library/adapters/nda.py — map structures → classes, fields → slots (with aliases from NDA API `aliases` field as slot.aliases), valueRange → min/max on slots, coded values (notes) → enums; preserve dedup logic as pre-LinkML slot consolidation before building SchemaDefinition
- [X] T010 [US5] Implement `to_linkml()` in library/src/undata_library/adapters/openneuro.py — map each TSV file type → class, columns → slots (with type inference), JSON sidecar metadata → slot annotations (units, min/max), categorical values → enums; unify common columns (participant_id, age, sex) as shared slots across dataset classes
- [X] T011 [US5] Implement `to_linkml()` in library/src/undata_library/adapters/bids.py — convert existing direct extraction to build SchemaDefinition via linkml_builder, mapping BIDS objects/rules → classes, fields → slots; call extract_from_schema_definition() instead of manual entity construction
- [X] T012 [P] [US5] Update library/src/undata_library/adapters/base.py — make `to_linkml()` abstract method on BaseAdapter with return type `SchemaDefinition`; update `extract()` default implementation to call `to_linkml()` → `extract_from_schema_definition()`
- [X] T013 [US5] Update each of the 5 existing LinkML adapters (nwb.py, dandi.py, openminds.py, aind.py) to pass aliases through `add_slot()` where applicable — review each adapter for alias opportunities (e.g., openminds has short_name vs full URI)
- [X] T014 [US5] Integration test: run all 8 adapters and verify each produces a valid SchemaDefinition with >0 classes and >0 slots — compare entity counts before/after SchemaView dedup

---

## Phase 4: User Story 1 — Intra-Source Deduplication (P1)

**Goal**: Elements like roi_name across 100 OpenNeuro datasets merge into a single canonical element

**Independent Test**: Run pipeline for OpenNeuro → roi_name, participant_id, age each appear exactly once → provenance lists all contributing datasets

- [X] T015 [US1] Rewrite `align_entities()` in library/src/undata_library/align.py — new signature per contract: accept registry_path, entity_types, threshold, weights, dry_run, backend; implement intra-source dedup pass that groups entities by (source, name, data_type, range) and designates canonical (earliest created_at)
- [X] T016 [US1] Implement canonical designation logic in library/src/undata_library/align.py — for identical entities: designate existing entity as canonical, set `aligned_members` on canonical and `aligned_to` on members; for entities requiring content merge: create new entity only when merged content differs
- [X] T017 [US1] Implement provenance merging in library/src/undata_library/align.py — combine provenance lists from all group members onto the canonical entity, preserving source identity, dataset path, and original element name
- [X] T018 [US1] Add `update_alignment_fields()` method to library/src/undata_library/storage/parquet_store.py — bulk update entities with aligned_to, aligned_members, alignment_score, alignment_signals in their semantic JSON
- [X] T019 [US1] Implement range compatibility check in library/src/undata_library/align.py — entities with different min/max or different valuesets MUST NOT be merged; entities with identical or absent ranges are compatible
- [X] T020 [US1] Add lightweight intra-source verification pass in library/src/undata_library/align.py — after SchemaView dedup, scan committed entities for remaining duplicates (slight naming variations not caught by SchemaView)
- [X] T021 [US1] Update CLI `align` subcommand in library/src/undata_library/cli.py — add --threshold, --weights, --dry-run, --entity-types flags; output alignment report summary to console
- [X] T022 [US1] Integration test: run OpenNeuro pipeline → align → verify participant_id appears once with provenance from all datasets, and elements with different ranges remain separate

---

## Phase 5: User Story 2 — Cross-Source Alignment (P1)

**Goal**: BIDS `age` and NDA `interview_age` recognized as same concept across sources

**Independent Test**: Run BIDS + NDA pipeline → age and interview_age in same alignment group → search for "age" returns one unified result

- [X] T023 [US2] Implement name blocking candidate generation in library/src/undata_library/align.py — use normalize_name() to group entities by normalized name across all sources; each name group becomes a candidate set
- [X] T024 [US2] Implement embedding k-NN candidate generation in library/src/undata_library/align.py — load all entity embeddings into numpy matrix, compute dot product for top-k (k=10) neighbors per entity across different sources; add pairs above threshold to candidate set
- [X] T025 [US2] Implement cross-source alignment pass in library/src/undata_library/align.py — for each candidate pair: compute_alignment_score(), apply threshold filter, form groups via union-find, check range compatibility, detect conflicts
- [X] T026 [US2] Implement conflict detection in library/src/undata_library/align.py — flag pairs where embedding similarity is high but ontology annotations disagree, or units differ (years vs months); store conflicts in alignment report
- [X] T027 [US2] Implement alias hint boosting in library/src/undata_library/similarity.py — when two entities share alias_hints entries (e.g., both have "nda_alias:gender"), set alias signal to 0.95
- [X] T028 [US2] Implement ontology annotation overlap signal in library/src/undata_library/similarity.py — compute Jaccard similarity of ontology annotation URIs between two entities; return as ontology signal (0-1)
- [X] T029 [US2] Generate alignment report in library/src/undata_library/align.py — produce AlignmentReport dict per contract with total_entities_processed, alignment_groups, canonical_entities, member_entities, unaligned_entities, conflicts, entity_type_breakdown; write to alignment-report.yaml
- [X] T030 [US2] Implement incremental alignment mode in library/src/undata_library/align.py — when aligning, skip entities that already have `aligned_to` or `aligned_members` set; only process new/unaligned entities against existing canonical entities; add `--incremental` flag to CLI (FR-008)
- [X] T031 [US2] Implement re-alignment trigger in library/src/undata_library/align.py — detect entities whose embedding was recomputed after last alignment (compare embedding timestamp vs alignment timestamp); clear their alignment fields and re-process them (FR-013)
- [X] T032 [US2] Integration test: run BIDS + NDA pipeline → align → verify age↔interview_age and sex↔gender are in same alignment groups with scores above 0.7

---

## Phase 6: User Story 3 — Alignment Visibility in UI (P2)

**Goal**: Curators can see which source elements merged into each canonical element

**Independent Test**: Browse any element in UI → "Aligned From" section shows contributing source elements with scores

- [X] T033 [US3] Add alignment fields to backend DB models in backend/src/db/models.py — add `aligned_to` (nullable string), `aligned_members` (JSON array), `alignment_score` (nullable float) columns to Element, Schema, Value, ValueSet tables
- [X] T034 [US3] Update database import in backend/src/storage/database_backend.py — when importing entities from ParquetStore, read and store aligned_to, aligned_members, alignment_score from entity semantic JSON
- [X] T035 [US3] Add alignment resolvers to backend/src/graphql/resolvers.py — for each entity type, add `alignedTo` resolver (fetch entity by sha256), `alignedMembers` resolver (fetch list by sha256s), `alignmentScore` field
- [X] T036 [P] [US3] Add GraphQL queries in frontend/graphql/queries.ts — add `alignedTo { sha256 name source }` and `alignedMembers { sha256 name source }` fragments to element/schema/value/valueset detail queries
- [X] T037 [US3] Add "Aligned From" section to frontend/app/elements/[id]/page.tsx — show table of aligned member entities with source, original name, and alignment score; show "Canonical for N entities" badge if entity is canonical; paginate if >20 members
- [X] T038 [P] [US3] Add alignment section to frontend/app/schemas/[id]/page.tsx, frontend/app/values/[id]/page.tsx, and frontend/app/valuesets/[id]/page.tsx — same pattern as element detail page
- [X] T039 [US3] Update browse pages (elements, schemas, values, valuesets) to show canonical count vs total count — e.g., "1,234 canonical elements (from 5,678 source elements)"

---

## Phase 7: User Story 4 — All Entity Types Aligned (P2)

**Goal**: Alignment works for schemas, values, and valuesets — not just elements

**Independent Test**: Run pipeline → duplicate values (Male/Female) merged → duplicate schemas merged → alignment report covers all types

- [X] T040 [US4] Extend alignment passes in library/src/undata_library/align.py to iterate over all entity types — apply intra-source dedup and cross-source alignment to schemas (by property structure), values (by label + value type), and valuesets (by member overlap ≥80%)
- [X] T041 [US4] Implement valueset alignment heuristic in library/src/undata_library/align.py — compute Jaccard similarity of member sha256 sets between valuesets; merge if overlap ≥ 80%
- [X] T042 [US4] Implement schema alignment in library/src/undata_library/align.py — compare schemas by their properties list (set of property sha256 hashes); merge if property sets match
- [X] T043 [US4] Integration test: run all 8 sources → align → verify "Male"/"Female" values from BIDS+NDA+openMINDS are merged; verify sex/gender valuesets are merged; verify alignment report shows per-type stats

---

## Phase 8: Search-Driven Feedback (Cross-Cutting)

**Goal**: Semantic search results flag unaligned entities as alignment candidates

- [X] T044 Add alignment candidate recording to search resolver in backend/src/graphql/resolvers.py — after semantic/both search returns results, if 2+ unaligned entities have similarity > 0.8, insert pairs into alignment_candidates table
- [X] T045 Add alignment_candidates table to backend/src/db/models.py — entity_a (string), entity_b (string), similarity (float), source (string), created_at (datetime), resolved (bool)
- [X] T046 Add `read_search_candidates()` to library/src/undata_library/align.py — at start of alignment, load unresolved candidates from alignment_candidates.parquet and include them in candidate generation; mark as resolved after evaluation
- [X] T047 Update search page frontend/app/search/page.tsx — show small indicator when search results contain potential alignment candidates (e.g., "2 potential alignments detected")

---

## Phase 9: Polish & Integration

**Purpose**: End-to-end validation, eval record, and cleanup

- [X] T048 Run full pipeline across all 8 sources with alignment enabled — record entity counts before/after alignment in eval-record.md per constitution
- [X] T049 Verify alignment report: confirm known cross-source pairs (age↔interview_age, sex↔gender) aligned; confirm no false merges for entities with different ranges
- [X] T050 Performance validation: time full alignment of registry and verify <30 minutes; document in eval-record.md
- [X] T051 Fix any ruff lint/format issues across all modified files — run `uv run ruff check --fix` and `uv run ruff format` in library/ and backend/
- [X] T052 Verify frontend builds cleanly — run `pnpm lint && pnpm build` in frontend/
- [X] T053 Update library/src/undata_library/cli.py pipeline command to include alignment as default post-commit step — `pipeline --source X` runs extract→enrich→commit→align→transform

---

## Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational) → all user stories

US5 (LinkML adapters) → US1 (Intra-source dedup) → US2 (Cross-source alignment)
                                                       ↓
                                                   US4 (All entity types)
                                                       ↓
                                                   US3 (UI visibility)
                                                       ↓
                                                   Phase 8 (Search feedback)
```

US5 must complete first (adapters produce SchemaDefinitions).
US1 depends on US5 (SchemaView dedup feeds into alignment).
US2 depends on US1 (cross-source uses same infrastructure).
US3 and US4 can run in parallel after US2.
Phase 8 depends on US2 + US3.

## Parallel Execution Opportunities

**Within Phase 3 (US5)**: T008, T009, T010, T011 can run in parallel (different adapter files)
**Within Phase 6 (US3)**: T036 and T038 can run in parallel (different frontend files)
**Within Phase 7 (US4)**: T040, T041, T042 can run in parallel (different alignment heuristics, same file but independent functions)

## Implementation Strategy

**MVP**: Phase 1 + Phase 2 + US5 + US1 — delivers SchemaView dedup and intra-source alignment. This alone should reduce OpenNeuro element count by 50%+.

**Increment 2**: US2 — adds cross-source alignment (age↔interview_age). Core value proposition.

**Increment 3**: US3 + US4 — UI visibility and all entity types. Makes alignment results accessible.

**Increment 4**: Phase 8 — search feedback loop. Continuous improvement.
