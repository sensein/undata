# Quickstart: Unified Embedding & Storage

## Test Scenarios

### 1. Parquet-Only Pipeline

```bash
# Run pipeline — verify zero YAML files
uv run undata-library pipeline --source bids -o /tmp/test-040
find /tmp/test-040 -name "*.yaml" -not -path "*/runs/*" | wc -l
# Expected: 0 (only runs/ has YAML summaries)

# Verify Parquet files exist
find /tmp/test-040 -name "*.parquet" | head -10
```

### 2. Embeddings at Commit

```bash
# Check that committed entities have embeddings
uv run undata-library inspect /tmp/test-040 --sha256 <any-sha> | grep embedding
# Expected: "embedding": [0.123, -0.456, ...]
```

### 3. Backend Import Speed

```bash
docker compose up -d
# Time the import
time curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { importRegistry(registryPath: \"/app/full-registry\") { elements schemas } }"}'
# Expected: < 30 seconds for 7K entities
```

### 4. Update Triggers Recomputation

```bash
# Update an element, verify embedding changes
OLD=$(curl -s localhost:8002/graphql -d '{"query":"{ element(sha256:\"abc\") { sha256 } }"}')
# Mutation to update description...
NEW=$(curl -s localhost:8002/graphql -d '{"query":"{ element(sha256:\"abc\") { sha256 } }"}')
# Embeddings should differ
```
