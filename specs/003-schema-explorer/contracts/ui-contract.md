# UI Contract: Schema Explorer Frontend
**Feature**: 003-schema-explorer | **Date**: 2026-03-07

Defines the URL schema, backend API dependencies, and component interaction contracts.

---

## URL Schema (Shareable Routes)

| Route | State encoded in URL | Description |
|-------|---------------------|-------------|
| `/` | — | Search home |
| `/elements?q=age&source=BIDS&type=number&offset=0` | query, filters, pagination | Search results |
| `/elements/{uuid}` | element ID | Element detail |
| `/elements/{uuid}?depth=3` | depth control | Detail with expanded graph |
| `/aliases/{uuid}` | alias group ID | Alias group detail |
| `/compare?a={uuid}&b={uuid}` | two element IDs | Side-by-side comparison |
| `/add` | — | Add element form |

---

## Backend API Dependencies

| UI feature | Backend endpoint |
|------------|-----------------|
| Search | `GET /api/v1/elements?q=...` |
| Filter by source | `GET /api/v1/elements?source_id=...` |
| Element detail | `GET /api/v1/elements/{id}` |
| Relationship graph | `GET /api/v1/mappings?source_element_id={id}` + `?target_element_id={id}` |
| Alias group detail | `GET /api/v1/aliases/{id}` |
| Comparison | Two calls to `GET /api/v1/elements/{id}` |
| Add element | `POST /api/v1/elements` |
| Duplicate check | `GET /api/v1/elements?q={name}&limit=5` |
| Register alias from comparison | `POST /api/v1/aliases` |
| Schema sources list (filter dropdown) | `GET /api/v1/sources` |

---

## Component Interaction Contracts

### SearchBar → SearchResults

- SearchBar emits `search` event with `{ query: string, filters: FilterState }`.
- Debounce: 300ms from last keystroke.
- SearchResults subscribes to the shared `SearchState` store.
- On empty query: show recent elements or "type to search" placeholder.

### SearchResults → ElementDetail

- Clicking a result navigates to `/elements/{id}` via `goto()` (SvelteKit).
- Navigating back restores scroll position and search state from URL.

### ElementDetail → RelationshipGraph

- ElementDetail passes `{ element_id, depth }` props to RelationshipGraph component.
- RelationshipGraph fetches its own data (mappings_as_input, mappings_as_output)
  using element_id; does not receive pre-fetched graph data from parent.
- RelationshipGraph emits `node-click` event → parent navigates to `/elements/{id}`.

### RelationshipGraph depth control

- Depth slider (1–5, default 2) is rendered inside RelationshipGraph.
- Changing depth re-fetches one hop further from the API.
- URL param `?depth=N` reflects the current depth for shareability.

### ComparisonView → Register Alias

- ComparisonView shows a "Register as Alias" button.
- Button is enabled only when both elements have the same `data_type`.
- On click: POST `/api/v1/aliases` with both element IDs.
- On success: refresh both element detail sections.

### AddElement Form validation rules (client-side)

| Field | Validation |
|-------|-----------|
| `name` | Required; 1–200 chars; pattern `[a-zA-Z_][a-zA-Z0-9_ ]*` |
| `data_type` | Required; one of {string, number, boolean, object, array} |
| `description` | Required; 10–2000 chars |
| `cardinality` | Required; radio: required/optional × single/multi |
| `allowed_values` | Optional; non-empty list if provided; each value ≤ 100 chars |
| `source_provenance` | Optional; free text |

Duplicate check fires on `name` field blur: debounced 500ms, `GET /elements?q={name}&limit=5`.
If results contain exact match: show warning banner with links to existing elements.

---

## Accessibility Requirements

- All interactive elements must have visible focus indicators.
- Search results list uses `role="list"` / `role="listitem"`.
- Graph canvas provides a table fallback listing connected elements for keyboard users.
- Form fields have associated `<label>` elements with explicit `for` attributes.
- Color is not used as the sole indicator of diff status in comparison view.
