# GraphQL Contract: System Hardening

## New Queries

```graphql
type Query {
  # Ontology admin from pyoxigraph store (not DB)
  ontologyStoreInfo: [OntologyStoreEntry!]!

  # Audit log
  auditLog(entityType: String, entityRef: String, agent: String, first: Int = 50): [AuditLogEntry!]!
}

type OntologyStoreEntry {
  name: String!
  termCount: Int!
  loadedAt: String
  checksum: String
  format: String
}

type AuditLogEntry {
  id: ID!
  activity: String!
  agent: String!
  agentType: String!
  entityType: String!
  entityRef: String!
  generatedEntityRef: String
  details: JSON
  createdAt: String!
}
```

## New Mutations

```graphql
type Mutation {
  # Refresh a specific ontology (re-download and reload)
  refreshOntologySource(name: String!): OntologyStoreEntry!

  # Trigger version check on all registered sources
  checkDependencyVersions: [VersionCheckResult!]!
}

type VersionCheckResult {
  name: String!
  dependencyType: String!  # "ontology" or "source"
  hasUpdate: Boolean!
  oldChecksum: String
  newChecksum: String
}
```

## Modified Queries

```graphql
# browseElements now supports sortBy/sortOrder on ALL columns
type Query {
  browseElements(
    source: String
    dataType: DataType
    hasAnnotations: Boolean
    searchText: String
    sortBy: String      # "name", "dataType", "unit", "description", "source"
    sortOrder: String   # "asc" or "desc"
    first: Int = 20
    after: String
  ): ElementConnection!

  # Search with mode toggle
  search(
    query: String!
    mode: SearchMode = BOTH  # LEXICAL, SEMANTIC, or BOTH
    first: Int = 50
  ): [SearchResultType!]!
}

enum SearchMode {
  LEXICAL
  SEMANTIC
  BOTH
}
```
