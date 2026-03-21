# Tasks: Staged Enrichment Pipeline

**Feature**: `026-staged-enrichment` | **Branch**: `026-staged-enrichment`

**User Stories** (mapped from spec):
- US1 — Staged Pipeline: Extract → Enrich → Commit (P1, FR-004 to FR-006)
- US2 — ontology_term Removed from Identity Hash (P1, FR-001 to FR-003)
- US3 — Enrichment Updates In-Place (P1, FR-007 to FR-010)
- US4 — Commit Stage Rehashes and Finalizes (P1, FR-011 to FR-016)

---

## Phase 1: Foundational — Identity Hash Change

**Goal**: Remove ontology_term from hash. This unblocks all other phases.

- [ ] T001 Add `"ontology_term"` to `_EXCLUDED_FROM_HASH` in `library/src/undata_library/hashing.py`
- [ ] T002 Write test in `library/tests/test_hashing.py`: two elements differing only in ontology_term produce the same sha256 hash
- [ ] T003 Update existing tests that assert ontology_term affects the hash (if any)
- [ ] T004 Lint + run all tests; commit Phase 1

---

## Phase 2: US1 — Staging Directory

**Goal**: Pipeline writes to `.staging/{run_id}/`, not directly to registry.

- [ ] T005 [US1] Add `generate_run_id() -> str` utility to `library/src/undata_library/ingest.py` (UUID-based)
- [ ] T006 [US1] Add `create_staging_dir(output_dir, run_id) -> Path` to `ingest.py`: creates `{output_dir}/.staging/{run_id}/elements/`, `schemas/`, `values/`, `valuesets/`
- [ ] T007 [US1] Modify `ingest_source()` in `ingest.py`: accept optional `staging_dir` parameter; when provided, write all entities to staging instead of output dir
- [ ] T008 [US1] Modify `pipeline` command in `library/src/undata_library/cli.py`: generate run_id, create staging dir, pass to ingest → enrich → commit
- [ ] T009 [US1] Add `cleanup_stale_staging(output_dir, max_age_hours=24)` to `ingest.py`: delete staging dirs older than threshold
- [ ] T010 [US1] Write tests in `library/tests/test_staging.py`: (a) staging dir created with correct structure; (b) entities written to staging, not output dir; (c) stale staging cleaned up
- [ ] T011 Lint + run all tests; commit Phase 2

---

## Phase 3: US3 — In-Place Enrichment

**Goal**: Enrich modifies staged entity files in-place. No new entities created.

- [ ] T012 [US3] Remove `_create_enriched_element()` from `library/src/undata_library/enrich.py`
- [ ] T013 [US3] Add `_update_entity_in_place(filepath, ontology_annotations: list[OntologyAnnotation], value_domain, provenance_entry)` to `enrich.py`: reads YAML, writes `ontology_annotations` list (multi-term with SKOS relation + match_level + score + model per 025 model), adds/replaces value_domain in semantic block, appends enrichment provenance, writes back to same file
- [ ] T014 [US3] Refactor `enrich_elements()` in `enrich.py`: use `_assign_ontology_annotations()` from 025 (multi-term heuristic: threshold + gap cutoff + max 10); call `_update_entity_in_place()` instead of `_create_enriched_element()`; remove all `enriched_new` / `derived_from` logic
- [ ] T015 [US3] Implement enrichment dependency order in `enrich.py`: `enrich_all(staging_dir)` calls: (1) `enrich_elements()` + `enrich_values()` in parallel, (2) `enrich_valuesets()`, (3) `enrich_schemas()`
- [ ] T016 [P] [US3] Add `enrich_values(staging_dir, onto_store, threshold=0.8)` to `enrich.py`: embed value labels, assign `ontology_annotations: list[OntologyAnnotation]` with `match_level: element_match` for score ≥ 0.9, SKOS relation from score
- [ ] T017 [P] [US3] Add `enrich_valuesets(staging_dir)` to `enrich.py`: derive `ontology_namespace` from enriched member value annotations; assign own `ontology_annotations` for collection concept
- [ ] T018 [US3] Add `enrich_schemas(staging_dir, onto_store)` to `enrich.py`: assign `ontology_annotations: list[OntologyAnnotation]` with `match_level: concept_match` for class concepts, SKOS relation from score
- [ ] T019 [US3] Write tests in `library/tests/test_staged_enrich.py`: (a) enrichment does NOT create new files; (b) sha256 unchanged after enrichment; (c) ontology_annotations present after enrichment; (d) value_domain set; (e) enrichment provenance appended; (f) idempotent on re-run; (g) dependency order: values before valuesets before schemas
- [ ] T020 Lint + run all tests; commit Phase 3

---

## Phase 4: US4 — Commit Stage

**Goal**: Rehash staged entities → content-addressed filenames → registry. Delete staging.

- [ ] T021 [US4] Create `library/src/undata_library/commit.py`: `commit_staged(staging_dir, output_dir) -> dict` — for each entity type (elements, schemas, values, valuesets): read staged YAML, compute sha256 from semantic (excl annotations), generate `{name}_{hash}.yaml` filename, write to output dir; merge provenance if file exists; return stats
- [ ] T022 [US4] Handle merge on commit: if `{output_dir}/elements/{name}_{hash}.yaml` already exists (from a prior source), merge provenance entries (dedup by source+name)
- [ ] T023 [US4] Add sha256 field to committed YAML files (computed from canonical semantic, excl annotations)
- [ ] T024 [US4] Delete staging directory after successful commit
- [ ] T025 [US4] Update `pipeline` CLI command to call: `ingest(staging_dir)` → `enrich_all(staging_dir)` → `commit_staged(staging_dir, output_dir)` → cleanup
- [ ] T026 [US4] Write tests in `library/tests/test_commit.py`: (a) committed file has content-addressed name; (b) sha256 matches recomputed hash; (c) duplicate hash merges provenance; (d) staging dir deleted after commit; (e) no provenance for staging mechanics
- [ ] T027 Lint + run all tests; commit Phase 4

---

## Phase 5: US2 — Migration of Existing Elements

**Goal**: Rehash existing registry elements (ontology_term no longer in hash). Merge duplicates.

- [ ] T028 [US2] Add `migrate_registry(output_dir) -> dict` to `library/src/undata_library/commit.py`: read all elements, recompute sha256 (excl ontology_term), rename files to new hash, merge duplicates, return stats (migrated, merged, unchanged)
- [ ] T029 [US2] Write tests in `library/tests/test_migration.py`: (a) element with ontology_term rehashes to same hash as element without; (b) two elements differing only in ontology_term merge into one; (c) provenance combined on merge
- [ ] T030 Lint + run all tests; commit Phase 5

---

## Phase 6: Re-extraction + Evaluation

**Goal**: Full pipeline run with staged model. Verify no proliferation. Record in eval-record.md.

- [ ] T031 Clean output dir: `rm -rf /tmp/undata-registry && mkdir -p /tmp/undata-registry`
- [ ] T032 Run ontology refresh (reuse cached store if available)
- [ ] T033 Extract all 5 sources via staged pipeline: `undata-library pipeline --source bids --output-dir /tmp/undata-registry` (repeat for nwb, dandi, openminds, aind)
- [ ] T034 [P] Verify element count = pre-enrichment count (no proliferation from enrichment)
- [ ] T035 [P] Verify sha256 unchanged before/after enrichment on sample elements
- [ ] T036 [P] Verify ontology_annotations present on enriched elements
- [ ] T037 [P] Verify values have ontology_annotations with element_match where applicable
- [ ] T038 [P] Verify valuesets have ontology_namespace from member values
- [ ] T039 Run `undata-library transform /tmp/undata-registry` and compare transform count to baseline
- [ ] T040 Update `eval-record.md` with new results + comparison to 2026-03-21 baseline
- [ ] T041 Run all library tests: `uv run pytest tests/ -v`
- [ ] T042 Lint all code: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- [ ] T043 Final commit and push

---

## Dependencies

```
Phase 1 (T001-T004): Hash change — foundational
Phase 2 (T005-T011): Staging dir — depends on Phase 1
Phase 3 (T012-T020): In-place enrichment — depends on Phase 2
Phase 4 (T021-T027): Commit stage — depends on Phase 3
Phase 5 (T028-T030): Migration — depends on Phase 1 (can parallel with Phases 2-4)
Phase 6 (T031-T043): Re-extraction + eval — depends on all
```

## Implementation Strategy

1. **Phase 1** (T001-T004): Hash change. **Immediate, foundational.** One line + tests.
2. **Phase 2** (T005-T011): Staging directory plumbing.
3. **Phase 3** (T012-T020): Core refactor — in-place enrichment for all entity types.
4. **Phase 4** (T021-T027): Commit stage — rehash + registry write.
5. **Phase 5** (T028-T030): Migration (can parallel with 2-4 since it's registry-only).
6. **Phase 6** (T031-T043): Full re-extraction, verify counts, update eval-record.md.

**Suggested MVP**: Phases 1+3 (T001-T004, T012-T020) — hash change + in-place enrichment. Eliminates element proliferation immediately.
