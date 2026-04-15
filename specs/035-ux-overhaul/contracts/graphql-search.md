# GraphQL Contract: Global Search

## Query

```graphql
type Query {
  globalSearch(
    query: String!
    entityTypes: [EntityType!]  # optional filter: [ELEMENT, SCHEMA, VALUE, VALUESET, TRANSFORM]
    limit: Int = 20
  ): SearchResultConnection!
}

type SearchResultConnection {
  results: [SearchResult!]!
  totalCount: Int!
  query: String!
}

type SearchResult {
  entityType: EntityType!
  sha256: String!
  name: String!
  matchType: SearchMatchType!  # LEXICAL or SEMANTIC
  score: Float!                # 1.0 for exact lexical, 0.0-1.0 for semantic
  snippet: String              # matching text excerpt
  source: String               # provenance source
  dataType: String             # for elements
  unit: String                 # for elements
  label: String                # for values
}

enum SearchMatchType {
  LEXICAL
  SEMANTIC
}
```

## Behavior

1. Lexical search: full-text search across name, label, description fields using tsvector `@@` operator
2. Semantic search: encode query with all-MiniLM-L6-v2, find nearest embeddings via pgvector `<->` operator
3. Results: lexical matches first (sorted by ts_rank), then semantic matches (sorted by cosine similarity)
4. Deduplication: if an entity appears in both lexical and semantic results, keep the lexical match only
5. Entity type filter: when provided, only search specified types

## Example

```graphql
{
  globalSearch(query: "age of participant", limit: 10) {
    totalCount
    results {
      entityType
      sha256
      name
      matchType
      score
      source
    }
  }
}
```
