# Research: Robust Ingestion Pipeline v2

## R1: Binary Container Format for Entity Storage

**Decision**: Use **Parquet** as the primary binary container format for both staging and committed entities.

**Rationale**:
- Parquet is already a dependency (used for embedding storage)
- Columnar format allows efficient filtering by sha256, entity_type, source
- Compression reduces storage 10-20x vs individual YAML files
- Pandas/PyArrow provide fast read/write APIs
- Compatible with the existing StorageBackend protocol pattern
- Can store JSONB-like nested dicts via JSON-serialized columns

**Alternatives considered**:
- SQLite: Good for indexed lookups but requires schema management; less efficient for bulk read/write of heterogeneous JSON data
- JSONL (newline-delimited JSON): Simple but no indexing, no compression, still one file but O(n) scan for lookups
- MessagePack: Binary JSON, fast, but no columnar indexing

**Container structure**: One Parquet file per entity type per source:
```
registry/
├── elements/
│   ├── bids.parquet          # All BIDS elements
│   ├── nda.parquet           # All NDA elements
│   ├── openneuro.parquet     # All OpenNeuro elements
│   └── _index.parquet        # Cross-source index (sha256 → source file)
├── schemas/
│   ├── ...
├── values/
│   ├── ...
└── valuesets/
    ├── ...
```

**Columns**: sha256, file_name, semantic (JSON string), provenance (JSON string), ontology_annotations (JSON string), source, created_at

**Threshold**: >1,000 entities → Parquet; ≤1,000 → individual YAML files (configurable)

## R2: Pipeline Routing for Batch Sources

**Decision**: Add `--batch N` and `--all` flags to the existing pipeline CLI. Batch sources produce a stream of `ClassifiedEntity` objects that feed into the same staging → enrich → align → commit pipeline.

**Rationale**: The pipeline already works source-by-source. Batch mode iterates over multiple datasets/structures from the same adapter, staging all entities before running enrichment and commit once.

**Key design**:
1. Adapter's `extract()` called once per dataset/structure in the batch
2. All entities from the batch accumulated in a single staging area
3. Enrichment runs once on the full batch (not per-dataset)
4. Commit deduplicates across all datasets in the batch
5. One run summary per batch, with per-dataset breakdown

**For OpenNeuro**: Clone dataset → extract → clean up clone → next dataset → (after all) enrich → commit
**For NDA**: Fetch structure from API → extract → next structure → (after all) enrich → commit

## R3: NDA Cross-Structure Aliasing

**Decision**: NDA elements that share the same `name` across different data structures are aliased by adding all structures to the element's provenance list, plus an `alias_hints` field in the element's semantic dict.

**Rationale**: NDA's data dictionary API returns elements by structure. Elements like `subjectkey`, `interview_date`, `interview_age`, `sex`, `gender` appear across hundreds of structures with identical semantics. The adapter should detect this during extraction (not alignment) by grouping by element name.

**Implementation**:
1. During NDA batch extraction, maintain a `name → [structure1, structure2, ...]` map
2. Deduplicate elements by name+type, accumulating provenance from all structures
3. Add `alias_hints: ["nda:{structure1}", "nda:{structure2}", ...]` to semantic dict
4. Alignment step checks `alias_hints` and treats these as high-confidence pre-verified aliases

## R4: Element Range Fields Across Adapters

**Decision**: Audit all 8 adapters to ensure they populate range fields. Add a `range_display` computed section to the frontend element detail page.

**Adapter audit**:
| Adapter | response_options | min/max | pattern | type_ref | Status |
|---------|-----------------|---------|---------|----------|--------|
| BIDS | enum from JSON Schema | from constraints | regex from pattern | $ref | Mostly complete |
| NWB | via hdmf enums | ✗ | ✗ | type_ref from class refs | Needs min/max |
| DANDI | from Pydantic literals | from ge/le | from regex | from model refs | Complete |
| openMINDS | from instance values | ✗ | ✗ | from ranges | Needs min/max |
| AIND | from JSON Schema enum | from minimum/maximum | from pattern | from $ref | Complete |
| OpenNeuro | from TSV unique values + JSON Levels | ✗ | ✗ | ✗ | Needs JSON sidecar range |
| ReproSchema | from choices | from minValue/maxValue | ✗ | ✗ | Complete |
| NDA | from notes parsing | from valueRange | ✗ | ✗ | Complete |

## R5: Enrichment Scaling

**Decision**: Process enrichment in chunks of 10,000 elements. Use memory-mapped embedding index. Prefer species-level NCBITaxon matches by scoring penalty for genus-level.

**Rationale**: At 220K elements, loading all embeddings into memory at once is feasible (384-dim × 220K = ~320MB). The bottleneck is the ontology index (268K terms × 384-dim = ~390MB). Total peak memory ~1.5GB, well within 8GB budget.

**Species precision**: When both genus and species match above threshold, prefer the more specific (species > genus > family > order). Implementation: post-filter annotations to remove genus-level when species-level exists for the same organism.
