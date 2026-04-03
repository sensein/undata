# Implementation Plan: Unified Embedding & Storage

**Branch**: `040-unified-embedding-storage` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)

## Summary

Eliminate YAML from the pipeline. Make Parquet the sole storage format. Compute embeddings at commit for all entity types. Recompute on update. Unified store interface.

## Technical Context

**Language/Version**: Python 3.14 (library + backend), TypeScript (frontend)
**Primary Dependencies**: pyarrow (Parquet), sentence-transformers (embeddings), pyoxigraph (ontologies)
**Storage**: Parquet files (library registry), PostgreSQL 16 + pgvector (backend)
**Testing**: pytest (463 existing tests)
**Project Type**: Full-stack (library + backend + frontend)
**Performance Goals**: Import 7K entities <30s, embedding computation 10K entities <60s
**Constraints**: Peak memory <4GB, no YAML files in pipeline
**Scale/Scope**: 7K entities (core), up to 1M+ (with batch sources)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Removes complexity (dual format → single format) |
| II. TDD | PASS | Tests for unified store, embedding at commit |
| III. API-First | PASS | Unified store interface defined before implementation |
| IV. Observability | PASS | Missing embedding detection logged |
| V. No Deprecation | PASS | YAML store deleted, not deprecated |
| VI. Environment Isolation | PASS | No new dependencies |
| VII. Developer Experience | PASS | Single store, single format, simpler debugging |
| VIII. Merge Before New Spec | PASS | 039 merged to main |

## Project Structure

```text
library/
├── src/undata_library/
│   ├── storage/
│   │   ├── protocol.py         # Simplified — single EntityStore protocol
│   │   ├── parquet_store.py    # THE store — read/write/list/count/update
│   │   └── file_backend.py     # Thin wrapper: FileBackend(ParquetStore)
│   ├── ingest.py               # Extract → write_batch to ParquetStore
│   ├── enrich.py               # Read from store, write enriched back
│   ├── commit.py               # Read from store, compute sha256 + embeddings, write
│   ├── align.py                # Read from store (entities have embeddings)
│   ├── alias_detection.py      # Read from store
│   ├── staging.py              # Simplified — create_staging_dir + store ref
│   └── embeddings.py           # compute_entity_embeddings + ontology index

backend/
├── src/
│   ├── storage/database_backend.py  # Use pre-computed embeddings
│   └── services/import_service.py   # Read Parquet only
```

## Phases

### Phase 1: Unified Store (US5)
- Consolidate EntityStore protocol to Parquet-only
- FileBackend becomes thin wrapper over ParquetStore
- All callers use ParquetStore directly or via FileBackend
- Tests for unified store

### Phase 2: Parquet-Only Pipeline (US1)
- Rewrite ingest to collect entities → write_batch
- Rewrite enrichment to read/write ParquetStore
- Rewrite commit to read ParquetStore, write ParquetStore
- Cross-reference resolution on DataFrames
- Remove iter_staged YAML path, write_staged_entity

### Phase 3: Embeddings at Commit (US2)
- Compute embeddings during commit for all entity types
- Comprehensive embedding text (name + desc + type + unit + annotations + provenance)
- Store embedding in Parquet entity record
- Backend import uses pre-computed embeddings (no model loading)

### Phase 4: Recompute on Update (US3)
- Backend mutations trigger embedding recomputation
- update_element, approve_annotation, version_element all recompute
- Embedding service only loaded when needed

### Phase 5: Missing Embedding Detection (US4)
- Backend detects entities without embeddings during import
- Computes embedding on demand
- Flags entity for re-alignment
