# Implementation Plan: UX & UI Overhaul

**Branch**: `035-ux-overhaul` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)

## Summary

Comprehensive frontend and backend upgrade: rich property tables with entity chips, global search (lexical + semantic via pgvector), chat-first curation accessible from anywhere, modernized dense layouts, link health monitoring, and transform validation rules.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript (frontend)
**Primary Dependencies**: FastAPI, Strawberry GraphQL, Next.js, Apollo Client, TanStack Table, sentence-transformers (all-MiniLM-L6-v2)
**Storage**: PostgreSQL 16 + pgvector (vector similarity) + tsvector (full-text search)
**Testing**: pytest + pytest-asyncio (backend), Playwright (frontend visual)
**Target Platform**: Web (desktop 1080p+ primary, mobile responsive)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Search results <1s, detail page load <2s, 20+ visible rows at 1080p
**Scale/Scope**: ~2,300 entities, ~5,500 curation flags, ~20 external domains

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Reuses existing components (EntityDataGrid, EntityTag, SplitPanel). pgvector already in Docker image. No new services added. |
| II. TDD | PASS | Contract tests for search endpoint, visual regression tests for UI density |
| III. API-First | PASS | GraphQL contracts defined for search and link health |
| IV. Observability | PASS | Search queries logged with timing; link health results persisted |
| V. No Deprecation | PASS | Replacing current property tables, not deprecating them |
| VI. Environment Isolation | PASS | No new venvs needed; sentence-transformers already a library dependency |
| VII. Developer Experience | PASS | `docker compose up` continues to work; seed data includes embeddings |

## Project Structure

### Documentation (this feature)

```text
specs/035-ux-overhaul/
├── spec.md
├── plan.md              # This file
├── research.md
├── data-model.md
├── contracts/
│   ├── graphql-search.md
│   └── graphql-link-health.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Next: /speckit.tasks
```

### Source Code (changes by area)

```text
backend/
├── src/
│   ├── db/
│   │   └── models.py            # Add embedding, search_tsv columns; LinkHealthCheck model
│   ├── graphql/
│   │   ├── types.py             # SearchResult, LinkHealthCheck types
│   │   ├── resolvers.py         # globalSearch resolver, link health resolvers
│   │   └── schema.py            # Wire new queries
│   ├── services/
│   │   ├── search_service.py    # Hybrid search (tsvector + pgvector)
│   │   ├── embedding_service.py # Compute embeddings during import
│   │   └── link_checker.py      # Background link health task
│   └── storage/
│       └── database_backend.py  # Persist embeddings during entity write
├── postgres-init/
│   └── 02-enable-extensions.sql # CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;
└── seed/                        # Regenerate with embeddings

frontend/
├── components/
│   ├── GlobalSearch.tsx          # Search bar + results dropdown
│   ├── EntityTag.tsx             # Add "Chat about this" to popover
│   ├── EntityDataGrid.tsx        # Compact row height, case-insensitive sort
│   ├── EntityDetailLayout.tsx    # Dense layout, cross-reference sections
│   ├── ChatPanel.tsx             # General assistant mode (no entity required)
│   └── PropertyTable.tsx         # Shared rich table for schema props & valueset members
├── app/
│   ├── elements/[sha256]/page.tsx    # Dense layout, transforms section, used-in-schemas
│   ├── schemas/[sha256]/page.tsx     # PropertyTable instead of ad-hoc table
│   ├── values/[sha256]/page.tsx      # Dense layout
│   ├── valuesets/[sha256]/page.tsx   # PropertyTable for members
│   ├── transforms/[sha256]/page.tsx  # Dense layout
│   ├── curation/chat/page.tsx        # Full entity context right panel, standalone mode
│   └── status/page.tsx               # Link health dashboard
└── graphql/
    └── queries.ts               # globalSearch query, link health queries

library/
└── src/undata_library/
    ├── transform.py             # Array→singleton validation rule
    └── models.py                # structural_type field on SemanticIdentity
```

**Structure Decision**: Enhancement of existing web application structure. No new projects or services. All changes are within the existing backend/, frontend/, and library/ directories.

## Complexity Tracking

No constitution violations to justify.

## Phases

### Phase 1: Backend Search Infrastructure
- Enable pgvector and pg_trgm extensions in PostgreSQL init
- Add embedding and search_tsv columns to entity models
- Compute embeddings during import (reuse library's encode function)
- Implement globalSearch resolver with hybrid scoring
- Add search GraphQL query

### Phase 2: Frontend — Rich Tables & Dense Layout
- Create shared PropertyTable component (reuses EntityDataGrid internals)
- Replace schema/valueset ad-hoc tables with PropertyTable
- Add unit column to element browse grid
- Reduce whitespace: row height, card padding, section gaps
- Fix case-insensitive sorting
- Add cross-reference sections to detail pages

### Phase 3: Chat-First Curation
- Full entity context in chat right panel (all fields, provenance, annotations, flags, related)
- "Chat about this" action on EntityTag popovers and browse rows
- Standalone assistant mode (sidebar link, no entity required)
- Entity type-appropriate layouts in right panel

### Phase 4: Global Search UI
- GlobalSearch component (search bar in sidebar/header)
- Results dropdown grouped by entity type
- Lexical matches above semantic with scores
- Navigate to detail or launch chat from results

### Phase 5: Link Health Monitoring
- LinkHealthCheck model and table
- Background checker task (daily domain + prefix checks)
- Status page with dashboard
- Curation flag generation for broken links

### Phase 6: Transform Validation
- structural_type field on SemanticIdentity
- Array→singleton rejection rule in transform pipeline
- UI display of structural type on transform detail pages
