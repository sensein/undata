# Quickstart: 032 Authentication Validation

## QS-001: Keycloak starts with Docker
```bash
cd backend && docker compose up -d
curl -f http://localhost:8080/health/ready
# Expected: 200 OK
```

## QS-002: Sign in via GitHub
```
Open http://localhost:3000 → Click "Sign in" → redirected to Keycloak
→ Click "GitHub" → approve → returned to app with name displayed
```

## QS-003: Unauthenticated mutation rejected
```bash
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { resolveFlag(input: {flagId: \"test\", action: APPROVED, resolvedBy: \"anon\"}) { status } }"}'
# Expected: 401 Unauthorized
```

## QS-004: Authenticated mutation succeeds
```bash
# With valid JWT token:
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"query": "mutation { resolveFlag(input: {flagId: \"<id>\", action: APPROVED, resolvedBy: \"curator\"}) { status resolvedBy } }"}'
# Expected: 200 with resolvedBy = curator's name
```

## QS-005: Viewer cannot resolve flags
```bash
# With viewer-role JWT:
# Expected: 403 Forbidden
```

## QS-006: API key works
```bash
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api-key>" \
  -d '{"query": "mutation { importRegistry(registryPath: \"/data/seed\") { elements } }"}'
# Expected: 200 OK
```

## QS-007: Frontend shows user identity
```
Sign in → sidebar shows display name + role badge
Curation page shows Approve/Reject buttons for curators
```

## QS-008: Existing tests still pass
```bash
cd frontend && pnpm exec playwright test
# Expected: 20+ tests pass (queries are public, unaffected by auth)
```
