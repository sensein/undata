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

1. **Given** the system is running, **When** the background link checker runs, **Then** it samples external URIs from the registry (ontology term URIs, QUDT URIs, source repo URLs) and records their HTTP status.
2. **Given** the status page, **When** a user opens it, **Then** it shows a dashboard with: per-domain health (green/red), total URIs checked, last check timestamp, and a list of any broken/unreachable URIs with the entities that reference them.
3. **Given** a broken external link is detected, **When** the checker finds a non-200 response, **Then** a curation flag is created for each entity referencing the broken URI, with flag type "broken_link" and context containing the URI and HTTP status.
4. **Given** the status page, **When** a domain shows degraded health, **Then** clicking it expands to show all specific URIs that failed, with links to the affected entities.

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

### Edge Cases

- What happens when an EntityTag references an entity that has been deleted? The tag shows a "removed" indicator with the sha256 prefix.
- What happens when a property name in a schema doesn't match any element in the registry? The table row shows the raw name with an "unresolved" badge and a tooltip explaining the property may not have been ingested from this source.
- What happens when the link health checker encounters a rate-limited domain? The checker respects rate limits (exponential backoff), marks the domain as "rate-limited" rather than "broken", and retries in the next cycle.
- What happens when a curator opens the chat for an entity type that the LLM tools don't yet support (e.g., transforms)? The chat shows the entity in read-only mode with a message indicating editing tools are available for elements only; the entity context is still fully displayed.
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
- **FR-010**: The backend MUST run a background link health checker that periodically samples external URIs from the registry and records their reachability status.
- **FR-011**: A status page MUST display link health results per domain, with drill-down to specific broken URIs and the entities that reference them.
- **FR-012**: Broken external links detected by the health checker MUST generate curation flags of type "broken_link" for affected entities.
- **FR-013**: The transform pipeline MUST reject transforms where the source element has data_type "array" and the target is a singleton type, unless the source element has a structural annotation indicating a mathematically valid transform.
- **FR-014**: Provenance entries MUST be displayed as compact source badges with expandable details, not verbose vertical lists.
- **FR-015**: Every entity detail page MUST include a prominent "Start Chat" or "Suggest Change" action that launches the curation flow for that entity.
- **FR-016**: All data grids and property tables MUST use case-insensitive lexical sorting on the name/label column by default, so "age" and "Age" sort adjacently rather than ASCII-order separated.

### Key Entities

- **LinkHealthCheck**: A periodic check result for an external URI — domain, full URI, HTTP status, last checked timestamp, entities referencing it.
- **StructuralAnnotation**: A tag on an array-typed element indicating it represents a mathematically transformable structure (e.g., "affine_matrix", "rotation_matrix", "covariance_matrix") — used by transform validation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Schema and valueset property tables display interactive entity chips for 95%+ of properties (resolved from registry data).
- **SC-002**: At least 20 data rows are visible without scrolling on any browse page at 1080p resolution.
- **SC-003**: The curation chat right panel displays all semantic fields, provenance, and annotations for any entity type within 2 seconds of navigation.
- **SC-004**: 100% of ontology term URIs and QUDT unit URIs in the UI are clickable outbound links.
- **SC-005**: The link health checker runs at least once per day and reports results on the status page within 1 hour of completion.
- **SC-006**: Zero array→singleton transforms exist in the registry without a valid structural annotation justification.
- **SC-007**: Every entity detail page has a working "Suggest Change" action that opens the curation chat with full entity context pre-loaded.

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
- The link health checker will use HEAD requests with appropriate rate limiting and respect robots.txt
- Structural annotations for array elements will be curated manually (not auto-detected)
- The current authentication system (Keycloak/Globus OIDC) handles curator identity for all curation flows

## Dependencies

- Feature 031 (CivicDB UI) — provides base entity display components and layout
- Feature 034 (Curation Interface) — provides chat, diff, and split-panel components
- Feature 032 (Authentication) — provides curator identity for curation flows
- Feature 029 (Backend service) — provides GraphQL API for all entity operations
