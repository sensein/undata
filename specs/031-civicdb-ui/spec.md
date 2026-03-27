# Feature Specification: CivicDB-Inspired UI Redesign

**Feature Branch**: `031-civicdb-ui`
**Created**: 2026-03-27
**Status**: Draft
**Input**: Redesign frontend pages following CivicDB UI/UX patterns defined in VISION.md — entity data grids, connected navigation, curation evidence panels, activity feed, consistent detail layouts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Entity Data Grids (Priority: P1)

As a researcher browsing the registry, I need filterable data grids for each entity type with entity-specific columns, clickable counts that navigate to related entities, and multi-column sort — so I can efficiently explore thousands of elements across sources.

**Why this priority**: The current table is basic — one column layout, no sorting, no clickable counts. CivicDB's data grids are the primary browsing experience and the feature most visible to users.

**Independent Test**: Open the element browser — the grid has sortable columns, source badges, clickable annotation counts, and per-column filter controls.

**Acceptance Scenarios**:

1. **Given** the element browser, **When** a user clicks a column header, **Then** the table sorts by that column (ascending/descending toggle).
2. **Given** an element with 3 provenance sources, **When** the browser displays it, **Then** the source count "3 sources" is a clickable link that expands to show all sources.
3. **Given** an element with ontology annotations, **When** the browser displays it, **Then** the annotation count is clickable and navigates to the annotation details.
4. **Given** the schema browser, **When** a schema has 5 properties, **Then** "5 properties" is a clickable link that shows the property elements.

---

### User Story 2 — Consistent Entity Detail Pages (Priority: P1)

As a researcher exploring a specific element, I need a consistent detail page layout across all entity types — identity block, semantic content, provenance chain, ontology annotations, and related entities — so I can understand any entity at a glance.

**Why this priority**: The detail page is where users spend the most time. A consistent layout reduces cognitive load and enables the connected navigation that makes the registry useful.

**Independent Test**: Click any entity in any browser — the detail page follows the same layout pattern with all sections populated.

**Acceptance Scenarios**:

1. **Given** an element detail page, **When** it loads, **Then** it shows: identity block (sha256, type, unit) → description → semantic properties → provenance chain → ontology annotations → related schemas → curation status.
2. **Given** an element that appears in a schema's properties, **When** viewing that element, **Then** a "Used in schemas" section lists the referencing schemas as clickable links.
3. **Given** a schema detail page, **When** it lists properties, **Then** each property is a clickable link to the element detail page.
4. **Given** any entity with a pending curation flag, **When** the detail page loads, **Then** a yellow "pending review" indicator is visible near the title.

---

### User Story 3 — Connected Entity Navigation (Priority: P1)

As a user exploring the knowledge graph, I need entities to link bidirectionally — elements link to their schemas, schemas link to their elements, values link to their valuesets — so I can traverse relationships in any direction.

**Why this priority**: This is the "graph" in "knowledge graph." Without bidirectional navigation, users hit dead ends. CivicDB's Gene→Variant→EvidenceItem navigation is what makes it powerful.

**Independent Test**: Start at any element → click related schema → click a property element → arrive at a different element. The traversal is seamless.

**Acceptance Scenarios**:

1. **Given** an element detail page, **When** the element appears in schemas, **Then** those schemas are listed and clickable.
2. **Given** a schema detail page, **When** it has properties, **Then** each property links to its element detail page.
3. **Given** a value detail page, **When** the value belongs to a valueset, **Then** the valueset is listed and clickable.
4. **Given** a valueset detail page, **When** it has members, **Then** each member links to its value detail page.

---

### User Story 4 — Curation Queue with Evidence Panels (Priority: P2)

As a curator reviewing flags, I need each flag to show an evidence panel — the automated match candidates, similarity scores, LLM justification, and related entities — so I can make informed decisions quickly.

**Why this priority**: The current curation page shows flags as flat cards. CivicDB shows evidence alongside decisions. P2 because the basic queue works from 030; this adds the "expert reviewer" experience.

**Independent Test**: Open a curation flag — the evidence panel shows match candidates with scores.

**Acceptance Scenarios**:

1. **Given** a low_confidence flag, **When** a curator opens it, **Then** the evidence panel shows the top ontology candidates with similarity scores.
2. **Given** a flag with LLM verification, **When** the evidence panel loads, **Then** it shows the LLM model, justification text, and confidence score.
3. **Given** a flag, **When** a curator clicks "Approve" with a note, **Then** the flag status updates to approved and the note is recorded.

---

### User Story 5 — Activity Feed (Priority: P2)

As a community member, I need to see recent activity across the platform — flags created, contributions submitted, flags resolved — so I can follow the curation progress and see what's happening.

**Why this priority**: Activity feeds drive engagement and transparency. P2 because the core browsing/curation flows must work first.

**Independent Test**: Navigate to the activity feed — recent events are listed with entity references, action types, and timestamps.

**Acceptance Scenarios**:

1. **Given** the activity feed page, **When** events exist, **Then** they are listed chronologically with action type, entity reference, and timestamp.
2. **Given** an entity detail page, **When** activity exists for that entity, **Then** a "Recent activity" section shows events specific to that entity.

---

### User Story 6 — Responsive Layout and Polish (Priority: P1)

As any user on any device, I need the interface to be clean, consistent, and readable — with proper spacing, color coding for entity types, and a cohesive visual design.

**Why this priority**: CivicDB's visual polish is part of what makes it trustworthy. An inconsistent or cluttered UI undermines credibility.

**Independent Test**: Open the site on desktop and mobile — all pages are readable and properly laid out.

**Acceptance Scenarios**:

1. **Given** any page, **When** viewed on desktop (1200px+), **Then** content uses the full width with proper spacing.
2. **Given** any page, **When** viewed on mobile (375px), **Then** tables become responsive cards and navigation collapses to a menu.
3. **Given** entities from different sources, **When** displayed in any browser, **Then** each source has a consistent color badge (BIDS=blue, DANDI=green, NWB=purple, openMINDS=orange, AIND=teal).

---

### Edge Cases

- What happens when an entity has no related entities? The "Related" section is hidden, not shown empty.
- What happens when the activity feed has hundreds of entries? Pagination with "Load older" button.
- What happens when a curation flag's context is very large? The evidence panel shows a summary with "Show full context" expand.
- What happens on slow connections? Skeleton loading states for all sections, progressive disclosure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Entity browsers MUST display sortable data grids with entity-specific columns.
- **FR-002**: Counts in data grids (sources, annotations, properties) MUST be clickable links navigating to the referenced entities.
- **FR-003**: Entity detail pages MUST follow a consistent layout: identity → semantic → provenance → annotations → related entities → curation status.
- **FR-004**: Entities MUST link bidirectionally — elements ↔ schemas, values ↔ valuesets.
- **FR-005**: Curation flags MUST display evidence panels with match candidates, scores, and LLM justification when available.
- **FR-006**: System MUST display an activity feed showing platform events chronologically.
- **FR-007**: Source badges MUST use consistent color coding across all pages.
- **FR-008**: Entities with pending curation flags MUST show an inline status indicator.
- **FR-009**: All pages MUST be responsive (desktop + mobile layouts).
- **FR-010**: Playwright E2E tests MUST cover entity navigation, sorting, and curation flow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can navigate from any element to a related schema and back in under 3 clicks.
- **SC-002**: Data grids support column sorting for all entity types.
- **SC-003**: Curation evidence panels display match candidates when available.
- **SC-004**: Activity feed displays at least 20 recent events with entity links.
- **SC-005**: All pages render correctly at 375px and 1200px viewports.
- **SC-006**: Playwright E2E tests cover navigation traversal and pass.

## Scope Boundaries

### In Scope

- Entity data grid redesign with sorting and clickable counts
- Consistent entity detail page layout
- Bidirectional entity navigation (element ↔ schema, value ↔ valueset)
- Curation evidence panels
- Activity feed page
- Source color coding
- Inline curation status indicators
- Responsive layout
- Playwright E2E tests

### Out of Scope

- Authentication and user accounts (separate feature)
- Contribution submission forms
- User profiles and leaderboards (requires auth)
- Real-time notifications
- Meilisearch integration
- Backend changes (this feature is frontend-only, using existing GraphQL API)

## Assumptions

- The backend GraphQL API from feature 029 provides all needed data
- Schema properties contain element identifiers that can be resolved to element detail pages
- Curation flag context contains match candidate data (scores, terms) from the enrichment pipeline
- The existing shadcn/ui component library and Tailwind CSS are used for all new components

## Dependencies

- Feature 030 (frontend integration) — provides working page foundations
- Feature 029 (backend service) — provides the GraphQL API
- VISION.md Community Model and UI Design Patterns sections
