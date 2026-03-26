# Quickstart: 029 Backend Service Validation

## QS-001: Docker stack starts cleanly
```bash
docker compose up -d
# Wait for health check
curl -f http://localhost:8002/health
# Expected: {"status": "ok", "database": "connected"}
```

## QS-002: GraphQL playground accessible
```bash
# Open browser to http://localhost:8002/graphql
# Expected: Strawberry GraphiQL interface with schema explorer
```

## QS-003: DatabaseBackend passes conformance tests
```bash
cd backend && uv run pytest tests/test_database_backend.py -v
# Expected: 52 conformance tests pass (same as FileBackend + MockBackend)
```

## QS-004: Registry import loads all entities
```bash
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { importRegistry(registryPath: \"/data/seed\") }"}'
# Then query counts:
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ browseElements(first: 1) { totalCount } }"}'
# Expected: totalCount > 0
```

## QS-005: Browse queries with cursor pagination
```bash
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ browseElements(first: 5) { edges { cursor node { sha256 } } pageInfo { hasNextPage endCursor } totalCount } }"}'
# Expected: 5 edges, hasNextPage true, endCursor non-null, totalCount matches import
```

## QS-006: Single entity lookup
```bash
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ element(sha256: \"<sha256_from_browse>\") { sha256 semantic provenance ontologyAnnotations } }"}'
# Expected: full entity with all fields populated
```

## QS-007: Resolve a curation flag
```bash
# Create a flag via import, then resolve it:
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { resolveFlag(input: { flagId: \"<id>\", action: APPROVED, resolvedBy: \"test\", note: \"OK\" }) { status resolvedBy } }"}'
# Expected: status = "approved", resolvedBy = "test"
```

## QS-008: Frontend connects and shows data
```bash
# With backend running:
cd frontend && pnpm dev
# Open http://localhost:3000
# Expected: element browser shows elements loaded from backend
```

## QS-009: Library tests still pass
```bash
cd library && uv run pytest tests/ -v
# Expected: 400+ tests pass (zero regressions)
```

## QS-010: Backend tests pass
```bash
cd backend && uv run pytest tests/ -v
# Expected: all GraphQL + conformance tests pass
```
