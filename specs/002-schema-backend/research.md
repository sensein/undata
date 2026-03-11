# Research: Schema Backend Service
**Feature**: 002-schema-backend | **Date**: 2026-03-07

---

## Decision 1: Storage Backend

**Decision**: PostgreSQL 16 as the primary data store.

**Rationale**:
- The data model has a strong relational structure: elements reference schema sources,
  mappings reference multiple elements (FK relationships), audit entries reference any
  record. JSONB columns handle flexible metadata (allowed_values, function parameters)
  without sacrificing queryability.
- PostgreSQL's `WITH RECURSIVE` CTEs enable transitive cycle detection in the mapping
  DAG at write time without a separate graph database.
- Full-text search via `tsvector`/`GIN` index provides keyword search over element
  names and descriptions sufficient for the expected corpus size (≤200k elements).
- SQLite is rejected: lacks row-level locking needed for concurrent write safety and
  lacks `WITH RECURSIVE` for complex graph queries.
- Neo4j/ArangoDB are rejected: add operational complexity without clear benefit; the
  mapping graph is a DAG (not a property graph) and is well-served by adjacency tables.

**Alternatives considered**:
- SQLite: eliminated due to limited concurrency and missing recursive query support.
- Neo4j: overkill for a DAG with ~10k edges; adds separate operational dependency.
- Elasticsearch: considered for search; rejected as primary store — use PG full-text
  first, add ES if performance targets are not met.

---

## Decision 2: Python ORM and Async Stack

**Decision**: SQLAlchemy 2.x (async) with Pydantic v2 models, managed separately.
Alembic for schema migrations.

**Rationale**:
- SQLAlchemy 2.x async (`asyncpg` driver) integrates cleanly with FastAPI's async
  request handling and provides fine-grained control over complex queries (recursive
  CTEs, window functions).
- SQLModel (SQLAlchemy + Pydantic combined) was considered but rejected: it adds a
  layer that obscures complex join patterns and lags behind both upstream projects
  in incorporating new features. Keeping ORM models and API models separate is cleaner
  at this scale.
- Tortoise-ORM is rejected: smaller ecosystem, less mature for recursive queries.
- **Migration tooling**: Alembic with CalVer-tagged migration files
  (`2026_03_0_initial_schema.py`).

---

## Decision 3: Versioning / Audit Trail Pattern

**Decision**: Application-level versioning with explicit `*_version` tables and an
`audit_log` table. No database triggers.

**Rationale**:
- Trigger-based history (e.g., PostgreSQL temporal tables) is hard to introspect and
  test from Python; application-level history is transparent and testable.
- Pattern: each mutable entity (`data_element`, `mapping_function`) has a companion
  `*_version` table. On every write, a new version row is inserted; the parent row
  carries a `current_version_id` FK pointing at the latest version. Deletes set a
  `deleted_at` timestamp rather than removing rows.
- `audit_log` captures operation type, actor, timestamp, and a JSON diff for every
  mutation. Written in the same transaction as the entity change.
- Optimistic concurrency: each entity carries a `version_num` column; updates must
  supply the last-known `version_num` or receive a 409 Conflict.

---

## Decision 4: Cycle Detection in Mapping DAG

**Decision**: Two-layer approach: in-memory DFS (optimistic, fast) + PostgreSQL
advisory lock with a `WITH RECURSIVE` CTE inside the same transaction (race-safe).

**Rationale**:
- **Optimistic layer**: At write time, fetch the existing adjacency list as a Python
  list of (input, output) pairs. Run DFS from the proposed target node; if it can
  reach any proposed source node, reject immediately with a clear error. Covers 99.9%
  of cases and is testable as a pure Python function.
- **Race-safe layer**: TOCTOU risk — two concurrent insertions could each pass the
  optimistic check and together create a cycle. Mitigate with a PostgreSQL advisory
  lock (`pg_advisory_xact_lock`) scoped to the mapping DAG, held for the duration of
  the insert transaction. Inside the lock, re-verify with a `WITH RECURSIVE` CTE.
  The advisory lock serializes mapping insertions without locking unrelated tables.
- At ≤10k edges, the full adjacency fetch + DFS + advisory lock completes in <10ms.
- For scale beyond 50k edges, a materialized transitive closure table can be
  introduced as a future enhancement.

---

## Decision 5: Semantic Similarity for Alias Detection

**Decision**: `sentence-transformers` with `all-MiniLM-L6-v2`, cosine similarity
threshold of 0.88 for `skos:exactMatch`, 0.75–0.88 for `skos:closeMatch`, gated by
exact type and cardinality compatibility.

**Rationale**:
- Pipeline: (1) exact normalized-name match → identity alias; (2) type + cardinality
  compatible → candidate pair; (3) description cosine similarity ≥ 0.88 → alias.
- `all-MiniLM-L6-v2` (22M parameters, 384-dim embeddings) is fast enough to embed
  200k elements in under 5 minutes on CPU and widely used for short-text similarity
  in schema harmonization tasks (LinkML, OMOP CDM, BioPortal mapping tools).
- Threshold of 0.88 balances recall and precision for schema harmonization; configurable
  via env var `ALIAS_SIMILARITY_THRESHOLD`.
- TF-IDF and edit distance are rejected for description comparison: they miss semantic
  synonyms (e.g., "participant age" vs. "subject age").
- SSSOM (Simple Standard for Sharing Ontological Mappings) is adopted for recording
  alias relationships: predicates `skos:exactMatch` for identity aliases,
  `skos:closeMatch` for high-similarity non-identical pairs. SSSOM TSV format used
  for export.

---

## Decision 6: API Framework

**Decision**: FastAPI 0.111+ with Pydantic v2 request/response models.

**Rationale**:
- FastAPI's async request handling pairs naturally with SQLAlchemy 2.x async.
- Automatic OpenAPI 3.1 spec generation from Pydantic models gives us a machine-
  readable contract for downstream services (migration API, frontend).
- Pydantic v2's performance improvements (Rust core) are significant for high-volume
  serialization of large element collections.
- `httpx` (async) used for integration tests against the live FastAPI test app.

---

## Decision 7: OIDC / Keycloak Federation

**Decision**: Keycloak (self-hosted) as OIDC/OAuth2 federation hub; `authlib` for FastAPI
OIDC callback handling; JWT RS256 validated against Keycloak's JWKS endpoint.

**Rationale**:
- Keycloak natively federates Globus (OIDC), GitHub (OAuth2 social login), and
  InCommon/Shibboleth (SAML 2.0 identity brokering) behind a single OIDC interface,
  eliminating per-IdP custom logic in the backend.
- `authlib` provides first-class async OIDC/OAuth2 support including JWKS caching, token
  refresh, and provider auto-discovery — `python-jose` is a JWT-only library with no
  OIDC protocol support; FastAPI's built-in security utilities lack callback state
  management and are not suitable for federated login flows.
- RS256 (asymmetric) with Keycloak's JWKS endpoint is preferred over HS256: Keycloak
  publishes its public key via `/.well-known/openid-configuration` → `/certs`; the
  backend fetches and caches it once, validating tokens offline. HS256 requires shared
  secret distribution and is unsuitable for federation.
- Flow: User → Keycloak login (chooses Globus/GitHub/InCommon) → OIDC authorization code
  → `GET /auth/callback` → authlib exchanges code for token → JWT validated → `UserProfile`
  upserted from `sub` + `iss` claims → session established.

**Alternatives considered**:
- Auth0: rejected — cloud-only SaaS, vendor lock-in, adds cost.
- python-jose: rejected — JWT library only; no protocol, no JWKS caching, no refresh.
- Per-IdP custom integration: rejected — duplicates protocol logic for each provider.

---

## Decision 8: RBAC + ReBAC Authorization

**Decision**: Four-tier RBAC (`admin > curator > contributor > viewer`) stored in a
`user_role` join table; source-scoped ReBAC in a `source_membership` table; permission
checks via FastAPI dependency injection at the router layer; in-request cache for role
lookups; no external policy engine.

**Rationale**:
- **Four-tier RBAC**: `admin` — full access + user/token management; `curator` — full
  element/mapping/alias CRUD; `contributor` — create elements, propose (not register)
  mappings; `viewer` — read-only (all GET endpoints unauthenticated or viewer-level).
  Reflects neuroscience data stewardship roles (system admin → data curator → data
  contributor → researcher).
- **ReBAC override**: `source_membership(user_id, source_id, role: owner|contributor)`
  grants effective curator-equivalent write access on elements from that source, computed
  as `max(global_role, source_role)` at request time. Avoids requiring every research
  group member to have a global curator role.
- **Router-layer dependencies**: `require_role(min_role)` and `require_source_access(
  source_id, min_role)` are FastAPI `Depends` callables injected into route functions.
  Placing checks in the router layer makes the authorization boundary explicit and
  independently testable; service-layer checks are avoided to prevent accidental bypass.
- **No external policy engine**: OPA/Casbin add operational dependency and configuration
  language complexity for a four-role system; simple Python enum comparison is sufficient
  at ≤10k users and ≤10k sources.

**Alternatives considered**:
- Open Policy Agent (OPA): rejected — adds separate service dependency, Rego DSL unfamiliar.
- Casbin: rejected — synchronous library, poor async integration, overkill for 4 roles.
- Decorator-based checks: rejected — easily bypassed when service methods called outside routes.

---

## Decision 9: API Key Token Storage

**Decision**: `secrets.token_hex(32)` (256-bit entropy); SHA-256 hash stored in
`api_key.token_hash` (B-tree UNIQUE index); in-process LRU cache (TTL 5 min) avoids
per-request DB round-trip; acceptable revocation propagation lag ≤ 5 minutes.

**Rationale**:
- 256-bit hex token is returned to the user once at issuance; no recovery path.
  Sufficiently large entropy space prevents brute-force enumeration.
- SHA-256 (unsalted) is appropriate for tokens of this entropy — salting is needed for
  low-entropy secrets (passwords), not for 256-bit randoms. Storing the hash prevents
  token reuse if the DB is compromised.
- B-tree UNIQUE index on `token_hash` supports O(log N) equality lookup for every
  authenticated request.
- In-process LRU cache (Python `cachetools.TTLCache`) with 5-minute TTL: cache key is
  the SHA-256 hash; cache value is `(user_id, revoked_at)`. Trades minor revocation lag
  for eliminating a DB query on every API call. Cache is per-process; in multi-replica
  deployments, revocation lag is at most 5 minutes across all replicas.
- Bcrypt rejected: bcrypt's intentional slowness is for password guessing resistance, not
  needed for 256-bit tokens. Redis rejected: adds operational dependency; in-process cache
  is sufficient at expected request volumes. JWT as API key rejected: revocation still
  requires a DB blacklist, and adds token size / parsing overhead without benefit.

---

---

## Decision 10: Persistent URI Minting Strategy

**Decision**: HTTP URI with configured base URL prefix (`UNDATA_BASE_URL`), derived
deterministically from the entity's UUID. Pattern: `{BASE_URL}/elements/{uuid}`,
`{BASE_URL}/mappings/{uuid}`, `{BASE_URL}/schemas/{uuid}`.

**Rationale**:
- HTTP URIs are dereferenceable: a GET request on the URI returns the resource, aligning
  with Linked Data best practices (FAIR principles, W3C PROV-O).
- UUID-based suffix guarantees global uniqueness without coordination; deterministic
  generation avoids a separate URI-minting service.
- The base URL is configurable via `UNDATA_BASE_URL` environment variable, allowing the
  URI to reflect the deployment domain in production (e.g., `https://undata.io`) while
  using `http://localhost:8002` in development without changing stored data.
- URIs are stored in the DB as TEXT (immutable); they are never recomputed after creation.
- W3C PROV-O and schema.org patterns are compatible with this scheme via HTTP content
  negotiation: accept `application/ld+json` to receive a JSON-LD representation with
  `@id` set to the URI.

**Alternatives considered**:
- URN-based (`urn:undata:element:{uuid}`): Not dereferenceable; requires a separate
  resolver. Rejected in favour of HTTP URIs.
- DOI-style minting: Requires external registration and adds operational dependency;
  premature at this stage. May be layered on top later.
- CURIE / prefix registry: Useful for display but does not replace the need for a base
  HTTP URI; can be added as an alias field in future.

---

## Decision 11: Nested Schema and DynamicSchema Persistence

**Decision**: `DataElementChild` join table for nesting; `DynamicSchema` +
`DynamicSchemaElement` tables for dynamic schema composition. All three carry
independent UUIDs and URIs.

**Rationale**:
- Nesting is a structural relationship, not a versioned property: a join table
  (`parent_id`, `child_id`, `position`, `field_name`) is the simplest correct model.
  Child elements keep their own URIs; the parent-child link is traversable in O(depth)
  queries with a B-tree index on `parent_id`.
- `DynamicSchema` is a first-class object (not computed on-the-fly) so that its URI can
  be stable and stored in audit logs or external references. Schema membership changes
  bump `version_num` without changing the URI.
- `field_alias` in `DynamicSchemaElement` allows the same DataElement to appear under
  different names in different schema contexts (e.g., `age_years` in one schema,
  `subject_age` in another) without duplicating the underlying element or its URI.

**Alternatives considered**:
- Storing nesting as JSONB on `DataElementVersion`: breaks independent URIs for child
  elements and makes nesting hard to query. Rejected.
- Separate `NestedSchema` table distinct from `DynamicSchema`: unnecessary split; a
  DynamicSchema with nested elements (whose `data_type = "object"`) covers both cases.

---

## Decision 12: Semantic Graph Representation

**Decision**: Store a structured `semantic_graph` JSONB field on every `DataElementVersion`.
The graph encodes: `entities` (subject/object nodes with label, type, role, optional
`external_uri`), `property` (what is measured), `unit` (measurement unit with symbol and
optional `external_uri`), `relations` (named edges), `domain`, `range_type`, and `context`.
The `unit.label` field is also denormalised into a top-level `unit TEXT` column on
`DataElementVersion` for fast B-tree indexed filtering without JSONB path queries.

**Rationale**:
- A pure text description of "temperature of water in Celsius" is ambiguous and opaque to
  programmatic comparison. A structured graph makes the discriminating dimensions (entity,
  property, unit) explicit and queryable.
- JSONB is sufficient at the expected scale (~100k elements); there is no requirement to
  run SPARQL or full RDF graph traversal. A GIN `jsonb_path_ops` index supports label
  lookups efficiently.
- `external_uri` fields are optional but enable future alignment with PATO, CHEBI, QUDT,
  OBI, and schema.org without mandating an external triple store today.
- Embedding-based alias detection (SentenceTransformer) continues to operate on `name +
  description` text; the semantic graph provides a complementary structured layer for
  unit/entity disambiguation that embeddings alone cannot reliably separate.

**Alternatives considered**:
- Separate `unit` and `subject` tables with FKs: adds join overhead and schema migration
  cost for each new semantic dimension; JSONB with a denormalised `unit` column is simpler
  and sufficient.
- External RDF store (Blazegraph, Virtuoso): operational complexity not warranted at this
  scale; deferred until corpus exceeds 1M elements with complex graph queries.

---

## Decision 13: Semantic Change Policy and URI Supersession

**Decision**: A URI represents a **semantic identity**. When a DataElement or DynamicSchema
undergoes a semantic change — defined as any modification to `data_type`, `unit`,
`subject entity`, `measured property`, or `domain` — a new entity with a new URI is
created via `POST /{id}/supersede`. The old entity is soft-deprecated with `superseded_by`
pointing to the new entity. Minor updates (description wording, typo fixes, constraint
bounds, `required`/`multivalued` flags) are handled as ordinary version updates with no
URI change.

**Canonical examples**:
- `temperature_water_celsius` vs `temperature_water_fahrenheit` → **different elements**
  (unit differs); a MappingFunction expressing the `°C → °F` conversion SHOULD be
  registered but they MUST NOT share a URI.
- `temperature_water` vs `temperature_milk` → **different elements** (subject entity
  differs); they share property and unit but represent distinct physical measurements.
- `subject_age` with description corrected from "age in years" to "age of the research
  subject in years" → **same element** (minor wording fix, no semantic change); new
  `DataElementVersion` only.

**Rationale**:
- Immutable URIs that outlive semantic drift would cause downstream consumers to silently
  receive an element with a different meaning than the one they referenced. Supersession
  makes the discontinuity explicit and auditable.
- `superseded_by` as a self-referential FK is the simplest model that supports full
  lineage traversal without a separate provenance table.
- The `supersede_reason` required field forces curators to document why a semantic change
  was made, feeding into the audit log and enabling future governance queries.

**Alternatives considered**:
- Flag-based approach (add `is_deprecated: bool` without lineage): does not capture the
  relationship between old and new URI; rejected.
- Automatic semantic-change detection from the `semantic_graph` diff: useful as a warning
  signal but must not replace curator judgement (e.g., adding an ontology URI to an entity
  node changes the graph but is not a semantic change). Decision is always curator-made;
  the system provides the diff as evidence.

---

## Decision 14: Unit Symbol Standardization — cmixf + QUDT

**Date**: 2026-03-09

**Decision**: Use cmixf-12 grammar for unit symbol validation at input time and QUDT (Quantities, Units, Dimensions and Types) as the authoritative ontology for semantic resolution. Both operate as server-side enrichment; neither is a blocking API requirement for symbol format.

**Background**: The existing `SemanticGraphUnit` model stores `label`, `symbol`, and `external_uri`. The `external_uri` field is documented as SHOULD reference QUDT when available, but resolution was manual and not enforced. This decision standardizes both validation and resolution.

### cmixf (sensein/cmixf) — Role: Input Symbol Validation

**What it is**: A Python parser/validator for the CMIXF-12 specification (Currency and Metric Interchange Format). It validates whether a quantity expression (number + unit) conforms to a precise grammar. The library exposes a `CMIXFParser` that parses compound expressions like `1m/s^2`, `1J/(kg.K)`, `1nV/Hz^(1/2)`.

**Scope**: 42 base unit symbols (SI units + accepted non-SI). Supports decimal prefixes (`m`=milli, `k`=kilo, `n`=nano, `u`/`µ`=micro), binary prefixes (`Ki`, `Mi`, `Gi`, `Ti`, `Pi`, `Ei`), and compound expressions.

**Key symbols** (grouped by prefix restriction):
- Both prefixes: `A Bq C F Gy H Hz J K N Ohm/Ω Pa S Sv T V W Wb bit cd eV g kat lm lx m mol s`
- Decimal-multiple only: `Bd B r t`
- Decimal-submultiple only: `L Np oC/°C o/° rad sr`
- No prefix: `dB d h min u`

**Notable**: cmixf does NOT define `yr` or `year` — QUDT `unit:YR` (symbol `a`, ucumCode `a`) is used for years. Input `yr` would fail cmixf validation but can still be QUDT-resolved via label lookup.

**Library**: `cmixf==0.2.0` on PyPI. Dependencies: `sly` (lexer) and `click` (CLI).

**Role in this service**: Validate `symbol` in `SemanticGraphUnit` at write time. Store `cmixf_valid: bool | None` on the unit node — `None` means no symbol was provided; `true`/`false` indicates parse result.

### QUDT — Role: Ontology URI Resolution

**What it is**: A formal RDF/OWL ontology (originally NASA, now QUDT.org nonprofit) defining ~2,897 units with full semantic metadata: dimension vectors, quantity kinds, conversion multipliers, UCUM codes, cross-references to DBpedia/Wikidata.

**URI pattern**: `http://qudt.org/vocab/unit/{LocalName}` — e.g., `http://qudt.org/vocab/unit/KiloGM`, `http://qudt.org/vocab/unit/DEG_C`, `http://qudt.org/vocab/unit/YR`.

**Key fields per unit entry**:
```turtle
unit:KiloGM
  qudt:symbol "kg" ;      # display symbol (may be Unicode)
  qudt:ucumCode "kg" ;    # ASCII UCUM code (primary lookup key)
  qudt:hasQuantityKind quantitykind:Mass ;
  qudt:conversionMultiplier 1.0 ;
  rdfs:label "Kilogram"@en ;
```

**Source file**: `VOCAB_QUDT-UNITS-ALL.ttl` (~3MB, 65,586 lines) — pinned release from `qudt/qudt-public-repo` on GitHub.

**Python library**: `rdflib>=7.0` (pure Python, no C extensions). Load TTL once at startup, build in-memory dict indexed by ucumCode + symbol + label.

**Resolution strategy (multi-pass)**:
1. Try `qudt:ucumCode` match (most reliable, ASCII)
2. Try `qudt:symbol` match (may be Unicode)
3. Try `rdfs:label` English match (fallback for natural-language labels like "year", "degree Celsius")
4. If no match → `qudt_unresolvable = true`

### cmixf → QUDT Symbol Mapping (key cases)

| cmixf symbol | QUDT local name | QUDT symbol | ucumCode | Notes |
|---|---|---|---|---|
| `oC` / `°C` | `DEG_C` | °C | Cel | Both ASCII and Unicode accepted |
| `Ohm` / `Ω` | `OHM` | Ω | Ohm | ASCII→URI direct override |
| `o` / `°` | `DEG` | ° | deg | Angle degree (not OCTET) |
| `bit` | `BIT` | b | bit | QUDT display symbol differs |
| `r` | `REV` | rev | r | Symbol mismatch: store `unit:REV`, note |
| `g` | `GM` | g | g | Local name uses GM, not G |
| `s` | `SEC` | s | s | Local name uses SEC |
| `d` | `DAY` | d | d | Not DARCY (permeability) |
| `h` | `HR` | h | h | Hour |
| `L` | `L` | L | L | Litre |
| `u` | `U` | u | u | Unified atomic mass unit (not AMU) |

**Note on year**: cmixf has no year symbol. QUDT `unit:YR` has symbol `a` and ucumCode `a`. Labels "year", "yr", "a" all resolve to `unit:YR`.

**Prefix construction for compound QUDT URIs**:
`m`→`Milli`, `k`→`Kilo`, `n`→`Nano`, `u`/`µ`→`Micro`, `M`→`Mega`, `G`→`Giga`, `p`→`Pico`, `f`→`Femto`, `a`→`Atto`, `Ki`→`Kibi`, `Mi`→`Mebi`, `Gi`→`Gibi`, `Ti`→`Tebi`, `Pi`→`Pebi`, `Ei`→`Exbi`.

Example: `ms` → base `s`→`SEC`, prefix `m`→`Milli` → `unit:MilliSEC`.

### Common Neuroscience Units

| Concept | cmixf expression | QUDT URI | QUDT symbol |
|---|---|---|---|
| Age in years | *(no cmixf symbol — use label "year")* | `unit:YR` | a |
| Age in months | *(use label "month")* | `unit:MO` | mo |
| Body weight | `kg` | `unit:KiloGM` | kg |
| Temperature (Celsius) | `oC` or `°C` | `unit:DEG_C` | °C |
| EEG voltage | `mV` | `unit:MilliV` | mV |
| Spike voltage | `uV` | `unit:MicroV` | μV |
| Time (ms) | `ms` | `unit:MilliSEC` | ms |
| Frequency | `Hz` | `unit:HZ` | Hz |
| Patch current | `nA` | `unit:NanoA` | nA |
| Membrane resistance | `MOhm` | `unit:MegaOHM` | MΩ |
| Membrane capacitance | `pF` | `unit:PicoFARAD` | pF |
| Concentration | `umol/L` | `unit:MicroMOL-PER-L` | μmol/L |
| Angular velocity | `rad/s` | `unit:RAD-PER-SEC` | rad/s |

### Alternatives Considered

- **UCUM-only**: UCUM (Unified Code for Units of Measure) provides ASCII codes but lacks semantic metadata (quantity kinds, dimension vectors, conversion factors). QUDT ucumCode is used as a bridge, so UCUM compatibility is preserved while gaining QUDT's richer ontology.
- **Units ontology (UO)**: Simpler and widely used in bioinformatics (OBO Foundry), but far fewer units and no conversion metadata. QUDT preferred for its completeness and maintained status.
- **Pint**: Python unit library with its own registry. Rejected — adds a runtime parsing engine that duplicates cmixf's role; Pint does not emit ontology URIs.
- **QUDT SPARQL endpoint (live queries)**: Rejected for production use — adds latency and availability dependency. Bundle TTL locally.

**Rationale for cmixf + QUDT combination**: cmixf provides a compact, well-defined grammar for expressing unit quantities in a neutral interchange format. QUDT provides the semantic backbone connecting symbols to formal ontology terms, enabling downstream reasoning. Together they cover: (1) input validation, (2) canonical symbol normalization (Unicode ↔ ASCII), (3) ontology URI resolution, (4) identification of gaps (units with no QUDT match).

---

## Technology Summary

| Concern | Choice | Version |
|---------|--------|---------|
| Language | Python | 3.14 |
| API framework | FastAPI | 0.111+ |
| ORM | SQLAlchemy async | 2.x |
| DB driver | asyncpg | 0.29+ |
| Migrations | Alembic | 1.13+ |
| Validation | Pydantic | v2 |
| Database | PostgreSQL | 16 |
| Similarity | sentence-transformers | 3.x (all-MiniLM-L6-v2) |
| Mapping format | SSSOM + custom registry | - |
| OIDC / federation | authlib + Keycloak | authlib 1.x |
| JWT validation | authlib (RS256 + JWKS) | - |
| Identity federation hub | Keycloak | 24+ |
| Token storage | SHA-256 hash in PostgreSQL | - |
| Token cache | cachetools TTLCache (in-process) | 5.x |
| Authorization | Custom RBAC + ReBAC (FastAPI Depends) | - |
| Persistent URI scheme | HTTP URIs (`UNDATA_BASE_URL`/{type}/{uuid}) | - |
| Dynamic schema | DynamicSchema + DynamicSchemaElement tables | - |
| Semantic graph | JSONB `semantic_graph` on DataElementVersion | - |
| Semantic change / supersession | `superseded_by` FK + `POST /{id}/supersede` | - |
| Testing | pytest + pytest-asyncio + httpx | latest |
| Containerisation | Docker + Docker Compose | - |

