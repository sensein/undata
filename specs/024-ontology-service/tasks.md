# Tasks: Local Ontology Service with Vector Index

**Feature**: `024-ontology-service` | **Branch**: `024-ontology-service`

**User Stories** (mapped from spec):
- US1 — Bulk Ontology Download and Local Store (P1, FR-001 to FR-005)
- US2 — SPARQL-Based Term Lookup (P1, FR-006 to FR-009)
- US3 — Vector Index for Semantic Search (P1, FR-010 to FR-013)
- US4 — Extensible to New Ontologies (P2, FR-014 to FR-016)

---

## Phase 1: Setup

- [ ] T001 Add `pyoxigraph>=0.4` to dependencies in `library/pyproject.toml`
- [ ] T002 [P] Create `library/src/undata_library/source_defs/ontologies.yaml` with 5 bundled ontology configs (ncit, pato, hp, obi, ncbitaxon) — each with name, url, format

---

## Phase 2: Foundational — OntologyStore + OBO→RDF Parser

**Goal**: Persistent pyoxigraph store, fast OBO line parser → RDF triples, basic term lookup.

- [ ] T003 [US1] Create `library/src/undata_library/ontology_store.py`: `OntologyStore` class with `__init__(store_path: Path)` using `pyoxigraph.Store(str(store_path))`; persistent on disk
- [ ] T004 [US1] Implement `load_obo(name, obo_path) -> int` in `ontology_store.py`: fast line-based OBO parser generating RDF triples — `[Term]` id → subject URI, `name:` → rdfs:label, `synonym:` → oboInOwl:hasExactSynonym, `is_a:` → rdfs:subClassOf, `is_obsolete:` → owl:deprecated; bulk insert into pyoxigraph store; return term count
- [ ] T005 [P] [US1] Implement `load_rdf(name, rdf_path, format) -> int` in `ontology_store.py`: load OWL/TTL/RDF-XML files directly via `store.load()` for ontologies that don't use OBO format
- [ ] T006 [US1] Implement `list_loaded() -> list[dict]` and `term_count(ontology=None) -> int` in `ontology_store.py`: SPARQL queries to count terms per loaded ontology; track loaded ontologies via a metadata named graph
- [ ] T007 [US1] Implement `_load_ontology_config(name_or_path) -> list[OntologyConfig]` in `ontology_store.py`: load from bundled `source_defs/ontologies.yaml` or custom path
- [ ] T008 [US1] Write tests in `library/tests/test_ontology_store.py`: (a) store creates persistent directory; (b) load_obo with small OBO fixture → terms queryable; (c) term_count returns correct number; (d) list_loaded shows ontology; (e) store persists across instantiations (reopen same path)
- [ ] T009 Lint + run all tests; commit Phase 2

---

## Phase 3: US2 — SPARQL Term Lookup and Search

**Goal**: lookup_term(), search_terms() via SPARQL against local store.

- [ ] T010 [US2] Implement `lookup_term(uri) -> dict | None` in `ontology_store.py`: SPARQL SELECT for label, synonyms, parents, deprecated status given a term URI; return dict or None
- [ ] T011 [US2] Implement `search_terms(query, ontology=None, limit=100) -> list[dict]` in `ontology_store.py`: SPARQL FILTER(CONTAINS(LCASE(?label), LCASE("{query}"))) on rdfs:label and oboInOwl:hasExactSynonym; return list of {uri, label, ontology, score}
- [ ] T012 [US2] Write tests in `library/tests/test_ontology_lookup.py`: (a) lookup_term for known URI returns correct label+synonyms+parents; (b) lookup_term for unknown URI returns None; (c) search_terms("age") returns terms containing "age"; (d) search_terms with ontology filter restricts to that ontology
- [ ] T013 Lint + run all tests; commit Phase 3

---

## Phase 4: US3 — Vector Index

**Goal**: Embed all term labels+synonyms into parquet vector index; nearest_terms() for enrichment.

- [ ] T014 [US3] Implement `build_vector_index(store, model_name, output_path) -> EmbeddingStore` in `ontology_store.py`: iterate `all_terms()` yielding (uri, "{label}: {synonyms}"), embed in batches (1000 at a time for memory), save to ontology-vectors.parquet using EmbeddingStore
- [ ] T015 [US3] Implement `all_terms() -> Iterator[tuple[str, str, list[str]]]` in `ontology_store.py`: SPARQL query yielding (uri, label, synonyms) for all non-deprecated terms with labels
- [ ] T016 [US3] Implement `nearest_terms(embedding, top_k=5) -> list[dict]` in `ontology_store.py`: load ontology-vectors.parquet, compute cosine similarity, return top-k {uri, label, score}
- [ ] T017 [US3] Write tests in `library/tests/test_ontology_vectors.py`: (a) build_vector_index produces parquet file with correct columns; (b) nearest_terms returns terms sorted by similarity; (c) identical embedding returns score ~1.0
- [ ] T018 Lint + run all tests; commit Phase 4

---

## Phase 5: US2+US3 — Wire Into Enrich/Verify/CLI

**Goal**: Replace YAML cache with OntologyStore across all commands.

- [ ] T019 [US2] Update `library/src/undata_library/verify.py`: replace `OntologyCache` usage with `OntologyStore.lookup_term()`; remove ontology_cache import
- [ ] T020 [US3] Update `library/src/undata_library/enrich.py`: replace YAML-based ontology embeddings with `OntologyStore` vector index; use `nearest_terms()` for ontology_term assignment
- [ ] T021 [US2] Update `ontology refresh` in `library/src/undata_library/cli.py`: download OBO files → load into OntologyStore → build vector index; remove --cache-dir flag; use `{output_dir}/ontology-store/` and `{output_dir}/ontology-vectors.parquet`
- [ ] T022 [US2] Add `ontology search QUERY` CLI command in `library/src/undata_library/cli.py`: calls `OntologyStore.search_terms()`, displays results
- [ ] T023 [US2] Add `ontology info` CLI command in `library/src/undata_library/cli.py`: shows loaded ontologies, term counts, store size, vector index status
- [ ] T024 [US2] Deprecate `library/src/undata_library/ontology_cache.py`: add deprecation note; remove imports from other modules
- [ ] T025 Write tests in `library/tests/test_ontology_cli.py`: (a) ontology refresh creates store + vector index; (b) ontology search returns results; (c) ontology info shows loaded ontologies; (d) enrich uses OntologyStore not OntologyCache
- [ ] T026 Lint + run all tests; commit Phase 5

---

## Phase 6: US4 — Extensible Config + US1 Full Load

**Goal**: Custom ontology config; load all 5 ontologies including NCIT and NCBITaxon.

- [ ] T027 [US4] Implement `add_ontology(name, url, format)` in `ontology_store.py`: append to ontologies.yaml config; download and load on next refresh
- [ ] T028 [US4] Add `--exclude NAME` flag to `ontology refresh` CLI: skip specified ontologies (useful for NCBITaxon which is very large)
- [ ] T029 [US1] Load all 5 ontologies: run `undata-library ontology refresh --output-dir /tmp/undata-registry`; verify PATO >2K terms, HP >15K, OBI >4K, NCIT >170K, NCBITaxon >2M
- [ ] T030 [US3] Build full vector index over all loaded terms; verify parquet file size reasonable
- [ ] T031 [US3] Run `undata-library enrich` with full vector index; verify more ontology_terms assigned than with old YAML cache
- [ ] T032 Write tests in `library/tests/test_extensible_ontology.py`: (a) custom ontology URL added to config; (b) --exclude skips specified ontology; (c) term from custom ontology queryable after load
- [ ] T033 Lint + run all tests; commit Phase 6

---

## Phase 7: Polish

- [ ] T034 Remove old `ontology-cache/` references from cli.py, enrich.py, verify.py, .gitignore
- [ ] T035 Update README.md: document ontology service (store, search, vector index)
- [ ] T036 Run full pipeline (all 5 sources + enrich with full ontology index)
- [ ] T037 Verify term lookup < 1ms (benchmark)
- [ ] T038 Run all library tests: `uv run pytest tests/ -v`
- [ ] T039 Lint all code: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- [ ] T040 Final commit and push

---

## Dependencies

```
Phase 1 (T001-T002): Setup — no deps
Phase 2 (T003-T009): OntologyStore — depends on Phase 1
Phase 3 (T010-T013): SPARQL lookup — depends on Phase 2
Phase 4 (T014-T018): Vector index — depends on Phase 2 (can parallel with Phase 3)
Phase 5 (T019-T026): Wiring — depends on Phase 3 + Phase 4
Phase 6 (T027-T033): Config + full load — depends on Phase 5
Phase 7 (T034-T040): Polish — depends on all

Parallelizable: Phase 3 ‖ Phase 4
```

## Implementation Strategy

1. **Phase 1-2** (T001-T009): OntologyStore with pyoxigraph + OBO parser. **Suggested MVP.**
2. **Phase 3** (T010-T013): SPARQL lookup — core query interface.
3. **Phase 4** (T014-T018): Vector index — enables semantic enrichment.
4. **Phase 5** (T019-T026): Wire into all commands — full integration.
5. **Phase 6** (T027-T033): Extensible config + full 5-ontology load.
6. **Phase 7** (T034-T040): Cleanup + polish.

**Suggested MVP**: Phases 1-3 (T001-T013) — persistent store + SPARQL lookup.
