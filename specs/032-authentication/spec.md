# Feature Specification: Authentication & Authorization

**Feature Branch**: `032-authentication`
**Created**: 2026-03-27
**Status**: Draft
**Input**: Phase 5 of iteration 2 — add OIDC authentication via Keycloak, role-based access control, API key support, and user identity on all mutations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Sign In with GitHub/ORCID (Priority: P1)

As a researcher, I need to sign in with my existing GitHub or ORCID identity so I don't need to create a new account.

**Why this priority**: Identity is the foundation for all other auth features. Without sign-in, curation decisions can't be attributed, contributions can't be tracked, and the community model doesn't work.

**Independent Test**: Click "Sign in" → redirected to identity provider → approve → returned to app with session.

**Acceptance Scenarios**:

1. **Given** the application, **When** a user clicks "Sign in with GitHub", **Then** they are redirected to GitHub's OAuth flow, approve access, and are returned to the app with their identity displayed.
2. **Given** a signed-in user, **When** they refresh the page, **Then** their session persists (they remain signed in).
3. **Given** a signed-in user, **When** they click "Sign out", **Then** their session is cleared and they return to anonymous browsing.
4. **Given** a first-time user, **When** they complete sign-in, **Then** a user profile is created with their external identity, email, and display name.

---

### User Story 2 — Role-Based Access Control (Priority: P1)

As a platform administrator, I need users to have roles (viewer, contributor, curator, admin) that control what actions they can perform, so the curation workflow has proper access control.

**Why this priority**: Without roles, anyone can resolve flags or trigger pipelines. The three-tier CivicDB model (contributor → curator → admin) requires role enforcement.

**Independent Test**: A viewer can browse but not resolve flags. A curator can resolve flags. An admin can trigger pipeline runs.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user, **When** they browse elements, **Then** they see all data (read access is public).
2. **Given** an unauthenticated user, **When** they attempt a mutation (resolveFlag, submitContribution), **Then** the request is rejected with a 401 error.
3. **Given** a user with "viewer" role, **When** they attempt to resolve a flag, **Then** the request is rejected with a 403 error.
4. **Given** a user with "curator" role, **When** they resolve a flag, **Then** the flag is resolved with their identity recorded.
5. **Given** a user with "admin" role, **When** they trigger a pipeline run, **Then** the pipeline executes.

---

### User Story 3 — API Key Authentication (Priority: P2)

As a developer running scripts or CI pipelines, I need to authenticate with an API key instead of a browser session, so automated tools can call mutations.

**Why this priority**: CI/CD and scripts can't go through a browser OAuth flow. API keys enable programmatic access for pipeline triggers and batch operations. P2 because browser auth (P1) must work first.

**Independent Test**: Generate an API key in the UI → use it in a curl command → mutation succeeds with the key's associated user identity.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they generate an API key, **Then** a key is created and displayed once (stored hashed in the database).
2. **Given** an API key, **When** a mutation request includes `Authorization: Bearer <key>`, **Then** the request is authenticated as the key's owner.
3. **Given** an API key, **When** the owner revokes it, **Then** subsequent requests with that key are rejected.

---

### User Story 4 — User Identity on Mutations (Priority: P1)

As a curator reviewing the history of a curation decision, I need every mutation to record who performed it, so I can see who resolved which flags and when.

**Why this priority**: Attribution is what makes the curation workflow trustworthy. Without identity on mutations, there's no accountability.

**Independent Test**: Resolve a flag as curator → query the flag → resolved_by shows the curator's identity.

**Acceptance Scenarios**:

1. **Given** a curator resolves a flag, **When** the flag is queried, **Then** `resolvedBy` contains the curator's display name or email.
2. **Given** a contributor submits a contribution, **When** the contribution is queried, **Then** `contributor` contains the user's identity.
3. **Given** a pipeline run triggered by an admin, **When** the run summary is queried, **Then** it records the triggering user.

---

### User Story 5 — Frontend Auth Integration (Priority: P1)

As a user, I need to see my identity in the UI, see role-appropriate actions, and sign in/out through the interface.

**Why this priority**: Auth must be visible in the UI for users to know they're signed in and what actions are available to them.

**Independent Test**: Sign in → sidebar shows user name and role. Curation page shows resolve buttons only for curators.

**Acceptance Scenarios**:

1. **Given** the sidebar, **When** a user is signed in, **Then** their display name and role badge are shown at the bottom.
2. **Given** the curation page, **When** a curator is signed in, **Then** "Approve" and "Reject" buttons appear on pending flags.
3. **Given** the curation page, **When** a viewer is signed in, **Then** no action buttons appear (read-only).
4. **Given** any page, **When** no user is signed in, **Then** a "Sign in" button appears in the sidebar.

---

### Edge Cases

- What happens when the identity provider is down? Users see a clear error on the sign-in page. Existing sessions remain valid. Read access continues to work.
- What happens when a user's role changes? The next API call after token refresh reflects the new role.
- What happens when an API key is used with an expired user account? The request is rejected with a 401.
- What happens when a signed-in user's session expires during a page interaction? The next mutation returns a 401, and the UI prompts re-authentication.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support sign-in via external identity providers (GitHub, ORCID) using OIDC.
- **FR-002**: System MUST persist user sessions across page refreshes using secure HTTP-only cookies or JWT.
- **FR-003**: System MUST assign roles to users: viewer (default), contributor, curator, admin.
- **FR-004**: All GraphQL queries MUST remain publicly accessible without authentication.
- **FR-005**: All GraphQL mutations MUST require authentication.
- **FR-006**: Mutations MUST enforce role-based access: viewers cannot mutate, contributors can submit, curators can resolve, admins can manage.
- **FR-007**: System MUST support API key authentication via `Authorization: Bearer <key>` header.
- **FR-008**: Every mutation MUST record the authenticated user's identity in the affected entity.
- **FR-009**: Users MUST be able to sign out, clearing their session.
- **FR-010**: The frontend MUST display the signed-in user's identity and role in the sidebar.
- **FR-011**: Action buttons (resolve flag, submit contribution, trigger pipeline) MUST only appear for users with the appropriate role.
- **FR-012**: System MUST provide a health-check-style endpoint to verify token validity.

### Key Entities

- **UserProfile**: External identity (sub, issuer), email, display name, role, created_at. Already exists in DB from feature 029.
- **APIKey**: Hashed token, user_id, label, created_at, revoked_at. New table.
- **Session**: JWT or cookie-based session linking to UserProfile.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can sign in via GitHub OAuth and see their name in the UI within 10 seconds.
- **SC-002**: Unauthenticated mutation requests receive 401 responses.
- **SC-003**: Viewer-role mutation requests receive 403 responses.
- **SC-004**: Curator-resolved flags show the curator's identity in the `resolvedBy` field.
- **SC-005**: API key authentication works for all mutations.
- **SC-006**: All existing Playwright tests (20+) continue to pass (no regressions from auth changes since queries are public).

## Scope Boundaries

### In Scope

- OIDC authentication via Keycloak with GitHub and ORCID providers
- Keycloak Docker service in docker-compose
- JWT validation middleware in FastAPI
- Role-based mutation access control
- API key generation and authentication
- User identity recorded on all mutations
- Frontend sign-in/sign-out UI
- Role-aware action buttons in curation UI

### Out of Scope

- User profiles page (deferred)
- Leaderboards and contribution statistics (deferred)
- Email notifications
- Password-based authentication (OIDC only)
- Fine-grained per-entity permissions

## Assumptions

- Keycloak 24+ Docker image is available and configurable
- GitHub and ORCID OAuth apps can be configured in Keycloak
- The existing UserProfile table from feature 029 is the user store
- JWT tokens from Keycloak contain the user's sub, email, and name
- Default role for new users is "viewer" — role promotion is manual (admin action)

## Dependencies

- Feature 029 (backend service) — provides UserProfile model and GraphQL mutations
- Feature 031 (CivicDB UI) — provides sidebar where user identity is displayed
- Keycloak Docker image
