# GraphQL API Contract

## Core Queries

```graphql
type Query {
  # Entity lookups
  element(sha256: String!): Element
  schema(sha256: String!): Schema
  value(sha256: String!): Value
  valueset(sha256: String!): ValueSet
  transform(id: ID!): Transform

  # Browse with faceted filtering + cursor pagination
  browseElements(
    source: String
    dataType: DataType
    ontology: String
    curationStatus: CurationStatus
    hasAnnotations: Boolean
    searchText: String
    first: Int = 20
    after: String
  ): ElementConnection!

  browseSchemas(source: String, searchText: String, first: Int, after: String): SchemaConnection!
  browseValues(source: String, searchText: String, first: Int, after: String): ValueConnection!
  browseTransforms(functionType: String, first: Int, after: String): TransformConnection!

  # Curation
  curationQueue(
    flagType: FlagType
    status: FlagStatus = PENDING
    first: Int = 20
    after: String
  ): CurationFlagConnection!

  contributions(status: ContributionStatus, first: Int, after: String): ContributionConnection!

  # Pipeline
  runSummaries(source: String, first: Int, after: String): RunSummaryConnection!
  latestRun(source: String): RunSummary
}
```

## Core Mutations

```graphql
type Mutation {
  # Curation decisions
  resolveFlag(input: ResolveFlagInput!): CurationFlag!
  batchResolveFlags(input: BatchResolveFlagInput!): [CurationFlag!]!

  # Contributions
  submitContribution(input: SubmitContributionInput!): Contribution!
  reviewContribution(input: ReviewContributionInput!): Contribution!

  # Pipeline triggers
  triggerPipelineRun(source: String!): RunSummary!
  importRegistry(registryPath: String!): ImportResult!
}
```

## Key Types

```graphql
type Element {
  sha256: String!
  semantic: SemanticIdentity!
  provenance: [ProvenanceEntry!]!
  ontologyAnnotations: [OntologyAnnotation!]
  relatedTransforms: TransformConnection!
  schemas: [Schema!]!
  curationFlags: [CurationFlag!]!
  contributions: [Contribution!]!
}

type CurationFlag {
  id: ID!
  entityType: EntityType!
  entityRef: String!
  flagType: FlagType!
  context: FlagContext!
  llmVerification: LLMVerification
  status: FlagStatus!
  resolvedBy: User
  resolvedAt: DateTime
  resolutionNote: String
  createdAt: DateTime!
}

type Contribution {
  id: ID!
  entityType: EntityType!
  entity: Entity! # Union type
  contributor: User!
  contributionType: ContributionType!
  content: JSON!
  status: ContributionStatus!
  reviewedBy: User
  createdAt: DateTime!
}
```

## Enums

```graphql
enum FlagType { LOW_CONFIDENCE, AMBIGUOUS_MATCH, MULTIPLE_CANDIDATES, UNKNOWN_TRANSFORM, NEEDS_REVIEW }
enum FlagStatus { PENDING, APPROVED, REJECTED, DEFERRED }
enum ContributionType { SUGGEST_ANNOTATION, COMMENT, FLAG_ISSUE, SUGGEST_EDIT }
enum ContributionStatus { PENDING, APPROVED, REJECTED }
enum CurationStatus { UNFLAGGED, PENDING, CURATED }
enum DataType { STRING, INTEGER, FLOAT, BOOLEAN, ARRAY, OBJECT }
enum EntityType { ELEMENT, SCHEMA, VALUE, VALUESET, TRANSFORM }
```
