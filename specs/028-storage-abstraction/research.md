# Research: Library Storage Abstraction

## R1: StorageBackend Protocol Design

**Decision**: Use Python `typing.Protocol` with entity-type-specific methods rather than a single generic CRUD interface.

**Rationale**: The library has distinct I/O patterns per entity type:
- Core entities (elements, schemas, values, valuesets) have dual staging/committed lifecycle with content-addressed filenames
- Curation flags have UUID filenames, status filtering, and resolution updates
- Run summaries have timestamp-based filenames and latest-run lookups
- Discovery candidates are a singleton file with merge semantics

A single `read(type, id)` interface would lose these distinctions and require every backend to reimplement routing logic. Instead, the protocol defines operations per entity category:
- `EntityStore` — CRUD + list + merge_provenance for core entity types
- `FlagStore` — write/read/resolve for curation flags
- `RunStore` — save/load_previous for run summaries
- `StorageBackend` — composes all three

**Alternatives considered**:
- Generic CRUD (`read(type, id)`) — loses type-specific semantics, requires runtime dispatch
- One method per entity type (`read_element`, `read_schema`, ...) — too many methods (40+), hard to extend
- Repository pattern with abstract base classes — requires subclassing, more complex than Protocol

## R2: Staging vs Committed Entities

**Decision**: The StorageBackend manages the committed registry. Staging remains a separate concern handled by `StagingArea` which wraps a StorageBackend for temporary writes.

**Rationale**: Staging is a transient workspace — entities have UUID filenames, are modified in-place during enrichment, and are deleted after commit. The committed registry is persistent — entities have content-addressed filenames and accumulate provenance over time. These are fundamentally different lifecycles.

The staging area uses the same `EntityStore` methods but with a separate instance (FileBackend pointed at `.staging/{run_id}/` for files, or a temporary schema/table for databases).

**Alternatives considered**:
- Single backend with a `staged` flag on entities — mixes lifecycles, complicates queries
- Staging outside the protocol entirely — current behavior, but means the backend can't reuse staging logic

## R3: Pipeline Function Signatures

**Decision**: Pipeline functions accept `backend: StorageBackend` as their primary parameter. The CLI creates a `FileBackend(output_dir)` and passes it. Functions that need both staging and output get `staging: StorageBackend, output: StorageBackend`.

**Rationale**: Current signatures use `Path` for both staging and output directories. Replacing `Path` with `StorageBackend` is a mechanical change that preserves the same call structure. Functions that only read (align, transform) get a single backend. Functions that read from staging and write to committed (commit) get two.

Pattern:
```
ingest_source(source_name, schema_path, staging) → stats
enrich_elements(staging, cache_dir, ...) → stats
align_elements(backend, ...) → stats
commit_staged(staging, output) → stats
generate_transforms(backend, ...) → stats
```

## R4: Pipeline Reordering Impact

**Decision**: Reorder from extract→enrich→commit→align to extract→enrich→align→commit.

**Rationale**: Currently alignment runs on committed entities and modifies them in-place (adds provenance, transfers annotations). But these modifications happen *after* the content hash is computed at commit time. Moving align before commit means:
1. Cross-source annotation transfers happen on staged entities
2. Transferred annotations are included in the content hash
3. Two entities from different sources that share a concept (via transfer) may now produce the same hash and merge at commit time

**Risk**: Alignment currently reads from `elements/` (committed). Moving it to staging means it reads from `.staging/{run_id}/elements/`. For multi-source alignment to work, all sources must be staged *together* before alignment. This is already the case in the pipeline command — all sources are ingested into the same staging area. But it changes the standalone `align` CLI command behavior.

**Mitigation**: The standalone `align` command continues to work on committed entities (backward compatible). The pipeline command reorders stages internally.

## R5: Adapter Interface Change

**Decision**: Rename `BaseAdapter.extract()` to `BaseAdapter.to_linkml()` returning `SchemaDefinition`, and add a standard `LinkMLExtractor.extract(schema_def)` that produces `[ClassifiedEntity]`.

**Rationale**: Brainstorm v1 found 51 misclassification issues because adapters did their own entity classification. The LinkML-first pattern was validated — all 5 adapters now build SchemaDefinition objects. But some adapters still have hybrid code paths. The rename makes the contract explicit: adapters produce LinkML, the extractor classifies.

**Alternatives considered**:
- Keep `extract()` name but change return type — confusing, same name different semantics
- Two-method interface (`to_linkml()` + `extract()`) — redundant, `extract()` becomes a one-liner wrapper
