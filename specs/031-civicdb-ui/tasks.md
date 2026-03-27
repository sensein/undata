# Tasks: CivicDB UI Redesign

**Input**: Design documents from `/specs/031-civicdb-ui/`
**Prerequisites**: plan.md, spec.md (with clarifications), research.md, quickstart.md

**Tests**: Playwright E2E tests included (FR-013).

**Organization**: 6 user stories. Shared components (Phase 2) block all page work. US1 (grids) + US2 (detail) + US3 (navigation) are coupled P1s. US4 + US5 are P2s. US6 (responsive + tests) is polish.

**Key clarifications incorporated**:
- Sidebar navigation with grouped sections (not top nav)
- Detail pages use tab navigation: Summary + Flags + Activity
- Hover popovers on primary entity types (elements, schemas, values)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Which user story (US1–US6)
- All paths relative to `frontend/` unless noted

## Phase 1: Setup

**Purpose**: Shared utilities, GraphQL queries, color maps

- [X] T001 Create `lib/source-colors.ts` — centralized color maps: SOURCE_COLORS (bids→blue, dandi→green, nwb→purple, openminds→orange, aind→teal) + ENTITY_TYPE_COLORS (element→cyan, schema→blue, value→lime, valueset→green, flag→red). Export `getSourceColor(source)` and `getEntityColor(type)` returning Tailwind class pairs (bg + text)
- [X] T002 Add new GraphQL queries to `graphql/queries.ts` — GET_SCHEMA (schema by sha256 with properties + provenance + annotations), GET_VALUE (value by sha256), GET_VALUESET (valueset by sha256 with members), ELEMENT_POPOVER (lightweight element query for hover: sha256, dataType, unit, description, first provenance source), SCHEMA_POPOVER, VALUE_POPOVER
- [X] T003 Update `lib/apollo.ts` — add cache policies for browseSchemas, browseValues (cursor merge), add type policies for popover queries (cache-first)

**Checkpoint**: Utilities, queries, and cache ready

---

## Phase 2: Foundational — Shared Components

**Purpose**: Reusable components used across all pages — BLOCKS all UI redesign

**⚠️ CRITICAL**: All redesigned pages depend on these components

- [X] T004 Create `components/SourceBadge.tsx` — color-coded source pill using `getSourceColor()`. Props: source string. Renders as small rounded badge with background + text color
- [X] T005 [P] Create `components/StatusBadge.tsx` — status pill: pending (yellow bg, exclamation icon), approved (green, check icon), rejected (red, x icon), deferred (gray). Props: status string. Matches CivicDB status tag pattern
- [X] T006 [P] Create `components/EntityTag.tsx` — clickable entity reference tag with optional hover popover. Props: entityType, sha256, label, showPopover?. Renders colored tag (using getEntityColor), on hover loads popover with key details via lightweight GraphQL query. Popovers for elements/schemas/values only; others are plain links
- [X] T007 Create `components/EntityDataGrid.tsx` — TanStack Table wrapper. Props: columns config (with sort keys), data rows, isLoading, onSort. Features: clickable column headers (asc/desc/none toggle), row hover highlight, skeleton loading rows, per-column filter inputs in header row 2. Renders SourceBadge and EntityTag in cells
- [X] T008 Create `components/Sidebar.tsx` — collapsible sidebar navigation following CivicDB pattern. Dark theme. Grouped sections: BROWSE (Elements, Schemas, Values, Value Sets), CURATION (Queue, Activity), RESOURCES (About). Collapsed mode: icons + tooltips only. Toggle button. Active route highlighting
- [X] T009 Create `components/EntityDetailLayout.tsx` — consistent detail page wrapper. Props: title, subtitle, entityType, sha256, status?, children, tabs. Renders: back link → title row (entity icon + name + SourceBadge + StatusBadge) → description → tab navigation (Summary/Flags/Activity) → tab content slot. Sections: provenance list, annotations list, related entities slot
- [X] T010 [P] Create `components/RelatedEntities.tsx` — displays linked entities as EntityTag cards. Props: title, items list with {entityType, sha256, label}. Hidden when items empty (edge case)
- [X] T011 [P] Create `components/EvidencePanel.tsx` — curation flag evidence display. Shows: match candidates table (term_label, ontology, score, relation), LLM verification (model, justification, confidence) if present, expandable "Show full context" for large context objects
- [X] T012 [P] Create `components/ActivityTimeline.tsx` — vertical event timeline. Props: events list with {type, entityRef, entityType, timestamp, description}. Type badges: flag_created (red), flag_resolved (green), contribution (blue). Pagination via "Load older" button

**Checkpoint**: All 9 shared components exist. Pages not yet changed.

---

## Phase 3: User Story 1 — Entity Data Grids (Priority: P1) 🎯 MVP

**Goal**: Sortable data grids for elements, schemas, values with per-column filters and clickable counts.

**Independent Test**: Open /elements → click "Type" header → rows sort. Hover element name → popover appears.

- [X] T013 [US1] Update `app/layout.tsx` — replace horizontal nav with Sidebar component. Content area shifts right with sidebar width. Mobile: sidebar hidden, toggle button in top bar
- [X] T014 [US1] Redesign `app/elements/page.tsx` — use EntityDataGrid with columns: name (EntityTag with popover), source (SourceBadge), type (sortable), unit (sortable), annotations count (clickable → detail #annotations), description (truncated). Per-column filter for source + type. Keep search + pagination
- [X] T015 [P] [US1] Redesign `app/schemas/page.tsx` — use EntityDataGrid. Columns: name (EntityTag), source (SourceBadge), properties count (clickable badge), is_mixin badge, description
- [X] T016 [P] [US1] Redesign `app/values/page.tsx` — use EntityDataGrid. Columns: label (EntityTag with popover), source (SourceBadge), value_type, primary annotation (term label), description
- [X] T017 [US1] Verify all three grids: sorting works, source badges consistent, entity tags render with popovers

**Checkpoint**: All entity browsers use sortable data grids with CivicDB-style entity tags

---

## Phase 4: User Stories 2+3 — Detail Pages + Connected Navigation (Priority: P1)

**Goal**: Consistent detail layouts with tabs (Summary/Flags/Activity) and bidirectional entity links.

**Independent Test**: Click element → detail page has tabs → Summary shows props + provenance + annotations + related schemas. Click schema → schema detail → click property element → round-trip.

- [ ] T018 [US2] Redesign `app/elements/[sha256]/page.tsx` — use EntityDetailLayout with tabs. Summary tab: semantic properties grid, provenance entries, ontology annotations (with id="annotations" anchor). Flags tab: list flags for this entity. Activity tab: timeline for this entity. Add RelatedEntities "Used in schemas" (client-side: load schemas, filter by properties containing this element)
- [ ] T019 [US3] Create `app/schemas/[sha256]/page.tsx` — use EntityDetailLayout with tabs. Summary: properties as EntityTag links to elements, subclass_of link, description. Flags + Activity tabs. RelatedEntities: property elements
- [ ] T020 [P] [US3] Create `app/values/[sha256]/page.tsx` — EntityDetailLayout with tabs. Summary: label, value_type, ontology annotation. RelatedEntities: "Part of valuesets"
- [ ] T021 [P] [US3] Redesign `app/valuesets/[sha256]/page.tsx` — EntityDetailLayout with tabs. Summary: members as EntityTag links to values. Replace placeholder
- [ ] T022 [US3] Update all browser pages — ensure entity names use EntityTag linking to /{entityType}/{sha256} detail pages
- [ ] T023 [US3] Verify bidirectional navigation: element → schema → element round-trip. Value → valueset → value round-trip

**Checkpoint**: All 4 entity types have tabbed detail pages with bidirectional navigation

---

## Phase 5: User Stories 4+5 — Curation Evidence + Activity Feed (Priority: P2)

**Goal**: Curation flags show evidence panels. Global activity feed page.

**Independent Test**: Open curation flag → expand → evidence panel with scores. Navigate to /activity → events listed.

- [ ] T024 [US4] Redesign `app/curation/page.tsx` — flags as expandable cards. Collapsed: entity_ref, flag_type badge, status badge, created_at. Expanded: EvidencePanel showing context.candidates with scores, LLM verification details. Approve/Reject action buttons (call resolveFlag mutation)
- [ ] T025 [P] [US5] Create `app/activity/page.tsx` — full-page ActivityTimeline. Sources events from curation flags (by created_at) merged chronologically. Add "Activity" to sidebar under CURATION group
- [ ] T026 [US4] Add entity-level activity to Flags and Activity tabs in EntityDetailLayout — filter events/flags by entity_ref matching the current entity

**Checkpoint**: Curation has evidence panels, activity feed works globally and per-entity

---

## Phase 6: User Story 6 — Responsive + Polish + Tests (Priority: P1)

**Goal**: Mobile responsive. Playwright tests. CI green.

**Independent Test**: Resize to 375px — sidebar hidden, grids become cards. `pnpm exec playwright test` passes.

- [ ] T027 [US6] Add responsive breakpoints to Sidebar — hidden below `md:`, toggle button appears in top bar
- [ ] T028 [US6] Add responsive breakpoints to EntityDataGrid — below `md:`, table rows become stacked cards with label:value pairs
- [ ] T029 [US6] Add responsive breakpoints to EntityDetailLayout — single column on mobile, two-column semantic grid on desktop
- [ ] T030 [US6] Update `tests/e2e/elements.spec.ts` — add: sidebar visible, column sorting works, entity tag popover appears on hover, click-through to detail shows tabs (Summary/Flags/Activity)
- [ ] T031 [US6] Update `tests/e2e/navigation.spec.ts` — add: sidebar links work, element → schema → element traversal via RelatedEntities
- [ ] T032 [US6] Update `tests/e2e/curation.spec.ts` — add: flag card expands, evidence panel visible with match candidates
- [ ] T033 Verify `pnpm exec eslint` and `pnpm exec next build` pass
- [ ] T034 Run quickstart validation QS-001 through QS-008
- [ ] T035 Push branch and verify CI is green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Components)**: Depends on Phase 1 — BLOCKS all UI work
- **Phase 3 (Data Grids)**: Depends on Phase 2 (needs EntityDataGrid, Sidebar, EntityTag)
- **Phase 4 (Detail + Navigation)**: Depends on Phase 2 — can start in parallel with Phase 3 after Sidebar exists
- **Phase 5 (Curation/Activity)**: Depends on Phase 2
- **Phase 6 (Responsive/Tests)**: Depends on all previous phases

### Parallel Opportunities

**Phase 2**: T005, T006, T010, T011, T012 — independent components

**Phase 3**: T015, T016 — schemas + values grids parallel after T007 (EntityDataGrid) exists

**Phase 4**: T020, T021 — value + valueset detail pages parallel

**Phase 5**: T025 (activity feed) parallel with T024 (curation redesign)

---

## Implementation Strategy

### MVP (Phases 1-3)

1. Shared utilities + all 9 components
2. Sidebar navigation + element browser with data grid
3. **STOP and VALIDATE**: Sidebar works, sorting works, entity tags render with popovers

### Full Delivery

4. All 4 detail pages with tabs + bidirectional navigation
5. Curation evidence + activity feed
6. Responsive + Playwright tests + CI green

---

## Notes

- Frontend-only — no backend changes
- TanStack Table already installed — no new deps
- Sidebar replaces top nav — layout.tsx is the key file
- Entity popovers need lightweight GraphQL queries (ELEMENT_POPOVER etc.) to avoid loading full entities on hover
- Tab state can use URL hash (#summary, #flags, #activity) or React state
- Commit after each completed phase
