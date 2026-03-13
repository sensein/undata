# Feature Specification: Schema Explorer Frontend

**Feature Branch**: `003-schema-explorer`
**Created**: 2026-03-07
**Status**: Draft
**Input**: Web-based frontend that allows users to view, search, and contribute new
data elements within the undata neuroscience schema integration system.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Browse and Search Data Elements (Priority: P1)

A neuroscientist wants to find which schemas define a concept like "subject age" or
"electrode impedance." They open the Schema Explorer, type a keyword, and immediately
see a ranked list of matching data elements from across all integrated schemas — with
each result showing the element's name, type, description, source schema, and any
known aliases.

**Why this priority**: Discovery is the primary reason a user visits the Explorer.
Without search and browse, the tool has no value. All other stories build on this.

**Independent Test**: Open the explorer in a browser, enter a keyword, and verify
that matching elements are displayed with correct metadata from the backend. No
login or add-element flow is needed.

**Acceptance Scenarios**:

1. **Given** a populated data element store, **When** a user enters a keyword in the
   search bar, **Then** matching elements appear within 2 seconds, showing name, type,
   description, source schema, and alias count.

2. **Given** search results, **When** a user selects a result, **Then** a detail view
   opens showing the full element record: all metadata, all source schemas that define
   it, its alias groups, and all registered mappings where it appears as input or output.

3. **Given** the element list, **When** a user applies a filter by source schema (e.g.,
   "BIDS only"), **Then** only elements from that schema are shown and the count updates.

4. **Given** the element list, **When** a user applies a filter by data type
   (e.g., "string", "number"), **Then** only elements of that type are shown.

5. **Given** a data element detail view, **When** the element has known aliases,
   **Then** the aliases are listed with their source schemas and a link to each
   alias's detail view.

6. **Given** no results for a search query, **When** the results area renders, **Then**
   a clear "no results" message is shown with a suggestion to broaden the query or
   contribute the element.

---

### User Story 2 — Explore Mappings and Alias Graph (Priority: P2)

A data engineer wants to understand how a specific data element relates to elements
in other schemas — what it maps to, what maps to it, and which elements are considered
aliases. They navigate to the element's detail view and see an interactive relationship
graph showing direct mappings and alias connections.

**Why this priority**: Understanding relationships is as important as finding elements.
This story transforms the explorer from a lookup tool into an integration navigator.

**Independent Test**: Navigate to a data element that has registered mappings and alias
groups. Verify the relationship graph renders with correct connections and that clicking
a connected node navigates to that element's detail view.

**Acceptance Scenarios**:

1. **Given** a data element with registered mappings, **When** a user views its detail
   page, **Then** an interactive graph shows all directly connected elements (inputs and
   outputs of mappings) with edge labels indicating function type (identity vs. custom).

2. **Given** the relationship graph, **When** a user clicks on a connected element node,
   **Then** the view navigates to that element's detail page.

3. **Given** an alias group, **When** a user views any member element, **Then** all
   alias members are visually grouped and distinguished from non-alias mappings.

4. **Given** a multi-hop mapping chain (A → B → C), **When** a user views element A,
   **Then** the graph shows the full reachable chain and allows the user to expand
   or collapse depth levels.

---

### User Story 3 — Contribute New Data Elements (Priority: P3)

A researcher has identified a data element used in their lab's data pipeline that is
not yet in the system. They open the "Add Element" form, fill in the required metadata
(name, type, description, cardinality), optionally specify allowed values and source
provenance, and submit. After submission the element appears in search results and its
detail page is immediately accessible.

**Why this priority**: Community contribution is essential for the system to grow
beyond the four initially ingested schemas. It enables the system to evolve into a
living registry.

**Independent Test**: Submit the add-element form with valid data and confirm the new
element appears in search results and has a detail page. Then submit with missing
required fields and confirm appropriate validation errors are shown.

**Acceptance Scenarios**:

1. **Given** the "Add Element" form, **When** a user fills all required fields and
   submits, **Then** the element is created and the user is redirected to the new
   element's detail page.

2. **Given** the "Add Element" form, **When** a user omits a required field and submits,
   **Then** the form highlights the missing field with a descriptive error message and
   does not submit.

3. **Given** a successfully submitted element, **When** another user searches for it
   by name, **Then** it appears in results immediately (no manual refresh required).

4. **Given** the "Add Element" form, **When** the element name already exists in the
   store, **Then** the form warns the user of the potential duplicate and shows the
   existing element(s) before allowing submission.

5. **Given** a submitted element, **When** a user views its detail page, **Then** the
   page shows the submission timestamp and contributor identity (if authenticated).

---

### User Story 4 — Compare Elements Across Schemas (Priority: P4)

A schema harmonization expert wants to compare two data elements side by side —
seeing their names, types, descriptions, constraints, and mappings in a two-column
layout — to decide whether they are aliases or require a custom mapping.

**Why this priority**: Side-by-side comparison directly supports the core workflow of
discovering and registering alias relationships, making it a high-value tool for
schema harmonization work.

**Independent Test**: Select two data elements from the search view, open the compare
view, and confirm both elements' full metadata is shown side by side with visual
highlights on fields that differ.

**Acceptance Scenarios**:

1. **Given** two selected data elements, **When** a user opens the comparison view,
   **Then** all metadata fields are shown side by side with differences visually
   highlighted.

2. **Given** the comparison view, **When** two fields have identical values,
   **Then** they are visually marked as matching (not highlighted as differences).

3. **Given** the comparison view, **When** a user decides the two elements are aliases,
   **Then** there is a one-click action to register an identity mapping between them
   (creating the alias relationship in the backend).

---

### Edge Cases

- What happens when the backend is unavailable? The explorer MUST display a clear
  service-unavailable message and MUST NOT show stale or partial data without clearly
  labelling it as cached.
- What happens when a user enters a very long query string (>500 characters)? The
  input MUST be trimmed or rejected with a clear length limit message.
- What happens when the relationship graph contains hundreds of nodes? The graph MUST
  remain interactive; it MUST offer a depth-limit control to prevent rendering an
  unmanageably large graph.
- What happens when a user submits an element with a name containing special characters
  or non-ASCII text? The system MUST accept valid Unicode element names and MUST
  sanitize input to prevent injection.

---

## Requirements *(mandatory)*

### Functional Requirements

**Search and Browse**

- **FR-001**: Interface MUST provide a keyword search input that queries element names
  and descriptions, returning ranked results within 2 seconds.
- **FR-002**: Results MUST be filterable by: source schema, data type, alias presence,
  and mapping presence.
- **FR-003**: Each search result item MUST display: element name, data type, description
  excerpt, source schema badge(s), and alias count.
- **FR-004**: Selecting a result MUST open a full detail view without a full page reload.

**Element Detail View**

- **FR-005**: Detail view MUST display all element metadata: name, type, description,
  cardinality, allowed values, source schema(s), version, ingestion timestamp.
- **FR-006**: Detail view MUST list all alias group members with their source schemas.
- **FR-007**: Detail view MUST list all mappings where the element is an input or output,
  showing function type and linked elements.
- **FR-008**: Detail view MUST include an interactive relationship graph showing
  directly connected elements with depth-expansion controls.

**Add Element**

- **FR-009**: Interface MUST provide an "Add Element" form with fields for: name (required),
  data type (required), description (required), cardinality (required), allowed values
  (optional), and source provenance (optional).
- **FR-010**: Form MUST validate all required fields client-side before submission.
- **FR-011**: Form MUST detect potential duplicates (same name in store) and surface
  existing matches before allowing submission.
- **FR-012**: On successful submission, the user MUST be redirected to the new element's
  detail page.

**Comparison View**

- **FR-013**: Interface MUST allow selecting exactly two elements for side-by-side
  comparison from search results or detail views.
- **FR-014**: Comparison view MUST visually distinguish matching fields from differing
  fields.
- **FR-015**: Comparison view MUST include a one-click action to register an identity
  mapping (alias) between the two elements.

**General**

- **FR-016**: All views MUST be accessible via a stable, shareable URL so users can
  link directly to an element, a search result set, or a comparison.
- **FR-017**: Interface MUST display a clear error state when the backend is unavailable.
- **FR-018**: All user-supplied text inputs MUST be sanitized to prevent injection.

### Key Entities *(frontend perspective)*

- **SearchQuery**: User-entered keyword plus active filter set; encodable in the URL.
- **SearchResult**: A lightweight element summary (name, type, description excerpt,
  source, alias count) returned from the backend.
- **ElementDetail**: The full data element record including mappings and alias group,
  as returned by the backend.
- **RelationshipGraph**: A client-side graph model derived from an element's mapping
  and alias data, rendered interactively.
- **ComparisonPair**: Two ElementDetail records held side by side for diff rendering.

---

## Assumptions

- The frontend communicates exclusively with the backend service (spec 002) and the
  migration API (spec 004) through their defined interfaces.
- Authentication is required to submit new elements (write access); browse and search
  are available without authentication.
- The relationship graph uses a depth-first traversal up to a configurable maximum
  depth (default: 2 hops); deeper traversal is opt-in.
- "Immediately" in story 3 means the element is searchable without manual page refresh;
  the acceptable latency is defined as the normal search response time (≤2 seconds).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Search results for a known keyword appear within 2 seconds of submission
  on a standard broadband connection.
- **SC-002**: The relationship graph for an element with up to 50 direct connections
  renders and is interactive within 3 seconds.
- **SC-003**: A new element submitted via the form is retrievable via search within
  5 seconds of submission confirmation.
- **SC-004**: Form validation prevents submission with missing required fields in 100%
  of test cases (zero invalid submissions reach the backend from the form).
- **SC-005**: Duplicate-name warning is surfaced before submission in 100% of cases
  where a name collision exists in the store.
- **SC-006**: All views are accessible via stable, shareable URLs; navigating to a
  stored URL reproduces the same view state in 100% of tested cases.
