# Tasks: Rich Data Element Model

**Feature**: `018-rich-data-model` | **Branch**: `018-rich-data-model`

**User Stories** (mapped from FRs):
- US1 — Enriched SemanticIdentity + PROV-O Provenance (FR-001 to FR-007) ✅
- US2 — Underscore Entry Reclassification (FR-008 to FR-010) ✅
- US3 — Ontology Cache + Verification (FR-011 to FR-014) ✅
- US4 — Semantic Similarity + Alias Detection (FR-019 to FR-022) ✅
- US5 — Semantic Embedding Layer (FR-015 to FR-018)
- US6 — Enrichment Pipeline (FR-023 to FR-029)
- US7 — Alignment Pipeline (FR-030 to FR-033)
- US8 — Pipeline Orchestration (FR-034 to FR-036)

---

## Phase 1: Setup

- [X] T001 Add `sentence-transformers` to `library/pyproject.toml` optional dependencies (`[similarity]` extra); add `requests` to base dependencies for OLS API in `library/pyproject.toml`
- [X] T002 [P] Create `library/ontology-cache/` directory with `.gitkeep`; add `ontology-cache/*.yaml` to `.gitignore` (cache is generated, not committed — only the fetch script is committed)

---

## Phase 2: Foundational — Model + Hash Updates

- [X] T003 Update `library/src/undata_library/models.py`: add `ResponseOption` (value, label, ontology_term) model; add `response_options: list[ResponseOption] | None`, `question_text: str | None`, `value_domain: str | None`, `min_value: float | None`, `max_value: float | None` to `SemanticIdentity`
- [X] T004 [P] Update `library/src/undata_library/models.py`: add `generated_at: str | None`, `attributed_to: str | None`, `activity: str | None`, `derived_from: str | None` to `ProvenanceEntry`; add `ActivityType` enum (ingestion, curation, enrichment, migration)
- [X] T005 Update `library/src/undata_library/hashing.py`: include `min_value`, `max_value`, `response_options` (sorted by value) in canonical_json when present; EXCLUDE `question_text` and `value_domain`
- [X] T006 [P] Update `library/library-schema.linkml.yaml`: add `ResponseOption` class, new slots on `SemanticIdentity` and `ProvenanceEntry`, `ActivityType` enum
- [X] T007 Update test fixtures in `library/tests/fixtures/`: create `valid-element-rich.yaml` with response_options + min/max + PROV-O provenance fields
- [X] T008 Write tests in `library/tests/test_rich_models.py`: (a) ResponseOption parses; (b) min_value/max_value in hash; (c) question_text excluded from hash; (d) PROV-O provenance fields parse; (e) activity enum validates
- [X] T009 Run tests; commit Phase 2

---

## Phase 3: US1 — Enriched Extractors + PROV-O Ingestion

**Goal**: Extractors populate new fields; provenance entries include PROV-O metadata.

- [X] T010 [US1] Update `library/src/undata_library/ingest.py`: auto-populate `generated_at` (datetime.now UTC), `attributed_to` (urn:undata:ingestion-pipeline), `activity` (ingestion) on every provenance entry during ingestion
- [X] T011 [P] [US1] Update `library/src/undata_library/extractors/bids.py`: extract `enum` values as `response_options` (list of ResponseOption with value + label); detect numeric fields for `min_value`/`max_value` from BIDS schema constraints
- [X] T012 [P] [US1] Update `library/src/undata_library/extractors/aind.py`: extract `enum` as `response_options`; extract `minimum`/`maximum` from JSON Schema constraints as `min_value`/`max_value`; extract `title` as `question_text`
- [X] T013 [P] [US1] Update `library/src/undata_library/extractors/dandi.py`: extract Pydantic field `ge`/`le`/`gt`/`lt` validators as `min_value`/`max_value`; extract enum classes as `response_options`
- [X] T014 [P] [US1] Update `library/src/undata_library/extractors/nwb.py`: extract `quantity` constraints as `min_value`/`max_value` where available
- [X] T015 [US1] Re-ingest all 5 sources; verify elements now have response_options, min/max, PROV-O fields; run `undata-library validate elements/` — 0 violations
- [X] T016 Commit Phase 3

---

## Phase 4: US2 — Underscore Reclassification

**Goal**: AIND `_Abcam` etc. filtered from elements, reclassified as ValueConcepts.

- [X] T017 [US2] Update `library/src/undata_library/extractors/aind.py`: in `extract_aind()`, detect `$defs` names starting with `_`; instead of creating elements, yield ValueConcept tuples with source-qualified tag `aind.{schema}.{parent_class}.{name_without_underscore}`
- [X] T018 [US2] Update `library/src/undata_library/ingest.py`: accept mixed element + value tuples from extractors; route values to `values/` directory
- [X] T019 [US2] Re-ingest AIND sources; verify element count decreases and value count increases
- [X] T020 [US2] Write test: AIND extractor with `_Abcam` fixture → produces ValueConcept not Element
- [X] T021 Commit Phase 4

---

## Phase 5: US3 — Ontology Cache + Verification

**Goal**: Bundled ontology term cache; `verify` and `ontology refresh` CLI commands.

- [X] T022 [US3] Create `library/src/undata_library/ontology_cache.py`: `OntologyCache` class with `load(ontology_name)`, `lookup(term_uri)` → `{label, synonyms, parents, deprecated}`, `save(ontology_name, terms)`
- [X] T023 [US3] Create `library/src/undata_library/ontology_fetch.py`: `fetch_ontology(name, ols_base_url)` → downloads term labels + parents from OLS API for NCIT, PATO, HP, OBI, NCBITaxon; writes to `ontology-cache/{name}.yaml`
- [X] T024 [US3] Create `library/scripts/build-ontology-cache.py`: script to fetch initial cache for all 5 ontologies; run once to populate `ontology-cache/`
- [X] T025 [US3] Create `library/src/undata_library/verify.py`: `verify_elements(elements_dir, cache)` → for each element with ontology_term: check existence in cache, compute label similarity (difflib.SequenceMatcher), check deprecated flag; return list of warnings
- [X] T026 [US3] Add `verify` CLI command: `undata-library verify [PATH]` — loads cache, scans elements, reports misalignments
- [X] T027 [US3] Add `ontology refresh` CLI command: `undata-library ontology refresh [--ontology NAME]` — calls fetch, updates cache
- [X] T028 [US3] Write tests: (a) cache lookup returns correct term; (b) verify catches missing term; (c) verify catches deprecated term; (d) verify passes for valid term
- [X] T029 Commit Phase 5

---

## Phase 6: US4 — Semantic Similarity + Alias Detection

**Goal**: Compute element similarity; detect alias candidates with SKOS relations.

- [X] T030 [US4] Create `library/src/undata_library/similarity.py`: `compute_similarity(elem_a, elem_b)` → returns `SimilarityResult` with `score: float`, `relation: str` (SKOS), `components: {name_sim, ontology_match, range_overlap, valueset_jaccard}`
- [X] T031 [P] [US4] Implement `name_embedding_similarity(name_a, name_b)` using sentence-transformers all-MiniLM-L6-v2 (lazy-loaded, cached); fallback to difflib if sentence-transformers not installed
- [X] T032 [P] [US4] Implement `range_overlap_score(min_a, max_a, min_b, max_b)` → intersection / union of numeric ranges; return 0.0 if no overlap, 1.0 if identical
- [X] T033 [P] [US4] Implement `valueset_jaccard(choices_a, choices_b)` → Jaccard similarity of response_option values; handle ValueConcept URIs and raw strings
- [X] T034 [US4] Implement SKOS relation mapping: `map_to_skos(score, range_subsumption)` → exactMatch (≥0.95), closeMatch (0.8-0.95), broadMatch/narrowMatch (subsumption), relatedMatch (0.5-0.8)
- [X] T035 [US4] Create `library/src/undata_library/alias_detection.py`: `detect_aliases(elements_dir, cache, threshold=0.5)` → scan all elements, compute pairwise similarity (optimized: skip pairs with different data_type), output candidate pairs sorted by score
- [X] T036 [US4] Add `similarity` CLI command: `undata-library similarity FILE_A FILE_B` — prints score, relation, components
- [X] T037 [US4] Add `detect-aliases` CLI command: `undata-library detect-aliases [PATH] [--threshold N]` — outputs candidate pairs as YAML or TSV
- [X] T038 [US4] Write tests: (a) identical elements → exactMatch 1.0; (b) same name different type → relatedMatch; (c) overlapping ranges → closeMatch; (d) shared valueset → score boost; (e) no overlap → score < 0.5
- [X] T039 Commit Phase 6

---

## Phase 7: Re-ingest + Backend + Polish

- [X] T040 Delete old element/schema/value/mapping files; re-ingest all 5 sources with full enriched model
- [X] T041 Run `undata-library verify elements/` on full library; report misalignment count
- [X] T042 Run `undata-library detect-aliases elements/` on full library; report candidate count
- [X] T043 [P] Update backend ORM `Element` model in `backend/src/models/element.py` to accept enriched semantic JSONB (no schema change needed — JSONB is flexible)
- [X] T044 [P] Update backend API Pydantic schemas to include new fields in request/response
- [X] T045 [P] Update frontend `ElementDetail` component to show response_options, min/max range, PROV-O provenance fields (generated_at, attributed_to, activity)
- [X] T046 Lint all code: `uv run ruff check + format` (library + backend)
- [X] T047 Run all tests: library (pytest), backend (pytest), frontend (vitest)
- [X] T048 Update `library/README.md` with enriched model documentation and new CLI commands
- [X] T049 Final commit and push

---

## Phase 8: US5 — Semantic Embedding Layer

**Goal**: Precomputed embeddings from `"{class} {name}: {description}"` in parquet;
replaces bare name similarity in scoring.

- [X] T050 [US5] Add `pyarrow` to `library/pyproject.toml` base dependencies; add `sentence-transformers` to `[embeddings]` optional extra (separate from existing `[similarity]`)
- [X] T051 [US5] Create `library/src/undata_library/embeddings.py`: `EmbeddingStore` class with `load(path) -> DataFrame`, `save(path, df)`, `get_vector(uri) -> ndarray | None`, `cosine_similarity(vec_a, vec_b) -> float`; parquet I/O with metadata (`model`, `generated_at`)
- [X] T052 [P] [US5] Add `build_element_embeddings(elements_dir, model_name) -> DataFrame` to `embeddings.py`: for each element YAML, construct text `"{class} {name}: {description}"` from first provenance entry; encode with sentence-transformers; return DataFrame with `uri`, `text`, `vector` columns
- [X] T053 [P] [US5] Add `build_ontology_embeddings(cache_dir, model_name) -> DataFrame` to `embeddings.py`: for each ontology term in cache, construct text `"{label}: {synonym1}, {synonym2}"` ; encode; return DataFrame with `term_uri`, `text`, `vector` columns; save to `ontology-cache/embeddings.parquet`
- [X] T054 [US5] Add model mismatch detection: on `load()`, compare stored `model` metadata against requested model; warn and offer to regenerate if mismatch
- [X] T055 [US5] Update `library/src/undata_library/similarity.py`: replace `name_similarity()` with `semantic_embedding_similarity(uri_a, uri_b, store)` that looks up precomputed vectors from `EmbeddingStore` and returns cosine similarity; keep difflib fallback if store is None or URIs not found
- [X] T056 [US5] Update `library/src/undata_library/alias_detection.py`: accept optional `EmbeddingStore` parameter in `detect_aliases()`; pass to `compute_similarity()`
- [X] T057 [US5] Add `embed` CLI command to `library/src/undata_library/cli.py`: `undata-library embed [PATH] [--model MODEL] [--include-ontology]` — builds element embeddings (+ optionally ontology embeddings) and writes parquet files
- [X] T057b [US5] Update `ontology refresh` CLI in `library/src/undata_library/cli.py`: after fetching terms, call `build_ontology_embeddings()` to regenerate `ontology-cache/embeddings.parquet`
- [X] T058 [US5] Write tests in `library/tests/test_embeddings.py`: (a) text construction from element YAML; (b) parquet round-trip (save + load); (c) cosine similarity of identical vectors = 1.0; (d) model mismatch warning; (e) difflib fallback when store unavailable; (f) ontology embedding text construction
- [X] T059 Lint + run all tests; commit Phase 8

---

## Phase 9: US6 — Enrichment Pipeline

**Goal**: `undata-library enrich` — auto-assign ontology_term via embedding distance,
resolve response_options to ValueConcept URIs, auto-populate value_domain.

- [X] T060 [US6] Create `library/src/undata_library/enrich.py`: `enrich_elements(elements_dir, cache_dir, model_name, threshold) -> dict` — orchestrates all enrichment operations; returns stats
- [X] T061 [US6] Implement `_assign_ontology_term(element, ontology_store) -> str | None` in `enrich.py`: compute cosine distance between element embedding and all ontology term embeddings; return best match URI above threshold (default 0.7)
- [X] T062 [P] [US6] Implement `_resolve_response_options(element, values_dir) -> list[dict]` in `enrich.py`: scan values/ directory for matching ValueConcepts by label/raw_value; replace raw choices with ValueConcept URIs
- [X] T063 [P] [US6] Implement `_populate_value_domain(element) -> str | None` in `enrich.py`: map data_type → value_domain (string→text, integer/float→numeric, boolean→boolean); override to `categorical` if response_options present
- [X] T064 [US6] Implement `_create_enriched_element(old_element, new_semantic, library_path) -> Path` in `enrich.py`: compute new hash/URI from modified semantic; write new element file; add provenance entry with `derived_from`, `activity: enrichment`, `attributed_to: urn:undata:enrichment-pipeline`
- [X] T065 [US6] Implement idempotency check: compare computed enrichments against current element state; skip if no changes would occur
- [X] T066 [US6] After creating new elements, call `build_element_embeddings()` to regenerate `embeddings.parquet` with new elements included
- [X] T067 [US6] Add `enrich` CLI command to `library/src/undata_library/cli.py`: `undata-library enrich [PATH] [--cache-dir DIR] [--threshold FLOAT] [--model MODEL] [--dry-run]`
- [X] T068 [US6] Write tests in `library/tests/test_enrich.py`: (a) ontology_term assigned via embedding distance; (b) response_options resolved to ValueConcept URIs; (c) value_domain populated from data_type; (d) identity-changing enrichment creates new element with derived_from; (e) old element not deleted; (f) idempotent re-run produces no new elements; (g) dry-run mode produces no file changes
- [X] T069 Lint + run all tests; commit Phase 9

---

## Phase 10: US7 — Alignment Pipeline

**Goal**: `undata-library align` — re-run alias detection post-enrichment using precomputed
embeddings, persist alias groups with provenance, produce alignment report.

- [X] T070 [US7] Create `library/src/undata_library/align.py`: `align_elements(elements_dir, threshold, output_path) -> dict` — orchestrates alias detection + grouping + report
- [X] T071 [US7] Implement `_form_alias_groups(candidates) -> list[dict]` in `align.py`: group elements by transitive closure of `skos:exactMatch` pairs using union-find; record `skos:closeMatch` pairs (0.8–0.95) as candidate groups
- [X] T072 [US7] Implement `_update_provenance(element_path, alias_group_info)` in `align.py`: append provenance entry with `activity: enrichment`, `attributed_to: urn:undata:alignment-pipeline` to elements newly added to alias groups
- [X] T073 [US7] Implement `_persist_report(groups, stats, output_path)` in `align.py`: write `alignment-report.yaml` with groups, ungrouped, stats, generated_at; if previous report exists, compute diff (new/dissolved/changed groups) and include
- [X] T074 [US7] Add `align` CLI command to `library/src/undata_library/cli.py`: `undata-library align [PATH] [--threshold FLOAT] [--output FILE] [--dry-run]`
- [X] T075 [US7] Write tests in `library/tests/test_align.py`: (a) exact match elements grouped; (b) close match elements recorded as candidates; (c) provenance updated on newly grouped elements; (d) alignment report YAML valid and contains expected sections; (e) diff from previous report detected; (f) dry-run produces no file changes; (g) idempotent re-run reports no changes
- [X] T076 Lint + run all tests; commit Phase 10

---

## Phase 11: US8 — Pipeline Orchestration

**Goal**: `undata-library pipeline` — convenience command chaining ingest → enrich → align.

- [X] T077 [US8] Add `pipeline` CLI command to `library/src/undata_library/cli.py`: `undata-library pipeline --source SOURCE [--path PATH] [--library-path PATH] [--model MODEL] [--skip-enrich] [--skip-align]`
- [X] T078 [US8] Implement pipeline logic: call `ingest_source()` → `enrich_elements()` → `align_elements()` in sequence; collect stats per step with elapsed time; report aggregate summary
- [X] T079 [US8] Write tests in `library/tests/test_pipeline.py`: (a) full pipeline runs ingest+enrich+align; (b) --skip-enrich skips enrichment; (c) --skip-align skips alignment; (d) stats report includes per-step timing; (e) missing --source raises error
- [X] T080 Lint + run all tests; commit Phase 11

---

## Phase 12: Polish + Integration

- [X] T081 Run full pipeline on all 5 sources: `undata-library pipeline --source bids --library-path .` (repeat for nwb, dandi, aind, openminds)
- [X] T082 [P] Verify `embeddings.parquet` generated with correct columns and metadata
- [X] T083 [P] Verify `alignment-report.yaml` generated with alias groups
- [X] T084 [P] Verify enriched elements have `derived_from` links and correct ontology_term assignments
- [X] T085 Run all library tests: `uv run pytest tests/ -v`
- [X] T086 Lint all code: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- [X] T087 Final commit and push

---

## Dependencies

```
Phases 1-7 (T001-T049): COMPLETE

T050 → T051 → T052, T053 (parallel) → T054 → T055 → T056 → T057 → T058 → T059
T060 → T061 → T062, T063 (parallel) → T064 → T065 → T066 → T067 → T068 → T069
T070 → T071 → T072 → T073 → T074 → T075 → T076
T077 → T078 → T079 → T080
T081 → T082-T084 (parallel) → T085 → T086 → T087
```

## Implementation Strategy

1. **Phases 1-7** (T001-T049): COMPLETE — enriched model, extractors, ontology cache, similarity, backend/frontend.
2. **Phase 8 — Embedding Layer** (T050-T059): Foundation for all subsequent phases. Precomputed embeddings in parquet, replaces bare name similarity.
3. **Phase 9 — Enrichment** (T060-T069): Post-ingestion enrichment using embedding distance for ontology matching.
4. **Phase 10 — Alignment** (T070-T076): Alias detection with provenance tracking and report generation.
5. **Phase 11 — Pipeline** (T077-T080): Convenience command chaining all steps.
6. **Phase 12 — Polish** (T081-T087): Full re-run, verification, final commit.

**Suggested MVP**: Phase 8 (T050-T059) — embedding layer is independently useful and testable.
