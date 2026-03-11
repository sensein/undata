# Research: Schema Explorer Frontend
**Feature**: 003-schema-explorer | **Date**: 2026-03-07

---

## Decision 1: Frontend Framework

**Decision**: Next.js (React) with App Router and TypeScript.

**Rationale**:
- For a system requiring 100k-record search, interactive graph visualization, and
  complex side-by-side comparison state, Next.js has the strongest ecosystem:
  Cytoscape.js (`react-cytoscapejs`) is first-class React; TanStack Table + TanStack
  Virtual handle 100k-row virtualization natively; shadcn/ui provides accessible
  component primitives.
- React Server Components (App Router) serve the read-heavy schema browsing pages
  without client-side hydration overhead; interactive components (graph, search) use
  Client Components.
- SvelteKit is rejected: Cytoscape.js and TanStack Table Svelte adapters are less
  mature; fewer community patterns for data-heavy admin tooling.
- Nuxt (Vue) is rejected: smallest graph-lib wrapper ecosystem of the three options.

---

## Decision 2: Graph Visualization Library

**Decision**: Cytoscape.js with the `dagre` layout plugin.

**Rationale**:
- Cytoscape.js is purpose-built for network/graph visualization and handles large
  graphs (500+ nodes) without performance degradation via canvas rendering.
- `dagre` layout produces clean directed acyclic graph layouts matching the mapping
  DAG structure.
- Depth-limit controls are easy to implement by filtering the fetched adjacency list
  client-side before passing to Cytoscape.
- D3-force is rejected: optimized for force-directed layouts, not DAGs; harder to
  control edge routing for schema relationship graphs.
- React Flow is rejected: React-only, incompatible with SvelteKit.
- Sigma.js is rejected: smaller ecosystem, less mature TypeScript types.

---

## Decision 3: Search UX Pattern

**Decision**: Meilisearch as primary search engine (server-side); PostgreSQL FTS as
fallback if operational simplicity is required. Client-side search (Fuse.js) used
only for sub-set filtering within already-fetched result pages (≤200 items).

**Rationale**:
- 100k elements rule out client-side indexing (Fuse.js index for 100k records is
  15–40 MB of JS objects; 2–5s build time on page load — unacceptable).
- Meilisearch provides typo tolerance, faceted filter counts, and sub-50ms ranked
  search over 100k records with minimal query tuning. Self-hosted; indexes are
  updated via event/webhook on element create/update.
- PostgreSQL FTS (`tsvector` + GIN + `pg_trgm`) is a viable fallback: sub-10ms at
  100k records with proper indexes. Used when adding Meilisearch to the stack is
  not acceptable.
- Debounce: 300ms from last keystroke before API call.
- Client-side filter refinement (source, type toggles) applied to the ≤50 item
  result page without additional API calls.

---

## Decision 4: Data Fetching Library

**Decision**: `@tanstack/react-query` (TanStack Query for React).

**Rationale**:
- Provides stale-while-revalidate caching, automatic background refetch, and loading/
  error state management.
- Works naturally with Next.js App Router (client components).
- Much simpler than building a custom fetch abstraction.

---

## Decision 5: Component Library / Styling

**Decision**: shadcn/ui (Radix UI + Tailwind CSS).

**Rationale**:
- shadcn/ui provides accessible, composable components (combobox for source filter,
  table, dialog, badge, form) without a runtime bundle — components are copied into
  the project and customized directly.
- Radix UI primitives ensure WCAG 2.1 AA accessibility without manual ARIA work.
- Tailwind CSS keeps styling co-located with markup.
- The graph canvas area is separate from shadcn components and does not conflict.

---

## Technology Summary

| Concern | Choice | Version |
|---------|--------|---------|
| Language | TypeScript | 5.x |
| Framework | Next.js (React) | 15.x |
| Graph viz | Cytoscape.js (react-cytoscapejs) + cose-bilkent/dagre | 3.x |
| Data fetching | @tanstack/react-query | 5.x |
| Data tables | TanStack Table + TanStack Virtual | 8.x |
| Components | shadcn/ui (Radix UI + Tailwind CSS) | latest |
| Search | Meilisearch (primary) / PostgreSQL FTS (fallback) | 1.x |
| Testing (E2E) | Playwright | 1.x |
| Testing (unit) | Vitest + React Testing Library | 2.x |
| Build | Next.js / Turbopack | built-in |
| API client | Native fetch + generated types from OpenAPI | — |
