# Implementation Plan: Knowledge Service

**Branch**: `036-knowledge-service` | **Date**: 2026-03-30 | **Spec**: [spec.md](spec.md)

## Summary

Expand the knowledge base: integrate domain-specific ontologies (HoMBA, NIDM, DICOM, RadLex, ReproSchema), add data source adapters (OpenNeuro via datalad, ReproSchema library, stats repos), build automated source discovery with ingestion queue, LLM-powered enrichment skills, and curator review workflow for annotations with element versioning.

## Technical Context

**Language/Version**: Python 3.14 (library + backend), TypeScript (frontend)
**Primary Dependencies**: pyoxigraph (ontology store), datalad (dataset access), pydicom (DICOM tags), litellm (LLM calls), sentence-transformers (embeddings)
**Storage**: PostgreSQL 16 + JSONB (ontology sources, ingestion jobs, LLM proposals)
**Testing**: pytest + pytest-asyncio (backend), library unit tests
**Target Platform**: Web (backend + frontend), CLI (library)
**Project Type**: Full-stack (library + backend + frontend)
**Performance Goals**: Ontology refresh <5 min per source, enrichment <1s per element, discovery scan <1 min
**Scale/Scope**: 4-5 new ontologies (~60K+ new terms), OpenNeuro (800+ datasets), ReproSchema (~200 activities)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Extends existing ontology store and adapter framework; no new architecture |
| II. TDD | PASS | Contract tests for new GraphQL endpoints; unit tests for adapters |
| III. API-First | PASS | GraphQL contracts defined for ontology management, ingestion queue, LLM enrichment |
| IV. Observability | PASS | Ingestion jobs and LLM proposals are persisted with full status tracking |
| V. No Deprecation | PASS | Additive changes only — new ontology sources, new adapters, new models |
| VI. Environment Isolation | PASS | datalad is a pip dependency; pydicom already available via bridge pattern |
| VII. Developer Experience | PASS | CLI commands for all operations; docker compose continues to work |

## Project Structure

### Source Code (changes by area)

```text
library/
├── src/undata_library/
│   ├── ontology.py                  # Extend: add_source(), refresh(), list_sources()
│   ├── adapters/
│   │   ├── openneuro.py             # NEW: OpenNeuro via datalad adapter
│   │   ├── reproschema.py           # NEW: ReproSchema library adapter
│   │   ├── registry.py              # Register new adapters
│   │   └── standalone_scripts/
│   │       └── dicom_to_ttl.py      # NEW: Generate TTL from pydicom dict
│   ├── enrich.py                    # Extend: curated annotation protection, re-enrich single
│   ├── llm_enrich.py                # Extend: enrichment skills (annotate, unit, align, describe)
│   ├── discovery.py                 # NEW: repository discovery scanner
│   └── models.py                    # Add: OntologySourceConfig, IngestionJobConfig

backend/
├── src/
│   ├── db/models.py                 # Add: OntologySource, IngestionJob, LLMEnrichmentProposal
│   ├── graphql/
│   │   ├── types.py                 # Add: OntologySource, IngestionJob, LLMEnrichmentProposal types
│   │   ├── resolvers.py             # Add: ontology/ingestion/enrichment resolvers
│   │   └── schema.py                # Wire new queries and mutations
│   ├── services/
│   │   ├── discovery_service.py     # NEW: background discovery scheduler
│   │   └── enrichment_service.py    # NEW: LLM enrichment orchestrator
│   └── tools/
│       └── enrichment_tools.py      # NEW: LLM tool definitions for enrichment skills

frontend/
├── app/
│   ├── admin/
│   │   ├── ontologies/page.tsx      # NEW: Ontology management interface
│   │   └── ingestion/page.tsx       # NEW: Ingestion queue interface
│   └── curation/
│       └── chat/page.tsx            # Extend: enrichment commands
├── components/
│   └── IngestionQueue.tsx           # NEW: Queue table component
└── graphql/
    └── queries.ts                   # Add: ontology, ingestion, enrichment queries
```

## Phases

### Phase 1: Domain-Specific Ontologies (US1)
- Add ontology source registration to ontology store (name, URL, format, active flag)
- Implement HoMBA, NIDM loaders (OWL/JSON-LD)
- Generate DICOM TTL from pydicom data dictionary
- Load RadLex OWL
- Re-run enrichment to verify coverage increase

### Phase 2: OpenNeuro & ReproSchema Adapters (US2)
- Implement OpenNeuro adapter using datalad (clone, scan TSV/CSV, parse JSON sidecars)
- Implement ReproSchema adapter (parse activity/item JSON-LD)
- Register new adapters in adapter registry
- Test ingestion on sample datasets

### Phase 3: Enrichment Review & Versioning (US3)
- Add curated_annotations field (protected from re-enrichment)
- Add superseded_by field for element versioning
- Create curation_update transform on semantic field changes
- Curator UI for approve/reject annotations

### Phase 4: Ontology Store Management (US4)
- OntologySource DB model and GraphQL endpoints
- Admin interface for ontology listing, add, refresh, toggle active
- CLI commands for ontology management

### Phase 5: Source Discovery & Ingestion Queue (US5 + US6)
- IngestionJob DB model and GraphQL endpoints
- Background discovery service polling OpenNeuro/DANDI APIs
- Auto-ingest for pre-approved sources
- Queue UI for curator review of pending ingestions

### Phase 6: LLM Enrichment Skills (US7)
- LLMEnrichmentProposal DB model and GraphQL endpoints
- Implement 4 enrichment skills (annotate, unit, align, describe)
- Batch enrichment with progress tracking
- Chat integration for enrichment commands
