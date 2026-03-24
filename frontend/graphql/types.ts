// TypeScript types matching the GraphQL schema

export interface OntologyAnnotation {
  termUri: string;
  termLabel: string;
  ontology: string;
  mappingRelation: string;
  score: number;
  primary: boolean;
}

export interface ProvenanceEntry {
  source: string;
  className: string;
  name: string;
  description?: string;
}

export interface ElementNode {
  sha256?: string;
  dataType?: string;
  unit?: string;
  valueDomain?: string;
  description?: string;
  ontologyAnnotations: OntologyAnnotation[];
  provenance: ProvenanceEntry[];
  fileName: string;
}

export interface ElementEdge {
  node: ElementNode;
  cursor: string;
}

export interface PageInfo {
  hasNextPage: boolean;
  hasPreviousPage: boolean;
  startCursor?: string;
  endCursor?: string;
}

export interface ElementConnection {
  edges: ElementEdge[];
  pageInfo: PageInfo;
  totalCount: number;
}

export interface ValueNode {
  sha256?: string;
  label: string;
  valueType?: string;
  ontologyId?: string;
  ontologyAnnotations: OntologyAnnotation[];
  provenance: ProvenanceEntry[];
  fileName: string;
}

export interface RunSummaryNode {
  runId: string;
  source: string;
  startedAt: string;
  completedAt?: string;
  entityCounts: Record<string, Record<string, number> | number>;
  enrichmentRate?: Record<string, number>;
  curationFlags?: Record<string, number>;
  timing?: Record<string, number>;
}
