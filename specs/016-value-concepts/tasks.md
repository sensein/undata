# Tasks: Value Concepts

**Feature**: `016-value-concepts` | **Branch**: `016-value-concepts`

---

## Phase 1: Model + Fixtures

- [ ] T001 Add `ValueSemanticIdentity` (ontology_term, value_type, label), `ValueProvenance` (source, raw_value), `ValueConcept` (semantic + provenance) to `library/src/undata_library/models.py`
- [ ] T002 [P] Update `library/library-schema.linkml.yaml`: add `ValueConcept`, `ValueSemanticIdentity`, `ValueProvenance` classes
- [ ] T003 [P] Create `library/tests/fixtures/valid-value.yaml` and `library/tests/fixtures/multi-provenance-value.yaml`
- [ ] T004 Write `library/tests/test_values.py`: valid value parses, multi-provenance accepted, missing label fails
- [ ] T005 Run tests; commit Phase 1

## Phase 2: Value Mappings + Ingestion

- [ ] T006 Create `library/value-mappings.yaml`: curated mappings for sex (male/female/other), species (mus_musculus/rattus_norvegicus/homo_sapiens/callithrix_jacchus), handedness (left/right/ambidextrous), modality (MRI/EEG/MEG/iEEG/PET/NIRS)
- [ ] T007 Update `library/src/undata_library/ingest.py`: during element ingestion, detect `constraints.allowed_values`, look up each value in `value-mappings.yaml`, create/merge ValueConcept files in `values/`, replace raw strings with value URIs in element constraints
- [ ] T008 Create `library/values/.gitkeep`; update `library/src/undata_library/hashing.py` with `build_value_uri(label, key)`
- [ ] T009 Write `library/tests/test_value_ingest.py`: (a) enum field creates value files; (b) mapped value gets ontology hash; (c) unmapped value uses raw_value fallback; (d) cross-source same ontology merges
- [ ] T010 Run tests; commit Phase 2

## Phase 3: Validation + Index

- [ ] T011 Update `library/src/undata_library/validation.py`: detect value files from semantic block (`value_type` field), validate against `ValueConcept` model
- [ ] T012 Update `library/src/undata_library/index.py`: add `value_count` to index output, scan `values/` directory
- [ ] T013 Update CLI `index` command output to show value count
- [ ] T014 Run tests; verify `undata-library validate values/` works; commit Phase 3

## Phase 4: Re-ingest + Polish

- [ ] T015 Delete old element + value files; re-ingest all 5 sources with value extraction
- [ ] T016 Verify cross-source value dedup (sex values from BIDS/AIND should merge)
- [ ] T017 Run `undata-library validate elements/ schemas/ values/` — 0 violations
- [ ] T018 Update `library/README.md` with value concepts section
- [ ] T019 Lint: `uv run ruff check src/ tests/` + `uv run ruff format src/ tests/`
- [ ] T020 Final commit and push

---

## Dependencies

T001 → T002, T003 (parallel) → T004 → T005
T006 → T007 → T008 → T009 → T010
T011 → T012 → T013 → T014
T015 → T016 → T017 → T018 → T019 → T020
