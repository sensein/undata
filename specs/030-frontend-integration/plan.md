# Implementation Plan: Frontend Integration

**Branch**: `030-frontend-integration` | **Date**: 2026-03-26 | **Spec**: [spec.md](spec.md)

## Summary

Wire the existing Next.js frontend to the backend GraphQL API. Fix query/type mismatches, ensure all entity browsers work with real data, add error handling and empty states, write Playwright E2E tests.

## Technical Context

**Language/Version**: TypeScript 5.x + Next.js 16.x (React 19)
**Primary Dependencies**: Apollo Client 4.x, shadcn/ui, Tailwind CSS 4
**Testing**: Playwright for E2E, Vitest for unit
**Target Platform**: Browser (Chrome, Firefox, Safari)
**Project Type**: Web application (frontend)
**Constraints**: Must work with backend Docker stack from 029

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Fix existing pages, don't rewrite. Remove broken pages. |
| II. TDD | PASS | Playwright tests written for key flows. |
| III. API-First Design | PASS | Frontend consumes the GraphQL API contract from 027/029. |
| IV. Observability | N/A | Frontend doesn't emit server logs (browser console only). |
| V. No Deprecation | PASS | Remove broken pages directly, no stubs. |
| VI. Environment Isolation | PASS | pnpm for deps, no system installs. |
| VII. Developer Experience | PASS | pnpm dev starts frontend with hot reload. |
| CI Green Before Merge | PASS | Playwright tests run in CI. |

## Project Structure

```text
frontend/
├── app/
│   ├── layout.tsx            # KEEP: root layout with nav
│   ├── page.tsx              # KEEP: home/landing
│   ├── elements/
│   │   ├── page.tsx          # FIX: wire to browseElements query
│   │   └── [sha256]/
│   │       └── page.tsx      # FIX: wire to element(sha256) query
│   ├── schemas/
│   │   └── page.tsx          # FIX: wire to browseSchemas query
│   ├── values/
│   │   └── page.tsx          # FIX: wire to browseValues query
│   ├── curation/
│   │   └── page.tsx          # FIX: wire to curationQueue query
│   └── runs/
│       └── page.tsx          # FIX: wire to runSummaries query
├── graphql/
│   ├── queries.ts            # UPDATED in 029 — verify correct
│   └── types.ts              # UPDATE: match backend schema
├── lib/
│   └── apollo.ts             # KEEP: already configured
├── components/               # FIX: update as needed
└── tests/
    └── e2e/
        ├── elements.spec.ts  # REWRITE: test against real backend
        └── navigation.spec.ts # REWRITE: basic nav tests
```

**Pages to remove** (depend on unbuilt features):
- `app/migrations/` (migration API not in scope)
- `app/aliases/` (alias groups not yet exposed via API)
- `app/compare/` (comparison not yet exposed)
- `app/add/` (contribution form — deferred)
- `app/profile/` (auth deferred)

## Implementation Approach

### Phase 1: Fix Element Browser + Detail (US1 + US2)
1. Update `app/elements/page.tsx` to use updated BROWSE_ELEMENTS query
2. Fix TypeScript types to match backend response shape
3. Update `app/elements/[sha256]/page.tsx` to use GET_ELEMENT query
4. Add error and empty state handling

### Phase 2: Fix Other Browsers (US3)
1. Update schemas page to use BROWSE_SCHEMAS query
2. Update values page to use BROWSE_VALUES query

### Phase 3: Fix Curation + Runs (US4 + US5)
1. Update curation page to use CURATION_QUEUE query
2. Update runs page to use RUN_SUMMARIES query

### Phase 4: Cleanup + Tests (US6)
1. Remove broken pages (migrations, aliases, compare, add, profile)
2. Write Playwright E2E tests
3. Verify all pages load without errors
