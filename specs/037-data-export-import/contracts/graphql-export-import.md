# GraphQL Contract: Export, Import & Downloads

## Queries

```graphql
type Query {
  releases(releaseType: String): [Release!]!
  release(version: String!): Release
}

type Release {
  id: ID!
  version: String!
  releaseType: String!  # "nightly" or "versioned"
  filePath: String!
  fileSize: Int!
  entityCounts: JSON!
  downloadCount: Int!
  createdAt: String!
}
```

## Mutations

```graphql
type Mutation {
  exportRegistry(version: String): ExportResult!
  importRegistryFromUpload(clear: Boolean = false): ImportResult!
  tagRelease(version: String!): Release!
}

type ExportResult {
  version: String!
  filePath: String!
  fileSize: Int!
  entityCounts: JSON!
  manifest: JSON!
}
```

## REST Endpoints (file serving)

```
GET /api/downloads/{version}.tar.gz  → download compressed archive
GET /api/downloads/releases.json     → list of available releases
POST /api/admin/import               → upload + import (multipart form)
```

## CLI Commands

```bash
# Export full registry
undata-library export-full --output /tmp/export --version v2026.03.31

# Import from export directory
undata-library import-full --path /tmp/export --clear

# Round-trip test
undata-library test-roundtrip --backend-url http://localhost:8002
```
