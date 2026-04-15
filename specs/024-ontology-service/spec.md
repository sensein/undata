# Feature Specification: Local Ontology Service with Vector Index

**Feature Branch**: `024-ontology-service`
**Created**: 2026-03-21
**Status**: Draft
**Input**: Build a local SPARQL-backed ontology service using oxigraph that downloads bulk ontology files (OBO/OWL/TTL), loads them into a persistent local store, exposes SPARQL queries for term lookup, and builds a vector index over term labels+synonyms for semantic search and element-to-ontology alignment.

## User Scenarios & Testing

### User Story 1 — Bulk Ontology Download and Local Store (Priority: P1)

A data curator runs `undata-library ontology refresh` and the system downloads full ontology files (OBO, OWL, or TTL) from their canonical distribution points, loads them into a persistent local oxigraph store, and makes all terms available for SPARQL query. Large ontologies (NCIT ~170K terms, NCBITaxon ~2.4M terms) load in minutes, not hours.

**Why this priority**: The current OLS API approach is rate-limited, incomplete (max_terms truncation), and slow. Bulk download + local store gives complete coverage and instant queries.

**Independent Test**: Run `ontology refresh`, then query for NCIT:C25150 (Age) via the local store and verify it returns the full term with label, synonyms, parents, and deprecated status.

**Acceptance Scenarios**:

1. **Given** `ontology refresh` runs, **When** PATO is downloaded, **Then** the full PATO OBO file (~3MB) is loaded into the local oxigraph store with all terms queryable.
2. **Given** NCIT OBO (~236MB) is downloaded, **When** loaded into oxigraph, **Then** >170,000 terms are available and the load completes in under 5 minutes.
3. **Given** NCBITaxon OBO (~624MB) is downloaded, **When** loaded, **Then** >2 million terms are available.
4. **Given** the store is persistent, **When** the user restarts the tool, **Then** no re-download or re-load is needed — the store is on disk.

---

### User Story 2 — SPARQL-Based Term Lookup (Priority: P1)

Any component that needs ontology term metadata (label, synonyms, parents, deprecated status) queries the local oxigraph store via SPARQL, replacing the flat YAML cache. Queries return in microseconds, not milliseconds.

**Why this priority**: The flat YAML cache is slow to load (parsing large YAML files), doesn't support complex queries (e.g., "all terms with label containing 'age'"), and is incomplete for large ontologies.

**Independent Test**: Query for all terms whose label contains "age" across all loaded ontologies. Verify results include NCIT:C25150 (Age), HP:0011462 (Young adult), etc.

**Acceptance Scenarios**:

1. **Given** ontologies are loaded, **When** `lookup_term(uri)` is called, **Then** it returns {label, synonyms, parents, deprecated} in < 1ms.
2. **Given** ontologies are loaded, **When** `search_terms(query="age")` is called, **Then** it returns all terms with "age" in label or synonyms, ranked by relevance.
3. **Given** the verify command checks ontology alignment, **When** it runs, **Then** it queries the local store instead of loading YAML cache files.

---

### User Story 3 — Vector Index for Semantic Search (Priority: P1)

Term labels and synonyms are embedded into a vector index (using the same embedding model as element embeddings). This enables semantic similarity search: given an element's `"{class} {name}: {description}"` embedding, find the nearest ontology terms by cosine distance. This powers the `enrich` step's ontology_term auto-assignment.

**Why this priority**: The current enrichment uses embedding distance between elements and ontology terms, but the ontology embeddings are limited by the YAML cache size. With the full ontology store + vector index, enrichment can search across all 170K+ NCIT terms, not just 1,000.

**Independent Test**: Embed the text "Subject age: Age of the subject in years" and find the nearest NCIT term. Verify NCIT:C25150 (Age) is in the top 3 results.

**Acceptance Scenarios**:

1. **Given** ontology terms are loaded and embedded, **When** `nearest_terms(embedding, top_k=5)` is called, **Then** it returns the 5 most semantically similar ontology terms with cosine similarity scores.
2. **Given** the `enrich` command runs, **When** assigning ontology_term to an element, **Then** it uses the vector index over the full ontology store (not the truncated YAML cache).
3. **Given** a new ontology is added, **When** `ontology refresh` runs, **Then** the vector index is rebuilt to include the new terms.

---

### User Story 4 — Extensible to New Ontologies (Priority: P2)

A curator can add a new ontology by specifying its download URL and format. The system downloads, loads into the store, and builds embeddings — no code changes required.

**Why this priority**: The 5 bundled ontologies cover the current sources but new domains (imaging modalities, experimental protocols) may need additional ontologies.

**Independent Test**: Add a custom ontology URL to the configuration, run `ontology refresh`, and verify its terms appear in the store and vector index.

**Acceptance Scenarios**:

1. **Given** a new ontology URL is added to the ontology config, **When** `ontology refresh` runs, **Then** the new ontology is downloaded, loaded, and indexed.
2. **Given** the config specifies format (obo, owl, ttl), **When** the ontology is loaded, **Then** oxigraph parses the correct format automatically.

---

### Edge Cases

- What if an ontology file is corrupted mid-download? Verify checksum after download; retry once; fail with clear error.
- What if oxigraph store becomes corrupted? Delete and rebuild from cached OBO files.
- What if the vector index is out of sync with the store? Rebuild index on `ontology refresh`.
- What if disk space is insufficient for NCBITaxon (large store)? Log warning with size estimate; allow `--exclude` flag to skip specific ontologies.

## Requirements

### Functional Requirements

**Ontology Store**

- **FR-001**: The system MUST download full ontology files (OBO preferred, OWL/TTL as alternatives) from canonical URLs and load them into a persistent local oxigraph store.
- **FR-002**: The oxigraph store MUST be persistent on disk at `{output_dir}/ontology-store/` (not in-memory), surviving restarts without re-download.
- **FR-003**: The store MUST support the 5 bundled ontologies (NCIT, PATO, HP, OBI, NCBITaxon) and be extensible to custom ontologies via configuration.
- **FR-004**: Loading a large ontology (NCIT ~236MB OBO) MUST complete in under 5 minutes.
- **FR-005**: The system MUST track which ontologies are loaded, their version/download date, and file checksums.

**SPARQL Query Interface**

- **FR-006**: `lookup_term(uri) -> {label, synonyms, parents, deprecated}` MUST query the oxigraph store via SPARQL and return results in < 1ms.
- **FR-007**: `search_terms(query, ontology=None, limit=100) -> list[{uri, label, score}]` MUST search term labels and synonyms using SPARQL CONTAINS or regex.
- **FR-008**: The `verify` command MUST use the oxigraph store instead of the flat YAML cache.
- **FR-009**: The flat YAML ontology cache (ontology-cache/*.yaml) MUST be replaced by the oxigraph store. The old cache format is no longer written.

**Vector Index**

- **FR-010**: Term labels + synonyms MUST be embedded using the same model as element embeddings (default: all-MiniLM-L6-v2) and stored in a vector index at `{output_dir}/ontology-vectors.parquet`.
- **FR-011**: `nearest_terms(embedding, top_k=5) -> list[{uri, label, score}]` MUST return the nearest ontology terms by cosine distance.
- **FR-012**: The `enrich` command MUST use the vector index over the full ontology store for ontology_term auto-assignment (replacing the truncated YAML-based embeddings).
- **FR-013**: The vector index MUST be rebuilt on every `ontology refresh`.

**CLI Integration**

- **FR-014**: `undata-library ontology refresh [--ontology NAME] [--exclude NAME]` MUST download ontologies, load into oxigraph store, and build vector index.
- **FR-015**: `undata-library ontology search QUERY [--ontology NAME] [--limit N]` NEW command for interactive term search against the local store.
- **FR-016**: `undata-library ontology info` NEW command showing loaded ontologies, term counts, store size, and vector index status.

### Key Entities

- **OntologyStore**: Persistent oxigraph-backed RDF store. Loads OBO/OWL/TTL files. Exposes SPARQL query interface. Stored at `{output_dir}/ontology-store/`.
- **OntologyVectorIndex**: Parquet-based vector index over term embeddings. Same format as element embeddings but keyed by term URI.
- **OntologyConfig**: Per-ontology configuration — name, download URL, format, enabled/disabled.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All 5 ontologies loaded into oxigraph store with full term counts (NCIT >170K, PATO >2K, HP >15K, OBI >4K, NCBITaxon >2M).
- **SC-002**: Term lookup by URI returns in < 1ms.
- **SC-003**: `ontology refresh` for all 5 ontologies completes in under 15 minutes (including download + load + vector index).
- **SC-004**: `enrich` with full ontology vector index assigns ontology_term to more elements than the truncated YAML cache did.
- **SC-005**: `ontology search "age"` returns relevant terms from multiple ontologies.
- **SC-006**: Store is persistent — second run of `ontology refresh` skips already-loaded ontologies unless `--force`.

### Assumptions

- `pyoxigraph` is used for the local RDF store (pure Python bindings to oxigraph Rust engine).
- OBO format is parsed by pronto (small ontologies) or fast line parser (large ontologies) and converted to RDF triples for oxigraph.
- The vector index uses the same embedding model and parquet format as the element embedding store.
- The oxigraph store replaces the flat YAML ontology cache entirely.
