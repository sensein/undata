// Content-addressed element model (017-backend-library-alignment)

export interface SemanticIdentity {
  ontology_term: string | null;
  data_type: string;
  unit: string | null;
  constraints: Record<string, unknown> | null;
}

export interface ProvenanceEntry {
  source: string;
  class: string;
  name: string;
  description: string | null;
  required: boolean | null;
  multivalued: boolean | null;
}

export interface ElementV2 {
  uri: string;
  semantic: SemanticIdentity;
  provenance: ProvenanceEntry[];
}

export interface ValueConceptResponse {
  uri: string;
  semantic: {
    ontology_term: string | null;
    value_type: string;
    label: string;
  };
  provenance: Array<{ source: string; raw_value: string }>;
}

export interface ElementMappingResponse {
  id: number;
  source_element_uri: string;
  target_element_uri: string;
  function_type: string;
  expression: string | null;
  expression_type: string | null;
  sssom_predicate: string | null;
  confidence: number | null;
}

// Legacy API Response Types (retained for backward compatibility)

export interface DataElementSummary {
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

export interface DataElementDetail extends DataElementSummary {
  allowed_values: string[] | null;
  constraints: Record<string, unknown>;
  source: { id: string; name: string; version_tag: string };
  alias_groups: AliasGroupSummary[];
  mappings_as_input: MappingRef[];
  mappings_as_output: MappingRef[];
  created_at: string;
  deleted_at: string | null;
}

export interface AliasGroupSummary {
  id: string;
  name: string;
  member_count: number;
  sssom_predicate: string;
}

export interface AliasGroupDetail {
  id: string;
  name: string;
  sssom_predicate: string;
  confidence: number | null;
  detection_method: string;
  members: DataElementSummary[];
}

export interface MappingRef {
  id: string;
  function_type: string;
  output_name?: string;
  input_names?: string[];
}

export interface PaginatedList<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

// Client-Side UI State

export interface FilterState {
  source_id: string | null;
  data_type: string | null;
  has_aliases: boolean | null;
  has_mappings: boolean | null;
}

export interface SearchState {
  query: string;
  debouncedQuery: string;
  filters: FilterState;
  offset: number;
  limit: number;
}

export interface GraphNode {
  id: string;
  label: string;
  data_type: string;
  source_name: string;
  is_alias: boolean;
  is_root: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  function_type: string;
  label: string;
}

export interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  max_depth: number;
  layout: "dagre" | "breadthfirst";
}

export interface ComparisonState {
  element_a: DataElementDetail | null;
  element_b: DataElementDetail | null;
  diffs: FieldDiff[];
}

export interface FieldDiff {
  field: string;
  value_a: unknown;
  value_b: unknown;
  is_match: boolean;
}

export interface CreateElementPayload {
  name: string;
  data_type: string;
  description: string;
  required: boolean;
  multivalued: boolean;
  source_id: string;
  allowed_values?: string[];
  constraints?: Record<string, unknown>;
}

export interface SearchParams {
  q?: string;
  source_id?: string;
  data_type?: string;
  has_aliases?: boolean;
  has_mappings?: boolean;
  limit?: number;
  offset?: number;
}

// Migration API types

export interface PathwaySummary {
  id: string;
  source_schema: { id: string; name: string };
  target_schema: { id: string; name: string };
  step_count: number;
  created_at: string;
}

export interface PathwayStep {
  position: number;
  mapping_id: string;
  function_type: string;
  expression: string | null;
  expression_type: string | null;
  input_element: string;
  output_element: string;
}

export interface PathwayDetail extends PathwaySummary {
  steps: PathwayStep[];
}

export interface MigrationJob {
  id: string;
  pathway_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface SchemaDiffResult {
  schema_a: { id: string; name: string };
  schema_b: { id: string; name: string };
  added: string[];
  removed: string[];
  modified: Array<{
    field: string;
    old_type: string;
    new_type: string;
  }>;
}
