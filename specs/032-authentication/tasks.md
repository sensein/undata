# Tasks: Authentication & Authorization

**Input**: Design documents from `/specs/032-authentication/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Included — backend auth tests with mock JWTs, existing Playwright regression.

**Organization**: 5 user stories. US1+US2 (sign-in + roles) are tightly coupled. US4 (identity on mutations) follows immediately. US3 (API keys) is P2. US5 (frontend) depends on backend auth.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Which user story (US1–US5)

## Phase 1: Setup

**Purpose**: Keycloak Docker, auth module structure

- [X] T001 Add Keycloak service to `backend/docker-compose.yml` — Keycloak 24+ on port 8080, import realm from `keycloak/realm-export.json`, depends_on db, health check at /health/ready
- [X] T002 Verify `backend/keycloak/realm-export.json` exists and has GitHub/ORCID identity providers configured. Update realm settings if needed (redirect URIs to localhost:8002 and localhost:3000)
- [X] T003 Create `backend/src/auth/` package with `__init__.py`
- [X] T004 Add `python-jose[cryptography]` or `PyJWT` to `backend/pyproject.toml` for JWT decode

**Checkpoint**: Keycloak starts with docker compose up, auth module exists

---

## Phase 2: Foundational — JWT Middleware + Role Enforcement (US1 + US2)

**Purpose**: Backend validates JWTs and enforces roles on mutations — BLOCKS all other auth work

**⚠️ CRITICAL**: All mutation auth depends on this middleware

### Tests

- [X] T005 [US2] Write `backend/tests/test_auth.py` — test JWT validation middleware with mock tokens: valid token → user extracted, expired token → 401, invalid signature → 401, missing token on mutation → 401, valid token with viewer role on curator mutation → 403, valid token with curator role → success

### Implementation

- [X] T006 [US1] Create `backend/src/auth/middleware.py` — JWT validation using Keycloak JWKS endpoint. Fetches public keys from `{keycloak_url}/realms/{realm}/protocol/openid-connect/certs`. Caches keys. Validates token signature, expiry, issuer. Returns decoded payload with sub, email, name, realm_roles
- [X] T007 [US2] Create `backend/src/auth/dependencies.py` — FastAPI dependencies: `get_current_user(request) → UserProfile | None` (extracts JWT from Authorization header or cookie, looks up/creates UserProfile), `require_auth(user)` (raises 401 if None), `require_role(role)(user)` (raises 403 if insufficient). Expired tokens return 401 prompting re-login (acceptable for MVP — token refresh deferred)
- [X] T008 [US1] Update `backend/src/main.py` — add Keycloak config (URL, realm, client_id from env vars), register auth middleware. Add `GET /auth/me` endpoint returning current user from JWT (or 401 if not authenticated) for FR-012 token validity check
- [X] T009 [US2] Update `backend/src/graphql/schema.py` — wrap all mutations with `require_auth`. Apply `require_role("curator")` to resolveFlag/batchResolveFlags, `require_role("contributor")` to submitContribution, `require_role("admin")` to triggerPipelineRun. Queries remain unauthenticated
- [X] T010 [US1] Update `backend/src/db/models.py` — ensure UserProfile has `external_sub` (unique), `email`, `display_name`, `role` with proper defaults
- [X] T011 [US2] Run auth tests: `uv run pytest tests/test_auth.py -v` — all must pass with mock JWTs

**Checkpoint**: Mutations require auth, roles enforced, queries remain public

---

## Phase 3: User Identity on Mutations (US4)

**Goal**: Every mutation records who performed it.

**Independent Test**: Resolve flag as curator → query flag → resolved_by shows curator's name.

- [ ] T012 [US4] Update `backend/src/graphql/resolvers.py` — `resolve_resolve_flag` uses `current_user.display_name` for `resolved_by` (not client-provided). `resolve_submit_contribution` uses `current_user.display_name` for `contributor`
- [ ] T013 [US4] Update `backend/src/graphql/schema.py` — pass `current_user` from auth context to resolver functions. Remove `resolved_by` and `contributor` from mutation inputs (server sets them)
- [ ] T014 [US4] Write test in `backend/tests/test_auth.py` — resolve flag with mock curator JWT, verify resolved_by matches JWT's name claim

**Checkpoint**: All mutations record authenticated user identity

---

## Phase 4: API Keys (US3)

**Goal**: Programmatic authentication via API keys.

**Independent Test**: Generate key → use in curl → mutation succeeds.

- [ ] T015 [US3] Add `APIKey` model to `backend/src/db/models.py` — id (UUID), user_id (FK to UserProfile), token_hash (VARCHAR, indexed), label (VARCHAR), created_at, revoked_at (nullable)
- [ ] T016 [US3] Create `backend/src/auth/api_keys.py` — `validate_api_key(token) → UserProfile | None` (SHA-256 hash the token, look up by hash, check not revoked, return associated UserProfile)
- [ ] T017 [US3] Update `backend/src/auth/dependencies.py` — `get_current_user` checks for API key if no JWT present (Authorization: Bearer <key> where key is not a JWT)
- [ ] T018 [US3] Add `generateApiKey` and `revokeApiKey` mutations to GraphQL — require auth, return the raw key once on creation
- [ ] T019 [US3] Write API key test in `backend/tests/test_auth.py` — create key, use key for mutation, revoke key, verify revoked key rejected

**Checkpoint**: API keys work for all mutations

---

## Phase 5: Frontend Auth Integration (US5)

**Goal**: Sign in/out in UI, user identity in sidebar, role-aware buttons.

**Independent Test**: Sign in → name in sidebar. Curation shows resolve buttons for curators only.

- [ ] T020 [US5] Create `frontend/lib/auth.ts` — auth helpers: `getSession()` → {user, token} | null, `signIn()` redirect to Keycloak, `signOut()` clear session
- [ ] T021 [US5] Create `frontend/components/AuthProvider.tsx` — React context wrapping auth state, provides `useAuth()` hook returning {user, role, isAuthenticated, signIn, signOut}
- [ ] T022 [US5] Create `frontend/app/auth/callback/route.ts` — handle OAuth callback, exchange code for tokens via backend proxy, set session cookie
- [ ] T023 [US5] Update `frontend/components/Sidebar.tsx` — bottom section: if signed in show display_name + role badge + "Sign out" link. If not signed in show "Sign in" button
- [ ] T024 [US5] Update `frontend/app/curation/page.tsx` — show Approve/Reject buttons only when `useAuth().role` is "curator" or "admin". Show "Sign in to review" for unauthenticated users
- [ ] T025 [US5] Update `frontend/app/layout.tsx` — wrap children with AuthProvider

**Checkpoint**: Frontend shows identity, role-aware actions work

---

## Phase 6: Polish + Validation

**Purpose**: Tests, CI, documentation

- [ ] T026 Verify existing Playwright tests (20+) still pass — queries are public, auth doesn't break browsing
- [ ] T027 Update `CLAUDE.md` with auth developer setup: Keycloak URL, creating test users, generating API keys
- [ ] T028 Run quickstart validation QS-001 through QS-008
- [ ] T029 Verify `ruff check` and `ruff format` pass on backend
- [ ] T030 Push branch and verify CI is green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (JWT + Roles)**: Depends on Phase 1 — BLOCKS all auth work
- **Phase 3 (Identity on Mutations)**: Depends on Phase 2
- **Phase 4 (API Keys)**: Depends on Phase 2 — can parallel with Phase 3
- **Phase 5 (Frontend)**: Depends on Phase 2 (needs backend auth working)
- **Phase 6 (Polish)**: Depends on all previous

### Parallel Opportunities

**Phase 2**: T006, T007 can be developed in parallel (middleware + dependencies are separate files)
**Phase 4**: Can run in parallel with Phase 3 after Phase 2

---

## Implementation Strategy

### MVP (Phases 1-3)

1. Keycloak + JWT middleware + role enforcement
2. User identity on all mutations
3. **STOP and VALIDATE**: Mutations require auth, identity recorded

### Full Delivery

4. API keys for programmatic access
5. Frontend sign-in/out + role-aware UI
6. Tests + CI green

---

## Notes

- Keycloak adds ~10s to Docker startup — acceptable for auth features
- Existing realm-export.json from brainstorm v1 may need URL updates for localhost:3000/8002
- Mock JWT tests don't need running Keycloak — test middleware in isolation
- API key detection: if Authorization header value is a JWT (contains dots), validate as JWT. Otherwise validate as API key
- Commit after each phase
