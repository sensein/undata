# Feature Specification: Frontend Integration

**Feature Branch**: `030-frontend-integration`
**Created**: 2026-03-26
**Status**: Draft
**Input**: Phase 3 of iteration 2 — wire the existing frontend pages to the backend GraphQL API so users can browse elements, view details, manage curation queue, and see run history.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Element Browser (Priority: P1)

As a researcher, I need to browse data elements with filters (source, data type, search text) and pagination so I can find elements across ecosystems.

**Why this priority**: This is the primary user-facing page. If the element browser works end-to-end (database → API → UI), the system demonstrates its core value.

**Independent Test**: Start the stack, open the browser, verify elements load with correct data.

**Acceptance Scenarios**:

1. **Given** a running stack with seed data, **When** a user opens the element browser, **Then** elements are displayed with name, source, data type, unit, and description.
2. **Given** the element browser, **When** a user filters by source "bids", **Then** only BIDS-sourced elements are shown.
3. **Given** a list of elements, **When** the user scrolls past the first page, **Then** more elements load via cursor pagination.
4. **Given** the element browser, **When** a user types in the search box, **Then** elements matching the search text are displayed.

---

### User Story 2 — Element Detail Page (Priority: P1)

As a researcher, I need to click an element and see its full details — semantic properties, provenance chain, and ontology annotations — so I understand what the element represents and where it came from.

**Why this priority**: The detail page is the second most important page — it's where users go after finding an element in the browser. It validates the full data model renders correctly.

**Independent Test**: Click any element in the browser — the detail page shows all fields.

**Acceptance Scenarios**:

1. **Given** the element browser, **When** a user clicks an element, **Then** the detail page shows data type, unit, pattern, description, and all semantic properties.
2. **Given** an element detail page, **When** provenance data exists, **Then** each provenance entry shows source, class, name, and description.
3. **Given** an element with ontology annotations, **When** the detail page loads, **Then** annotations show term label, ontology, mapping relation (e.g., skos:exactMatch), and confidence score.

---

### User Story 3 — Schema and Value Browsers (Priority: P1)

As a standards developer, I need to browse schemas (class definitions) and values (enum options) so I can understand the full data model across sources.

**Why this priority**: These are the other two entity types beyond elements. Without them, the registry is incomplete.

**Independent Test**: Navigate to schemas page — schemas load. Navigate to values page — values load.

**Acceptance Scenarios**:

1. **Given** the running stack, **When** a user navigates to the schemas page, **Then** schemas are listed with name, description, properties, and source.
2. **Given** the running stack, **When** a user navigates to the values page, **Then** values are listed with label, ontology annotation, and source.

---

### User Story 4 — Curation Queue (Priority: P2)

As a curator, I need to see pending curation flags with their evidence so I can review and resolve them.

**Why this priority**: The curation queue is central to the community model, but it requires populated flags which may not exist in seed data. P2 because browsers (P1) must work first.

**Independent Test**: Navigate to curation page — flags load (or empty state shown).

**Acceptance Scenarios**:

1. **Given** the curation page, **When** flags exist, **Then** they are displayed with entity reference, flag type, context, and status.
2. **Given** a pending flag, **When** a curator clicks resolve, **Then** they can approve/reject with a note and the flag status updates.

---

### User Story 5 — Run History Dashboard (Priority: P2)

As a developer, I need to see pipeline run history so I can track extraction progress and compare runs.

**Why this priority**: Run summaries are a supporting feature. P2 because the core browsers must work first.

**Independent Test**: Navigate to runs page — run summaries load (or empty state shown).

**Acceptance Scenarios**:

1. **Given** the runs page, **When** run summaries exist, **Then** they show source, timestamp, entity counts, and timing.

---

### User Story 6 — Playwright E2E Tests (Priority: P1)

As a maintainer, I need automated browser tests that verify the frontend works with real backend data so regressions are caught in CI.

**Why this priority**: Constitution requires CI green before merge. Visual tests catch UI regressions that unit tests miss.

**Independent Test**: Run Playwright against the running stack — all tests pass.

**Acceptance Scenarios**:

1. **Given** a running stack with seed data, **When** Playwright tests run, **Then** element browser loads, displays data, and pagination works.
2. **Given** the Playwright suite, **When** it runs in CI, **Then** all tests pass within 5 minutes.

---

### Edge Cases

- What happens when the backend is down? The frontend shows a connection error, not a blank page.
- What happens when a query returns zero results? The page shows an empty state message.
- What happens when an element has no ontology annotations? The annotations section is hidden or shows "No annotations yet".
- What happens when the user navigates directly to an element detail URL with an invalid sha256? The page shows "Element not found".

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Element browser MUST load data from the backend GraphQL API and display elements with name, source, data type, and description.
- **FR-002**: Element browser MUST support filtering by source and data type.
- **FR-003**: Element browser MUST support cursor-based pagination (load more on scroll or button click).
- **FR-004**: Element detail page MUST display all semantic properties, provenance chain, and ontology annotations.
- **FR-005**: Schema browser MUST load and display schemas with properties and source information.
- **FR-006**: Value browser MUST load and display values with labels and ontology annotations.
- **FR-007**: Curation queue MUST display pending flags with filter by type and status.
- **FR-008**: Run history page MUST display pipeline run summaries.
- **FR-009**: All pages MUST show appropriate empty states when no data exists.
- **FR-010**: All pages MUST show error messages when the backend is unreachable.
- **FR-011**: Playwright E2E tests MUST cover element browsing, detail page navigation, and pagination.
- **FR-012**: Frontend MUST work with the backend Docker stack started via `docker compose up`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Element browser displays seed data (5+ elements) within 2 seconds of page load.
- **SC-002**: All 5 main pages (elements, schemas, values, curation, runs) load without JavaScript errors.
- **SC-003**: Playwright E2E tests pass against the running backend.
- **SC-004**: Element detail page renders all fields for the seed data elements.
- **SC-005**: Pagination works — requesting a second page returns different elements.

## Scope Boundaries

### In Scope

- Wiring existing pages to the backend GraphQL API
- Fixing query/type mismatches between frontend and backend
- Element browser with filters and pagination
- Element detail page
- Schema and value browsers
- Curation queue page (basic display)
- Run history page (basic display)
- Playwright E2E tests
- Error handling and empty states

### Out of Scope

- Authentication UI (deferred)
- Contribution submission forms (deferred)
- New page designs or layouts
- Mobile responsive design
- Performance optimization (SSR, code splitting)
- Search with Meilisearch integration
- CivicDB-inspired UI redesign (entity grids with clickable counts, inline curation status indicators, evidence panels, activity feeds, bidirectional entity navigation) — deferred to a dedicated feature (031)

## Clarifications

### Session 2026-03-26

- Q: Should this feature include redesigning pages to match CivicDB's UI patterns? → A: No — wire existing pages now, defer CivicDB UI redesign to a dedicated feature (031).

## Assumptions

- The backend (feature 029) is running and serves seed data via GraphQL
- Existing page components from brainstorm v1 are the starting point — fix, don't rewrite
- Apollo Client is already configured to connect to the backend
- Frontend queries (graphql/queries.ts) were updated in 029 to match the backend schema

## Dependencies

- Feature 029 (backend service) — provides the GraphQL API and seed data
- Feature 028 (storage abstraction) — provides the entity model
