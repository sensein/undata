# Research: Frontend Integration

## R1: Existing Page State

**Finding**: 14 page.tsx files exist from brainstorm v1. The element browser (`app/elements/page.tsx`) already uses Apollo `useQuery` with `BROWSE_ELEMENTS`. The queries were updated in feature 029 to match the backend's Relay cursor pagination schema.

**Decision**: Fix and connect existing pages rather than rewrite. Focus on: element browser, element detail, schemas, values, curation, runs. Remove or stub broken pages (migrations, aliases, compare — these depend on features not yet built).

## R2: GraphQL Field Name Mapping

**Finding**: Strawberry converts Python snake_case to camelCase in GraphQL. The backend returns `dataType`, `hasNextPage`, `endCursor`, `ontologyAnnotations`, etc. Frontend queries must use camelCase.

**Decision**: Queries updated in 029. Frontend TypeScript interfaces need updating to match.

## R3: Apollo Client Pagination

**Finding**: The existing Apollo client has a merge policy for `browseElements` that appends edges. This works with Relay cursor pagination — `fetchMore` with `after: endCursor` appends new edges to the cache.

**Decision**: Keep existing merge policy. Add similar policies for browseSchemas, browseValues if needed.

## R4: Error Handling Pattern

**Decision**: Use Apollo's `error` state from `useQuery` to show inline error banners. Use `loading` state for skeleton UI. Empty results show a descriptive message, not a blank page.

## R5: Playwright Test Strategy

**Decision**: Write E2E tests that require a running backend with seed data. Tests verify: page loads, elements visible, click-through to detail, pagination works. Run via `pnpm exec playwright test` after `docker compose up`.
