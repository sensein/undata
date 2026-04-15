# Tasks: undata-library v2 — Content-Addressed RDF Property Model

**Feature**: `015-undata-library` | **Branch**: `015-undata-library-v2`
**Input**: Design documents from `/specs/015-undata-library/`

**User Stories**:
- US1 P1 — Validate library YAML (content-addressed format)
- US2 P1 — Ingest from raw schemas (offline, no backend)
- US3 P2 — Export from backend
- US4 P2 — Diff element provenance
- US5 P3 — Build index

---

## Phase 1: Setup (Core Hashing + Models)

**Purpose**: Content-addressed identity system — the foundation everything else builds on.

- [ ] T001 Rewrite `library/src/undata_library/models.py`: `SemanticIdentity` (ontology_term, data_type, unit, constraints), `ProvenanceEntry` (source, class, name, description, required, multivalued), `ElementRecord` (semantic: SemanticIdentity, provenance: list[ProvenanceEntry]), `SchemaRecord` (semantic: SchemaIdentity, provenance: list[SchemaProvenance]), `HashRegistryEntry`, `DataType` enum, `MappingFunctionType` enum per data-model.md
- [ ] T002 [P] Create `library/src/undata_library/hashing.py`: `canonical_json(semantic_dict)` → sorted keys, nulls omitted, compact JSON; `compute_sha256(canonical)` → 64-hex string; `generate_short_key(sha256_hex, registry)` → 6-char base36 key with collision check; `build_element_uri(attribute, key)` → full URI; `build_schema_uri(name, key)` → full URI
- [ ] T003 [P] Rewrite `library/library-schema.linkml.yaml`: define `ElementRecord`, `SemanticIdentity`, `ProvenanceEntry`, `SchemaRecord`, `SchemaIdentity`, `SchemaProvenance` classes with `class_uri` (rdf:Property, sh:NodeShape) and `slot_uri` annotations per data-model.md
- [ ] T004 [P] Create test fixtures in `library/tests/fixtures/`: `valid-element-v2.yaml` (semantic + 2 provenance entries), `valid-schema-v2.yaml` (properties + subclass_of + provenance), `invalid-element-no-datatype.yaml`, `invalid-element-bad-enum.yaml`, `multi-provenance-element.yaml` (3 sources for same semantic graph)
- [ ] T005 Write `library/tests/test_hashing.py`: (a) same semantic dict in different key order → same hash; (b) different semantic dicts → different hashes; (c) null fields omitted from canonical JSON; (d) 6-char key is alphanumeric; (e) collision detection extends to 7+ chars; (f) URI format matches `https://schema.undata.live/elements/{attr}_{key}`
- [ ] T006 Write `library/tests/test_models.py`: (a) valid ElementRecord parses; (b) missing data_type → ValidationError; (c) bad enum → ValidationError; (d) multiple provenance entries accepted; (e) SchemaRecord with properties + subclass_of parses
- [ ] T007 Run tests; verify all pass; commit Phase 1

---

## Phase 2: Foundational (Validation + Hash CLI)

**Purpose**: Validate the new format + compute hashes from CLI.

- [ ] T008 [US1] Rewrite `library/src/undata_library/validation.py`: validate YAML against v2 Pydantic models (ElementRecord, SchemaRecord); detect record type from `semantic` block structure; report structured violations
- [ ] T009 [US1] Update `library/src/undata_library/cli.py`: rewrite `validate` command for v2 format
- [ ] T010 Create `hash` CLI command in `library/src/undata_library/cli.py`: load YAML, compute semantic hash, display attribute name, 6-char key, full SHA-256, URI
- [ ] T011 [US1] Rewrite `library/tests/test_validation.py`: (a) valid v2 element passes; (b) valid v2 schema passes; (c) missing data_type fails; (d) bad enum fails; (e) multi-provenance element passes; (f) directory scan finds all violations
- [ ] T012 Run tests; verify `undata-library validate` and `undata-library hash` work; commit Phase 2

---

## Phase 3: User Story 2 — Ingest from Raw Schemas (P1)

**Goal**: Read raw schema files (BIDS/NWB/AIND/DANDI/openMINDS) → extract semantic graphs → compute content hashes → merge provenance → write element + schema files.
**Independent Test**: `undata-library ingest --source bids --path ../ingestion/schemas/` produces `elements/` files in v2 format with content-addressed filenames.

- [ ] T013 [US2] Create `library/src/undata_library/ingest.py`: `ingest_source(source_name, schema_path, library_path)` function that: (a) delegates to source-specific extractor; (b) computes semantic hash per element; (c) if element file exists with same hash, appends provenance entry; (d) if new hash, creates new file; (e) updates `hash-registry.yaml`
- [ ] T014 [P] [US2] Create source extractors in `library/src/undata_library/extractors/`: `bids.py` (use bidsschematools load_code), `dandi.py` (use dandischema load_code), `aind.py` (use fixed adapter with $defs recursion), `nwb.py` (direct YAML parse of neurodata_type_def), `openminds.py` (JSON-LD file parse); each returns `list[tuple[SemanticIdentity, ProvenanceEntry]]`
- [ ] T015 [US2] Add `ingest` CLI command: `--source NAME --path DIR --library-path DIR`; calls `ingest_source()`; prints element/schema counts and merge stats
- [ ] T016 [US2] Write `library/tests/test_ingest.py`: (a) ingest BIDS fixture → elements created with content-addressed names; (b) ingest same source twice → provenance merged, no duplicate files; (c) ingest two different sources with same-named element → single file with 2 provenance entries if semantic graph matches; (d) different semantic graphs → separate files
- [ ] T017 [US2] Delete old `library/elements/*.yaml` (v1 format); run `undata-library ingest` for all 5 sources; verify all files pass `undata-library validate`
- [ ] T018 Commit Phase 3

---

## Phase 4: Schema Shapes

**Goal**: Extract class shapes from ingested sources, write `schemas/` files.

- [ ] T019 [US2] Extend `ingest.py` with `ingest_schemas(source_name, schema_path, library_path)`: extract class definitions, compute schema hashes (sorted property URIs + subclass_of), merge provenance, write to `schemas/`
- [ ] T020 [P] [US2] Extend each source extractor with `extract_classes()` → `list[tuple[SchemaIdentity, SchemaProvenance]]`: BIDS (vocabulary types), AIND ($defs models with property URIs), NWB (neurodata_type_def groups with neurodata_type_inc inheritance), openMINDS (JSON-LD class definitions)
- [ ] T021 [US2] Write `library/tests/test_schemas.py`: (a) schema hash is deterministic; (b) subclass_of tracked for NWB inheritance; (c) same class from two sources → single schema file with 2 provenance entries; (d) AIND Device subclasses reference parent schema
- [ ] T022 [US2] Run ingestion for schemas on all 5 sources; build `hash-registry.yaml` with both elements and schemas sections
- [ ] T023 Commit Phase 4

---

## Phase 5: User Story 3+4+5 — Export, Diff, Index

- [ ] T024 [US3] Rewrite `library/src/undata_library/export.py`: fetch from backend API, compute semantic hash, merge provenance into existing element files or create new; write schema files from DynamicSchema endpoint
- [ ] T025 [US4] Rewrite `library/src/undata_library/diff.py`: diff provenance entries (which sources attest this element), diff semantic changes (if element hash changed across versions)
- [ ] T026 [US4] Update `diff` CLI: `--format text|json`; show provenance additions/removals and semantic changes
- [ ] T027 [US5] Rewrite `library/src/undata_library/index.py`: scan elements/ + schemas/ + mappings/; count unique elements, schemas, cross-source elements (>1 provenance); write `index.yaml`
- [ ] T028 Update `library/tests/test_diff.py` and `library/tests/test_index.py` for v2 format
- [ ] T029 Commit Phase 5

---

## Phase 6: Polish

- [ ] T030 Run `undata-library validate elements/ schemas/` on full library; fix any violations
- [ ] T031 Run full test suite; verify all pass
- [ ] T032 Update `library/README.md` with v2 format documentation, examples, content-addressing explanation
- [ ] T033 Update CLAUDE.md
- [ ] T034 Final commit and push

---

## Dependencies

```
T001 → T002, T003, T004 (parallel) → T005, T006 (parallel) → T007
T008, T009, T010 → T011 → T012
T013, T014 (parallel) → T015 → T016 → T017 → T018
T019, T020 (parallel) → T021 → T022 → T023
T024, T025, T026, T027 (parallel) → T028 → T029
T030 → T031 → T032 → T033 → T034
```

## Parallel Execution Per Phase

**Phase 1**: T002, T003, T004 [P] after T001 → T005, T006 [P] → T007
**Phase 3**: T014 [P] after T013 → T015 → T016 → T017
**Phase 4**: T020 [P] after T019 → T021 → T022
**Phase 5**: T024, T025, T026, T027 [P] → T028

## Implementation Strategy

1. **MVP** (Phase 1-2): Core hashing + validation. Proves the content-addressed model works.
2. **Ingestion** (Phase 3-4): Populate library from all 5 sources. Validates dedup.
3. **Tools** (Phase 5): Export/import/diff/index. Enables round-trip with backend.
4. **Polish** (Phase 6): Documentation, full validation, cleanup.

**Expected outcome**: 9,629 v1 elements → ~2,000-4,000 deduplicated v2 elements + schemas with inheritance.
