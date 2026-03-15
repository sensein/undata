# Tasks: Schema Explorer Frontend

**Feature**: `003-schema-explorer` | **Branch**: `003-schema-explorer`
**Input**: Design documents from `/specs/003-schema-explorer/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ui-contract.md ✅, quickstart.md ✅

**Tests**: TDD approach — Playwright E2E + Vitest/React Testing Library component tests.

**User Stories**:
- US1 P1 — Browse and Search Data Elements (search, filter, detail view)
- US2 P2 — Explore Mappings and Alias Graph (interactive relationship graph)
- US3 P3 — Contribute New Data Elements (add element form with validation)
- US4 P4 — Compare Elements Across Schemas (side-by-side diff + alias registration)

---

## Phase 1: Setup (Project Infrastructure)

**Purpose**: Initialize Next.js 15 project structure, dependencies, configuration.

- [X] T001 Scaffold Next.js 15 App Router project: run `pnpm create next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=no --import-alias="@/*"` from repo root; verify `frontend/app/` directory created in frontend/
- [X] T002 [P] Install runtime dependencies: `pnpm add @tanstack/react-query cytoscape react-cytoscapejs cytoscape-cose-bilkent cytoscape-dagre meilisearch @tanstack/react-table @tanstack/react-virtual` in frontend/
- [X] T003 [P] Install shadcn/ui: run `pnpm dlx shadcn@latest init` (New York style, CSS variables), then add components: `button input badge card label select textarea skeleton` in frontend/
- [X] T004 [P] Install dev dependencies: `pnpm add -D vitest @vitejs/plugin-react @testing-library/react @testing-library/user-event @testing-library/jest-dom playwright @playwright/test` in frontend/
- [X] T005 [P] Create `frontend/next.config.ts`: configure `rewrites` to proxy `/api/backend/**` → `http://localhost:8002/api/**` and `/api/search/**` → `http://localhost:7700/**`; export `NEXT_PUBLIC_BACKEND_URL` and `NEXT_PUBLIC_MEILI_URL` from environment
- [X] T006 [P] Create `frontend/playwright.config.ts`: baseURL `http://localhost:3000`, webServer `pnpm dev`, testDir `tests/e2e/`, workers 1 for CI; add `frontend/.env.local.example` with `NEXT_PUBLIC_BACKEND_URL=http://localhost:8002` and `MEILI_MASTER_KEY`
- [X] T007 [P] Create `frontend/vitest.config.ts`: use `@vitejs/plugin-react`, `jsdom` environment, setup file `tests/setup.ts`; add `tests/setup.ts` with `@testing-library/jest-dom` import
- [X] T008 Create `frontend/lib/types.ts` with all TypeScript types from data-model.md: `DataElementSummary`, `DataElementDetail`, `AliasGroupSummary`, `AliasGroupDetail`, `MappingRef`, `PaginatedList<T>`, `SearchState`, `FilterState`, `ComparisonState`, `GraphNode`, `GraphEdge`
- [X] T009 [P] Create `frontend/lib/api/client.ts`: base fetch wrapper with error handling, `Content-Type: application/json`, `Authorization: Bearer` header injection from env `API_TOKEN`; `ApiError` class with `status` and `detail` fields
- [X] T010 [P] Create `frontend/lib/api/elements.ts`: `getElements(params: SearchParams): Promise<PaginatedList<DataElementSummary>>`, `getElementById(id: string): Promise<DataElementDetail>`, `createElement(payload: CreateElementPayload): Promise<DataElementDetail>` using the client from `lib/api/client.ts`
- [X] T011 [P] Create `frontend/lib/api/aliases.ts`: `getAliasGroup(id: string): Promise<AliasGroupDetail>`, `registerAlias(elementAId: string, elementBId: string): Promise<AliasGroupDetail>` in frontend/lib/api/aliases.ts
- [X] T012 [P] Create `frontend/lib/api/mappings.ts`: `getMappings(params: { source_element_id?: string; target_element_id?: string }): Promise<PaginatedList<MappingRef>>` in frontend/lib/api/mappings.ts
- [X] T013 [P] Create `frontend/lib/api/sources.ts`: `getSources(): Promise<Array<{ id: string; name: string }>>` for the source-filter dropdown in frontend/lib/api/sources.ts
- [X] T014 Create `frontend/app/api/[...path]/route.ts`: Next.js Route Handler that proxies all requests to backend, injects `Authorization: Bearer ${process.env.API_TOKEN}` header, forwards body and method unchanged

---

## Phase 2: Foundational (Shared Components + Query Provider)

**Purpose**: Shared layout, QueryClient, error boundary, and loading skeletons that all user stories depend on.

- [X] T015 Create `frontend/app/layout.tsx`: root layout wrapping children in `<QueryClientProvider>` (client component wrapper), `<html lang="en">`, Tailwind base styles, Inter font; add `frontend/components/Providers.tsx` as `"use client"` QueryClientProvider wrapper
- [X] T016 [P] Create `frontend/components/ErrorBanner.tsx`: displays `ApiError` message or generic "Service unavailable" when `status` is 503/network failure; used in all pages (FR-017)
- [X] T017 [P] Create `frontend/components/LoadingSkeleton.tsx`: animated pulse skeleton for search result rows and detail sections; used while `isLoading` is true
- [X] T018 [P] Create `frontend/app/page.tsx`: search home page — renders `<SearchBar>` centered, recent elements placeholder when no query, links to `/elements` on submit
- [X] T019 Write Vitest component test for `ErrorBanner.tsx`: renders "Service unavailable" on 503 error prop, renders `error.detail` text on API error prop in `frontend/tests/unit/ErrorBanner.test.tsx`
- [X] T020 Write Vitest component test for `LoadingSkeleton.tsx`: renders correct number of skeleton rows for `count` prop in `frontend/tests/unit/LoadingSkeleton.test.tsx`

---

## Phase 3: User Story 1 — Browse and Search Data Elements (P1)

**Goal**: Keyword search with filters, paginated results, element detail page.
**Independent Test**: Enter "subject" in search bar → results appear within 2s with name/type/description/source badges; click result → detail page shows full metadata (no graph required).

- [X] T021 [P] [US1] Create `frontend/components/SearchBar.tsx`: controlled input with 300ms debounce, `onSearch(query, filters)` callback, filter sidebar toggle; URL-synced via `useSearchParams` (FR-001, FR-002)
- [X] T022 [P] [US1] Create `frontend/components/FilterPanel.tsx`: source schema dropdown (fetches `/api/v1/sources`), data-type multi-select (string/number/boolean/object/array), has-aliases toggle, has-mappings toggle; emits `onFilterChange(FilterState)` (FR-002)
- [X] T023 [P] [US1] Create `frontend/components/SearchResults.tsx`: uses `useQuery` to fetch `/api/v1/elements?q=...` on query/filter change, renders list of `<ElementCard>`, handles empty state "no results" message with suggestion (FR-003, US1 AC6)
- [X] T024 [P] [US1] Create `frontend/components/ElementCard.tsx`: displays element name, `data_type` badge, description excerpt (≤120 chars), source schema badge, alias count; links to `/elements/{id}` (FR-003)
- [X] T025 [US1] Create `frontend/app/elements/page.tsx`: search results page — reads `q`, `source`, `type`, `offset` from `searchParams`; renders `<SearchBar>` + `<FilterPanel>` + `<SearchResults>`; handles `?q=` URL encoding (FR-016, FR-001)
- [X] T026 [US1] Create `frontend/app/elements/[id]/page.tsx`: element detail Server Component — fetches `getElementById(id)` via server fetch, renders `<ElementDetail>` with full metadata (FR-004, FR-005)
- [X] T027 [P] [US1] Create `frontend/components/ElementDetail.tsx`: renders all metadata fields (name, type, description, cardinality, allowed_values, source, version, timestamps), alias group list with links to `/aliases/{id}`, mappings list (FR-005, FR-006, FR-007); `<RelationshipGraph>` placeholder section with "loading graph…"
- [X] T028 [US1] Write Playwright E2E test `frontend/tests/e2e/search.spec.ts`: (1) visit `/`, type "subject", verify results appear within 2s with name+type+description+source badge; (2) apply source filter → results update; (3) apply type filter → results update; (4) enter query with no results → "no results" message shown (SC-001, FR-001, FR-002, FR-003)
- [X] T029 [US1] Write Playwright E2E test `frontend/tests/e2e/element-detail.spec.ts` (part 1): click search result → navigates to `/elements/{id}`; verify name, type, description, source badge, alias list, mappings list render (FR-004, FR-005, FR-006, FR-007)
- [X] T030 [US1] Write Vitest component test `frontend/tests/unit/SearchBar.test.tsx`: (1) renders input; (2) debounce — only calls onSearch once after 300ms; (3) clears query on clear button; (4) input over 500 chars is trimmed to 500 (edge case FR-018)
- [X] T031 [US1] Write Vitest component test `frontend/tests/unit/ElementCard.test.tsx`: renders name, truncated description, badge color by data_type, alias count "2 aliases" in `frontend/tests/unit/ElementCard.test.tsx`

---

## Phase 4: User Story 2 — Explore Mappings and Alias Graph (P2)

**Goal**: Interactive Cytoscape.js graph on element detail page showing mappings + aliases.
**Independent Test**: Navigate to an element with ≥1 mapping; verify graph renders within 3s, nodes are clickable and navigate to connected element's detail page.

- [X] T032 [P] [US2] Create `frontend/components/RelationshipGraph.tsx`: `"use client"` component; accepts `elementId: string` and `depth: number` (default 2) props; fetches mappings_as_input + mappings_as_output; builds `GraphNode[]` + `GraphEdge[]`; renders with `react-cytoscapejs` + cose-bilkent layout; depth slider (1–5); keyboard-accessible table fallback listing nodes; emits `onNodeClick(elementId)` (FR-008, SC-002, edge case depth limit)
- [X] T033 [US2] Integrate `<RelationshipGraph>` into `frontend/components/ElementDetail.tsx`: replace placeholder with actual component; pass `elementId` and `depth` from URL param `?depth=N`; sync depth changes back to URL (FR-008, FR-016)
- [X] T034 [US2] Create `frontend/app/aliases/[id]/page.tsx`: alias group detail page — fetches `getAliasGroup(id)`, renders group name, sssom_predicate, confidence, member list with links to each element detail page
- [X] T035 [US2] Write Playwright E2E test `frontend/tests/e2e/element-detail.spec.ts` (part 2 — graph): navigate to element with mappings; verify graph canvas renders within 3s; click a graph node → navigates to that element's detail; verify depth slider changes graph (SC-002, FR-008, US2 AC2, US2 AC4)
- [X] T036 [P] [US2] Write Vitest component test `frontend/tests/unit/RelationshipGraph.test.tsx`: (1) renders fallback table when Cytoscape fails to load; (2) depth change re-queries API; (3) onNodeClick fires with correct elementId on node click; uses mocked `react-cytoscapejs`

---

## Phase 5: User Story 3 — Contribute New Data Elements (P3)

**Goal**: Form with client-side validation, duplicate detection, redirect on success.
**Independent Test**: Fill form with valid data → element created → redirected to detail page. Omit required field → error shown, no submission. Enter existing element name → duplicate warning appears.

- [X] T037 [P] [US3] Create `frontend/components/AddElementForm.tsx`: controlled form with fields: `name` (required, pattern `[a-zA-Z_][a-zA-Z0-9_ ]*`, 1–200 chars), `data_type` (required, select: string/number/boolean/object/array), `description` (required, textarea, 10–2000 chars), `cardinality` (required, radio: required/optional × single/multi), `allowed_values` (optional, tag input), `source_provenance` (optional, text); client-side validation per ui-contract.md rules; duplicate-name check on blur (debounced 500ms, `GET /elements?q={name}&limit=5`), warns if exact match; uses `useMutation` to `POST /api/v1/elements`; on success redirects to `/elements/{id}` (FR-009, FR-010, FR-011, FR-012, SC-004, SC-005)
- [X] T038 [US3] Create `frontend/app/add/page.tsx`: "Add Element" page — renders `<AddElementForm>`, requires auth (redirect to login if no `API_TOKEN` env); page title "Contribute a Data Element"
- [X] T039 [US3] Write Playwright E2E test `frontend/tests/e2e/add-element.spec.ts`: (1) submit with all required fields → redirect to `/elements/{id}` + element appears in search; (2) submit with missing `name` → inline error shown, no submission; (3) enter duplicate name → warning banner with link to existing element shown before submit (FR-009, FR-010, FR-011, FR-012, SC-003, SC-004, SC-005)
- [X] T040 [P] [US3] Write Vitest component test `frontend/tests/unit/AddElementForm.test.tsx`: (1) renders all fields; (2) submit with missing description → description error shown; (3) name over 200 chars → length error; (4) duplicate check fires on name blur; (5) `useMutation` success → `router.push` called with new element ID (FR-010, FR-011, SC-004)

---

## Phase 6: User Story 4 — Compare Elements Across Schemas (P4)

**Goal**: Side-by-side element comparison with diff highlighting and one-click alias registration.
**Independent Test**: Navigate to `/compare?a={id1}&b={id2}` → both elements rendered side by side with differing fields highlighted; click "Register as Alias" → alias created.

- [X] T041 [P] [US4] Create `frontend/components/ComparisonView.tsx`: accepts `elementA: DataElementDetail` and `elementB: DataElementDetail` props; renders two-column grid of all metadata fields; marks identical values as "match" (green checkmark, `aria-label="matching"`), differing values as "diff" (amber highlight, `aria-label="differs"`); "Register as Alias" button enabled only when `data_type` matches; on click calls `registerAlias(a.id, b.id)` via `useMutation`, refreshes both detail sections on success (FR-013, FR-014, FR-015, US4 AC1–3)
- [X] T042 [US4] Create `frontend/app/compare/page.tsx`: reads `a` and `b` UUIDs from `searchParams`; fetches both elements via `getElementById`; renders `<ComparisonView>`; if either ID missing shows "select two elements to compare" prompt (FR-013, FR-016)
- [X] T043 [US4] Add "Compare" affordance: in `frontend/components/SearchResults.tsx` add multi-select checkbox to each result row with "Compare selected" button (enabled when exactly 2 checked) that navigates to `/compare?a={id1}&b={id2}`; in `frontend/components/ElementDetail.tsx` add "Compare with…" button that stores current element ID in `sessionStorage` and navigates to `/elements` to pick a second element (FR-013)
- [X] T044 [US4] Write Playwright E2E test `frontend/tests/e2e/comparison.spec.ts`: (1) navigate to `/compare?a={id1}&b={id2}` → both elements render; (2) differing fields highlighted, identical fields marked matching; (3) "Register as Alias" button disabled when data_types differ; (4) click "Register as Alias" when types match → success toast + button disabled (US4 AC1–3, FR-014, FR-015)
- [X] T045 [P] [US4] Write Vitest component test `frontend/tests/unit/ComparisonView.test.tsx`: (1) renders two columns; (2) identical field values → match class; (3) differing values → diff class; (4) "Register as Alias" disabled when data_types differ; (5) `registerAlias` mutation called with correct IDs on button click (FR-014, FR-015)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Input sanitization, backend unavailable handling, URL stability, Meilisearch indexer, lint, accessibility audit.

- [X] T046 Add input sanitization: in `frontend/components/SearchBar.tsx` trim input to 500 chars and strip HTML tags using `DOMPurify` (install: `pnpm add dompurify @types/dompurify`); in `frontend/components/AddElementForm.tsx` sanitize `name`, `description`, `source_provenance` before mutation call (FR-018, edge-case injection)
- [X] T047 [P] Add backend-unavailable error handling: in `frontend/lib/api/client.ts` catch network errors and throw `ApiError` with `status: 503`; in all page components wrap `useQuery` errors with `<ErrorBanner>` (FR-017, edge-case backend down)
- [X] T048 [P] Create `frontend/scripts/index-elements.ts`: Node script that fetches all elements from backend (`GET /api/v1/elements?limit=100` paginated) and upserts into Meilisearch index `elements` with fields `id, name, data_type, description, source_name`; add `pnpm run index-elements` script to `frontend/package.json`
- [X] T049 [P] Accessibility audit: verify all interactive elements in `SearchBar`, `ElementCard`, `RelationshipGraph`, `AddElementForm`, `ComparisonView` have visible focus rings, `aria-label` or `role` attributes, and `<label>` associations; fix any WCAG 2.1 AA violations found (WCAG 2.1 AA constraint)
- [X] T050 [P] Add `"compare" checkbox state` to `SearchResults.tsx` URL encoding: when user selects two elements via checkboxes, update URL to `/elements?q=...&compare=id1,id2` so the compare selection is shareable (FR-016, US4 AC1)
- [X] T051 Run `pnpm eslint . --fix` and `pnpm prettier --write .` across all frontend/ TypeScript files; resolve all lint errors; verify `pnpm build` succeeds without TypeScript errors in frontend/
- [X] T052 Verify all Playwright E2E tests pass with `pnpm exec playwright test` against a live backend (requires 002-schema-backend running with seed data); verify all Vitest unit tests pass with `pnpm vitest run` in frontend/

---

## Dependencies

```
T001 → T002, T003, T004, T005, T006, T007 (parallel)
T008 → T009 → T010, T011, T012, T013 (parallel)
T014 → T015 → T016, T017, T018 (parallel)
T019, T020 → US1 starts
US1 (T021-T031) → US2 (T032-T036) → US3 (T037-T040) → US4 (T041-T045) → Polish (T046-T052)
T033 depends on T032 (graph must exist before ElementDetail integration)
T043 depends on T023 (SearchResults must exist before adding checkboxes)
T051 depends on all implementation tasks
T052 depends on T051
```

## Parallel Execution Per Story

**Setup** (T001→T002–T007 in parallel → T008→T009→T010–T013 in parallel → T014→T015→T016–T020 in parallel)

**US1**: T021, T022, T023, T024 [P] → T025 → T026 → T027 → T028, T029, T030, T031

**US2**: T032 [P] → T033 → T034 → T035, T036 [P]

**US3**: T037 [P] → T038 → T039, T040 [P]

**US4**: T041 [P] → T042 → T043 → T044, T045 [P]

**Polish**: T046, T047, T048, T049, T050 [P] → T051 → T052

## Implementation Strategy

1. **MVP** (User Story 1 only): Search + Filter + Element Detail (no graph). Delivers immediate value — users can find and read element metadata. T001–T031.
2. **Graph** (User Story 2): Interactive relationship visualization. T032–T036.
3. **Contribute** (User Story 3): Add Element form with validation. T037–T040.
4. **Compare** (User Story 4): Side-by-side diff + alias registration. T041–T045.
5. **Polish** (Phase 7): Sanitization, error handling, Meilisearch indexer, lint, a11y, final test run. T046–T052.
