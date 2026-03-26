# Tasks: Frontend Integration

**Input**: Design documents from `/specs/030-frontend-integration/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Playwright E2E tests included (US6). Unit tests optional.

**Organization**: 6 user stories. US1+US2 tightly coupled (element browser + detail). US3 parallel (schemas + values). US4+US5 parallel (curation + runs). US6 (tests) as final phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Which user story (US1–US6)
- All paths relative to `frontend/` unless noted

## Phase 1: Setup

**Purpose**: Clean broken pages, update shared types

- [ ] T001 Remove broken pages that depend on unbuilt features: delete `app/migrations/`, `app/aliases/`, `app/compare/`, `app/add/`, `app/profile/`, `app/auth/`
- [ ] T002 Update navigation in `app/layout.tsx` — remove links to deleted pages, keep: Elements, Schemas, Values, Curation, Runs
- [ ] T003 Update `graphql/types.ts` — TypeScript interfaces matching backend schema: Element, Schema, Value, ValueSet, CurationFlag, RunSummary, PageInfo, Connection types, all with camelCase field names

**Checkpoint**: No broken imports, navigation works, types match backend

---

## Phase 2: User Story 1 — Element Browser (Priority: P1) 🎯 MVP

**Goal**: Element browser loads real data with filters and pagination.

**Independent Test**: Open /elements — seed elements displayed with source, type, description.

- [ ] T004 [US1] Rewrite `app/elements/page.tsx` — use BROWSE_ELEMENTS query from `graphql/queries.ts`, display elements in a table/grid with: name (from file_name or provenance), data_type, unit, source (from provenance[0].source), description. Handle three states: loading (skeleton), error (inline banner with retry — covers FR-010 backend-unreachable case), empty ("No elements found" message). Include search text input that passes `searchText` to the query.
- [ ] T005 [US1] Add source filter dropdown in `app/elements/page.tsx` — filter options: all, bids, dandi, nwb, openminds, aind. Passes `source` variable to browseElements query.
- [ ] T006 [US1] Add data type filter in `app/elements/page.tsx` — filter by DataType enum values (STRING, INTEGER, FLOAT, etc.)
- [ ] T007 [US1] Add cursor pagination in `app/elements/page.tsx` — "Load more" button that calls `fetchMore` with `after: endCursor`. Uses Apollo merge policy from `lib/apollo.ts`.
- [ ] T008 [US1] Verify element browser against running backend — start docker stack, open /elements, confirm 5 seed elements display correctly

**Checkpoint**: Element browser shows real data with working filters and pagination

---

## Phase 3: User Story 2 — Element Detail Page (Priority: P1)

**Goal**: Clicking an element shows full details — semantic, provenance, annotations.

**Independent Test**: Click any element → detail page renders all fields.

- [ ] T009 [US2] Rewrite `app/elements/[sha256]/page.tsx` — use GET_ELEMENT query from `graphql/queries.ts`, display: data_type, unit, pattern, value_domain, description, min/max values, type_ref
- [ ] T010 [US2] Add provenance section in element detail page — list each provenance entry with source, class, name, description
- [ ] T011 [US2] Add ontology annotations section in element detail page — list each annotation with term_label, ontology, mapping_relation, score, model
- [ ] T012 [US2] Handle missing element (invalid sha256) — show "Element not found" message
- [ ] T013 [US2] Verify element detail against running backend — click an element, confirm all fields render

**Checkpoint**: Element detail page shows complete entity information

---

## Phase 4: User Story 3 — Schema and Value Browsers (Priority: P1)

**Goal**: Schemas and values pages load from backend.

**Independent Test**: Navigate to /schemas and /values — data displays.

- [ ] T014 [P] [US3] Rewrite `app/schemas/page.tsx` — use BROWSE_SCHEMAS query, display: description, properties list, subclass_of, source. Handle loading/error/empty.
- [ ] T015 [P] [US3] Rewrite `app/values/page.tsx` — use BROWSE_VALUES query, display: label, value_type, description, ontology annotations. Handle loading/error/empty.
- [ ] T016 [US3] Verify schemas and values pages against running backend

**Checkpoint**: All entity browsers (elements, schemas, values) display real data

---

## Phase 5: User Stories 4+5 — Curation Queue + Run History (Priority: P2)

**Goal**: Curation and runs pages display data or appropriate empty states.

**Independent Test**: Navigate to /curation and /runs — pages load without errors.

- [ ] T017 [P] [US4] Rewrite `app/curation/page.tsx` — use CURATION_QUEUE query, display flags with: entity_ref, flag_type, status, context summary. Show empty state if no flags.
- [ ] T018 [P] [US5] Rewrite `app/runs/page.tsx` — use RUN_SUMMARIES query, display: source, started_at, entity_counts (formatted). Show empty state if no runs.
- [ ] T019 [US4] Verify curation and runs pages against running backend

**Checkpoint**: All 5 main pages load without errors

---

## Phase 6: User Story 6 — Playwright E2E Tests + Polish (Priority: P1)

**Goal**: Automated browser tests verify the UI works end-to-end.

**Independent Test**: `pnpm exec playwright test` — all tests pass.

- [ ] T020 [US6] Write `tests/e2e/elements.spec.ts` — test: page loads, elements visible, filter by source works, click element navigates to detail page, detail page shows provenance
- [ ] T021 [US6] Write `tests/e2e/navigation.spec.ts` — test: nav links work (elements, schemas, values, curation, runs), each page loads without JS errors
- [ ] T022 [US6] Update `playwright.config.ts` — set baseURL to http://localhost:3000, webServer config to start frontend
- [ ] T023 Verify `pnpm exec eslint` and `pnpm exec next build` pass without errors
- [ ] T024 Run quickstart validation scenarios QS-001 through QS-008
- [ ] T025 Push branch and verify CI is green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Element Browser)**: Depends on Phase 1 (clean types/nav)
- **Phase 3 (Element Detail)**: Depends on Phase 2 (links from browser)
- **Phase 4 (Schemas/Values)**: Depends on Phase 1 — can parallel with Phase 2
- **Phase 5 (Curation/Runs)**: Depends on Phase 1 — can parallel with Phase 2
- **Phase 6 (Tests)**: Depends on all previous phases

### Parallel Opportunities

- T014, T015 — schema and value pages are independent
- T017, T018 — curation and runs pages are independent
- Phase 4 and Phase 5 can run in parallel after Phase 1

---

## Implementation Strategy

### MVP (Phases 1-3)

1. Phase 1: Clean broken pages, update types
2. Phase 2: Element browser with real data
3. Phase 3: Element detail page
4. **STOP and VALIDATE**: Browse + click through works end-to-end

### Full Delivery

5. Phase 4: Schema + value browsers
6. Phase 5: Curation + runs pages
7. Phase 6: Playwright tests, lint, CI

---

## Notes

- Backend must be running (`cd backend && docker compose up -d`) for all verification tasks
- Existing components (shadcn/ui) should be reused, not rewritten
- All pages must handle three states: loading (skeleton/spinner), error (banner), empty (message)
- Commit after each completed phase
