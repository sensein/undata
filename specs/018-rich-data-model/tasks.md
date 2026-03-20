# Tasks: Rich Data Element Model

**Feature**: `018-rich-data-model` | **Branch**: `018-rich-data-model`

**User Stories** (mapped from FRs):
- US1 — Enriched SemanticIdentity + PROV-O Provenance (FR-001 to FR-007)
- US2 — Underscore Entry Reclassification (FR-008 to FR-010)
- US3 — Ontology Cache + Verification (FR-011 to FR-014)
- US4 — Semantic Similarity + Alias Detection (FR-015 to FR-018)

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

## Dependencies

```
T001, T002 (parallel) → T003-T006 (parallel) → T007 → T008 → T009
T010, T011-T014 (parallel) → T015 → T016
T017 → T018 → T019 → T020 → T021
T022, T023 (parallel) → T024 → T025 → T026, T027 (parallel) → T028 → T029
T030, T031-T033 (parallel) → T034 → T035 → T036, T037 (parallel) → T038 → T039
T040 → T041, T042 (parallel) → T043-T045 (parallel) → T046 → T047 → T048 → T049
```

## Implementation Strategy

1. **MVP** (Phases 1-2): Enriched model + hash changes. Proves the data model works.
2. **Reclassification** (Phase 4): Cleaner element set. Validates underscore filtering.
3. **Verification** (Phase 5): Ontology cache + verify. Quality gate for annotations.
4. **Similarity** (Phase 6): Alias detection. The high-value feature.
5. **Integration** (Phase 7): Backend + frontend + full re-ingest.

**Suggested MVP**: Phases 1-3 (T001-T016) — enriched model with extractors populating new fields.
