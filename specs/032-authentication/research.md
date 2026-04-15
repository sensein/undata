# Research: Authentication & Authorization

## R1: Keycloak vs Direct OAuth

**Decision**: Use Keycloak as OIDC identity broker with GitHub and ORCID as upstream providers.

**Rationale**: Keycloak handles token issuance, refresh, session management, and user federation. The backend validates JWTs without implementing OAuth flows directly. This matches the VISION.md architecture and brainstorm v1's Keycloak config (realm-export.json still in the repo).

**Alternatives**: Direct OAuth with authlib (simpler but requires implementing token refresh, session storage, CSRF protection manually). NextAuth.js in frontend (moves auth to frontend, complicates API key flow).

## R2: JWT Validation Strategy

**Decision**: Backend validates Keycloak-issued JWTs using the JWKS endpoint. FastAPI dependency extracts user identity from the token. Queries skip auth check; mutations require valid token.

**Rationale**: Stateless JWT validation means no session store on the backend. Keycloak publishes JWKS at a well-known URL. FastAPI's dependency injection makes per-route auth clean.

## R3: Role Storage

**Decision**: Store role in UserProfile table (already exists). Keycloak realm roles (admin, curator, contributor, viewer) are mapped to the local role field on first login. Role changes in Keycloak propagate on next token refresh.

**Rationale**: Single source of truth for roles avoids sync issues. Keycloak is authoritative; backend mirrors on login.

## R4: API Key Implementation

**Decision**: API keys are random 64-char hex strings, stored as SHA-256 hashes in an `api_keys` table. Lookup by hash on each request. Each key links to a UserProfile.

**Rationale**: Same pattern from brainstorm v1 (002-schema-backend). Hashing prevents key exposure if the database is compromised.

## R5: Frontend Auth Flow

**Decision**: Frontend redirects to Keycloak login page. After authentication, Keycloak redirects back with an authorization code. Frontend exchanges code for tokens via a backend proxy endpoint (to keep client_secret server-side). Access token stored in HTTP-only cookie.

**Rationale**: Server-side token exchange keeps the client_secret secure. HTTP-only cookies prevent XSS token theft. The backend sets the cookie on the auth callback endpoint.

## R6: Docker Stack Update

**Decision**: Add Keycloak service back to docker-compose.yml. Use the existing realm-export.json with GitHub/ORCID providers configured. Keycloak starts on port 8080.

**Rationale**: Keycloak config from brainstorm v1 is reusable. Developers need Keycloak running for auth testing but it's optional for query-only development.
