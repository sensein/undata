# Tasks: Ontology Expansion, Deduplication, and Precision Matching

**Feature**: `025-ontology-expansion` | **Branch**: `025-ontology-expansion`

**User Stories** (mapped from spec):
- US1 — Extended Neuroscience Ontology Coverage (P1, FR-001 to FR-003)
- US2 — Cross-Ontology Deduplication (P1, FR-004 to FR-006)
- US3 — SKOS/Multi-Term Precision Matching (P1, FR-007 to FR-010, FR-014 to FR-016)
- US4 — Value and Valueset Ontology Enrichment (P1, FR-011 to FR-013)

---

## Phase 1: Setup

- [ ] T001 Verify `pyoxigraph`, `pronto`, `sentence-transformers` installed in dev venv (`uv sync`)

---

## Phase 2: Foundational — OntologyAnnotation Model

**Goal**: Replace single ontology_term with multi-annotation list.

- [ ] T002 Add `MatchLevel` enum (`concept_match`, `element_match`) to `library/src/undata_library/models.py`
- [ ] T003 Add `OntologyAnnotation` Pydantic model to `library/src/undata_library/models.py`: `term_uri: str`, `term_label: str`, `ontology: str`, `mapping_relation: str`, `match_level: MatchLevel`, `score: float`, `model: str`, `primary: bool = False`
- [ ] T004 Add `ontology_annotations: list[OntologyAnnotation] | None` field to `SemanticIdentity` in `models.py` — NOT in hash (excluded via `_EXCLUDED_FROM_HASH`)
- [ ] T005 [P] Add `ontology_annotations: list[OntologyAnnotation] | None` field to `ValueSemanticIdentity` in `models.py` — NOT in hash
- [ ] T006 Update `_EXCLUDED_FROM_HASH` set in `library/src/undata_library/hashing.py`: add `"ontology_annotations"`
- [ ] T007 Write tests in `library/tests/test_annotation_model.py`: (a) OntologyAnnotation validates all fields; (b) ontology_annotations excluded from hash; (c) MatchLevel enum has concept_match + element_match; (d) primary defaults to False
- [ ] T008 Lint + run all tests; commit Phase 2

---

## Phase 3: US1 — Extended Ontology Configuration

**Goal**: Add 7 new ontologies with download URLs and format specs.

- [ ] T009 [US1] Update `library/src/undata_library/source_defs/ontologies.yaml`: add UBERON (`uberon.obo`), CL (`cl.obo`), EDAM (`EDAM.obo`), ATOM, TMN, BGO, HOMBA with URLs and formats
- [ ] T010 [US1] Update `library/src/undata_library/ontology_fetch.py`: add URL entries for new ontologies in `SUPPORTED_ONTOLOGIES`; handle non-OBO formats: OWL for ATOM (load via `OntologyStore.load_rdf()`), JSON-LD for HOMBA (parse with pyoxigraph load_rdf), YAML for TMN (custom parser)
- [ ] T011 [P] [US1] Add `_parse_yaml_ontology(path) -> dict` to `ontology_fetch.py`: parse TMN-style YAML ontologies into cache-format dict (term_uri, label, synonyms, parents)
- [ ] T012 [P] [US1] Add `_parse_jsonld_ontology(path) -> dict` to `ontology_fetch.py`: parse HOMBA JSON-LD into terms via pyoxigraph or json parsing
- [ ] T013 [US1] Write tests in `library/tests/test_extended_ontologies.py`: (a) ontologies.yaml has ≥12 entries; (b) UBERON/CL URLs resolve (mock); (c) YAML parser produces valid terms; (d) JSON-LD parser produces valid terms
- [ ] T014 Lint + run all tests; commit Phase 3

---

## Phase 4: US2 — Cross-Ontology Deduplication

**Goal**: Vector index deduplicated by URI with merged labels/synonyms.

- [ ] T015 [US2] Modify `all_terms()` in `library/src/undata_library/ontology_store.py`: SPARQL GROUP BY ?s to collect all labels + synonyms per URI across all ontology graphs; return merged (uri, merged_label, all_synonyms)
- [ ] T016 [US2] Modify `build_vector_index()` in `ontology_store.py`: consume deduplicated all_terms(); embedding text = "{primary_label}: {synonym1}, {synonym2}, ..." (merged from all ontologies)
- [ ] T017 [US2] Modify `lookup_term()` in `ontology_store.py`: return merged labels, all synonyms, all parents across ontology graphs
- [ ] T018 [US2] Write tests in `library/tests/test_dedup.py`: (a) same URI from 2 ontologies → 1 entry in vector index; (b) merged synonyms include both ontologies' synonyms; (c) lookup returns merged view
- [ ] T019 Lint + run all tests; commit Phase 4

---

## Phase 5: US3 — Multi-Term Enrichment + SKOS Precision

**Goal**: Assign multiple OntologyAnnotations per entity with heuristic selection.

- [ ] T020 [US3] Rewrite `_assign_ontology_term()` → `_assign_ontology_annotations()` in `library/src/undata_library/enrich.py`: query top-20 nearest terms from vector index; apply heuristic (threshold + gap cutoff + max 10); create OntologyAnnotation per match
- [ ] T021 [US3] Implement SKOS relation assignment in `enrich.py`: score ≥0.95 → exactMatch, 0.8-0.95 → closeMatch, 0.5-0.8 → relatedMatch; check rdfs:subClassOf chain in OntologyStore for broadMatch/narrowMatch (limit hierarchy traversal to 3 levels for performance in 3M+ term store)
- [ ] T022 [US3] Implement match_level assignment in `enrich.py`: `element_match` if entity is ValueConcept AND score ≥ 0.9; otherwise `concept_match`
- [ ] T023 [US3] Implement gap-based cutoff in `enrich.py`: if score[i] - score[i+1] > 0.15, stop at i; cap at 10 annotations; mark highest as primary
- [ ] T024 [US3] Update `_create_enriched_element()` in `enrich.py`: when annotations change identity (adding ontology_term from primary), create new element with derived_from; store full ontology_annotations list in semantic block (excluded from hash)
- [ ] T025 [US3] Write tests in `library/tests/test_multi_annotation.py`: (a) element gets multiple annotations; (b) primary has highest score; (c) gap cutoff limits count; (d) max 10 enforced; (e) SKOS relations assigned correctly; (f) concept_match for elements, element_match for values with high score
- [ ] T026 Lint + run all tests; commit Phase 5

---

## Phase 6: US4 — Value and Valueset Enrichment

**Goal**: Enrich values + valuesets with ontology annotations.

- [ ] T027 [US4] Add value enrichment to `enrich_elements()` in `library/src/undata_library/enrich.py`: scan values/ directory, embed labels (`"{label}"`), find nearest ontology terms with threshold 0.8, assign OntologyAnnotation list
- [ ] T028 [US4] Add valueset enrichment in `enrich.py`: after member values are annotated, set `ontology_namespace` on the valueset based on most common ontology prefix of member annotations
- [ ] T029 [US4] Update value YAML writing: include `ontology_annotations` in value files
- [ ] T030 [US4] Write tests in `library/tests/test_value_enrichment.py`: (a) value "male" gets PATO annotation with element_match; (b) value with no match above 0.8 gets no annotation; (c) valueset gets ontology_namespace from members
- [ ] T031 Lint + run all tests; commit Phase 6

---

## Phase 7: Wiring — Output + Index + Transforms

**Goal**: Annotations flow through to all outputs.

- [ ] T032 Update `_write_element()` in `library/src/undata_library/ingest.py`: include `ontology_annotations` in YAML output (excluded from hash)
- [ ] T033 [P] Update `build_ontology_index()` in `library/src/undata_library/index.py`: index by all annotations (not just primary); each entry includes match_level
- [ ] T034 [P] Update `generate_transforms()` in `library/src/undata_library/transform.py`: match elements by primary annotation's term_uri; concept_match elements with same term still need transforms
- [ ] T035 Update `validate_ingestion_output()` in `library/src/undata_library/validation.py`: validate ontology_annotations structure (term_uri present, score in range, mapping_relation valid)
- [ ] T036 Lint + run all tests; commit Phase 7

---

## Phase 8: Full Load + Re-enrichment

- [ ] T037 Load all 12+ ontologies: `undata-library ontology refresh --output-dir /tmp/undata-registry` (skip ATOM/TMN/BGO/HOMBA if URLs unresolvable — log warning); time the full refresh and assert < 30 minutes (SC-006)
- [ ] T038 Rebuild deduplicated vector index from full store
- [ ] T039 Re-enrich all entities: elements, values, valuesets with multi-term annotations
- [ ] T040 [P] Verify value "male" has PATO:0000384 annotation with element_match
- [ ] T041 [P] Verify element "age" has NCIT:C25150 annotation with concept_match + additional annotations from other ontologies
- [ ] T042 [P] Verify ontology-index includes match_level in entries
- [ ] T043 Run all library tests: `uv run pytest tests/ -v`
- [ ] T044 Lint all code: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- [ ] T045 Final commit and push

---

## Dependencies

```
Phase 1 (T001): Setup — no deps
Phase 2 (T002-T008): Annotation model — depends on Phase 1
Phase 3 (T009-T014): Extended ontologies — depends on Phase 1 (can parallel with Phase 2)
Phase 4 (T015-T019): Deduplication — depends on Phase 3
Phase 5 (T020-T026): Multi-term enrichment — depends on Phase 2 + Phase 4
Phase 6 (T027-T031): Value enrichment — depends on Phase 5
Phase 7 (T032-T036): Wiring — depends on Phase 5 + Phase 6
Phase 8 (T037-T045): Full load — depends on all

Parallelizable: Phase 2 ‖ Phase 3; T011 ‖ T012; T033 ‖ T034; T040 ‖ T041 ‖ T042
```

## Implementation Strategy

1. **Phase 1-2** (T001-T008): OntologyAnnotation model. **Suggested MVP.**
2. **Phase 3** (T009-T014): Extended ontology config + format parsers.
3. **Phase 4** (T015-T019): Dedup vector index — prerequisite for quality enrichment.
4. **Phase 5** (T020-T026): Multi-term enrichment heuristic — core feature.
5. **Phase 6** (T027-T031): Value/valueset enrichment.
6. **Phase 7** (T032-T036): Wire into all outputs.
7. **Phase 8** (T037-T045): Full 12+ ontology load + re-enrichment.

**Suggested MVP**: Phases 1-2 (T001-T008) — OntologyAnnotation model + hash exclusion.
