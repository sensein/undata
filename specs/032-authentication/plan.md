# Implementation Plan: Authentication & Authorization

**Branch**: `032-authentication` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)

## Summary

Add OIDC authentication via Keycloak (GitHub/ORCID), JWT validation middleware, role-based mutation access control, API key support, user identity on all mutations, and frontend auth integration.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: authlib 1.x (JWT validation), Keycloak 24+ (IdP), python-jose or PyJWT (token decode)
**Storage**: PostgreSQL (UserProfile + APIKey tables)
**Testing**: pytest + pytest-asyncio (backend), Playwright (frontend)
**Constraints**: Queries remain public. Only mutations require auth.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Keycloak handles OAuth complexity. Backend only validates JWTs. |
| II. TDD | PASS | Auth middleware tested with mock JWTs before wiring Keycloak. |
| III. API-First Design | PASS | Auth is a middleware concern, not a new API surface. |
| IV. Observability | PASS | Auth failures logged with reason (expired, invalid, insufficient role). |
| V. No Deprecation | PASS | Adding auth, not changing existing anonymous access for queries. |
| VI. Environment Isolation | PASS | Keycloak in Docker. No system deps. |
| VII. Developer Experience | PASS | Auth optional for query-only dev. Keycloak profile auto-creates dev user. |
| CI Green Before Merge | PASS | Existing Playwright tests unaffected (queries public). Backend auth tests added. |

## Project Structure

```text
backend/
├── src/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── middleware.py          # NEW: JWT validation + role extraction
│   │   ├── dependencies.py       # NEW: FastAPI deps (get_current_user, require_role)
│   │   └── api_keys.py           # NEW: API key validation
│   ├── db/
│   │   └── models.py             # UPDATE: add APIKey model
│   ├── graphql/
│   │   ├── schema.py             # UPDATE: pass auth context to mutations
│   │   └── resolvers.py          # UPDATE: use current_user in mutations
│   └── main.py                   # UPDATE: add auth middleware, Keycloak config
├── docker-compose.yml             # UPDATE: add Keycloak service
├── keycloak/
│   └── realm-export.json          # KEEP: existing Keycloak realm config
└── tests/
    └── test_auth.py               # NEW: auth middleware + role tests

frontend/
├── app/
│   ├── auth/
│   │   ├── callback/route.ts      # NEW: OAuth callback handler
│   │   └── login/route.ts         # NEW: redirect to Keycloak
│   └── layout.tsx                 # UPDATE: add auth context, sidebar user info
├── components/
│   ├── Sidebar.tsx                # UPDATE: show user name + role, sign in/out
│   └── AuthProvider.tsx           # NEW: auth context + token management
└── lib/
    └── auth.ts                    # NEW: auth helpers (getSession, isRole)
```

## Implementation Approach

### Phase 1: Backend Auth Middleware (US1 + US2)
1. Add Keycloak to docker-compose.yml
2. Create auth/middleware.py — JWT validation from Keycloak JWKS
3. Create auth/dependencies.py — `get_current_user()`, `require_role()`
4. Update graphql/schema.py — wrap mutations with auth dependency
5. Test with mock JWTs

### Phase 2: User Identity on Mutations (US4)
1. Update resolvers to pass current_user to DatabaseBackend operations
2. Update resolveFlag to set resolved_by from authenticated user
3. Update submitContribution to set contributor from authenticated user

### Phase 3: API Keys (US3)
1. Add APIKey model to db/models.py
2. Create auth/api_keys.py — lookup by hashed token
3. Update middleware to check API key if no JWT present

### Phase 4: Frontend Auth (US5)
1. Create auth callback/login routes
2. Create AuthProvider context
3. Update Sidebar with user info and sign in/out
4. Update curation page with role-aware action buttons

### Phase 5: Tests + CI
1. Backend auth tests (mock JWT, role enforcement)
2. Verify existing Playwright tests pass
3. CI green
