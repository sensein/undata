# Tasks: CivicDB UI Redesign

**Input**: Design documents from `/specs/031-civicdb-ui/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Playwright E2E tests included (US6 spec requirement).

**Organization**: 6 user stories. Shared components built first (Phase 2). US1 (grids) + US2 (detail) + US3 (navigation) are tightly coupled P1s. US4 + US5 are independent P2s. US6 (responsive + tests) is polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Which user story (US1–US6)
- All paths relative to `frontend/` unless noted

## Phase 1: Setup

**Purpose**: Create shared utilities and GraphQL queries needed by all pages

- [ ] T001 Create `lib/source-colors.ts` — centralized SOURCE_COLORS map: bids→blue, dandi→green, nwb→purple, openminds→orange, aind→teal, default→gray. Export `getSourceColor(source: string)` returning Tailwind classes
- [ ] T002 Add new GraphQL queries to `graphql/queries.ts` — GET_SCHEMA (schema by sha256 with properties + provenance), GET_VALUE (value by sha256), GET_VALUESET (valueset by sha256 with members)
- [ ] T003 Update `lib/apollo.ts` — add cache policies for browseSchemas, browseValues (same merge pattern as browseElements)

**Checkpoint**: Utilities and queries ready for all phases

---

## Phase 2: Foundational — Shared Components

**Purpose**: Reusable components used across all entity pages — BLOCKS UI redesign phases

**⚠️ CRITICAL**: All redesigned pages depend on these components

- [ ] T004 Create `components/SourceBadge.tsx` — renders color-coded source pill using `getSourceColor()`. Props: source string. Consistent across all entity pages
- [ ] T005 [P] Create `components/CurationIndicator.tsx` — inline status pill: pending (yellow), approved (green), rejected (red), deferred (gray). Props: status string
- [ ] T006 Create `components/EntityDataGrid.tsx` — reusable TanStack Table wrapper. Props: columns config, data rows, onSort callback. Features: clickable column headers for sort (asc/desc toggle), row hover highlight, loading skeleton rows
- [ ] T007 [P] Create `components/RelatedEntities.tsx` — displays linked entities as clickable cards. Props: title, items list with {label, href, type}. Used for: element→schemas, schema→elements, value→valuesets, valueset→values
- [ ] T008 Create `components/EntityDetailLayout.tsx` — consistent detail page wrapper. Sections: back link, title + source badge + curation indicator, description, children (semantic content), provenance list, annotations list, related entities slot
- [ ] T009 [P] Create `components/EvidencePanel.tsx` — curation flag evidence display. Shows: match candidates with scores, LLM verification (model, justification, confidence), expandable full context
- [ ] T010 [P] Create `components/ActivityFeed.tsx` — event timeline component. Props: events list with {type, entityRef, timestamp, actor}. Renders as vertical timeline with type badges
- [ ] T011 Create `components/ResponsiveNav.tsx` — collapsible mobile navigation. Desktop: horizontal links. Mobile (<768px): hamburger toggle with slide-out menu

**Checkpoint**: All shared components exist and can be imported. No pages changed yet.

---

## Phase 3: User Story 1 — Entity Data Grids (Priority: P1) 🎯 MVP

**Goal**: Sortable data grids for elements, schemas, values with clickable counts.

**Independent Test**: Open /elements → click column header → rows sort.

- [ ] T012 [US1] Redesign `app/elements/page.tsx` — replace HTML table with EntityDataGrid. Columns: name (link), source (SourceBadge), type, unit, annotations count (clickable), description. Sortable by all columns. Keep existing filters + search + pagination
- [ ] T013 [P] [US1] Redesign `app/schemas/page.tsx` — use EntityDataGrid. Columns: name (link), source, properties count (clickable badge showing "N properties"), is_mixin badge, description
- [ ] T014 [P] [US1] Redesign `app/values/page.tsx` — use EntityDataGrid. Columns: label (link), source, value_type, ontology annotation (primary term), description
- [ ] T015 [US1] Verify all three grids sort correctly and clickable counts work

**Checkpoint**: All entity browsers use sortable data grids with consistent styling

---

## Phase 4: User Stories 2+3 — Detail Pages + Connected Navigation (Priority: P1)

**Goal**: Consistent detail layouts with bidirectional entity links.

**Independent Test**: Click element → detail page → click related schema → schema detail → click property → back to element.

- [ ] T016 [US2] Redesign `app/elements/[sha256]/page.tsx` — use EntityDetailLayout. Add RelatedEntities for "Used in schemas" (resolve from schema properties). Add CurationIndicator if flags exist
- [ ] T017 [US3] Create `app/schemas/[sha256]/page.tsx` — use EntityDetailLayout. Show properties as clickable links to element detail pages (extract sha256 from property identifier). Add RelatedEntities for property elements
- [ ] T018 [P] [US3] Create `app/values/[sha256]/page.tsx` — use EntityDetailLayout. Add "Part of valuesets" section linking to parent valuesets
- [ ] T019 [P] [US3] Create `app/valuesets/[sha256]/page.tsx` — use EntityDetailLayout. Show members as clickable links to value detail pages. Replace placeholder page
- [ ] T020 [US3] Update element, schema, value, valueset browser pages — ensure all entity names link to their detail pages (element→/elements/sha256, schema→/schemas/sha256, etc.)
- [ ] T021 [US3] Verify bidirectional navigation: element→schema→element round-trip works

**Checkpoint**: All entity types have detail pages with bidirectional navigation

---

## Phase 5: User Stories 4+5 — Curation Evidence + Activity Feed (Priority: P2)

**Goal**: Curation flags show evidence panels. Activity feed shows platform events.

**Independent Test**: Open curation flag → evidence panel visible. Open /activity → events listed.

- [ ] T022 [US4] Redesign `app/curation/page.tsx` — add EvidencePanel to each flag card. Expand on click to show match candidates (from flag.context), LLM verification details, resolve action buttons
- [ ] T023 [P] [US5] Create `app/activity/page.tsx` — use ActivityFeed component. Source events from curation flags (sorted by created_at) + contributions. Add to navigation in layout.tsx
- [ ] T024 [US4] Add entity-level activity section to EntityDetailLayout — show "Recent activity" on each entity detail page (flags + contributions for that entity_ref)

**Checkpoint**: Curation queue has evidence panels, activity feed page works

---

## Phase 6: User Story 6 — Responsive Layout + Polish + Tests (Priority: P1)

**Goal**: All pages responsive. Playwright tests pass. CI green.

**Independent Test**: Resize to 375px — layout adapts. `pnpm exec playwright test` passes.

- [ ] T025 [US6] Update `app/layout.tsx` — replace current nav with ResponsiveNav. Add "Activity" link to navigation
- [ ] T026 [US6] Add responsive breakpoints to EntityDataGrid — tables become stacked cards below `md:` breakpoint
- [ ] T027 [US6] Add responsive breakpoints to EntityDetailLayout — single column on mobile, two-column grid on desktop for semantic properties
- [ ] T028 [US6] Update `tests/e2e/elements.spec.ts` — add tests: column sorting works, click-through to detail shows consistent layout, provenance and annotations sections present
- [ ] T029 [US6] Update `tests/e2e/navigation.spec.ts` — add test: element → schema → element traversal works (3-step round-trip)
- [ ] T030 [US6] Add `tests/e2e/curation.spec.ts` test — flag card expandable, evidence panel visible
- [ ] T031 Verify `pnpm exec eslint` and `pnpm exec next build` pass
- [ ] T032 Run quickstart validation QS-001 through QS-008
- [ ] T033 Push branch and verify CI is green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Components)**: Depends on Phase 1 — BLOCKS all UI work
- **Phase 3 (Data Grids)**: Depends on Phase 2
- **Phase 4 (Detail Pages)**: Depends on Phase 2 — can parallel with Phase 3
- **Phase 5 (Curation/Activity)**: Depends on Phase 2 — can parallel with Phase 3
- **Phase 6 (Responsive/Tests)**: Depends on all previous phases

### Parallel Opportunities

**Phase 2**: T005, T007, T009, T010 all independent components

**Phase 3**: T013, T014 (schemas + values grids) parallel after T006 exists

**Phase 4**: T018, T019 (value + valueset detail) parallel

**Phase 5**: T023 (activity) parallel with T022 (curation)

---

## Implementation Strategy

### MVP (Phases 1-3)

1. Shared utilities + components
2. Element browser with sortable data grid
3. **STOP and VALIDATE**: Sorting works, source badges consistent

### Full Delivery

4. Detail pages with connected navigation
5. Curation evidence + activity feed
6. Responsive layout + Playwright tests + CI green

---

## Notes

- Frontend-only — no backend changes
- TanStack Table already in package.json — no new install needed
- Source colors must be identical across all pages (centralized map)
- Connected navigation requires resolving property identifiers to sha256 prefixes
- Commit after each completed phase
