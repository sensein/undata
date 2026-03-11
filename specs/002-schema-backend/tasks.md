---
description: "Task list for Schema Backend Service implementation"
---

# Tasks: Schema Backend Service

**Input**: Design documents from `/specs/002-schema-backend/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/rest-api.md ✅ quickstart.md ✅

**User Stories**: US1 P1 (Element Storage + Supersession) · US2 P2 (Mapping Registry) · US3 P3 (Audit Trail) · US4 P2 (Identity + AuthZ) · US5 (Dynamic Schemas + Nesting + Supersession) · US6 P2 (Undata Curation + Downstream Integration) · US7 (Unit Standardization — cmixf + QUDT)
**Implementation order**: Setup → Foundational → US4 (auth prerequisite) → US1 → US5 (DynamicSchema, depends on US1) → US2 → US3 → Polish → US7 (Unit Standardization, depends on US1)
**Note**: US4 is P2 in the spec but is an implementation prerequisite for US1; it is scheduled first. US5 (DynamicSchema + nested schema support, FR-027–FR-030) depends on US1 elements existing. US7 enriches the unit node in semantic_graph with cmixf validation + QUDT URI resolution.

**Tests**: Written FIRST in each user story phase — Constitution Principle II (NON-NEGOTIABLE). Each test task must produce FAILING tests before any implementation task in its phase begins.

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]**: Parallelizable — different files, no dependencies on incomplete tasks in the same phase
- **[Story]**: Maps to user story (US1–US5)
- All paths relative to `backend/`

---

## Phase 1: Setup

**Purpose**: Project scaffolding, tooling, and containerization

- [x] T001 Create directory structure: `backend/src/{api/v1/,models/,services/,core/,db/migrations/}`, `backend/tests/{contract/,integration/,unit/}`, `backend/keycloak/`
- [x] T002 Create `backend/pyproject.toml`: `[project] name="schema-backend" version="2026.03.0"`; dependencies: fastapi>=0.111, sqlalchemy[asyncio]>=2.0, asyncpg>=0.29, alembic>=1.13, pydantic>=2.0, pydantic-settings>=2.0, authlib>=1.0, itsdangerous>=2.0, cachetools>=5.0, sentence-transformers>=3.0, pgvector>=0.3, httpx>=0.27, python-json-logger>=2.0; dev: pytest>=8.0, pytest-asyncio>=0.23, pytest-benchmark>=4.0; ruff config: line-length=100, select=["E","F","I"]
- [x] T003 [P] Create `backend/Dockerfile`: python:3.12-slim base; install deps from pyproject.toml; copy `src/`; expose 8002; CMD `uvicorn src.main:app --host 0.0.0.0 --port 8002`
- [x] T004 [P] Create `backend/docker-compose.yml`: services — `backend` (port 8002, env_file .env, `UNDATA_BASE_URL=http://localhost:8002`), `db` (postgres:16 with pgvector, port 5432 internal, named volume `pg_data`), `keycloak` (quay.io/keycloak/keycloak:24, port 8080, `--import-realm`, volume mount `./keycloak/realm-export.json:/opt/keycloak/data/import/realm-export.json`), `test` (pytest profile, `TEST_DATABASE_URL`)
- [x] T005 [P] Create `backend/.env.example`: `DATABASE_URL=postgresql+asyncpg://undata:undata@db:5432/undata`, `SECRET_KEY=changeme`, `KEYCLOAK_URL=http://keycloak:8080`, `KEYCLOAK_REALM=undata`, `KEYCLOAK_CLIENT_ID=`, `KEYCLOAK_CLIENT_SECRET=`, `ALIAS_SIMILARITY_THRESHOLD=0.88`, `TOKEN_CACHE_TTL_SECONDS=300`, `LOG_LEVEL=INFO`, `UNDATA_BASE_URL=http://localhost:8002`
- [x] T006 [P] Create `backend/keycloak/realm-export.json`: minimal Keycloak realm definition for `undata` realm — client `undata-backend` (confidentialClient, redirectUris: `["http://localhost:8002/*"]`, standardFlowEnabled: true), identity provider stubs for `globus`, `github`, `incommon`; used by `keycloak` docker-compose service to bootstrap realm on first start

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Settings, DB layer, ORM models (16 tables), Pydantic schemas, URI minting utility, Alembic migrations, base AuditService, logging, test harness, **undata source seeding test (T084 — write FIRST before T017)**, and main.py entry point. MUST be complete before any user story phase begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T007 Create `backend/src/core/config.py`: `class Settings(BaseSettings)` (pydantic-settings) with fields: `database_url: str`, `undata_base_url: str = "http://localhost:8002"`, `secret_key: str`, `keycloak_url: str`, `keycloak_realm: str = "undata"`, `keycloak_client_id: str`, `keycloak_client_secret: str`, `alias_similarity_threshold: float = 0.88`, `token_cache_ttl_seconds: int = 300`, `log_level: str = "INFO"`; `settings = Settings()` singleton; `model_config = SettingsConfigDict(env_file=".env")`
- [x] T008 Create `backend/src/db/session.py`: `create_async_engine` from `settings.database_url`; `AsyncSessionLocal` sessionmaker; `get_db` FastAPI dependency yielding `AsyncSession` with `begin()` context; `Base = DeclarativeBase()`
- [x] T009 Create `backend/src/models/db.py`: ALL 16 SQLAlchemy ORM models — `UserProfile` (id UUID PK, external_sub, external_iss, email, display_name, is_active, created_at, last_login_at; UNIQUE(external_sub, external_iss)), `APIKey` (id, user_id FK→UserProfile, token_hash TEXT UNIQUE, label, scopes JSONB, issued_at, last_used_at, revoked_at, revoked_by FK nullable), `UserRole` (PK: user_id+role, granted_at, granted_by FK), `SourceMembership` (PK: user_id+source_id, role, granted_at, granted_by FK), `SchemaSource` (id, name TEXT UNIQUE, format, url, version_tag, content_hash, ingested_at, is_active, metadata JSONB), `DataElement` (id UUID PK, **uri TEXT NOT NULL UNIQUE**, source_id FK, source_local_id, current_version_id FK, version_num, **superseded_by UUID FK→DataElement nullable**, created_at, deleted_at; UNIQUE(source_id, source_local_id); partial index on deleted_at IS NULL; B-tree index on superseded_by), `DataElementVersion` (id, element_id FK, version_num, name, data_type, description, required, multivalued, allowed_values JSONB, constraints JSONB, **semantic_graph JSONB** (structured knowledge graph: entities/property/unit/relations/domain/range_type/context — see FR-031), **unit TEXT** (denormalized from semantic_graph.unit.label; B-tree index for unit filtering), name_embedding VECTOR(384), description_embedding VECTOR(384), created_at, created_by UUID FK→UserProfile; GIN jsonb_path_ops index on semantic_graph; GIN tsvector indexes on name, description), `DataElementChild` (parent_id FK→DataElement, child_id FK→DataElement, position INT, field_name TEXT; PK: (parent_id, child_id); B-tree index on parent_id, child_id), `MappingFunction` (id UUID PK, **uri TEXT NOT NULL UNIQUE**, function_type, output_element_id FK, current_version_id FK, version_num, status DEFAULT "active", created_at, deleted_at), `MappingInput` (mapping_id FK, element_id FK, position INT; PK: (mapping_id, element_id); B-tree index on element_id), `MappingFunctionVersion` (id, mapping_id FK, version_num, description, expression, expression_type, parameter_schema JSONB, inverse_mapping_id FK nullable, sssom_predicate, created_at, created_by UUID FK→UserProfile), `AliasGroup` (id, name, sssom_predicate, confidence, detection_method, created_at), `AliasGroupMember` (alias_group_id FK, element_id FK; PK: (alias_group_id, element_id)), `DynamicSchema` (id UUID PK, **uri TEXT NOT NULL UNIQUE**, name, description, version_num, **superseded_by UUID FK→DynamicSchema nullable**, created_at, updated_at, deleted_at; B-tree index on superseded_by), `DynamicSchemaElement` (schema_id FK→DynamicSchema, element_id FK→DataElement, position INT, field_alias TEXT; PK: (schema_id, element_id); B-tree index on schema_id, element_id), `AuditLog` (id, record_type, record_id UUID, operation, **actor_id UUID FK→UserProfile NOT NULL**, timestamp, version_num, diff JSONB; B-tree indexes on (record_type, record_id), actor_id, timestamp); add B-tree UNIQUE on api_key.token_hash, B-tree on user_role.user_id, source_membership.(user_id, source_id), data_element.uri, mapping_function.uri, dynamic_schema.uri
- [x] T010 Create `backend/src/models/schemas.py`: ALL Pydantic v2 request/response models — `UserProfileResponse` (id, email, display_name, roles, source_memberships, created_at, last_login_at, is_active), `UserProfileSummary`, `RoleAssignRequest`, `SourceMembershipRequest`, `SourceMembershipResponse`, `APIKeySummary` (id, label, issued_at, last_used_at, revoked_at — NO token field), `APIKeyCreateResponse` (id, label, **token: str** — shown once), `TokenIssueRequest`, `SchemaSourceCreate`, `SchemaSourceResponse`, `DataElementCreate` (name, data_type, description, required, multivalued, source_id, source_local_id, allowed_values, constraints, **`semantic_graph: SemanticGraph | None`** — NO created_by; `unit` is NOT accepted in create, it is extracted from `semantic_graph.unit.label` by the service layer), `DataElementUpdate` (NO updated_by, includes version_num, **`semantic_graph: SemanticGraph | None`**), `DataElementChildRef` (id, uri, field_name, position), **`SemanticGraphEntity`** (label: str, type: str, role: str, external_uri: str | None), **`SemanticGraphProperty`** (label: str, type: str, external_uri: str | None), **`SemanticGraphUnit`** (label: str, symbol: str, external_uri: str | None), **`SemanticGraphRelation`** (subject: str, predicate: str, object: str), **`SemanticGraph`** (entities: list[SemanticGraphEntity], property: SemanticGraphProperty | None, unit: SemanticGraphUnit | None, relations: list[SemanticGraphRelation], domain: str | None, range_type: str | None, context: str | None), **`SemanticGraphOverlap`** (property_match: bool, unit_match: bool, entity_labels_match: bool, domain_match: bool | None — None when domain absent from both elements' semantic graphs), `DataElementSummary` (**uri: str**, id, name, data_type, description, required, multivalued, source, **unit: str | None**, **superseded_by: str | None**, alias_count, mapping_count, version_num), `DataElementResponse` (**uri: str**, id, name, data_type, description, required, multivalued, allowed_values, constraints, **semantic_graph: SemanticGraph | None**, **unit: str | None**, **superseded_by: str | None**, **supersedes: str | None**, source, source_local_id, **children: list[DataElementChildRef]**, alias_groups, mappings_as_input, mappings_as_output, version_num, created_at, deleted_at), **`DataElementVersionResponse`** (id: UUID, element_id: UUID, version_num: int, name: str, data_type: str, description: str | None, required: bool, multivalued: bool, allowed_values: list | None, constraints: dict | None, semantic_graph: SemanticGraph | None, unit: str | None, created_at: datetime, created_by_display_name: str), **`SupersedeElementRequest`** (supersede_reason: str — REQUIRED; new_element_data: DataElementCreate — full payload for replacement element), `BulkCreateRequest`, `BulkCreateResponse` (succeeded: list[{index, id, uri}], failed: list[{index, error, message}]), `MappingFunctionCreate`, `MappingFunctionUpdate`, `MappingFunctionSummary` (**uri: str**), `MappingFunctionResponse` (**uri: str**), `MappingFunctionVersionResponse`, `AliasGroupCreate`, `AliasGroupUpdate`, `AliasGroupSummary`, `AliasGroupResponse`, **`AliasCandidatePair`** (element_a: DataElementSummary, element_b: DataElementSummary, similarity_score: float, suggested_predicate: str, semantic_graph_overlap: SemanticGraphOverlap | None), **`AliasDetectRequest`** (source_id: UUID | None, threshold: float | None, cross_source_only: bool = False, limit: int = 50, offset: int = 0), `DynamicSchemaCreate` (name, description, elements: list[{element_id, position, field_alias}]), `DynamicSchemaUpdate` (add, remove, version_num), `DynamicSchemaSummary` (**uri: str**, id, name, element_count, version_num), `DynamicSchemaElementRef` (element_id, element_uri, element_name, position, field_alias, **element_unit: str | None**, **element_superseded_by: str | None**), `DynamicSchemaResponse` (**uri: str**, id, name, description, elements: list[DynamicSchemaElementRef], version_num, **superseded_by: str | None**, **supersedes: str | None**, created_at, updated_at), **`SupersedeSchemaRequest`** (supersede_reason: str — REQUIRED; new_schema_data: DynamicSchemaCreate — full payload for replacement schema), `AuditLogResponse` (id, record_type, record_id, operation, **actor_id: UUID**, **actor_display_name: str**, timestamp, version_num, diff), `PaginatedList[T]` (total, limit, offset, items), `ErrorEnvelope` (error, message, details)
- [x] T011 Initialize Alembic: `alembic init backend/src/db/migrations`; configure `env.py` for async SQLAlchemy — `run_migrations_online` using `AsyncEngine` and `asyncio.run`; `target_metadata = Base.metadata`; set `script_location` in `alembic.ini` to `backend/src/db/migrations`
- [x] T012 Create `backend/src/db/migrations/versions/2026_03_0_initial_schema.py`: `CREATE EXTENSION IF NOT EXISTS vector`; create all 16 tables with columns, constraints, and indexes as defined in data-model.md; `uri` columns on `data_element`, `mapping_function`, `dynamic_schema` — TEXT NOT NULL UNIQUE; `actor_id UUID` FK on `audit_log` (not `actor TEXT`); `superseded_by UUID NULL` self-referential FK on `data_element` (→ `data_element.id`) and on `dynamic_schema` (→ `dynamic_schema.id`); `semantic_graph JSONB NULL` on `data_element_version`; `unit TEXT NULL` on `data_element_version` (extracted from `semantic_graph.unit.label` by application layer); GIN tsvector indexes on `data_element_version.(name, description)`; **GIN jsonb_path_ops index on `data_element_version.semantic_graph`** for semantic field queries; **B-tree index on `data_element_version.unit`** for unit-based filtering; **B-tree index on `data_element.superseded_by`** for lineage traversal; **B-tree index on `dynamic_schema.superseded_by`** for lineage traversal; partial index `WHERE deleted_at IS NULL` on `data_element`; migration is idempotent (IF NOT EXISTS)
- [x] T013 Create `backend/src/core/uri.py`: `mint_element_uri(element_id: str) -> str` returns `f"{settings.undata_base_url}/elements/{element_id}"`; `mint_mapping_uri(mapping_id: str) -> str` returns `f"{settings.undata_base_url}/mappings/{mapping_id}"`; `mint_schema_uri(schema_id: str) -> str` returns `f"{settings.undata_base_url}/schemas/{schema_id}"`; URIs are deterministic from UUID; called at entity creation time and stored immutably; importable without app context
- [x] T014 Create `backend/src/services/audit.py`: `AuditService.record(session, record_type: str, record_id: UUID, operation: str, actor_id: UUID, version_num: int | None, diff: dict | None) -> None` — inserts `AuditLog` row in the **same transaction** as the caller; `diff` format: `{"field": {"old": v1, "new": v2}}`; `actor_id` is a UUID FK to `UserProfile` (not a plain string); uses `get_logger`
- [x] T015 Create `backend/src/core/logging.py`: `get_logger(name: str) -> logging.Logger` configured with `python_json_logger.JsonFormatter` emitting `level`, `service="schema-backend"`, `logger`, `message`, `timestamp`; configure root logger from `settings.log_level` in `main.py`
- [x] T016 Create `backend/tests/conftest.py` and `backend/pytest.ini`: `asyncio_mode = "auto"` in pytest.ini; `engine` fixture creating isolated test DB schema per session via Alembic migrations against `TEST_DATABASE_URL`; `db_session` fixture yielding `AsyncSession` with rollback teardown; `client` fixture — `httpx.AsyncClient(app=app, base_url="http://test")`; `mock_admin_user` fixture creating a `UserProfile` with `admin` role; `mock_curator_user` fixture with `curator` role; `mock_viewer_user` fixture with `viewer` role; `curator_token` + `viewer_token` fixtures issuing API keys for mock users
- [x] T084 [P] ⚠️ Write FIRST — must FAIL before T017. Create `backend/tests/unit/test_undata_seed.py`: unit test for startup seeding idempotency — (1) mock `AsyncSession.execute` to simulate empty DB; verify lifespan calls `INSERT INTO schema_source ... ON CONFLICT (name) DO NOTHING` for `name="undata"`, `format="canonical"`, `is_active=True`; (2) simulate DB already having the undata row; verify no duplicate insert attempt and no error raised; (3) assert after seeding `GET /sources?name=undata` returns exactly one record with `format="canonical"` and `is_active=True`; (Constitution Principle II: test must be committed and confirmed FAILING before T017 implementation begins)
- [x] T017 Create `backend/src/main.py`: FastAPI `app` with `title="Schema Backend"`, `version="2026.03.0"`; lifespan handler running (1) Alembic `command.upgrade(alembic_cfg, "head")` on startup, (2) idempotent `INSERT INTO schema_source (id, name, format, content_hash, ingested_at, is_active) VALUES (gen_random_uuid(), 'undata', 'canonical', 'seeded', now(), true) ON CONFLICT (name) DO NOTHING` to ensure the canonical undata SchemaSource exists; JSON request logging middleware using `get_logger` emitting `method`, `path`, `status_code`, `duration_ms`; `GET /health` returning `{"status": "ok", "version": "2026.03.0"}`; router includes added in US phases

**Checkpoint**: `docker compose up -d backend db keycloak && curl http://localhost:8002/health` returns `{"status":"ok","version":"2026.03.0"}`. `curl "http://localhost:8002/api/v1/sources?name=undata"` returns exactly one source record with `format="canonical"` and `is_active=true`. `docker compose run --rm test pytest tests/unit/test_undata_seed.py -v` passes. `docker compose run --rm test pytest --collect-only` discovers all test files without import errors. Foundation ready.

---

## Phase 3: User Story 4 — Identity, Access Control & User Profiles (Priority: P2) 🔐

**Goal**: OIDC login via Keycloak (federating Globus/GitHub/InCommon), `UserProfile` creation on first login, API key issuance/revocation, RBAC (`admin/curator/contributor/viewer`) and ReBAC source membership enforced via FastAPI dependencies on all write endpoints.

**Implementation note**: US4 is nominally P2 but is an implementation prerequisite for US1 — auth middleware must exist before write endpoints can enforce access control.

**Independent Test**: Authenticate via mock OIDC provider; confirm `UserProfile` created. Issue an API key; use it to call a protected endpoint and confirm 200. Revoke the key; confirm 401. Assign `viewer` role; confirm `POST /elements` returns 403. Assign source `owner` membership on a source; confirm viewer can now POST elements to that source.

### Tests for User Story 4 ⚠️ Write FIRST — must FAIL before T023

- [x] T018 [P] [US4] Create `backend/tests/contract/test_auth_contract.py`: assert `GET /auth/login` returns 302 with `Location` pointing to Keycloak; assert `GET /auth/callback?code=valid&state=valid` returns 302; assert callback with invalid/missing state returns 401; assert `POST /auth/logout` returns `{"status":"logged_out"}` with HTTP 200
- [x] T019 [P] [US4] Create `backend/tests/contract/test_users_contract.py`: assert `GET /users/me` without token returns 401; with valid curator token returns `UserProfile` shape including `roles` and `source_memberships`; assert `PUT /users/{id}/roles` by non-admin returns 403; by admin returns 200 with updated `UserProfile`; assert `GET /users` by viewer returns 403; by admin returns `PaginatedList` envelope
- [x] T020 [P] [US4] Create `backend/tests/contract/test_tokens_contract.py`: assert `POST /tokens` with valid session returns 201 with `token` (64-char hex); assert `GET /tokens` response items do NOT include `token` field; assert `DELETE /tokens/{id}` sets `revoked_at`; assert using revoked token on any write returns 401
- [x] T021 [P] [US4] Create `backend/tests/unit/test_authz.py`: unit tests for `require_role` — viewer blocked from curator-only action (403), curator allowed, admin allowed; unit tests for `require_source_access` — viewer with source `owner` membership allowed for that source; viewer without any membership is 403; admin bypasses all source checks; pure FastAPI dependency injection tests, no DB
- [x] T022 [P] [US4] Create `backend/tests/integration/test_auth.py`: full OIDC mock flow using `httpx` against test app — mock Keycloak JWKS endpoint (returning test RSA key); GET /auth/login → redirect; callback with valid mock JWT → `UserProfile` upsert → 302; POST /tokens → 64-char hex; authenticated write succeeds; DELETE /tokens/{id} → revocation; re-attempt write with revoked token → 401

### Implementation for User Story 4

- [x] T023 [P] [US4] Create `backend/src/services/tokens.py`: `TokenService.issue(session, user_id: UUID, label: str) -> tuple[str, APIKey]` — `secrets.token_hex(32)`, `hashlib.sha256(token.encode()).hexdigest()` stored, plaintext returned once; `TokenService.validate(session, token_str: str) -> UserProfile | None` — hash lookup with `cachetools.TTLCache(maxsize=1024, ttl=settings.token_cache_ttl_seconds)`; cache key = hash; cache value = `(user_id, revoked_at)`; returns `None` for revoked or missing tokens; updates `last_used_at` on DB hit; `TokenService.revoke(session, key_id: UUID, revoked_by_id: UUID)` — sets `revoked_at`, evicts cache entry; uses `get_logger`
- [x] T024 [P] [US4] Create `backend/src/services/users.py`: `UserService.upsert_from_oidc(session, sub, iss, email, display_name) -> UserProfile` — `INSERT ... ON CONFLICT (external_sub, external_iss) DO UPDATE SET last_login_at=now(), email=..., display_name=...`; `UserService.get(session, id)`, `.list(session, limit, offset) -> (total, list[UserProfile])`; `UserService.assign_roles(session, user_id, roles: list[str], granted_by_id: UUID)`; `UserService.set_source_membership(session, user_id, source_id, role, granted_by_id)`; `UserService.remove_source_membership(session, user_id, source_id)`; `UserService.get_roles(session, user_id) -> list[str]`; uses `get_logger`
- [x] T025 [US4] Create `backend/src/services/auth.py`: `AuthService` using `authlib.integrations.httpx_client.AsyncOAuth2Client`; `get_authorization_url(provider_hint) -> (url, state)` — constructs Keycloak OIDC URL from `settings.keycloak_url/realms/{realm}/.well-known/openid-configuration`; `handle_callback(session, code, state, stored_state) -> UserProfile` — exchanges code for token, validates JWT RS256 against Keycloak JWKS (fetched + cached in module-level dict), calls `UserService.upsert_from_oidc`; `sign_session(user_id: str) -> str` and `verify_session(signed: str) -> str` using `itsdangerous.URLSafeTimedSerializer(settings.secret_key)`; uses `get_logger`
- [x] T026 [US4] Create `backend/src/services/authz.py`: `Role` enum (`admin=3`, `curator=2`, `contributor=1`, `viewer=0`); `get_current_user(request: Request, session: AsyncSession = Depends(get_db)) -> UserProfile` — extracts Bearer token from `Authorization` header, calls `TokenService.validate`, raises `HTTPException(401)` if invalid/missing; `require_role(min_role: Role)` — returns `Depends` callable checking `max(Role[r] for r in user_roles) >= min_role`, raises `HTTPException(403, detail={"error":"insufficient_role"})`; `require_source_access(source_id_param: str, min_role: Role)` — checks global role first; if insufficient, checks `source_membership` for (user_id, source_id) and returns effective `max(global_role, membership_role)`; raises `HTTPException(403, detail={"error":"not_source_member"})` if still below threshold
- [x] T027 [US4] Create `backend/src/api/v1/tokens.py`: router `prefix="/tokens"` — `GET /` (list caller's non-revoked keys via `Depends(get_current_user)`, no `token` field); `POST /` (issue new key, `Depends(get_current_user)`, returns `APIKeyCreateResponse` with `token` once, status 201); `DELETE /{id}` (revoke own key OR admin revokes any, `Depends(get_current_user)` + ownership check, returns `{id, revoked_at}`)
- [x] T028 [US4] Create `backend/src/api/v1/users.py`: router `prefix="/users"` — `GET /me` (`Depends(get_current_user)`) → `UserProfileResponse`; `GET /` (admin only, `Depends(require_role(Role.ADMIN))`) → `PaginatedList[UserProfileSummary]`; `GET /{id}` (admin only); `PUT /{id}/roles` (admin only) → `UserProfileResponse`; `PUT /{id}/sources/{source_id}` (admin only); `DELETE /{id}/sources/{source_id}` (admin only)
- [x] T029 [US4] Create `backend/src/api/v1/auth.py`: router `prefix="/auth"` — `GET /login` (generate state, set state+nonce cookies, return `RedirectResponse` to Keycloak); `GET /callback` (validate state cookie, call `AuthService.handle_callback`, set signed session cookie, return `RedirectResponse` to frontend); `POST /logout` (clear session cookie, return `{"status":"logged_out"}`)
- [x] T030 [US4] Register US4 routers in `backend/src/main.py`: `app.include_router(auth_router, prefix="/api/v1")`, `app.include_router(users_router, prefix="/api/v1")`, `app.include_router(tokens_router, prefix="/api/v1")`

**Checkpoint**: `docker compose run --rm test pytest tests/contract/test_auth_contract.py tests/contract/test_users_contract.py tests/contract/test_tokens_contract.py tests/unit/test_authz.py tests/integration/test_auth.py -v` — all pass. Token issuance, RBAC, and ReBAC enforcement verified.

---

## Phase 4: User Story 1 — Persistent Data Element Storage (Priority: P1) 🎯 MVP

**Goal**: Durable CRUD for schema sources and data elements — each element assigned a **persistent URI** at creation, versioned, keyword-searchable, bulk-ingestable, supporting **nested element references** (DataElementChild for object/array types), with optimistic concurrency, embedding generation, cross-source collision flagging, and authz enforced from Phase 3.

**Independent Test**: Authenticate as curator; register a BIDS source; create 3 elements (one `data_type="object"` with 2 child element refs); confirm each element response includes a `uri` of form `http://localhost:8002/elements/{uuid}`; restart service; retrieve by ID and keyword; update one element (version history = 2 entries); soft-delete one element; confirm deleted element absent from list. Confirm two elements with same `name` but different sources have distinct URIs.

### Tests for User Story 1 ⚠️ Write FIRST — must FAIL before T034

- [x] T031 [P] [US1] Create `backend/tests/contract/test_sources_contract.py`: assert `POST /sources` returns 201 with UUID; `GET /sources` returns `PaginatedList` envelope; `GET /sources?name=undata` returns exactly one record (the pre-seeded canonical source); `PUT /sources/{id}` with wrong `version_num` returns 409; `GET /sources/{id}` unknown returns 404; unauthenticated POST returns 401; viewer-role POST returns 403
- [x] T032 [P] [US1] Create `backend/tests/contract/test_elements_contract.py`: assert `POST /elements` returns 201 `DataElementResponse` with `uri` field (http://…/elements/{uuid}), no `created_by` field; assert response includes **`semantic_graph` object** (entities, property, unit, relations) and **`unit: str | null`** matching `semantic_graph.unit.label`; assert two elements with same `name` but different `source_id` have distinct URIs; `POST /elements/bulk` returns 207 with `succeeded` list including `uri` per item; `GET /elements?q=age` returns `PaginatedList[DataElementSummary]` with `uri` and `unit` on each item; assert `GET /elements?unit=degree+Celsius` filters by unit (B-tree index path); `PUT /elements/{id}` increments `version_num`; `GET /elements/{id}/history` returns ordered version list; `DELETE /elements/{id}` sets `deleted_at`; deleted element excluded from `GET /elements`; unauthenticated writes return 401; assert `GET /elements/{id}` for object-type element includes `children` list
- [x] T033 [P] [US1] Create `backend/tests/integration/test_elements.py`: full lifecycle — register source (curator token), create 3 elements, keyword search, update with version bump, verify 2-entry history with diff, soft-delete, verify list exclusion, verify broken-mapping cascade (stub mapping), verify cross-source name collision returns `collision_candidates`, verify viewer 403, verify viewer with source ownership 200; verify nesting: create parent (object type) + 2 child elements + `POST /elements/{id}/children`; verify `GET /elements/{id}` returns children in position order with `semantic_graph` and `unit` on each child; **verify circular parent-child rejection**: create A (object), B (object); `POST /elements/A/children` [{child_id: B}]; then `POST /elements/B/children` [{child_id: A}] → assert HTTP 400 (cycle detected)
- [x] T073 [P] [US1] Create `backend/tests/contract/test_supersede_element_contract.py`: assert `POST /elements/{id}/supersede` with valid `SupersedeElementRequest` returns 201 with two objects: new element (`uri` distinct from old, `supersedes = old_uri`) and old element stub (`superseded_by = new_uri`, `deleted_at` non-null); assert missing `supersede_reason` returns 422; assert superseding a non-existent element returns 404; assert superseding an already-superseded element returns 409; assert unauthenticated request returns 401; assert viewer returns 403; assert both audit entries (old element DELETE, new element CREATE) appear in same response timestamp

### Implementation for User Story 1

- [x] T034 [P] [US1] Create `backend/src/services/sources.py`: `SourceService.create(session, data, actor_id: UUID) -> SchemaSource`; `.get(session, id) -> SchemaSource | None`; `.list(session, name: str | None, limit, offset) -> (total, list[SchemaSource])` — `name` filter is exact-match on `schema_source.name` column (supports `GET /sources?name=undata` lookup used by downstream consumers and seeding validation); `.update(session, id, data, actor_id, version_num) -> SchemaSource` — optimistic check raising `VersionConflictError` (→ 409); calls `AuditService.record(record_type="SchemaSource", operation="CREATE"/"UPDATE", actor_id=actor_id)`; uses `get_logger`
- [x] T035 [P] [US1] Create `backend/src/services/elements.py` — `ElementService.create(session, data, actor_id: UUID) -> DataElement`: generates `element_id = uuid.uuid4()`; calls `mint_element_uri(str(element_id))` and stores in `data_element.uri` (immutable); inserts `DataElement` + `DataElementVersion`; **extracts `data.semantic_graph.unit.label` (if present) → stores in `DataElementVersion.unit TEXT`** (denormalized for B-tree index; set to `None` if no unit node); generates `name_embedding` and `description_embedding` via `SentenceTransformer("all-MiniLM-L6-v2").encode(text)` as VECTOR(384); cross-source name collision check (same `name`, different `source_id`) → adds `collision_candidates: list[UUID]` to response; raises `DuplicateElementError` on `(source_id, source_local_id)` unique violation (→ 409); calls `AuditService.record(CREATE, actor_id=actor_id)`; uses `get_logger`
- [x] T036 [US1] Add `ElementService.add_children(session, parent_id, children: list[{child_id, position, field_name}], actor_id: UUID)` to `backend/src/services/elements.py`: validates parent `data_type` is `"object"` or `"array"` (else raises `InvalidNestingError` → 400); validates all child element IDs exist; **checks for circular parent-child relationship using DFS on `DataElementChild` table** — if adding any child would create a cycle (direct A→B→A or transitive A→B→C→A), raises `CircularNestingError` → 400; inserts `DataElementChild` rows with `position` and `field_name`; calls `AuditService.record(UPDATE)` for the parent; `ElementService.get_children(session, parent_id) -> list[DataElementChild]` ordered by `position`
- [x] T037 [US1] Add to `backend/src/services/elements.py` — `ElementService.list(session, source_id, data_type, q, unit, subject, property, has_aliases, has_mappings, include_superseded: bool = False, limit, offset)`: `q` → `to_tsvector('english', ...) @@ plainto_tsquery('english', q)` via GIN index; `unit` → `data_element_version.unit = :unit` via B-tree index; `subject` → `semantic_graph @? '$.entities[*] ? (@.label == $label)'` via GIN jsonb_path_ops index; `property` → `semantic_graph @? '$.property ? (@.label == $label)'` via GIN index; `include_superseded=False` → excludes `superseded_by IS NOT NULL` in addition to `deleted_at IS NOT NULL` (so superseded elements are hidden by default); `include_superseded=True` → still excludes `deleted_at IS NOT NULL` but allows `superseded_by IS NOT NULL`; joins to `current_version_id` for name/description/unit; `ElementService.get(session, id) -> DataElement | None` — returns element regardless of `deleted_at` or `superseded_by` (so any URI remains dereferenceable); eagerly loads `current_version`, `source`, `children` (via DataElementChild), `alias_groups` (count), mappings (count)
- [x] T038 [US1] Add to `backend/src/services/elements.py` — `ElementService.update(session, id, data, actor_id: UUID, version_num: int)`: optimistic lock check (→ 409 on mismatch); inserts new `DataElementVersion`; **extracts `data.semantic_graph.unit.label` (if present) → stores in `DataElementVersion.unit TEXT`** (same rule as create: `None` if no unit node); regenerates embeddings; updates `current_version_id`, bumps `version_num`; `uri` field on `DataElement` is **never updated** (immutable); calls `AuditService.record(UPDATE, diff=compute_diff(old_version, new_version), actor_id=actor_id)`
- [x] T039 [US1] Add to `backend/src/services/elements.py` — `ElementService.delete(session, id, actor_id: UUID, version_num: int)`: sets `deleted_at`; sets `status="broken"` on all `MappingFunction` rows referencing this element as input or output; calls `AuditService.record(DELETE, actor_id=actor_id)`; `ElementService.bulk_create(session, elements, actor_id) -> BulkCreateResponse`: per-element try/except, continue on failure; `ElementService.get_history(session, id) -> list[DataElementVersion]` ordered by `version_num ASC`
- [x] T040 [US1] Create `backend/src/api/v1/sources.py`: router `prefix="/sources"` — `GET /` (unauthenticated; query params: `name: str | None`, `limit: int = 50`, `offset: int = 0`; delegates to `SourceService.list`); `POST /` (`Depends(require_role(Role.CURATOR))`); `GET /{id}` (unauthenticated); `PUT /{id}` (`Depends(require_role(Role.CURATOR))`, 409 on `VersionConflictError`); actor always from `get_current_user`, never from request body
- [x] T041 [US1] Create `backend/src/api/v1/elements.py`: router `prefix="/elements"` — `GET /` (unauthenticated; query params: `q: str | None`, `source_id: UUID | None`, `data_type: str | None`, `unit: str | None`, `subject: str | None`, `property: str | None`, `has_aliases: bool | None`, `has_mappings: bool | None`, `include_superseded: bool = False`, `limit: int = 50`, `offset: int = 0`; delegates to `ElementService.list`); `GET /{id}` (unauthenticated; returns element at any lifecycle state — active, superseded, or soft-deleted); `GET /{id}/history` (unauthenticated); `POST /` (`Depends(require_source_access("source_id", Role.CONTRIBUTOR))`); `POST /bulk` (`Depends(require_role(Role.CONTRIBUTOR))`); `PUT /{id}` (`Depends(require_source_access)`, 409; body MUST NOT include `updated_by`); `DELETE /{id}` (`Depends(require_role(Role.CURATOR))`; body `{version_num}` only — MUST NOT include `deleted_by`); `POST /{id}/children` (`Depends(require_source_access)`) → `DataElementResponse`; `GET /{id}/children` (unauthenticated) → `list[DataElementChildRef]`; `DuplicateElementError` → 409; `VersionConflictError` → 409; `InvalidNestingError` → 400; `CircularNestingError` → 400 with `{"error":"circular_nesting","details":{"cycle_path":[...]}}`
- [x] T074 [US1] Add `ElementService.supersede(session, old_id: UUID, req: SupersedeElementRequest, actor_id: UUID) -> tuple[DataElement, DataElement]` to `backend/src/services/elements.py`: in a **single transaction** — (1) load old element (raise 404 if not found; raise 409 if already superseded — `superseded_by IS NOT NULL`); (2) call `ElementService.create(session, req.new_element_data, actor_id)` → new element with new UUID and new URI via `mint_element_uri`; (3) set `old_element.superseded_by = new_element.id`; set `old_element.deleted_at = now()`; (4) call `AuditService.record(DELETE, old_element.id, actor_id, diff={"supersede_reason": req.supersede_reason, "superseded_by": str(new_element.uri)})`; (5) call `AuditService.record(CREATE, new_element.id, actor_id, diff={"supersedes": str(old_element.uri)})`; returns `(new_element, old_element)`; semantic change rationale: a change in `data_type`, `unit` (in semantic_graph), `subject entity`, `measured property`, or `domain` triggers a call to this method; minor changes (typos in description, constraints adjustments) use `ElementService.update` instead
- [x] T075 [US1] Add `POST /{id}/supersede` route to `backend/src/api/v1/elements.py`: `Depends(require_source_access)`; calls `ElementService.supersede`; returns 201 with `{"new_element": DataElementResponse, "superseded_element": {"id", "uri", "superseded_by", "deleted_at"}}`; `ElementNotFoundError` → 404; `AlreadySupersededError` → 409; **Note**: the supersede endpoint does NOT auto-register a conversion `MappingFunction` between old and new elements — if a conversion mapping is needed (e.g. Celsius → Fahrenheit), the curator registers it separately via `POST /mappings` after supersession completes (US5-S4 "MAY" is a curator action, not a server side effect)
- [x] T042 [US1] Register US1 routers in `backend/src/main.py`: `app.include_router(sources_router, prefix="/api/v1")`, `app.include_router(elements_router, prefix="/api/v1")`

**Checkpoint**: `docker compose run --rm test pytest tests/contract/test_sources_contract.py tests/contract/test_elements_contract.py tests/contract/test_supersede_element_contract.py tests/integration/test_elements.py -v` — all pass. Quickstart steps 1a–4 validate. Element URIs present in all responses. Two same-name/different-source elements have distinct URIs. Nested object element returns `children` list. Superseded element has `superseded_by` URI; replacement has `supersedes` URI; both are distinct URIs.

---

## Phase 5: User Story 5 — Dynamic Schema Composition (FR-029, FR-030)

**Goal**: Durable `DynamicSchema` objects that compose named, ordered sets of `DataElement` references — each schema assigned a **persistent URI** at creation, versioned, membership-updatable without changing the URI, soft-deletable, audit-logged. Builds on US1 elements existing.

**Independent Test**: Authenticate as curator; create 3 elements (from US1); call `POST /schemas` composing all 3; confirm response includes `uri` (`http://localhost:8002/schemas/{uuid}`); call `PUT /schemas/{id}` removing one and adding another element; confirm response shows updated membership but same `uri`; call `GET /schemas?element_id={id}` — confirm schema appears; soft-delete; confirm absent from list. Unauthenticated user can GET but not POST.

### Tests for User Story 5 ⚠️ Write FIRST — must FAIL before T047

- [x] T043 [P] [US5] Create `backend/tests/contract/test_schemas_contract.py`: assert `POST /schemas` returns 201 with `uri` field (`http://…/schemas/{uuid}`); assert `GET /schemas` returns `PaginatedList[DynamicSchemaSummary]`; assert `GET /schemas/{id}` returns full `DynamicSchemaResponse` with `elements[]` including `element_uri`; assert `PUT /schemas/{id}` updates membership but `uri` is UNCHANGED; assert `DELETE /schemas/{id}` returns 200; assert unauthenticated POST returns 401; assert viewer POST returns 403; assert wrong `version_num` on PUT returns 409
- [x] T044 [P] [US5] Create `backend/tests/integration/test_dynamic_schemas.py`: full lifecycle — create 4 elements; create schema with 3; GET by ID; PUT to swap one element; confirm URI unchanged, `version_num` bumped, membership updated; GET filtered by `?element_id=` returns schema; DELETE; confirm absent from list but retrievable with `deleted_at`; audit log shows CREATE, UPDATE, DELETE entries with `actor_id` UUID
- [x] T076 [P] [US5] Create `backend/tests/contract/test_supersede_schema_contract.py`: assert `POST /schemas/{id}/supersede` with valid `SupersedeSchemaRequest` returns 201 with new schema (distinct `uri`, `supersedes = old_uri`) and old schema stub (`superseded_by = new_uri`, `deleted_at` non-null); assert missing `supersede_reason` returns 422; assert superseding a non-existent schema returns 404; assert superseding an already-superseded schema returns 409; assert unauthenticated returns 401; assert viewer returns 403; assert GET /schemas with `include_superseded=false` (default) excludes old schema; with `include_superseded=true` includes it

### Implementation for User Story 5

- [x] T045 [P] [US5] Create `backend/src/services/dynamic_schemas.py`: `DynamicSchemaService.create(session, data, actor_id: UUID) -> DynamicSchema`: generates `schema_id = uuid.uuid4()`; calls `mint_schema_uri(str(schema_id))` and stores in `dynamic_schema.uri` (immutable); validates all `element_id`s exist; inserts `DynamicSchema` + `DynamicSchemaElement` rows (position, field_alias from request); calls `AuditService.record(record_type="DynamicSchema", CREATE, actor_id=actor_id)`; uses `get_logger`
- [x] T046 [US5] Add to `backend/src/services/dynamic_schemas.py`: `DynamicSchemaService.get(session, id) -> DynamicSchema | None` — eagerly loads `DynamicSchemaElement` rows joined to `DataElement` for `element_uri` and `element_name`; `.list(session, q, element_id, limit, offset) -> (total, list[DynamicSchema])`; `.update(session, id, add, remove, version_num, actor_id) -> DynamicSchema` — optimistic lock check (→ 409); delete `DynamicSchemaElement` rows for `remove` ids; insert new rows for `add`; bump `version_num`, update `updated_at`; **`uri` is never updated**; calls `AuditService.record(UPDATE, diff=..., actor_id=actor_id)`; `.delete(session, id, actor_id)` — sets `deleted_at`; `AuditService.record(DELETE)`
- [x] T047 [US5] Create `backend/src/api/v1/schemas.py`: router `prefix="/schemas"` — `GET /` (unauthenticated, query params: `q`, `element_id`, `include_superseded: bool = False`, `limit`, `offset`); `POST /` (`Depends(require_role(Role.CURATOR))`); `GET /{id}` (unauthenticated); `PUT /{id}` (`Depends(require_role(Role.CURATOR))`, 409 on `VersionConflictError`); `DELETE /{id}` (`Depends(require_role(Role.CURATOR))`); `ElementNotFoundError` → 422
- [x] T077 [US5] Add `DynamicSchemaService.supersede(session, old_id: UUID, req: SupersedeSchemaRequest, actor_id: UUID) -> tuple[DynamicSchema, DynamicSchema]` to `backend/src/services/dynamic_schemas.py`: in a **single transaction** — (1) load old schema (raise 404 if not found; raise 409 if already superseded); (2) call `DynamicSchemaService.create(session, req.new_schema_data, actor_id)` → new schema with new UUID and new URI via `mint_schema_uri`; (3) set `old_schema.superseded_by = new_schema.id`; set `old_schema.deleted_at = now()`; (4) `AuditService.record(DELETE, old_schema.id, actor_id, diff={"supersede_reason": req.supersede_reason})`; (5) `AuditService.record(CREATE, new_schema.id, actor_id, diff={"supersedes": str(old_schema.uri)})`; returns `(new_schema, old_schema)`
- [x] T078 [US5] Add `POST /{id}/supersede` route to `backend/src/api/v1/schemas.py`: `Depends(require_role(Role.CURATOR))`; calls `DynamicSchemaService.supersede`; returns 201 with `{"new_schema": DynamicSchemaResponse, "superseded_schema": {"id", "uri", "superseded_by", "deleted_at"}}`; `SchemaNotFoundError` → 404; `AlreadySupersededError` → 409
- [x] T048 [US5] Register US5 router in `backend/src/main.py`: `app.include_router(schemas_router, prefix="/api/v1")`

**Checkpoint**: `docker compose run --rm test pytest tests/contract/test_schemas_contract.py tests/contract/test_supersede_schema_contract.py tests/integration/test_dynamic_schemas.py -v` — all pass. Quickstart step 7 validates. Schema URI is stable across membership updates. Superseded schema has `superseded_by` URI; replacement has `supersedes` URI and a new distinct URI.

---

## Phase 6: User Story 2 — Mapping Registry (Priority: P2)

**Goal**: Mapping CRUD with two-layer cycle detection, **persistent URI assigned at creation** for every `MappingFunction`, alias group management (identity mappings cycle-checked via `MappingService`), on-demand similarity-based alias detection endpoint, SSSOM predicates, and HNSW index for embedding search.

**Independent Test**: Register 4 elements (curator token). Register A→B, B→C; attempt C→A — confirm 409 with `cycle_path`. Confirm A→B mapping response includes `uri` (`http://…/mappings/{uuid}`). Register alias group {A,D} — confirm pairwise identity mappings created with URIs. Call `POST /aliases/detect` — confirm paginated `AliasCandidatePair` response. Update mapping expression — confirm version history has 2 entries; URI unchanged.

### Tests for User Story 2 ⚠️ Write FIRST — must FAIL before T053

- [x] T049 [P] [US2] Create `backend/tests/unit/test_cycle_detection.py`: pure Python unit tests for `CycleDetector.detect_cycle_dfs` — no cycle (returns None), direct A↔B cycle (returns path), transitive A→B→C→A (returns path), self-loop (returns path), valid deep DAG (returns None); no DB, no FastAPI
- [x] T050 [P] [US2] Create `backend/tests/contract/test_mappings_contract.py`: assert `POST /mappings` returns 201 `MappingFunctionResponse` with **`uri` field** (`http://…/mappings/{uuid}`); circular registration returns 409 with `{"cycle_path": [...]}` in details; unknown element IDs return 422; `GET /mappings?source_element_id=X` returns filtered list; `GET /mappings/{id}/history` returns versions; unauthenticated write returns 401; viewer returns 403; `PUT /mappings/{id}` bumps `version_num`; URI is unchanged after update
- [x] T051 [P] [US2] Create `backend/tests/contract/test_aliases_contract.py`: assert `POST /aliases` returns 201 and identity mappings created (each with `uri`); `POST /aliases/detect` returns 200 with `PaginatedList[AliasCandidatePair]` shape (`element_a`, `element_b`, `similarity_score`, `suggested_predicate`); assert `POST /aliases/detect` with `cross_source_only=true` returns only pairs from different source_ids; assert each `AliasCandidatePair` item includes `semantic_graph_overlap` object where `property_match`, `unit_match`, `entity_labels_match` are `bool` and `domain_match` is `bool | None` (assert `isinstance(domain_match, (bool, type(None)))`; None when domain absent from both elements); `POST /aliases` for element pair already forming a cycle returns 409
- [x] T052 [P] [US2] Create `backend/tests/integration/test_mappings.py`: full US2 lifecycle — valid DAG registration, cycle rejection with `cycle_path`, alias group creation with auto identity mappings (each has URI), `POST /aliases/detect` returns candidates, mapping update versioning (URI unchanged), soft-delete, broken-mapping cascade on element delete, `GET /mappings/{id}/history` ascending order

### Implementation for User Story 2

- [x] T053 [P] [US2] Create `backend/src/services/cycle_detection.py`: `CycleDetector.detect_cycle_dfs(adjacency: list[tuple[str, str]], proposed_input_ids: list[str], proposed_output_id: str) -> list[str] | None` — pure Python iterative DFS on the proposed augmented graph; returns first cycle path or `None`; no database, no FastAPI; importable for unit tests without app context
- [x] T054 [P] [US2] Create `backend/src/services/similarity.py`: `SimilarityService` with lazy-loaded singleton `SentenceTransformer("all-MiniLM-L6-v2")`; `embed(text: str) -> list[float]` → 384-dim vector; `find_candidates(session, element_ids: list[str] | None, threshold: float, limit: int, offset: int) -> tuple[int, list[AliasCandidatePair]]` — queries pgvector `<=>` cosine distance on `description_embedding` HNSW index; filters pairs by `threshold`; returns `AliasCandidatePair` objects with `element_a`, `element_b`, `similarity_score`, `suggested_predicate` populated and **`semantic_graph_overlap=None`** (overlap computation is the caller's responsibility — T059 `AliasGroupService.detect` populates it post-hoc); sorted desc by score; uses `get_logger`
- [x] T055 [US2] Create `backend/src/db/migrations/versions/2026_03_1_hnsw_index.py`: `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dev_name_emb ON data_element_version USING hnsw (name_embedding vector_cosine_ops) WITH (m=16, ef_construction=64)` and same for `description_embedding`; separate migration so initial schema runs first on cold DB
- [x] T056 [US2] Create `backend/src/services/mappings.py` — `MappingService.create(session, data, actor_id: UUID) -> MappingFunction`: (1) validate all `input_element_ids` + `output_element_id` exist → `ElementNotFoundError` (422); (2) fetch full adjacency list; (3) `CycleDetector.detect_cycle_dfs` → `CycleDetectedError(cycle_path)` (409); (4) `SELECT pg_advisory_xact_lock(hash)` inside same transaction; (5) re-verify with `WITH RECURSIVE` CTE; (6) generate `mapping_id = uuid.uuid4()`; call `mint_mapping_uri(str(mapping_id))` → store in `mapping_function.uri` (immutable); insert `MappingFunction` + `MappingInput` rows (position = index in `input_element_ids`) + `MappingFunctionVersion`; (7) `AuditService.record(CREATE, actor_id=actor_id)`; uses `get_logger`
- [x] T057 [US2] Add to `backend/src/services/mappings.py`: `MappingService.get(session, id)`; `.list(session, source_element_id, target_element_id, function_type, status, limit, offset) -> (total, list[MappingFunction])`; `.update(session, id, data, actor_id, version_num)` — inserts new `MappingFunctionVersion`, bumps `version_num`; **`uri` is never updated**; `AuditService.record(UPDATE, diff=...)`; `.delete(session, id, actor_id, version_num)` — soft-delete; `AuditService.record(DELETE)`; `.get_history(session, id) -> list[MappingFunctionVersion]`
- [x] T058 [US2] Create `backend/src/services/aliases.py` — `AliasGroupService.create(session, data, actor_id: UUID) -> AliasGroup`: inserts `AliasGroup` + `AliasGroupMember` rows; for each unique pair in member set calls **`MappingService.create`** (not raw insert) to register identity `MappingFunction` — ensures cycle detection and URI minting run; `CycleDetectedError` propagates as 409; `AuditService.record(CREATE)`; uses `get_logger`
- [x] T059 [US2] Add to `backend/src/services/aliases.py`: `AliasGroupService.get(session, id)`, `.list(session, element_id, limit, offset) -> (total, list[AliasGroup])`; `.update(session, id, add, remove, version_num, actor_id)` — add/remove members; `.delete(session, id, actor_id)` — deletes group only, not identity mappings; `.detect(session, source_id, threshold, cross_source_only: bool = False, limit, offset) -> (total, list[AliasCandidatePair])` — when `source_id` is provided, first query `element_ids` for all elements belonging to that source (`SELECT id FROM data_element WHERE source_id=:source_id AND deleted_at IS NULL`), pass as `element_ids` to `SimilarityService.find_candidates`; when `source_id` is None, pass `element_ids=None` (scan all); when `cross_source_only=True`, additionally filter result pairs to those where `element_a.source_id != element_b.source_id`; for each candidate pair compute `semantic_graph_overlap: SemanticGraphOverlap` by comparing `semantic_graph` JSONB of both elements' current versions: `property_match = (a.property.label == b.property.label)`, `unit_match = (a.unit.label == b.unit.label if both present else False)`, `entity_labels_match = (sorted(a.entity labels) == sorted(b.entity labels))`, `domain_match = (a.domain == b.domain if both present in either element else None)`; include `semantic_graph_overlap` in each `AliasCandidatePair` response item
- [x] T060 [US2] Create `backend/src/api/v1/mappings.py`: router `prefix="/mappings"` — `GET /`, `GET /{id}`, `GET /{id}/history` (unauthenticated); `POST /` (`Depends(require_role(Role.CURATOR))`); `PUT /{id}` (`Depends(require_role(Role.CURATOR))`); `DELETE /{id}` (`Depends(require_role(Role.CURATOR))`); `CycleDetectedError` → 409 with `{"error":"cycle_detected","details":{"cycle_path":[...]}}`; `ElementNotFoundError` → 422
- [x] T061 [US2] Create `backend/src/api/v1/aliases.py`: router `prefix="/aliases"` — `GET /`, `GET /{id}` (unauthenticated); `POST /` (`Depends(require_role(Role.CURATOR))`); `POST /detect` (`Depends(require_role(Role.CURATOR))`); `PUT /{id}` (`Depends(require_role(Role.CURATOR))`); `DELETE /{id}` (`Depends(require_role(Role.CURATOR))`); `CycleDetectedError` → 409
- [x] T062 [US2] Register US2 routers in `backend/src/main.py`: `app.include_router(mappings_router, prefix="/api/v1")`, `app.include_router(aliases_router, prefix="/api/v1")`

**Checkpoint**: `docker compose run --rm test pytest tests/unit/test_cycle_detection.py tests/contract/test_mappings_contract.py tests/contract/test_aliases_contract.py tests/integration/test_mappings.py -v` — all pass. Quickstart steps 5–6 validate. Mapping URIs present in all responses; URI unchanged after version update.

---

## Phase 7: User Story 3 — Audit Trail and Provenance (Priority: P3)

**Goal**: Queryable audit log returning every mutation with `actor_id` (UUID FK to UserProfile), `actor_display_name`, timestamp, diff, and resource type/ID; full version history accessible via element and mapping history endpoints. Confirms H1+H2 fixes are end-to-end correct.

**Independent Test**: Perform CREATE, UPDATE, DELETE on one element and one mapping (curator token). Query `GET /audit?record_type=DataElement` — 3 entries; confirm each has `actor_id` (UUID, not email string) and `actor_display_name`. Query `GET /audit?actor_id={uuid}` — all 3 entries. Confirm UPDATE entry has `diff`. Confirm `GET /elements/{id}/history` returns 2 versions ascending. Confirm deleted element retrievable by ID with `deleted_at` non-null.

### Tests for User Story 3 ⚠️ Write FIRST — must FAIL before T065

- [x] T063 [US3] Create `backend/tests/integration/test_audit.py`: create/update/delete element + mapping with curator token; assert `GET /audit` returns entries; assert entries have `record_type`, `record_id`, `operation`, **`actor_id` (UUID, not email string)**, **`actor_display_name` (string)**, `timestamp`, `diff`; assert `GET /audit?record_type=DataElement` filters correctly; assert `GET /audit?actor_id={uuid}` filters to that user; assert `GET /audit?from=<iso>&to=<iso>` time-bounds correctly; assert `GET /elements/{id}/history` ascending by `version_num`; assert soft-deleted element retrievable by ID with `deleted_at` non-null

### Implementation for User Story 3

- [x] T064 [US3] Add `AuditService.query(session, record_type, record_id, operation, actor_id, from_ts, to_ts, limit, offset) -> tuple[int, list[AuditLog]]` to `backend/src/services/audit.py`: dynamic SQLAlchemy `and_()` filter chain from non-None params; JOIN to `UserProfile` to populate `actor_display_name` for response serialization; ordered by `timestamp DESC`; returns `(total, items)` tuple
- [x] T065 [US3] Create `backend/src/api/v1/audit.py`: router `prefix="/audit"` — `GET /` accepting `record_type`, `record_id` (UUID), `operation`, `actor_id` (UUID), `from` (ISO datetime), `to` (ISO datetime), `limit`, `offset`; delegates to `AuditService.query`; returns `PaginatedList[AuditLogResponse]`; unauthenticated (read-only endpoint)
- [x] T066 [US3] Register US3 router in `backend/src/main.py`: `app.include_router(audit_router, prefix="/api/v1")`

**Checkpoint**: `docker compose run --rm test pytest tests/integration/test_audit.py -v` — all pass. Audit entries contain `actor_id` UUID and `actor_display_name`. Quickstart step 7a validates.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Complete test coverage, error envelope validation, performance validation, and final quickstart sign-off.

- [x] T067 [P] Create `backend/tests/contract/test_api_contract.py`: verify all response shapes match contracts/rest-api.md for every resource including `uri` fields on DataElement, MappingFunction, DynamicSchema; verify error envelopes `{"error","message","details"}` for 400, 401, 403, 404, 409, 422; verify `PaginatedList` envelope `{"total","limit","offset","items"}` on all list endpoints; verify `AuditEntry` has `actor_id` (UUID) and `actor_display_name` (string); verify `DynamicSchema.uri` unchanged after `PUT`
- [x] T068 [P] Create `backend/tests/unit/test_authz_edge_cases.py`: user with multiple roles (effective = max); user with `owner` on source A but no global curator cannot write to source B; revoked token returns 401 within TTL window; token with NULL `revoked_at` is valid; `mint_element_uri` / `mint_mapping_uri` / `mint_schema_uri` produce expected URI format using `settings.undata_base_url`
- [x] T069 [P] Create `backend/tests/unit/test_uri_stability.py`: unit tests confirming that `DataElement.uri` is never altered on update (verify `uri` field immutability in service layer); same for `MappingFunction.uri` and `DynamicSchema.uri`; confirm `AuditLog.actor_id` is UUID type (not str) by asserting service call signature
- [x] T070 [P] Create `backend/tests/unit/test_performance.py` (pytest-benchmark): seed 10k elements via bulk API; benchmark `GET /elements/{id}` — assert p95 < 100ms; benchmark `GET /elements?q=age` over 10k records — assert p95 < 500ms; benchmark `TokenService.validate` cache hit — assert < 5ms; benchmark `POST /elements/bulk` with 1000 elements — assert total wall-clock time ≤ 60 seconds (satisfies plan.md goal: bulk ingest ≥ 1k elements/min); document results in test output
- [x] T079 Create `backend/tests/integration/test_supersession.py`: full supersession lifecycle for both elements and schemas — (1) create element A (temperature of water in Celsius); call `POST /elements/{id}/supersede` with new element A' (same measurement in Fahrenheit: `unit.label="degree Fahrenheit"`); verify A has `superseded_by = A'.uri` and `deleted_at` set; verify A' has `supersedes = A.uri` and a new distinct URI; verify both audit entries in same timestamp window; (2) repeat for schema — create schema S containing A; call `POST /schemas/{id}/supersede`; verify S.superseded_by set, S'.supersedes set, S' has new URI; (3) confirm `GET /elements` default excludes A (superseded); confirm `GET /elements?include_superseded=true` includes A with `superseded_by` field; (4) verify attempting to supersede A again returns 409
- [x] T080 [P] Create `backend/tests/unit/test_semantic_graph.py`: unit tests for `SemanticGraph` Pydantic model — valid temperature/water/Celsius example deserializes correctly; `unit` field extracts to `element.unit`; missing `unit` node → `unit = None`; missing required fields on entity node raise `ValidationError`; `context` field is optional; `external_uri` on all nodes is optional; assert two elements with different `unit.label` are semantically distinct (by comparing semantic_graph dicts, not URI); assert two elements with different `entity.label` are semantically distinct
- [x] T082 [P] Create `backend/tests/contract/test_downstream_contract.py`: assert `GET /elements?source_id=<undata-id>` returns only elements belonging to the undata SchemaSource (no BIDS/DANDI elements); assert `GET /mappings?target_element_id=<id>` returns a `PaginatedList[MappingFunctionResponse]` where each item has `output_element_id` matching the queried target; assert each `MappingFunctionResponse` includes `uri`, `function_type`, `input_elements` list; assert `GET /sources?name=undata` returns exactly one source record with `format="canonical"`
- [x] T083 [US6] Create `backend/tests/integration/test_curation_workflow.py`: full curation integration test — **Note**: steps (4) and (13) use `SimilarityService` with pre-seeded name/description embeddings via fixture (or mock `SimilarityService.find_candidates` to return known candidate pair) to avoid flaky similarity threshold dependency — (1) register BIDS source + DANDI source; (2) create BIDS `subject_age` element with `semantic_graph` (person/age/year); (3) create DANDI `participant_age` element with same `semantic_graph`; (4) call `POST /aliases/detect` with body `{"cross_source_only": true, "threshold": 0.5}` — verify both elements appear as a candidate pair with `semantic_graph_overlap.property_match=true`, `unit_match=true`; verify `domain_match` is `null` when `domain` absent from both elements; (5) fetch undata source ID via `GET /sources?name=undata`; (6) create canonical `age_years` element under undata source; (7) register BIDS→undata identity mapping; (8) register DANDI→undata identity mapping; (9) compose a DynamicSchema from the undata element; (10) verify `GET /elements?source_id=<undata-id>` returns `age_years` but not `subject_age` or `participant_age`; (11) verify `GET /mappings?target_element_id=<age_years-id>` returns 2 mappings; (12) verify DynamicSchema `uri` is stable after membership update; (13) call `POST /aliases/detect` with body `{"source_id": "<undata-id>", "threshold": 0.5}` (intra-undata compactness audit) — verify response contains 0 candidate pairs (clean undata namespace after one canonical element created)
- [x] T071 Run `docker compose run --rm test pytest tests/ -v --tb=short`; run `ruff check backend/src/ && ruff format --check backend/src/`; confirm all pass; fix any ruff violations
- [x] T072 Run quickstart.md validation checklist (23 items) top to bottom; record pass/fail results in `specs/002-schema-backend/checklists/quickstart-results.md`; confirm URI fields present in all step outputs; confirm `actor_id` UUID in audit step output; confirm `cross_source_only` filter returns cross-source-only pairs; confirm pre-seeded undata source exists on fresh startup

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)             → no dependencies; start immediately
Phase 2 (Foundational)      → requires Phase 1; BLOCKS all user stories
Phase 3 (US4 Identity)      → requires Phase 2; BLOCKS US1/US5/US2 (authz Depends needed)
Phase 4 (US1 Elements)      → requires Phase 2 + Phase 3 (authz Depends)
Phase 5 (US5 DynSchemas)    → requires Phase 4 (DataElement records must exist)
Phase 6 (US2 Mappings)      → requires Phase 2 + Phase 3; calls ElementService for FK checks
Phase 7 (US3 Audit)         → requires Phase 2 only (AuditService.record already in T014)
Phase 8 (Polish)            → requires all user story phases complete
```

### User Story Dependencies

- **US4 (Identity)**: Phase 2 only; auth services independent of US1/US2/US3
- **US1 (Elements)**: Phase 2 + US4 complete; `require_role`/`require_source_access` must exist; URI minting (T013) must exist
- **US5 (DynamicSchemas)**: Phase 4 complete; `mint_schema_uri` (T013) already exists
- **US2 (Mappings)**: Phase 2 + US4 complete; calls `ElementService` for FK validation; `mint_mapping_uri` (T013) already exists
- **US3 (Audit)**: Phase 2 only; `AuditService.query` (T064) extends T014 base

### Within Each Phase

- Tests MUST be written first and confirmed FAILING before any implementation task begins
- `Settings` (T007) before `db/session.py` (T008); `session.py` before ORM models (T009)
- `core/uri.py` (T013) must exist before any service that mints URIs (T035, T056, T045)
- `AuditService.record` (T014) must exist before any service that calls it
- `CycleDetector` (T053) before `MappingService.create` (T056)
- `AliasGroupService.create` (T058) MUST call `MappingService.create` — never bypass cycle detection
- `MappingInput.position` MUST be set from `input_element_ids` list index (0-based)
- `DataElement.uri` / `MappingFunction.uri` / `DynamicSchema.uri` MUST be set at creation and NEVER updated thereafter

### Parallel Opportunities

- T003, T004, T005, T006 — Phase 1 setup files (different files, parallel)
- T007, T008, T009 — Phase 2: config/session/ORM (different files, parallel after T007 done for T008)
- T013, T015 — Phase 2: URI util + conftest (different files, parallel)
- T018, T019, T020, T021, T022 — US4 test files (parallel)
- T023, T024 — US4: TokenService + UserService (parallel)
- T027, T028, T029 — US4 routers (parallel once T025+T026 done)
- T031, T032, T033 — US1 test files (parallel)
- T034, T035 — US1: SourceService + ElementService.create (parallel)
- T043, T044 — US5 test files (parallel)
- T049, T050, T051, T052 — US2 test files (parallel)
- T053, T054 — US2: CycleDetector + SimilarityService (parallel)
- T067, T068, T069, T070, T079, T080, T082, T083 — Polish test tasks (T073, T076, T079, T080, T082 parallel; T083 sequential — full workflow)
- **Note**: T081 is an intentional numbering gap (T080→T082; scope absorbed into T080). T084 (Phase 2) is the undata seed test; Phase 9 tasks were renumbered T102–T108 to eliminate the duplicate ID. T071/T072 run after T082/T083 despite lower IDs — follow file order, not ID order in Phase 8.
- T073 [P] [US1] — supersede element contract test (parallel in Phase 4 test group)
- T076 [P] [US5] — supersede schema contract test (parallel in Phase 5 test group)
- T074 → T075 — supersede element service then route (sequential within US1)
- T077 → T078 — supersede schema service then route (sequential within US5)

---

## Parallel Example: Phase 4 — User Story 1

```bash
# Step 1: Launch all US1 tests in parallel (MUST FAIL before proceeding):
Task: "tests/contract/test_sources_contract.py"    # T031
Task: "tests/contract/test_elements_contract.py"  # T032 — includes uri assertions
Task: "tests/integration/test_elements.py"         # T033 — includes nesting

# Step 2: Confirm all FAIL, then implement in parallel:
Task: "services/sources.py — SourceService"        # T034
Task: "services/elements.py — ElementService.create (URI minting)"  # T035

# Step 3: Sequential (DataElementChild depends on DataElement existing):
Task: "services/elements.py — add_children/get_children"  # T036
Task: "services/elements.py — list/get"           # T037

# Step 4: Parallel routers (once services done):
Task: "api/v1/sources.py"   # T040
Task: "api/v1/elements.py"  # T041

# Step 5:
Task: "Register routers in main.py"  # T042
```

---

## Implementation Strategy

### MVP First (US4 + US1 Only)

1. Phase 1: Setup (T001–T006)
2. Phase 2: Foundational (T007–T017 + T084) — CRITICAL gate; T084 seeding test MUST precede T017 implementation
3. **Write and confirm FAILING tests** (T018–T022)
4. Phase 3: US4 Identity layer (T023–T030)
5. **Write and confirm FAILING tests** (T031–T033)
6. Phase 4: US1 Element storage with URI minting (T034–T042)
7. **STOP and VALIDATE**: Authenticated element storage with persistent URIs — independently functional MVP

### Incremental Delivery

1. Phase 1+2 → Foundation + URI minting + test harness
2. Phase 3 (US4) → Identity layer + auth token model
3. Phase 4 (US1) → Persistent element store with URIs and nesting (MVP!)
4. Phase 5 (US5) → Dynamic Schema composition with persistent URIs
5. Phase 6 (US2) → Mapping registry with persistent URIs + cycle detection + alias detection
6. Phase 7 (US3) → Audit trail (with UUID actor_id, actor_display_name)
7. Phase 8 → Production-ready
8. Phase 9 → Gap closure: tests for element response enrichment + semantic dedup guard

---

---

## Phase 9: Gap Closure — Element Response Enrichment & Semantic Dedup Guard

**Purpose**: Test coverage for three code changes applied post-T072: (1) `DataElementResponse`
now populates `alias_groups`, `mappings_as_input`, `mappings_as_output`, and `supersedes` from
DB (previously hardcoded `[]`/`None`); (2) server-side semantic duplicate guard on
`POST /elements` targeting the undata source.

**Story mapping**: US1 (element storage), US2 (alias/mapping registry), US6 (curation)

- [x] T102 [P] [US1] Add to `backend/tests/contract/test_elements_contract.py`: assert
  `DataElementResponse` shape includes `alias_groups: list`, `mappings_as_input: list`,
  `mappings_as_output: list`, and `supersedes: str | None` fields; assert all four are
  present in the response JSON for a freshly created element (values may be empty lists/null
  — this test verifies **field presence**, not population)

- [x] T103 [P] [US1] Add to `backend/tests/contract/test_supersede_element_contract.py`:
  assert `GET /elements/{new_id}` after `POST /elements/{old_id}/supersede` returns
  `supersedes = old_element.uri` (non-null); assert `GET /elements/{old_id}` returns
  `superseded_by = new_element.uri`; verify both URIs are distinct and non-null

- [x] T104 [P] [US2] Add to `backend/tests/integration/test_curation_workflow.py`: after
  step (8) registers identity mappings (BIDS→undata, DANDI→undata), call
  `GET /elements/{undata_age_id}` and assert `mappings_as_output` contains at least 2 entries
  with `function_type="identity"`; call `GET /elements/{bids_age_id}` and assert
  `mappings_as_input` contains at least 1 entry; call `GET /elements/{bids_age_id}` and
  assert `alias_groups` is non-empty after alias group creation in step (6)

- [x] T105 [P] [US6] Add to `backend/tests/contract/test_elements_contract.py`: assert
  `POST /elements` with `source_id=<undata_source_id>` and a `semantic_graph` whose
  `(sorted entity labels, property.label, unit.label)` triple matches an existing active
  undata element returns HTTP 409 with body
  `{"error": "semantic_duplicate", "existing_id": "<uuid>", "existing_uri": "<uri>"}`;
  assert a second `POST /elements` with a *different* `unit.label` on the same property/entity
  returns 201 (distinct triple → not a duplicate)

- [x] T106 [P] [US6] Add to `backend/tests/unit/test_semantic_graph.py`: unit tests for
  `_check_undata_semantic_duplicate()` helper in `backend/src/services/elements.py` —
  (a) no existing undata elements → no exception; (b) existing element with exact same
  `(entities, property, unit)` triple → raises `SemanticDuplicateError` with correct
  `existing_id` and `existing_uri`; (c) same property + unit, different entity label →
  no exception; (d) same entities + property, different unit label → no exception;
  (e) `semantic_graph=None` on incoming request → no exception (guard skips null graphs)

- [x] T107 [P] [US1] Add to `backend/tests/integration/test_elements.py`: assert
  `GET /elements?has_aliases=true` returns only elements that belong to at least one
  `AliasGroupMember` row; assert `GET /elements?has_mappings=true` returns only elements
  that appear in at least one active `MappingInput` or `MappingFunction.output_element_id`
  row; create a control element with no aliases/mappings and confirm it is absent from
  both filtered results

- [x] T108 Run `cd backend && docker compose run --rm test pytest tests/contract/test_elements_contract.py tests/contract/test_supersede_element_contract.py tests/integration/test_curation_workflow.py tests/integration/test_elements.py tests/unit/test_semantic_graph.py -v --tb=short` to confirm all Phase 9 tests pass; run `uv run ruff check src/ && uv run ruff format --check src/`; record results

---

## Notes

- **TDD**: Tests MUST fail before implementation begins — Constitution Principle II (NON-NEGOTIABLE)
- **Persistent URIs**: `mint_element_uri`, `mint_mapping_uri`, `mint_schema_uri` in `core/uri.py` (T013) use `settings.undata_base_url`; URI stored in DB at creation, **never updated** — services must not include `uri` in update logic
- **Actor identity**: Always derived from validated Bearer token (never from request body); `AuditService.record` receives `actor_id: UUID` (FK to UserProfile), never a plain string; `AuditLogResponse` exposes both `actor_id` and `actor_display_name` (H1+H2 fix)
- **Semantic change policy (FR-027)**: A URI is stable for minor changes (typo/wording in description, constraints adjustments, required/multivalued flag changes, external_uri annotation additions). A **new URI** is required (via `POST /{id}/supersede`) when: `data_type` changes, `unit` changes (e.g., Celsius → Fahrenheit), subject entity changes (e.g., water → milk), measured property changes, or domain changes. Examples: `temperature_water_celsius` vs `temperature_water_fahrenheit` → different elements (unit differs); `temperature_water` vs `temperature_milk` → different elements (entity differs); "age in years" description typo fix → same element, new version only
- **`semantic_graph` JSONB**: Per DataElementVersion — `entities` (label, type, role, optional external_uri), `property`, `unit` (label, symbol, optional external_uri), `relations`, `domain`, `range_type`, `context`. `unit.label` is denormalized to `data_element_version.unit TEXT` (B-tree indexed for unit-based filtering). Ontology references SHOULD use PATO/CHEBI/QUDT/OBI/schema.org URIs
- **Supersession**: `POST /elements/{id}/supersede` + `POST /schemas/{id}/supersede` create semantically distinct replacements in a single transaction; old entity gets `superseded_by = new.id`, `deleted_at` set; new entity gets `supersedes = old.id` in response; both audit entries share same transaction; attempting to supersede an already-superseded entity returns 409 (T074, T077)
- **Nested schemas**: `DataElementChild` join table; parent must have `data_type="object"` or `"array"`; children keep independent URIs; `GET /elements/{id}` eagerly loads children
- **DynamicSchema URI stability**: `DynamicSchema.uri` is assigned once at creation (T045) and is NEVER changed even after `PUT /schemas/{id}` membership updates
- **Cycle detection**: Two-layer — DFS (T053, optimistic) + advisory lock + CTE (T056, race-safe); alias identity mappings created via `MappingService.create` (T058) — cycle detection always runs; URI minting also always runs
- **Embeddings**: Generated at element create (T035) and update (T038); `SimilarityService` (T054) queries them for alias detection (T059)
- **Token cache**: `cachetools.TTLCache` in-process; 5-min TTL = max revocation propagation lag; evicted on explicit revocation (T023)
- **RBAC + ReBAC**: `require_role` for global; `require_source_access` for source-scoped override; both in `services/authz.py` (T026); tested in unit tests (T021, T068)
- **Two-tier architecture**: Source space (BIDS/DANDI/NWB/openMINDS — one `SchemaSource` row each, elements ingested verbatim) + Undata canonical space (pre-seeded `SchemaSource name="undata"` in T017 lifespan, idempotent `ON CONFLICT DO NOTHING`). Curators create canonical elements under the undata source after cross-source alias detection (`POST /aliases/detect?cross_source_only=true`) confirms semantic equivalence. Source elements are never auto-merged; downstream consumers use undata elements and DynamicSchemas, and trace back to source representations via mappings (`GET /mappings?target_element_id=<undata-id>`)
- **`cross_source_only` filter** (T059): Passed in `AliasDetectRequest` request body (not URL query param); when `True`, `AliasGroupService.detect` filters result pairs to those where the two elements belong to different `SchemaSource` rows. Each pair carries `semantic_graph_overlap: SemanticGraphOverlap` (property_match: bool, unit_match: bool, entity_labels_match: bool, domain_match: bool | None) computed from current version `semantic_graph` JSONB. `domain_match` is `null` when `domain` is absent from both elements' graphs. Tested in T051 (contract), T083 (integration)
- **`VECTOR(384)`**: Requires pgvector — T012 runs `CREATE EXTENSION IF NOT EXISTS vector` first
- **`UNDATA_BASE_URL`**: Configurable via `settings.undata_base_url`; defaults to `http://localhost:8002` in dev, should be set to production domain in prod deployment
- **keycloak/realm-export.json** (T006): Required by docker-compose; without it Keycloak container fails to bootstrap realm; must be created before `docker compose up keycloak`

---

## Phase 10: User Story 7 — Unit Standardization (cmixf + QUDT)

**Goal**: Validate unit symbols using cmixf-12 grammar; auto-resolve QUDT URIs from a bundled TTL vocabulary; expose unit coverage endpoints. Enrichment is non-blocking — elements are always created; failures surfaced via flags.

**Prerequisites**: US1 (element create/update pipeline must exist); Python 3.14 + uv in all environments.

**Independent Test**: POST an element with `semantic_graph.unit = {label: "year", symbol: "a"}` → response includes `unit.cmixf_valid` (bool) and `unit.external_uri` (QUDT URI or null) and `unit.qudt_unresolvable` (bool). POST with `symbol: "kg"` → `cmixf_valid=true`, `external_uri` non-null. POST with `symbol: "???"` (invalid) → `cmixf_valid=false`. GET `/units` returns paginated list of unit symbols. GET `/units/unresolvable` returns only elements with `qudt_unresolvable=true`.

- [x] T091 Update `backend/Dockerfile` to use Python 3.14 base image (`python:3.14-slim`) and install `uv`; add `COPY data/ data/` to ensure `data/qudt/` is bundled; replace all `pip install` with `uv sync --frozen`
- [x] T092 Update `backend/pyproject.toml`: change `requires-python = ">=3.12"` to `>=3.14`; add `rdflib>=7.0` and `cmixf>=0.2` to `[project.dependencies]`; add `pytest-benchmark>=4.0` to `[project.optional-dependencies.dev]` if not already present
- [x] T093 Download QUDT v3.1.x vocabulary file to `backend/data/qudt/VOCAB_QUDT-UNITS-ALL.ttl` (fetch from `https://raw.githubusercontent.com/qudt/qudt-public-repo/main/vocab/unit/VOCAB_QUDT-UNITS-ALL.ttl`); verify file is ~3MB and contains `qudt:Unit` triples
- [x] T094 [P] Create `backend/tests/unit/test_unit_resolution.py`: unit tests for `UnitResolutionService.resolve()` — (a) `resolve(label="kilogram", symbol="kg")` → `qudt_uri` non-null, `cmixf_valid=True`, `qudt_unresolvable=False`; (b) `resolve(label="year", symbol="a")` → `qudt_uri` non-null (QUDT YR via label lookup), `cmixf_valid` is bool; (c) `resolve(label="degree Celsius", symbol="oC")` → SYMBOL_OVERRIDES match → `external_uri` = QUDT DEG_C URI; (d) `resolve(label="unknown_unit_xyz", symbol="???_invalid")` → `cmixf_valid=False`, `qudt_unresolvable=True`, `qudt_uri=None`; (e) `resolve(label=None, symbol=None)` → `cmixf_valid=None`, `qudt_unresolvable=False`; (f) `list_known()` returns list with `len > 2000` (sanity-check TTL loaded); all tests import `UnitResolutionService` directly without FastAPI app context
- [x] T095 [P] Create `backend/tests/contract/test_units_contract.py`: assert `GET /units` returns 200 with `PaginatedList` envelope (`total`, `limit`, `offset`, `items`); assert each item has fields `label` (str | null), `symbol` (str | null), `cmixf_valid` (bool | null), `qudt_uri` (str | null), `qudt_unresolvable` (bool), `element_count` (int ≥ 1); assert `GET /units?limit=5` respects pagination; assert `GET /units/unresolvable` returns 200 with `PaginatedList` where every item has `qudt_unresolvable=true`; assert unauthenticated GET returns 200 (read-only endpoint)
- [x] T096 [P] [US7] Update `backend/src/models/schemas.py` — add `cmixf_valid: bool | None = None` and `qudt_unresolvable: bool = False` to `SemanticGraphUnit` Pydantic model; these fields are server-populated (clients MAY omit them; server always overwrites on create/update); update `DataElementResponse` serialization to include enriched unit fields
- [x] T097 [US7] Create `backend/src/services/units.py` — `UnitResolutionService` singleton: (1) `__init__(ttl_path: str)` loads QUDT TTL via `rdflib.Graph().parse(ttl_path, format="turtle")`; builds three dicts: `by_ucum_code: dict[str, str]` from `qudt:ucumCode` literals, `by_symbol: dict[str, str]` from `qudt:symbol` literals (lowercase key), `by_label: dict[str, str]` from `rdfs:label` literals (lowercase key); applies `SYMBOL_OVERRIDES = {"oC": "DEG_C", "Ohm": "OHM", "o": "DEG", "bit": "BIT"}` as pre-lookup aliases; (2) `resolve(label: str | None, symbol: str | None) -> UnitResolutionResult`: multi-pass — try `by_ucum_code[symbol]`, then `by_symbol[symbol.lower()]`, then SYMBOL_OVERRIDES, then `by_label[label.lower()]`; validates symbol via `cmixf.parse(symbol)` if symbol provided (sets `cmixf_valid`); returns `UnitResolutionResult(qudt_uri, qudt_unresolvable, cmixf_valid)`; (3) `list_known() -> list[dict]` returns all QUDT units as `[{label, symbol, qudt_uri}]`; uses `get_logger`
- [x] T098 [US7] Update `backend/src/services/elements.py` — in `ElementService.create()` and `ElementService._create_version()` (or `update()`): after validating payload, if `payload.semantic_graph and payload.semantic_graph.unit` call `unit_service.resolve(label=unit.label, symbol=unit.symbol)`; set `unit.external_uri = result.qudt_uri`; set `unit.cmixf_valid = result.cmixf_valid`; set `unit.qudt_unresolvable = result.qudt_unresolvable`; inject `unit_service: UnitResolutionService` as a FastAPI Depends parameter (or pass from router layer); resolution is non-blocking — element is always created regardless of result
- [x] T099 [US7] Create `backend/src/api/v1/units.py`: router `prefix="/units"` — `GET /` (unauthenticated; query params: `limit: int = 50`, `offset: int = 0`; queries `DataElementVersion` JSONB for distinct unit nodes with `qudt_unresolvable != true`, aggregated with `element_count`; returns `PaginatedList[UnitSummary]` where `UnitSummary` has `label: str | None`, `symbol: str | None`, `cmixf_valid: bool | None`, `qudt_uri: str | None`, `qudt_unresolvable: bool`, `element_count: int`); `GET /unresolvable` (unauthenticated; shortcut — same query filtered to `qudt_unresolvable=true` units, each item includes `element_ids: list[UUID]`)
- [x] T100 [US7] Update `backend/src/main.py` lifespan: initialize `UnitResolutionService(ttl_path=settings.qudt_ttl_path)` at startup and store in `app.state.unit_service`; add `qudt_ttl_path: str = "data/qudt/VOCAB_QUDT-UNITS-ALL.ttl"` to `backend/src/core/config.py` Settings class; register `units_router` with `app.include_router(units_router, prefix="/api/v1")`; add FastAPI dependency `get_unit_service(request: Request) -> UnitResolutionService` in `units.py` that reads from `request.app.state`
- [x] T101 Run `cd backend && docker compose build test && docker compose run --rm test pytest tests/unit/test_unit_resolution.py tests/contract/test_units_contract.py -v --tb=short`; then run full suite `pytest tests/ -v --tb=short`; run `uv run ruff check src/ && uv run ruff format --check src/`; confirm all pass; record results
