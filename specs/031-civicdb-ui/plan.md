# Implementation Plan: CivicDB UI Redesign

**Branch**: `031-civicdb-ui` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)

## Summary

Redesign frontend pages following CivicDB patterns: sortable data grids with clickable counts, consistent entity detail layouts, bidirectional entity navigation, curation evidence panels, activity feed, responsive layout with source color coding.

## Technical Context

**Language/Version**: TypeScript 5.x + Next.js 16.x (React 19)
**Primary Dependencies**: TanStack Table (headless sorting/filtering), Apollo Client 4.x, shadcn/ui, Tailwind CSS 4
**Testing**: Playwright for E2E
**Target Platform**: Browser (desktop + mobile)
**Project Type**: Frontend redesign
**Constraints**: Frontend-only — no backend API changes. Uses existing GraphQL queries.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | TanStack Table already in deps. No new heavy libraries. |
| II. TDD | PASS | Playwright tests for navigation traversal and sorting. |
| III. API-First Design | PASS | Uses existing GraphQL API — no new endpoints. |
| IV. Observability | N/A | Frontend (browser-only). |
| V. No Deprecation | PASS | Replace existing pages directly. |
| VI. Environment Isolation | PASS | pnpm, no system deps. |
| VII. Developer Experience | PASS | pnpm dev with hot reload. |
| CI Green Before Merge | PASS | Playwright + build must pass. |

## Project Structure

```text
frontend/
├── app/
│   ├── elements/
│   │   ├── page.tsx              # REDESIGN: TanStack data grid
│   │   └── [sha256]/page.tsx     # REDESIGN: consistent detail layout
│   ├── schemas/
│   │   ├── page.tsx              # REDESIGN: data grid + schema detail
│   │   └── [sha256]/page.tsx     # NEW: schema detail page
│   ├── values/
│   │   ├── page.tsx              # REDESIGN: data grid
│   │   └── [sha256]/page.tsx     # NEW: value detail page
│   ├── valuesets/
│   │   ├── page.tsx              # REDESIGN: data grid
│   │   └── [sha256]/page.tsx     # NEW: valueset detail page
│   ├── curation/
│   │   └── page.tsx              # REDESIGN: evidence panels
│   ├── activity/
│   │   └── page.tsx              # NEW: activity feed
│   └── layout.tsx                # UPDATE: sidebar navigation, source colors
├── components/
│   ├── Sidebar.tsx               # NEW: collapsible sidebar navigation (CivicDB pattern)
│   ├── EntityDataGrid.tsx        # NEW: reusable sortable grid component
│   ├── EntityDetailLayout.tsx    # NEW: consistent detail page wrapper with tabs
│   ├── EntityTag.tsx             # NEW: clickable entity tag with hover popover
│   ├── SourceBadge.tsx           # NEW: color-coded source badge
│   ├── StatusBadge.tsx           # NEW: pending/approved/rejected/deferred status pill
│   ├── EvidencePanel.tsx         # NEW: curation flag evidence display
│   ├── RelatedEntities.tsx       # NEW: bidirectional entity links
│   └── ActivityTimeline.tsx      # NEW: event timeline component
├── lib/
│   ├── apollo.ts                 # UPDATE: add cache policies for new queries
│   └── source-colors.ts          # NEW: centralized source color map
└── tests/
    └── e2e/
        ├── elements.spec.ts      # UPDATE: test sorting, navigation
        ├── navigation.spec.ts    # UPDATE: test traversal
        └── curation.spec.ts      # UPDATE: test evidence panel
```

## Implementation Approach

### Phase 1: Shared Components (Foundational)
1. Create `SourceBadge.tsx` — color-coded badge with `SOURCE_COLORS` map
2. Create `CurationIndicator.tsx` — inline status pill (pending/approved/rejected)
3. Create `EntityDetailLayout.tsx` — consistent detail page wrapper
4. Create `RelatedEntities.tsx` — bidirectional entity links section
5. Create `EntityDataGrid.tsx` — TanStack Table wrapper with sorting
6. Create `ResponsiveNav.tsx` — mobile-friendly navigation
7. Update `layout.tsx` — use ResponsiveNav

### Phase 2: Entity Browsers (US1)
1. Redesign elements page with EntityDataGrid
2. Redesign schemas page with EntityDataGrid
3. Redesign values page with EntityDataGrid

### Phase 3: Detail Pages (US2 + US3)
1. Redesign element detail with EntityDetailLayout + RelatedEntities
2. Create schema detail page with properties → element links
3. Create value detail page with valueset links
4. Create valueset detail page with member value links

### Phase 4: Curation + Activity (US4 + US5)
1. Redesign curation page with EvidencePanel
2. Create activity feed page

### Phase 5: Responsive + Polish + Tests (US6)
1. Add responsive breakpoints to all pages
2. Update Playwright tests for navigation traversal + sorting
3. Verify CI green

## Complexity Tracking

No violations — all work uses existing libraries (TanStack Table, Tailwind, shadcn/ui).
