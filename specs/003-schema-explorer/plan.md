# Implementation Plan: Schema Explorer Frontend

**Branch**: `003-schema-explorer` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-schema-explorer/spec.md`

## Summary

A SvelteKit web application that provides keyword search, detail views with interactive
relationship graphs, side-by-side element comparison, and a form for contributing new
data elements. Consumes the 002-schema-backend and 004-migration-api REST APIs.

## Technical Context

**Language/Version**: TypeScript 5.x
**Primary Dependencies**: Next.js 15.x (React), react-cytoscapejs 3.x (+ cose-bilkent/dagre),
@tanstack/react-query 5.x, TanStack Table 8.x, shadcn/ui, Tailwind CSS, Meilisearch JS client
**Storage**: N/A (all state from backend APIs + Meilisearch index)
**Testing**: Playwright (E2E), Vitest + React Testing Library (unit/component)
**Target Platform**: Modern web browsers (Chrome, Firefox, Safari; ES2022+)
**Project Type**: web-application
**Performance Goals**: Search results within 2 seconds; graph render (50 nodes) within
3 seconds; new element searchable within 5 seconds of submission
**Constraints**: All views accessible via stable shareable URL; no stale data displayed
without clear labelling; accessible (WCAG 2.1 AA)
**Scale/Scope**: ~100k elements in backend; UI renders ≤50 search results per page,
≤500 graph nodes per element view

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | ✅ PASS | No component library; bespoke components for limited surface area |
| II. Test-Driven Development | ✅ PASS | UI contract and route schema defined first; E2E tests written before components |
| III. API-First Design | ✅ PASS | UI contract in contracts/ui-contract.md; all backend calls documented |
| IV. Observability | ✅ PASS | Backend unavailable state surfaced clearly to user |
| V. CalVer | ✅ PASS | Frontend package version follows CalVer |

**Dependency gate**: 002-schema-backend with populated data required for meaningful
E2E tests. Unit/component tests use mocked API responses.

## Project Structure

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── page.tsx                    # / search home (Server Component)
│   ├── elements/
│   │   ├── page.tsx                # /elements search results
│   │   └── [id]/page.tsx           # /elements/{id} detail
│   ├── aliases/[id]/page.tsx       # /aliases/{id} group detail
│   ├── compare/page.tsx            # /compare?a=&b= comparison
│   ├── add/page.tsx                # /add element form
│   └── api/
│       └── [...path]/route.ts      # Server-side proxy (adds auth header)
├── components/
│   ├── SearchBar.tsx
│   ├── SearchResults.tsx
│   ├── ElementCard.tsx
│   ├── ElementDetail.tsx
│   ├── RelationshipGraph.tsx       # Cytoscape.js client component
│   ├── ComparisonView.tsx
│   └── AddElementForm.tsx
├── lib/
│   ├── api/
│   │   ├── elements.ts
│   │   ├── mappings.ts
│   │   └── aliases.ts
│   └── types.ts
├── tests/
│   ├── e2e/
│   │   ├── search.spec.ts
│   │   ├── element-detail.spec.ts
│   │   ├── comparison.spec.ts
│   │   └── add-element.spec.ts
│   └── unit/
│       ├── SearchBar.test.tsx
│       └── ComparisonView.test.tsx
├── playwright.config.ts
├── next.config.ts
├── tailwind.config.ts
└── package.json
```

**Structure Decision**: Next.js App Router with Server Components for read pages;
Client Components for graph and interactive search. API proxy route adds auth header
server-side to avoid exposing the token to the browser.

## Phase 0 Research Summary

See [research.md](research.md).

| Question | Decision |
|----------|----------|
| Framework | Next.js 15.x (React) + TypeScript |
| Graph visualization | Cytoscape.js + cose-bilkent/dagre layout |
| Search engine | Meilisearch (primary) / PostgreSQL FTS (fallback) |
| Data fetching | @tanstack/react-query |
| Styling | shadcn/ui + Tailwind CSS |
| Tables | TanStack Table + TanStack Virtual |

## Phase 1 Design Artifacts

- [data-model.md](data-model.md) — TypeScript types, UI state structures, SvelteKit route map
- [contracts/ui-contract.md](contracts/ui-contract.md) — URL schema, backend dependencies, component interaction contracts
- [quickstart.md](quickstart.md) — developer validation checklist
