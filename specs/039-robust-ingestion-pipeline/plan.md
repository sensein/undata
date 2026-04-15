# Implementation Plan: Robust Ingestion Pipeline v2

**Branch**: `039-robust-ingestion-pipeline` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)

## Summary

Replace per-entity YAML files with Parquet containers for million-scale storage. Route all adapters (including batch OpenNeuro/NDA) through the standard pipeline. Preserve NDA cross-structure aliases. Display element range information in the frontend.

## Technical Context

**Language/Version**: Python 3.14 (library + backend), TypeScript (frontend)
**Primary Dependencies**: pyarrow/pandas (Parquet), datalad (OpenNeuro), httpx (NDA API), litellm (enrichment)
**Storage**: Parquet files (staging + registry), PostgreSQL 16 + pgvector (backend), pyoxigraph (ontologies)
**Testing**: pytest, playwright
**Project Type**: Full-stack (library + backend + frontend)
**Performance Goals**: NDA full ingestion <30min, OpenNeuro 100 datasets <20min, enrichment 220K elements <30min
**Constraints**: Peak memory <8GB for enrichment, registry <5GB for 1M+ entities
**Scale/Scope**: 2.7M NDA entities, 257K OpenNeuro entities, 17K ReproSchema entities, 8 adapters

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Parquet is simpler than SQLite for this use case; single format |
| II. TDD | PASS | Tests for StorageBackend Parquet impl, batch CLI, range display |
| III. API-First | PASS | StorageBackend protocol extended, CLI contract defined |
| IV. Observability | PASS | Batch run summaries with per-dataset breakdown |
| V. No Deprecation | PASS | YAML backend replaced, not deprecated |
| VI. Environment Isolation | PASS | pyarrow via uv, no new venvs |
| VII. Developer Experience | PASS | CLI batch mode replaces ad-hoc scripts |
| VIII. Merge Before New Spec | PASS | 038 merged to main |

## Project Structure

```text
library/
├── src/undata_library/
│   ├── storage/
│   │   ├── protocol.py         # StorageBackend — add Parquet methods
│   │   ├── file_backend.py     # FileBackend — Parquet + YAML hybrid
│   │   └── parquet_store.py    # NEW: Parquet read/write for entity collections
│   ├── adapters/
│   │   └── nda.py              # Add alias dedup + alias_hints
│   ├── cli.py                  # Add --batch N, --all flags
│   ├── enrich.py               # Chunk-based enrichment, species precision
│   ├── align.py                # Use alias_hints from NDA
│   └── ingest.py               # Batch source iteration
│
backend/
├── src/
│   ├── services/
│   │   └── import_service.py   # Read Parquet registry format
│   └── graphql/resolvers.py    # No changes needed (reads from DB)
│
frontend/
├── components/
│   └── EntityDetailLayout.tsx  # Add range display section
└── app/
    └── elements/[id]/page.tsx  # Show range, valueset link, type_ref link
```

## Phases

### Phase 1: Parquet Storage Backend (US1)
- Implement ParquetStore for reading/writing entity collections
- Extend FileBackend to use Parquet when count > threshold
- Migrate staging and commit to Parquet output
- Maintain YAML fallback for small sources

### Phase 2: Pipeline Routing + Batch CLI (US2, US5)
- Add --batch N and --all flags to pipeline CLI
- OpenNeuro batch: iterate datasets, stage all, enrich+commit once
- NDA batch: iterate structures, stage all, enrich+commit once
- Remove ad-hoc batch scripts (replaced by CLI)

### Phase 3: NDA Aliases + Alignment (US3)
- NDA adapter: group elements by name across structures, dedup
- Add alias_hints to semantic dict
- Alignment step: boost confidence for alias_hints matches

### Phase 4: Element Range Display (US4)
- Audit all adapters for range field population
- Add range section to element detail page
- Link response_options to ValueSet entities
- Link type_ref to Schema entities

### Phase 5: Enrichment Scaling (US6)
- Chunk-based enrichment (10K batches)
- Species precision: prefer species over genus matches
- Test on full 220K registry
