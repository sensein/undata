# Research: CivicDB UI Redesign

## R1: Data Grid Component

**Decision**: Use TanStack Table (already in dependencies) for sortable, filterable data grids. It provides headless table logic (sorting, filtering, pagination) while we control rendering with Tailwind.

**Rationale**: TanStack Table is already installed (`@tanstack/react-table` in package.json). Adding AG Grid or similar would be a new heavy dependency. TanStack + Tailwind gives us CivicDB-style grids without framework lock-in.

## R2: Connected Navigation — Resolving Property References

**Decision**: Schema properties are stored as string identifiers (e.g., `age_a1b2c3d4e5f6`). To link to element detail pages, we need the element's sha256. The backend already supports lookup by file_name, so we can use `element(sha256: "a1b2c3d4e5f6")` with the hash portion of the identifier.

**Rationale**: The current seed data uses `{name}_{hash_prefix}` as property identifiers. Extracting the hash prefix and querying by sha256 prefix (which the backend supports via `startsWith`) gives us the link without new API endpoints.

## R3: Source Color Coding

**Decision**: Assign fixed Tailwind color classes per source:
- BIDS: blue-100/blue-800
- DANDI: green-100/green-800
- NWB: purple-100/purple-800
- openMINDS: orange-100/orange-800
- AIND: teal-100/teal-800
- Unknown: gray-100/gray-800

Centralize in a `SOURCE_COLORS` map used by all pages.

## R4: Activity Feed — Backend Support

**Finding**: The backend doesn't currently have an activity/audit log endpoint. Curation flag changes and contributions create records, but there's no unified activity stream.

**Decision**: For this feature, build the activity feed UI and source it from existing data: recent curation flags (by created_at) + recent contributions (by created_at), merged and sorted. A dedicated activity log table is deferred to a future feature.

## R5: Responsive Layout Strategy

**Decision**: Use Tailwind's responsive breakpoints (`sm:`, `md:`, `lg:`). Tables become stacked cards on mobile. Navigation collapses to a hamburger menu via a simple toggle component.
