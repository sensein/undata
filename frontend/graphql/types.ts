// TypeScript types matching the backend GraphQL schema (feature 029)

export interface OntologyAnnotation {
  termUri: string;
  termLabel: string;
  ontology: string;
  mappingRelation: string;
  matchLevel?: string;
  score: number;
  model?: string;
  primary: boolean;
}

export interface ProvenanceEntry {
  source: string;
  className: string;
  name: string;
  description?: string;
}

// --- Core Entity Types ---

export interface ElementNode {
  sha256: string;
  fileName?: string;
  dataType?: string;
  unit?: string;
  unitUri?: string;
  pattern?: string;
  valueDomain?: string;
  description?: string;
  minValue?: number;
  maxValue?: number;
  typeRef?: string;
  semantic?: Record<string, unknown>;
  provenance: ProvenanceEntry[];
  ontologyAnnotations: OntologyAnnotation[];
}

export interface SchemaNode {
  sha256: string;
  fileName?: string;
  subclassOf?: string;
  isMixin?: boolean;
  properties: string[];
  description?: string;
  provenance: ProvenanceEntry[];
  ontologyAnnotations: OntologyAnnotation[];
}

export interface ValueNode {
  sha256: string;
  fileName?: string;
  label?: string;
  valueType?: string;
  ontologyId?: string;
  description?: string;
  provenance: ProvenanceEntry[];
  ontologyAnnotations: OntologyAnnotation[];
}

export interface ValueSetNode {
  sha256: string;
  fileName?: string;
  name?: string;
  members: string[];
  description?: string;
  provenance: ProvenanceEntry[];
  ontologyAnnotations: OntologyAnnotation[];
}

export interface CurationFlagNode {
  id: string;
  entityType: string;
  entityRef: string;
  flagType: string;
  context: Record<string, unknown>;
  status: string;
  createdAt: string;
  resolvedAt?: string;
  resolvedBy?: string;
  resolutionNote?: string;
}

export interface TransformNode {
  sha256: string;
  fileName?: string;
  sourceElement: string;
  targetElement: string;
  functionType?: string;
  inputType?: string;
  outputType?: string;
  expression?: string;
  expressionType?: string;
  confidence?: number;
  description?: string;
  provenance: ProvenanceEntry[];
}

export interface RunSummaryNode {
  runId: string;
  source: string;
  startedAt?: string;
  completedAt?: string;
  entityCounts: Record<string, unknown>;
  enrichmentRate?: Record<string, unknown>;
  curationFlags?: Record<string, unknown>;
  timing?: Record<string, unknown>;
}

// --- Pagination ---

export interface PageInfo {
  hasNextPage: boolean;
  endCursor?: string;
}

export interface Edge<T> {
  node: T;
  cursor: string;
}

export interface Connection<T> {
  edges: Edge<T>[];
  pageInfo: PageInfo;
  totalCount: number;
}

// Convenience aliases
export type ElementConnection = Connection<ElementNode>;
export type SchemaConnection = Connection<SchemaNode>;
export type ValueConnection = Connection<ValueNode>;
export type TransformConnection = Connection<TransformNode>;
export type CurationFlagConnection = Connection<CurationFlagNode>;
export type RunSummaryConnection = Connection<RunSummaryNode>;
