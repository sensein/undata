# Data Model: Schema Explorer Frontend
**Feature**: 003-schema-explorer | **Date**: 2026-03-07

The frontend has no database. Its "data model" is the set of TypeScript types that
mirror the backend API responses plus client-side UI state structures.

---

## API Response Types (mirrors 002-schema-backend)

```typescript
// From GET /elements
interface DataElementSummary {
  id: string;
  name: string;
  data_type: string;
  description: string;
  required: boolean;
  multivalued: boolean;
  source: { id: string; name: string };
  alias_count: number;
  mapping_count: number;
  version_num: number;
}

// From GET /elements/{id}
interface DataElementDetail extends DataElementSummary {
  allowed_values: string[] | null;
  constraints: Record<string, unknown>;
  source: { id: string; name: string; version_tag: string };
  alias_groups: AliasGroupSummary[];
  mappings_as_input: MappingRef[];
  mappings_as_output: MappingRef[];
  created_at: string;
  deleted_at: string | null;
}

interface AliasGroupSummary {
  id: string;
  name: string;
  member_count: number;
  sssom_predicate: string;
}

interface MappingRef {
  id: string;
  function_type: string;
  output_name?: string;   // when used as input
  input_names?: string[]; // when used as output
}

// From GET /aliases/{id}
interface AliasGroupDetail {
  id: string;
  name: string;
  sssom_predicate: string;
  confidence: number | null;
  detection_method: string;
  members: DataElementSummary[];
}

// Paginated wrapper
interface PaginatedList<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}
```

---

## Client-Side UI State

### SearchState (Svelte store)

```typescript
interface SearchState {
  query: string;           // current input value
  debouncedQuery: string;  // debounced value sent to API
  filters: {
    source_id: string | null;
    data_type: string | null;
    has_aliases: boolean | null;
    has_mappings: boolean | null;
  };
  offset: number;
  limit: number;
}
```

### GraphState (per-element, client-computed)

```typescript
interface GraphNode {
  id: string;            // element ID
  label: string;         // element name
  data_type: string;
  source_name: string;
  is_alias: boolean;
  is_root: boolean;      // true for the focused element
}

interface GraphEdge {
  id: string;            // mapping ID
  source: string;        // input element ID
  target: string;        // output element ID
  function_type: string; // "identity" | "custom"
  label: string;
}

interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  max_depth: number;     // user-controlled (1–5, default 2)
  layout: 'dagre' | 'breadthfirst';
}
```

### ComparisonState

```typescript
interface ComparisonState {
  element_a: DataElementDetail | null;
  element_b: DataElementDetail | null;
  diffs: FieldDiff[];
}

interface FieldDiff {
  field: string;
  value_a: unknown;
  value_b: unknown;
  is_match: boolean;
}
```

---

## SvelteKit Route Structure

```
src/routes/
├── +page.svelte              # / — search home
├── elements/
│   ├── +page.svelte          # /elements — search results
│   └── [id]/
│       └── +page.svelte      # /elements/{id} — element detail
├── aliases/
│   └── [id]/
│       └── +page.svelte      # /aliases/{id} — alias group detail
├── compare/
│   └── +page.svelte          # /compare?a={id}&b={id} — comparison view
├── add/
│   └── +page.svelte          # /add — add element form
└── api/                      # SvelteKit API routes (thin proxies)
    └── [...path]/
        └── +server.ts        # Proxy to backend (adds auth header server-side)
```

All routes encode their full state in URL query parameters to enable shareable links.
