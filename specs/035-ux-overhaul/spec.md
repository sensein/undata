# Feature Specification: UX & UI Overhaul

**Feature Branch**: `035-ux-overhaul`
**Created**: 2026-03-29
**Status**: Draft
**Input**: Comprehensive UX/UI upgrade — modernized layouts, rich property tables, chat-first curation flows, link health monitoring, transform validation, and dandi-medit-inspired entity editing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Rich Property Tables & Entity Display (Priority: P1)

As a researcher browsing schemas or value sets, I need property/member rows to display as rich, interactive entity chips (with type, source, unit, and hover popovers) — the same way the element browse table works — so I can quickly understand what each property is without leaving the page.

**Why this priority**: The property tables currently display raw text strings instead of interactive entity tags. This is the most visible regression and affects every detail page.

**Independent Test**: Open any schema detail page → properties table shows entity chips with name, type badge, source badge, and hover popover with ontology annotations — not plain text.

**Acceptance Scenarios**:

1. **Given** a schema detail page with properties, **When** it loads, **Then** each property row shows an EntityTag chip (with name, colored type badge), a data type column, a unit column, and a source badge — identical in style to the element browse grid.
2. **Given** an element browse grid, **When** it loads, **Then** each row displays the unit column (currently missing from the grid) alongside data type, source, and ontology.
3. **Given** a valueset detail page with members, **When** it loads, **Then** each member row shows a value EntityTag chip with label, value type, and source badge — not a plain text string.
4. **Given** a property/member that cannot be resolved (no matching element/value in the registry), **When** the table renders, **Then** it shows a monospace hash/name with a subtle "unresolved" indicator rather than a truncated string.

---

### User Story 2 — Chat-First Curation Flow (Priority: P1)

As a curator, I need the "Suggest Change" button on any entity detail page to open the curation chat pre-loaded with the full entity context (all fields, provenance, annotations, related entities, and any existing curation flags) — modeled after dandi-medit's editing interface — so I can immediately start an informed conversation with the AI assistant.

**Why this priority**: The curation chat is the primary workflow for improving the registry. Currently the "Suggest Change" button navigates to the chat but the right panel shows minimal entity info (type, unit, description, SHA only). Curators need the complete picture.

**Independent Test**: Click "Suggest Change" on an element → curation chat opens → right panel shows all element fields (data type, unit with QUDT link, pattern, value domain, min/max, description), full provenance list, ontology annotations, related schemas, and any pending flags.

**Acceptance Scenarios**:

1. **Given** an entity detail page, **When** a curator clicks "Suggest Change", **Then** the curation chat opens with the entity's sha256 pre-loaded, and the right panel displays the complete entity card matching the detail page's summary tab content.
2. **Given** the curation chat right panel, **When** entity context loads, **Then** all fields are displayed in a structured card layout: semantic properties (type, unit, pattern, domain, min/max), provenance entries with source badges, ontology annotations as clickable chips, and related entities as EntityTag links.
3. **Given** any entity type (element, schema, value, valueset, transform), **When** the "Suggest Change" button is clicked, **Then** the curation chat loads the correct entity type context and displays type-appropriate fields (e.g., "properties" for schemas, "members" for valuesets).
4. **Given** an entity with pending curation flags, **When** the chat right panel loads, **Then** the flags are displayed with their type, reason, and status — enabling the curator to address them directly in conversation.
5. **Given** any EntityTag popover, browse table row, or search result, **When** the user clicks a "Chat about this" action, **Then** the curation chat opens with that entity pre-loaded — not only from detail pages.
6. **Given** no specific entity context, **When** a user opens the chat from the sidebar as a standalone assistant, **Then** the chat starts in general-purpose mode where the user can ask questions about the registry, search for entities within the conversation, or reference entities by name/sha256 to load them into context.

---

### User Story 3 — Modernized Layout & Reduced Whitespace (Priority: P1)

As any user, I need a denser, more information-rich UI with tighter spacing, consistent card layouts, and proper use of overlays/popovers — so I can see more data at a glance without excessive scrolling.

**Why this priority**: The current UI has generous whitespace and basic styling that wastes screen real estate. A modern, dense layout lets researchers scan more data efficiently.

**Independent Test**: Load the element browse page → the data grid is tighter (reduced row padding), column headers are compact, filter controls are inline, and the page shows 50%+ more rows in the viewport compared to the current layout.

**Acceptance Scenarios**:

1. **Given** any browse page (elements, schemas, values, valuesets, transforms), **When** it loads on a 1080p display, **Then** at least 20 data rows are visible without scrolling (currently ~12).
2. **Given** any entity detail page, **When** it loads, **Then** semantic properties are displayed in a compact multi-column card grid (not single-column with large gaps), and the full entity is visible without scrolling on a 1080p display.
3. **Given** ontology annotations on any entity, **When** displayed, **Then** they appear as compact clickable chips (CURIE label + score) — not a verbose list — with an external link icon that opens the ontology term in a new tab.
4. **Given** provenance entries, **When** displayed, **Then** they show as a compact horizontal list of source badges with expandable details (class, name, description) on click — not a verbose vertical list.

---

### User Story 4 — Contextual Overlays & Cross-Links (Priority: P2)

As a researcher exploring the registry, I need every entity reference to be an interactive link with a hover overlay showing key details — and every external URI (ontology terms, QUDT units, source repositories) to be a verified outbound link — so I can navigate the knowledge graph fluidly.

**Why this priority**: Cross-referencing is core to the registry's value. Researchers need to trace connections (element → schemas that use it, value → valuesets that contain it, transforms between elements) without losing context.

**Independent Test**: Hover over any EntityTag → popover shows entity summary with key fields, annotations, and "View Details" link. Click any ontology URI → opens external site in new tab.

**Acceptance Scenarios**:

1. **Given** an EntityTag for an element, **When** the user hovers, **Then** a popover appears showing: name, data type, unit, primary ontology annotation, source, and a "View Details" link to the detail page.
2. **Given** an element detail page, **When** it loads, **Then** a "Used in Schemas" section shows which schemas include this element as a property, with EntityTag links to each schema.
3. **Given** a schema detail page, **When** it loads, **Then** each property links to the element detail page, and the "Extends" field links to the parent schema if applicable.
4. **Given** an element detail page, **When** transforms exist for that element, **Then** a "Transforms" section shows source→target mappings with function type badges and EntityTag links to both elements.
5. **Given** a valueset detail page, **When** it loads, **Then** each member value links to the value detail page, and the "Used By" section shows which elements reference this valueset in their response_options.

---

### User Story 5 — Link Health Monitoring (Priority: P2)

As a system administrator, I need the backend to continuously verify that all external URIs referenced in the registry (ontology term URIs, QUDT unit URIs, source repository URLs) are reachable — with a status page showing the results — so broken links can be identified and fixed proactively.

**Why this priority**: The registry references thousands of external URIs. Broken links (renamed ontology terms, deprecated QUDT entries) degrade trust. Continuous monitoring catches issues before users encounter them.

**Independent Test**: Open the status page → see a table of all external URI domains with health status (up/down), last check time, and count of broken links per domain.

**Acceptance Scenarios**:

1. **Given** the system is running, **When** the background link checker runs daily, **Then** it checks one representative URL per distinct domain and per ontology base-URI prefix (e.g., `http://purl.obolibrary.org/obo/NCIT_`, `http://qudt.org/vocab/unit/`) and records HTTP status and redirect targets.
2. **Given** the status page, **When** a user opens it, **Then** it shows a dashboard with: per-domain health (green/red), per-ontology base-URI redirect mapping, last check timestamp, and count of entities affected by any unreachable domain.
3. **Given** an unreachable domain or ontology base-URI, **When** the checker detects failure, **Then** a single curation flag is created for the domain/base-URI with flag type "broken_link", the HTTP status, and the count of affected entities.
4. **Given** an ontology base-URI that redirects to a different server than previously recorded, **When** the checker detects the redirect change, **Then** the status page highlights the redirect change and the affected ontology prefix.

---

### User Story 6 — Transform Validation Rules (Priority: P2)

As a curator reviewing transforms, I need the system to enforce that transforms between array-type and singleton-type elements are invalid — unless the array represents a mathematically transformable structure (e.g., affine matrix to quaternion) — so that semantically meaningless transforms are prevented.

**Why this priority**: The current transform pipeline can create nonsensical transforms like "array → string" for unrelated fields. Validation ensures only meaningful transforms are preserved.

**Independent Test**: Run the transform pipeline → verify that transforms from array-typed elements to singleton-typed elements are rejected unless the array element has an approved structural transform annotation.

**Acceptance Scenarios**:

1. **Given** an element with data_type "array" and no structural annotation, **When** the transform pipeline evaluates a potential transform to a singleton element, **Then** the transform is rejected and not created.
2. **Given** an element with data_type "array" and a structural annotation (e.g., "affine_matrix"), **When** the transform pipeline evaluates a transform to a compatible target (e.g., "quaternion"), **Then** the transform is created with function_type "structural".
3. **Given** the transforms browse page, **When** a curator views transforms, **Then** array→singleton transforms are only shown when they have a valid structural justification visible in the function type and description.
4. **Given** the transform detail page, **When** an array→singleton transform is displayed, **Then** the description explains the mathematical relationship (e.g., "4x4 affine matrix → quaternion + translation vector").

---

### User Story 7 — Global Search (Priority: P1)

As a researcher, I need a single search bar accessible from any page that queries all entity types (elements, schemas, values, valuesets, transforms) and returns ranked results with both lexical and semantic matches — so I can discover relevant entities without knowing which type or page to look in.

**Why this priority**: Discovery is the primary use case for the registry. Without a global search, users must browse each entity type separately and rely on per-column text filters, which don't support fuzzy or semantic matching.

**Independent Test**: Type "age" in the global search → results show elements named "age" (lexical match) from BIDS/NWB/DANDI, plus semantically related elements like "date_of_birth" and "gestational_age" — grouped by entity type with match scores.

**Acceptance Scenarios**:

1. **Given** the global search bar is visible on every page, **When** a user types a query, **Then** results appear grouped by entity type (elements, schemas, values, valuesets, transforms) with lexical matches ranked above semantic matches.
2. **Given** a search query, **When** results load, **Then** each result shows the entity name as an EntityTag chip, the match type (lexical/semantic), the match score for semantic results, and the entity's source badge.
3. **Given** a search query with no lexical matches, **When** semantic matches exist, **Then** the results section shows only semantic matches with a label indicating "Similar entities" and their similarity scores.
4. **Given** a search query, **When** the user clicks a result, **Then** they navigate to that entity's detail page.

---

### Edge Cases

- What happens when an EntityTag references an entity that has been deleted? The tag shows a "removed" indicator with the sha256 prefix.
- What happens when a property name in a schema doesn't match any element in the registry? The table row shows the raw name with an "unresolved" badge and a tooltip explaining the property may not have been ingested from this source.
- What happens when the link health checker encounters a rate-limited domain? The checker respects rate limits (exponential backoff), marks the domain as "rate-limited" rather than "broken", and retries in the next cycle.
- What happens when a curator opens the chat for an entity type that the LLM tools don't yet support (e.g., transforms)? The chat shows the entity in read-only mode with a message indicating editing tools are available for elements only; the entity context is still fully displayed.
- What happens when a search query matches thousands of entities? Results are capped at 50 per entity type with a "Show more" action that navigates to the filtered browse page for that type.
- What happens on mobile viewport? Tables switch to card layouts, split panels stack vertically with tab toggle, popovers are replaced by bottom sheets.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Property tables in schema and valueset detail pages MUST display entity rows using the same interactive EntityTag components (with type badge, source badge, unit, and hover popover) as the element browse grid.
- **FR-002**: The element browse grid MUST include a Unit column displaying the element's unit value alongside data type and source.
- **FR-003**: The "Suggest Change" button on every entity detail page MUST navigate to the curation chat with the entity fully pre-loaded, displaying all semantic fields, provenance, annotations, related entities, and pending flags in the right panel.
- **FR-004**: The curation chat right panel MUST support all entity types (element, schema, value, valueset, transform) with type-appropriate field layouts.
- **FR-005**: All entity references across the UI (in tables, detail pages, popovers, diffs) MUST be interactive EntityTag links with hover popovers.
- **FR-006**: Entity detail pages MUST show cross-references: "Used in Schemas" for elements, "Transforms" for elements, "Used By Elements" for valuesets, "Extends" parent link for schemas.
- **FR-007**: All external URIs (ontology terms, QUDT units, source repos) MUST be rendered as outbound links that open in a new tab.
- **FR-008**: The UI MUST use compact, dense layouts — reduced padding/margins on table rows (24px→16px row height), inline filters, multi-column property cards — to maximize information density.
- **FR-009**: Ontology annotations MUST display as compact chips showing the CURIE label, mapping relation icon, and score — with a tooltip showing the full URI and an external link icon.
- **FR-010**: The backend MUST run a daily background link health checker that verifies reachability at the domain level (one check per distinct domain referenced in the registry) and follows redirects at the ontology base-URI level (e.g., `http://purl.obolibrary.org/obo/NCIT_` may redirect to a different server than `http://purl.obolibrary.org/obo/PATO_`) — but NOT at the individual term-URI level.
- **FR-011**: A status page MUST display link health results per domain and per ontology base-URI, showing redirect targets, HTTP status, and last check timestamp.
- **FR-012**: When a domain or ontology base-URI is unreachable, the health checker MUST generate a single curation flag of type "broken_link" referencing the domain/base-URI and the count of affected entities — not one flag per entity.
- **FR-013**: The transform pipeline MUST reject transforms where the source element has data_type "array" and the target is a singleton type, unless the source element has a structural annotation indicating a mathematically valid transform.
- **FR-014**: Provenance entries MUST be displayed as compact source badges with expandable details, not verbose vertical lists.
- **FR-015**: Every entity detail page MUST include a prominent "Start Chat" or "Suggest Change" action that launches the curation flow for that entity.
- **FR-015a**: A "Chat about this" action MUST be available on EntityTag popovers, browse table row context menus, and search results — launching the curation chat with that entity pre-loaded.
- **FR-015b**: The chat MUST also be accessible as a standalone assistant (from the sidebar) without a pre-loaded entity, where the user can ask general registry questions, search for entities within the conversation, or reference entities by name/sha256 to load them into context.
- **FR-016**: All data grids and property tables MUST use case-insensitive lexical sorting on the name/label column by default, so "age" and "Age" sort adjacently rather than ASCII-order separated.
- **FR-017**: A global search bar MUST be accessible from every page (sidebar or header) and query all entity types simultaneously.
- **FR-018**: Search results MUST include both lexical matches (substring/prefix on name, label, description) and semantic matches (embedding similarity), ranked with lexical matches first and semantic matches below with similarity scores.
- **FR-019**: Search results MUST be grouped by entity type and each result MUST display as an EntityTag chip with source badge, match type indicator, and match score for semantic results.

### Key Entities

- **LinkHealthCheck**: A periodic check result for an external URI — domain, full URI, HTTP status, last checked timestamp, entities referencing it.
- **StructuralAnnotation**: A tag on an array-typed element indicating it represents a mathematically transformable structure (e.g., "affine_matrix", "rotation_matrix", "covariance_matrix") — used by transform validation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Schema and valueset property tables display interactive entity chips for 95%+ of properties (resolved from registry data).
- **SC-002**: At least 20 data rows are visible without scrolling on any browse page at 1080p resolution.
- **SC-003**: The curation chat right panel displays all semantic fields, provenance, and annotations for any entity type within 2 seconds of navigation.
- **SC-004**: 100% of ontology term URIs and QUDT unit URIs in the UI are clickable outbound links.
- **SC-005**: The link health checker runs daily at the domain and ontology base-URI level and reports results on the status page within 1 hour of completion.
- **SC-006**: Zero array→singleton transforms exist in the registry without a valid structural annotation justification.
- **SC-007**: Every entity detail page has a working "Suggest Change" action that opens the curation chat with full entity context pre-loaded.
- **SC-008**: A search query returns both lexical and semantic results across all entity types within 1 second, with results visible from any page.

## Clarifications

### Session 2026-03-29

- Q: Should search be per-page or global, and what match types? → A: Global unified search bar querying all entity types with both lexical and semantic matches, ranked with lexical first.
- Q: Should curation chat only be accessible from detail pages? → A: Chat launchable from any entity reference (popovers, browse rows, search results) plus a standalone assistant mode from the sidebar without a pre-loaded entity.
- Q: Should link health checks verify every individual term URI? → A: Domain-level checks daily with ontology base-URI redirect tracking (fragments may resolve to different servers), not individual term-level checks.

## Scope Boundaries

### In Scope

- Rich property/member tables with EntityTag chips, type badges, unit display, hover popovers
- Unit column added to element browse grid
- Chat-first curation flow with full entity context in right panel
- Compact, dense UI layouts with reduced whitespace
- Cross-reference sections on detail pages (Used in Schemas, Transforms, Used By)
- External URI verification as clickable outbound links
- Background link health monitoring with status page
- Curation flag generation for broken links
- Transform validation rules for array→singleton type mismatches
- Global unified search bar with lexical + semantic matching across all entity types
- Mobile-responsive adaptations (card layouts, bottom sheets)

### Out of Scope

- Inline field editing on detail pages (editing is via chat-mediated AI proposals only)
- Custom theme/branding customization
- User-configurable dashboard layouts
- Real-time collaborative editing (multi-user simultaneous chat)
- Automated fix/redirect for broken links (only detection and flagging)

## Assumptions

- The existing component library (EntityTag, EntityDataGrid, SplitPanel, EntityDiff) provides a solid foundation that needs enhancement, not replacement
- The dandi-medit split-panel pattern is already implemented and working
- The backend GraphQL API already exposes all fields needed for the curation chat right panel
- The link health checker performs domain-level and ontology base-URI-level checks only (not individual term URIs), using HEAD requests with redirect following
- Structural annotations for array elements will be curated manually (not auto-detected)
- The current authentication system (Keycloak/Globus OIDC) handles curator identity for all curation flows

## Dependencies

- Feature 031 (CivicDB UI) — provides base entity display components and layout
- Feature 034 (Curation Interface) — provides chat, diff, and split-panel components
- Feature 032 (Authentication) — provides curator identity for curation flows
- Feature 029 (Backend service) — provides GraphQL API for all entity operations
