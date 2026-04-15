# Implementation Plan: Local Ontology Service with Vector Index

**Branch**: `024-ontology-service` | **Date**: 2026-03-21 | **Spec**: spec.md

## Summary

Replace the flat YAML ontology cache with a persistent pyoxigraph RDF store backed
by bulk OBO/OWL downloads. Add a vector index over all term labels+synonyms for
semantic search powering element-to-ontology alignment. SPARQL queries for term
lookup replace YAML parsing.

## Technical Context

**Language/Version**: Python 3.14
**New dependencies**: `pyoxigraph>=0.4` (Rust-based RDF store with Python bindings)
**Existing deps used**: pronto (OBO parsing), pyarrow (vector index parquet), sentence-transformers (optional, embeddings)
**Storage**: Persistent oxigraph store at `{output_dir}/ontology-store/`; vector parquet at `{output_dir}/ontology-vectors.parquet`
**Testing**: pytest
**Performance Goals**: NCIT load < 5 min; term lookup < 1ms; full refresh < 15 min
**Scale**: NCIT ~170K terms, NCBITaxon ~2.4M terms, total ~2.6M terms across 5 ontologies

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Single module (ontology_store.py) wraps pyoxigraph; replaces complex YAML cache |
| II. TDD | PASS | Test-alongside |
| III. API-First Design | PASS | OntologyStore API defined before implementation |
| IV. Observability | PASS | ontology info command shows loaded ontologies, term counts, store size |
| V. Versioning & Stability | PASS | Breaking: removes YAML cache. Not released — no migration needed. |
| VI. Environment Isolation | PASS | pyoxigraph is a pure pip install, no system deps |
| Git Commit Discipline | PASS | Commit per phase |

## Phase 1: OntologyStore with pyoxigraph

**Goal**: Persistent RDF store, bulk OBO loading, SPARQL term lookup.

| File | Change |
|------|--------|
| `ontology_store.py` | NEW — `OntologyStore` class: `__init__(store_path)`, `load_ontology(name, obo_path)`, `lookup_term(uri)`, `search_terms(query)`, `list_loaded()`, `term_count()` |
| `ontology_fetch.py` | MODIFY — `fetch_ontology()` now returns path to downloaded OBO file (not parsed dict); store loading happens separately |
| `pyproject.toml` | ADD `pyoxigraph>=0.4` to dependencies |

**OntologyStore design**:

```python
class OntologyStore:
    """Persistent RDF store for ontology terms using pyoxigraph."""

    def __init__(self, store_path: Path):
        self.store = pyoxigraph.Store(str(store_path))

    def load_obo(self, name: str, obo_path: Path) -> int:
        """Parse OBO file and insert triples. Returns term count."""
        # Fast OBO line parser → generate triples:
        # <uri> rdfs:label "Age"
        # <uri> oboInOwl:hasExactSynonym "patient age"
        # <uri> rdfs:subClassOf <parent_uri>
        # <uri> owl:deprecated "true"^^xsd:boolean

    def lookup_term(self, uri: str) -> dict | None:
        """SPARQL query for a single term."""
        # SELECT ?label ?deprecated WHERE { <uri> rdfs:label ?label . ... }

    def search_terms(self, query: str, limit: int = 100) -> list[dict]:
        """SPARQL CONTAINS search on labels + synonyms."""

    def all_terms(self) -> Iterator[tuple[str, str]]:
        """Yield (uri, label) for all terms — used for vector index building."""
```

**OBO → RDF triple conversion** (fast line parser, no pronto for large files):
- `[Term]` stanza → subject URI
- `name:` → `<uri> rdfs:label "..."`
- `synonym:` → `<uri> oboInOwl:hasExactSynonym "..."`
- `is_a:` → `<uri> rdfs:subClassOf <parent_uri>`
- `is_obsolete: true` → `<uri> owl:deprecated "true"^^xsd:boolean`
- `namespace:` → `<uri> oboInOwl:hasOBONamespace "..."`

## Phase 2: Vector Index Over Ontology Terms

**Goal**: Embed all term labels+synonyms, store in parquet for nearest-neighbor search.

| File | Change |
|------|--------|
| `ontology_store.py` | ADD `build_vector_index(model_name) -> EmbeddingStore`; iterate all_terms(), embed `"{label}: {synonym1}, {synonym2}"`, save to ontology-vectors.parquet |
| `embeddings.py` | Minor — reuse EmbeddingStore for ontology vectors |

**Vector index content**: For each term, embed the text `"{label}: {synonym1}, {synonym2}"` (same format as existing `build_ontology_embeddings`). Store in parquet with `term_uri` column.

## Phase 3: Wire Into Existing Commands

**Goal**: Replace YAML cache usage with OntologyStore across all commands.

| File | Change |
|------|--------|
| `ontology_cache.py` | DEPRECATE — `OntologyCache` class replaced by `OntologyStore` |
| `enrich.py` | MODIFY — use OntologyStore + vector index instead of YAML cache + embeddings |
| `verify.py` | MODIFY — use OntologyStore.lookup_term() instead of OntologyCache.lookup() |
| `cli.py` | MODIFY — `ontology refresh` loads into store + builds vectors; ADD `ontology search`, `ontology info` commands; REMOVE `--cache-dir` (replaced by store in output_dir) |

## Phase 4: Extensible Ontology Config

**Goal**: YAML config for custom ontologies.

| File | Change |
|------|--------|
| `ontology_store.py` | ADD `OntologyConfig` model (name, url, format, enabled); load from `source_defs/ontologies.yaml` |
| `source_defs/ontologies.yaml` | NEW — bundled config for 5 ontologies with canonical URLs |

```yaml
# source_defs/ontologies.yaml
ontologies:
  - name: ncit
    url: http://purl.obolibrary.org/obo/ncit.obo
    format: obo
  - name: pato
    url: http://purl.obolibrary.org/obo/pato.obo
    format: obo
  - name: hp
    url: http://purl.obolibrary.org/obo/hp.obo
    format: obo
  - name: obi
    url: http://purl.obolibrary.org/obo/obi.obo
    format: obo
  - name: ncbitaxon
    url: http://purl.obolibrary.org/obo/ncbitaxon.obo
    format: obo
```

## Phase 5: Polish + Full Ontology Load

- Load all 5 ontologies into store
- Build full vector index
- Run enrichment with full index
- Verify term counts match expectations
- Remove old ontology_cache.py and YAML cache references
- Lint + test + commit

## Project Structure

```text
library/src/undata_library/
├── ontology_store.py    # NEW — OntologyStore (pyoxigraph), vector index, SPARQL
├── ontology_fetch.py    # MODIFIED — returns OBO file path (not parsed dict)
├── ontology_cache.py    # DEPRECATED — replaced by ontology_store.py
├── enrich.py            # MODIFIED — uses OntologyStore
├── verify.py            # MODIFIED — uses OntologyStore
├── cli.py               # MODIFIED — ontology search, ontology info, wiring
├── source_defs/
│   └── ontologies.yaml  # NEW — bundled ontology config
└── ...
```

**Output directory**:
```text
{output_dir}/
├── ontology-store/          # NEW — persistent pyoxigraph RDF database
├── ontology-vectors.parquet # NEW — vector index over term embeddings
├── elements/
├── schemas/
└── ...
```

## Dependency Graph

```
Phase 1 (store)     → foundational
Phase 2 (vectors)   → depends on Phase 1
Phase 3 (wiring)    → depends on Phase 1 + Phase 2
Phase 4 (config)    → independent (can parallel with Phase 2/3)
Phase 5 (polish)    → depends on all
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| OBO → RDF triples | Medium | Line parser + triple generation; must handle OBO edge cases |
| pyoxigraph store | Low | Simple API; persistent store is a one-liner |
| SPARQL queries | Medium | Query construction for lookup/search; optimize for large stores |
| Vector index | Low | Reuses existing EmbeddingStore pattern |
| Wiring into enrich/verify | Medium | Replace OntologyCache references; different API |
| NCBITaxon scale (2.4M terms) | High | Memory and time for loading + embedding; may need chunked processing |

## Risks

| Risk | Mitigation |
|------|-----------|
| NCBITaxon too large for pyoxigraph in-memory | pyoxigraph Store is disk-based (not in-memory); handles large datasets |
| OBO parsing edge cases | Use pronto for small ontologies (validated); fast parser for large (well-tested on NCIT/NCBITaxon) |
| Vector index for 2.4M terms too slow | Embed in batches; only embed terms with labels (skip anonymous nodes) |
| pyoxigraph not available for Python 3.14 | Check compatibility; fallback to rdflib if needed |
