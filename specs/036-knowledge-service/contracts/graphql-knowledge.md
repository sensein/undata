# GraphQL Contract: Knowledge Service

## Ontology Management

```graphql
type Query {
  ontologySources(active: Boolean): [OntologySource!]!
  ontologySource(name: String!): OntologySource
}

type Mutation {
  refreshOntology(name: String!): OntologySource!
  addOntologySource(input: AddOntologySourceInput!): OntologySource!
  toggleOntologyActive(name: String!, active: Boolean!): OntologySource!
}

type OntologySource {
  id: ID!
  name: String!
  displayName: String!
  url: String!
  format: String!
  termCount: Int!
  active: Boolean!
  lastRefreshedAt: String
  createdAt: String!
}

input AddOntologySourceInput {
  name: String!
  displayName: String!
  url: String!
  format: String!  # "owl", "obo", "ttl", "json-ld"
}
```

## Ingestion Queue

```graphql
type Query {
  ingestionQueue(status: String, first: Int = 20): [IngestionJob!]!
  ingestionJob(id: ID!): IngestionJob
}

type Mutation {
  approveIngestion(id: ID!): IngestionJob!
  rejectIngestion(id: ID!, reason: String): IngestionJob!
  queueIngestion(input: QueueIngestionInput!): IngestionJob!
}

type IngestionJob {
  id: ID!
  repositoryUrl: String!
  adapterType: String!
  status: String!
  autoApproved: Boolean!
  entityCounts: JSON
  errorMessage: String
  approvedBy: String
  startedAt: String
  completedAt: String
  createdAt: String!
}

input QueueIngestionInput {
  repositoryUrl: String!
  adapterType: String  # optional — auto-detected if omitted
}
```

## LLM Enrichment

```graphql
type Query {
  enrichmentProposals(
    entityType: String
    entityRef: String
    status: String
    first: Int = 50
  ): [LLMEnrichmentProposal!]!
}

type Mutation {
  requestEnrichment(entityType: String!, entityRef: String!): LLMEnrichmentProposal!
  batchEnrichment(source: String, unannotatedOnly: Boolean = true): BatchEnrichmentResult!
  reviewProposal(id: ID!, decision: String!, reason: String): LLMEnrichmentProposal!
}

type LLMEnrichmentProposal {
  id: ID!
  entityType: String!
  entityRef: String!
  proposalType: String!
  proposedValue: JSON!
  reasoning: String!
  confidence: Float!
  status: String!
  reviewedBy: String
  reviewedAt: String
  createdAt: String!
}

type BatchEnrichmentResult {
  jobId: String!
  totalEntities: Int!
  status: String!
}
```

## CLI Commands

```bash
# Ontology management
undata-library ontology add --name homba --url https://purl.brain-bican.org/ontology/homba.owl --format owl
undata-library ontology add --name radlex --url /path/to/radlex.owl --format owl
undata-library ontology refresh --name homba
undata-library ontology list

# OpenNeuro ingestion via datalad
undata-library ingest --source openneuro --path ds000228
undata-library ingest --source reproschema --path /path/to/reproschema-library

# Discovery
undata-library discovery-scan --endpoint openneuro
undata-library discovery-scan --endpoint dandi
```
