# Tasks: Staged Enrichment Pipeline

**Feature**: `026-staged-enrichment` | **Branch**: `026-staged-enrichment`

**User Stories** (mapped from spec):
- US1 — Staged Pipeline: Extract → Enrich → Commit (P1)
- US2 — Identity Hash: ontology-anchored + structural fallback (P1)
- US3 — Enrichment Updates In-Place, All Entity Types (P1)
- US4 — Commit Stage Rehashes and Finalizes (P1)

---

## Phase 1: Foundational — Unify Registry Entity Model

**Goal**: Fix all consistency gaps. Remove legacy. Unified provenance + description + ontology_annotations across all 4 entity types.

- [ ] T001 Remove `ontology_term` field from `SemanticIdentity` in `library/src/undata_library/models.py`
- [ ] T002 Remove `Constraints` model from `models.py`; move `pattern: str | None` directly to `SemanticIdentity`; remove `constraints` field; update `allowed_values` reference to note it lives in `response_options`
- [ ] T003 Add `description: str | None = None` to `SemanticIdentity`, `ValueSemanticIdentity`, `SchemaIdentity`, `ValueSetIdentity` in `models.py` (marked NOT in hash for ontology-anchored mode)
- [ ] T004 [P] Add `ontology_annotations: list[OntologyAnnotation] | None = None` to `SchemaIdentity` and `ValueSetIdentity` in `models.py`
- [ ] T005 [P] Remove `SchemaProvenance` and `ValueProvenance` from `models.py`; update `SchemaRecord` and `ValueConcept` to use `provenance: list[ProvenanceEntry]`
- [ ] T006 Remove `source_attribute` and `source_class` from `SemanticIdentity` in `models.py` (replaced by class + attribute + description from provenance in fallback hash)
- [ ] T007 Update `_EXCLUDED_FROM_HASH` in `library/src/undata_library/hashing.py`: set = `{"question_text", "value_domain", "ontology_annotations", "description"}` (description excluded in ontology-anchored mode; included in fallback mode via separate logic)
- [ ] T008 Write tests in `library/tests/test_unified_model.py`: (a) all 4 entity types have `description` field; (b) all 4 have `ontology_annotations` field; (c) all 4 use `ProvenanceEntry` for provenance; (d) `Constraints` no longer exists; (e) `ontology_term` no longer on SemanticIdentity; (f) `source_attribute`/`source_class` no longer on SemanticIdentity
- [ ] T009 Fix all import errors and references to removed models (`Constraints`, `SchemaProvenance`, `ValueProvenance`, `ontology_term`, `source_attribute`, `source_class`) across: `ingest.py`, `enrich.py`, `transform.py`, `similarity.py`, `index.py`, `verify.py`, `validation.py`, `cli.py`, all adapters, all tests
- [ ] T010 Lint + run all tests; commit Phase 1

---

## Phase 2: US2 — Two-Mode Hash Function

**Goal**: `compute_identity_hash()` with ontology-anchored and structural fallback modes.

- [ ] T011 [US2] Add `compute_identity_hash(semantic: dict, provenance: list[dict], ontology_anchored: bool) -> str` to `library/src/undata_library/hashing.py`
- [ ] T012 [US2] Implement ontology-anchored mode: hash from `data_type + unit + pattern + response_options (sorted) + min_value + max_value + type_ref + primary_ontology_uri`
- [ ] T013 [US2] Implement structural fallback mode: hash from `data_type + unit + pattern + response_options (sorted) + min_value + max_value + type_ref + class + attribute + description` — class/attribute/description taken from the **first provenance entry** (original ingestion source, by insertion order)
- [ ] T014 [US2] Add `determine_hash_mode(ontology_annotations) -> tuple[bool, str | None]`: returns `(True, primary_uri)` if primary annotation has skos:exactMatch or element_match with high score; else `(False, None)`
- [ ] T015 [US2] Write tests in `library/tests/test_two_mode_hash.py`: (a) ontology-anchored: two elements with same data_type+unit+ontology_uri produce same hash regardless of class/attribute; (b) fallback: two elements with same data_type but different class+attribute produce different hashes; (c) PHQ-9 scenario: same response_options + different description → different hashes; (d) sex scenario: same response_options + same ontology → same hash (merge)
- [ ] T016 Lint + run all tests; commit Phase 2

---

## Phase 3: US1 — Staging Directory

**Goal**: Extract writes to `.staging/{run_id}/` with UUIDs.

- [ ] T017 [US1] Add `generate_run_id() -> str` and `create_staging_dir(output_dir, run_id) -> Path` to `library/src/undata_library/ingest.py`
- [ ] T018 [US1] Modify `ingest_source()` in `ingest.py`: accept `staging_dir` parameter; write entities with per-entity UUID filenames (`{uuid4()}.yaml`); no hashing at extraction time; store raw provenance (class, name, description from source)
- [ ] T019 [US1] Add `cleanup_stale_staging(output_dir, max_age_hours=24)` to `ingest.py`
- [ ] T020 [US1] Write tests in `library/tests/test_staging.py`: (a) staged entities have UUID filenames; (b) no sha256 computed at extraction; (c) staging dir has correct structure; (d) stale cleanup works
- [ ] T021 Lint + run all tests; commit Phase 3

---

## Phase 4: US3 — In-Place Enrichment (All Entity Types)

**Goal**: Enrich staged files in-place with ontology_annotations. Dependency-ordered passes.

- [ ] T022 [US3] Remove `_create_enriched_element()` from `library/src/undata_library/enrich.py`
- [ ] T023 [US3] Add `_update_entity_in_place(filepath, ontology_annotations: list[dict], value_domain: str | None, description: str | None)` to `enrich.py`: reads YAML, writes ontology_annotations + value_domain + description to semantic block, appends enrichment provenance
- [ ] T024 [US3] Refactor `enrich_elements(staging_dir, onto_store)` in `enrich.py`: iterate element files, call `_assign_ontology_annotations()` (025 heuristic), call `_update_entity_in_place()`; no new files
- [ ] T025 [P] [US3] Add `enrich_values(staging_dir, onto_store, threshold=0.8)` to `enrich.py`: embed value labels, assign ontology_annotations with element_match for score ≥ 0.9, update in-place
- [ ] T026 [P] [US3] Add `enrich_schemas(staging_dir, onto_store)` to `enrich.py`: assign ontology_annotations for class concepts (concept_match), update in-place
- [ ] T027 [US3] Add `enrich_valuesets(staging_dir)` to `enrich.py`: derive ontology_namespace from enriched member values, assign own ontology_annotations, update in-place
- [ ] T028 [US3] Add `enrich_all(staging_dir, onto_store)` to `enrich.py`: orchestrate (1) elements + values parallel, (2) valuesets, (3) schemas
- [ ] T029 [US3] Write tests in `library/tests/test_staged_enrich.py`: (a) no new files created; (b) ontology_annotations present after enrichment; (c) value_domain set; (d) values get element_match; (e) schemas get concept_match; (f) valuesets get ontology_namespace; (g) dependency order enforced; (h) idempotent
- [ ] T030 Lint + run all tests; commit Phase 4

---

## Phase 5: US4 — Commit Stage

**Goal**: Rehash enriched entities → content-addressed filenames → registry. Merge duplicates.

- [ ] T031 [US4] Create `library/src/undata_library/commit.py`: `commit_staged(staging_dir, output_dir) -> dict`
- [ ] T032 [US4] Implement per-entity commit logic in `commit.py`: read staged YAML → determine hash mode (ontology-anchored if primary annotation is exactMatch/element_match) → compute hash → write `{name}_{hash[:12]}.yaml` to output dir
- [ ] T033 [US4] Implement merge on commit: if target file exists, merge provenance entries (dedup by source+name)
- [ ] T034 [US4] Add sha256 field to committed YAML files
- [ ] T035 [US4] Delete staging directory after successful commit
- [ ] T036 [US4] Update `pipeline` CLI in `library/src/undata_library/cli.py`: `ingest(staging)` → `enrich_all(staging)` → `commit_staged(staging, output)` → cleanup
- [ ] T037 [US4] Write tests in `library/tests/test_commit.py`: (a) committed file has content-addressed name; (b) ontology-anchored: same concept from 2 sources → same hash → merged; (c) fallback: different description → different hash; (d) staging dir deleted; (e) sha256 matches recomputed
- [ ] T038 Lint + run all tests; commit Phase 5

---

## Phase 6: Downstream Updates

**Goal**: Transform, similarity, index, validation use new identity model.

- [ ] T039 Update `library/src/undata_library/transform.py`: group elements by primary annotation URI (not ontology_term)
- [ ] T040 [P] Update `library/src/undata_library/similarity.py`: use `_get_primary_ontology_uri()` from ontology_annotations for ontology match scoring
- [ ] T041 [P] Update `library/src/undata_library/index.py`: build ontology index from ontology_annotations (not ontology_term); include match_level
- [ ] T042 Update `library/src/undata_library/validation.py`: validate two-mode hash; verify ontology_annotations structure
- [ ] T043 Lint + run all tests; commit Phase 6

---

## Phase 7: Extractor Updates

**Goal**: Adapters output raw entities without hashing.

- [ ] T044 Update all adapters in `library/src/undata_library/adapters/`: remove Constraints references; use `pattern` directly on semantic; remove `source_attribute`/`source_class`; ensure `description` is set on semantic block from source metadata
- [ ] T045 [P] Update `library/src/undata_library/adapters/docker_scripts/bids_extract.py`: remove constraints; add description to semantic
- [ ] T046 [P] Update `library/src/undata_library/adapters/docker_scripts/dandi_extract.py`: same changes
- [ ] T047 Lint + run all tests; commit Phase 7

---

## Phase 8: Re-extraction + Evaluation

- [ ] T048 Clean output dir + staging: `rm -rf /tmp/undata-registry`
- [ ] T049 Run ontology refresh (reuse cached store)
- [ ] T050 Extract all 5 sources to staging: `undata-library pipeline --source bids --output-dir /tmp/undata-registry` (repeat for all sources)
- [ ] T051 [P] Verify staged entities have UUID filenames (no hashes)
- [ ] T052 [P] Verify enriched entities have ontology_annotations in-place
- [ ] T053 [P] Verify committed elements have content-addressed names
- [ ] T054 [P] Verify element count < 7,756 (cross-source merges expected)
- [ ] T055 [P] Verify sex elements from BIDS + DANDI merged (same hash)
- [ ] T056 [P] Verify age elements from BIDS + NWB separate (different hash — float vs string)
- [ ] T057 Run transforms; compare count to baseline (176,880)
- [ ] T058 Update `eval-record.md` with results + comparison to 2026-03-21 baseline
- [ ] T059 Run all library tests: `uv run pytest tests/ -v`
- [ ] T060 Lint all code
- [ ] T061 Final commit and push

---

## Dependencies

```
Phase 1 (T001-T010): Model unification — foundational
Phase 2 (T011-T016): Two-mode hash — depends on Phase 1
Phase 3 (T017-T021): Staging — depends on Phase 1
Phase 4 (T022-T030): Enrichment — depends on Phase 3
Phase 5 (T031-T038): Commit — depends on Phase 2 + Phase 4
Phase 6 (T039-T043): Downstream — depends on Phase 2
Phase 7 (T044-T047): Extractors — depends on Phase 1
Phase 8 (T048-T061): Re-extraction + eval — depends on all

Parallelizable: Phase 2 ‖ Phase 3; Phase 6 ‖ Phase 7; T025 ‖ T026; T045 ‖ T046
```

## Implementation Strategy

1. **Phase 1** (T001-T010): **Critical foundation** — unify models. Everything depends on this.
2. **Phase 2 ‖ Phase 3** (parallel): hash function + staging directory.
3. **Phase 4** (T022-T030): In-place enrichment with dependency order.
4. **Phase 5** (T031-T038): Commit stage — the core innovation.
5. **Phase 6 ‖ Phase 7** (parallel): downstream + extractors.
6. **Phase 8** (T048-T061): Validate everything against baseline.

**Suggested MVP**: Phase 1 (T001-T010) — unified model is the prerequisite for everything else.
