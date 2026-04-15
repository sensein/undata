# Implementation Plan: System Hardening

**Branch**: `038-system-hardening` | **Date**: 2026-04-02 | **Spec**: [spec.md](spec.md)

## Summary

Consolidation feature addressing 18+ outstanding tasks: wire LLM curation chat, evidence-based confidence, name-based transforms, additional data sources, search modes, ontology admin, server-side sorting, audit log, nightly exports, CI updates, and versioned dependency management.

## Technical Context

**Language/Version**: Python 3.14 (library + backend), TypeScript (frontend)
**Primary Dependencies**: litellm (LLM), sentence-transformers (embeddings), datalad (datasets), pyoxigraph (ontologies)
**Storage**: PostgreSQL 16 + pgvector + JSONB
**Testing**: pytest, playwright
**Project Type**: Full-stack (library + backend + frontend)
**Performance Goals**: Chat response <5s, search <1s, transform pipeline <10min
**Scale/Scope**: 2191 elements, 915 schemas, 5500 values across 5+ sources

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Extends existing infrastructure; no new services |
| II. TDD | PASS | Evidence chain testable; transform tests exist |
| III. API-First | PASS | GraphQL contracts defined |
| IV. Observability | PASS | Audit log is the core deliverable |
| V. No Deprecation | PASS | Additive changes |
| VI. Environment Isolation | PASS | No new venvs |
| VII. Developer Experience | PASS | Full registry via override; seed subset committed |
| VIII. Merge Before New Spec | PASS | All previous features merged |

## Project Structure

```text
library/
├── src/undata_library/
│   ├── transform.py           # Name-based matching, many-to-one
│   ├── enrich.py              # Evidence chain generation
│   ├── adapters/
│   │   └── nda.py             # NEW: NDA data dictionary adapter
│   └── version_check.py       # NEW: dependency version detection

backend/
├── src/
│   ├── db/models.py           # AuditLog writes on every mutation
│   ├── graphql/
│   │   ├── types.py           # SearchMode enum, EvidenceChain, AuditLogEntry
│   │   ├── resolvers.py       # ontologyStoreInfo, auditLog, search modes, sorting
│   │   └── schema.py          # Wire new queries/mutations
│   ├── services/
│   │   ├── chat_service.py    # Verify LLM wiring, auto-suggest on load
│   │   ├── audit_service.py   # NEW: write audit entries
│   │   ├── nightly_export.py  # Schedule + produce archives
│   │   └── version_service.py # NEW: check dependency versions
│   └── main.py                # Nightly task, static file serving

frontend/
├── app/
│   ├── search/page.tsx        # Add mode toggle
│   ├── downloads/page.tsx     # Download page for releases
│   └── admin/ontologies/      # Read from pyoxigraph store
├── components/
│   ├── EntityDataGrid.tsx     # Infinite scroll verification
│   └── EvidenceChain.tsx      # NEW: display evidence for proposals
└── graphql/queries.ts         # SearchMode, auditLog queries
```

## Phases

### Phase 1: LLM Chat Wiring + Evidence Chain (US1)
- Verify chat_service processes messages end-to-end
- Add auto-suggest on entity load
- Implement EvidenceChain generation for enrichment annotations
- Display evidence in proposal diffs

### Phase 2: Name-Based Transforms (US2)
- Add name-based matching to transform pipeline
- Extend TransformRecord for many-to-one
- Re-run transforms to verify 100+ generated

### Phase 3: Additional Sources (US3)
- NDA data dictionary adapter
- Test OpenNeuro + ReproSchema ingestion end-to-end
- Regenerate full registry with new sources

### Phase 4: Search Modes + Ontology Admin (US4 + US5)
- Add SearchMode enum and toggle to search page
- Ontology admin reads from pyoxigraph store
- NCBITaxon filtering for embeddings

### Phase 5: Server-Side Sorting + Infinite Scroll (US6)
- Extend sortBy/sortOrder to all browse resolvers
- Verify infinite scroll works across all pages

### Phase 6: Audit Log + Downloads (US7)
- Audit service writes entries on every mutation
- Nightly export scheduler
- Download page

### Phase 7: CI + Pipeline Maintenance (US8)
- Update GitHub Actions to v5/Node.js 24
- Ontology vector index auto-rebuild
- LLM-assisted enrichment for borderline candidates

### Phase 8: Versioned Dependency Management (US9)
- Version check service with checksum comparison
- Scheduled refresh with auto re-enrichment
- Provenance recording for version transitions
