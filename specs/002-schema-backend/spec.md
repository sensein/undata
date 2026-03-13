# Feature Specification: Schema Backend Service

**Feature Branch**: `002-schema-backend`
**Created**: 2026-03-07
**Status**: Complete
**Last Updated**: 2026-03-12
**Input**: Persistent backend service that houses data elements and their mappings,
serving as the authoritative data store for the undata integration system.

---

## Clarifications

### Session 2026-03-12

- Q: How should an object-typed DataElement reference its schema structure? → A: `data_type="object"` elements carry a `schema_ref` FK to a `DynamicSchema` — the element's value is an instance of that schema. `DataElementChild` is retained for anonymous inline structures only; named schema references use `schema_ref`.
- Q: What provenance model should underpin change tracking? → A: PROV-O internal model; every mutation is a `prov:Activity` with `wasGeneratedBy`, `wasAssociatedWith`, and `used` relations stored internally; exposed via `GET /{resource}/{id}/provenance` returning JSON-LD.
- Q: Should the semantic graph be used to infer mapping function types? → A: Aliases MUST have identical semantic graphs (same entities/property/unit) and differ only in label/name — all aliases are `skos:exactMatch`. Non-identity mappings inferred from semantic graph patterns (e.g. same property+entity, different unit → unit-conversion) are attributed to the system agent, assigned `status="pending_curation"`, and flagged for human review before acceptance. If the caller provides an explicit `confidence_threshold` parameter, mappings meeting that threshold are auto-accepted without curation.
- Q: Should LinkML serve as the canonical internal schema language? → A: No — the backend model remains PostgreSQL-native and independent. LinkML is a supported import/export format (`GET /schemas/{id}/linkml`, `POST /schemas/import/linkml`). Roundtrip fidelity is tracked via `RoundtripResult`; known loss points (slot versioning, URI stability policy, PROV-O) are documented. Roundtrips that cannot be lossless are flagged explicitly.
- Q: What form should the system meta-model take? → A: A self-describing LinkML YAML (`docs/undata-metamodel.yaml`) defining all core concepts as LinkML classes/slots with `slot_uri`, `class_uri`, PROV-O annotations, and SKOS mappings. Generated artifacts (JSON Schema, Python dataclasses) produced via LinkML tools. A GitHub Actions workflow renders and publishes the meta-model docs alongside the JupyterBook.

### Session 2026-03-08

- Q: When does automated alias/similarity detection run, and what does its response look like? → A: On-demand only — a dedicated endpoint triggers similarity search and returns a paginated response; consistent with all other query endpoints in the service (no sync-on-create, no background job).
- Q: How is actor identity established for write operations? → A: Bearer token as API key — each token is issued to and associated with a specific individual (responsible bearer); the backend validates the token on every write and derives actor identity from it; actor identity is NOT accepted from the request body.
- Q: How are tokens issued and what authorization model governs access? → A: `api_key` table binds token hash to a `UserProfile`; initial identity comes from an external IdP federation hub (e.g., Keycloak federating Globus, GitHub, InCommon/SAML); a `UserProfile` is created on first successful external authentication; access control uses RBAC (global roles: admin, curator, contributor, viewer) combined with ReBAC (source-level ownership and membership relationships).
- Design note: Schemas are variable-name-based and nested; the same field name (e.g., `age`) appears in multiple participant contexts (human vs. animal) with different units and semantics — each is a distinct `DataElement` with its own persistent URI. Every variable (DataElement), every transformation (MappingFunction), and every dynamically constructed schema (DynamicSchema) MUST have a stable, globally unique, dereferenceable URI that persists across service restarts and version changes.

---

## System Model

The backend operates a **two-tier data architecture** that separates source-faithful
ingestion from canonical curation.

### Source Space

Elements ingested from BIDS, DANDI, NWB, openMINDS, and any other registered
`SchemaSource` are stored verbatim under that source. Their naming, types, and local
identifiers are preserved exactly as the source schema defines them. Source elements
are **never merged**, even if they are semantically equivalent across sources — `BIDS::age`
and `DANDI::age` are distinct `DataElement` records with distinct URIs, because they
originate from different authoritative sources with potentially different provenance.

### Undata Canonical Space

A special `SchemaSource` named `"undata"` is pre-seeded at service startup. It serves as
the authoritative cross-source vocabulary. Undata elements are **curated, not ingested**.
They represent the minimal set of semantically distinct concepts that unifies the source
spaces. Two source elements that measure the same thing (same entity, property, and unit)
map to **one** undata element via identity `MappingFunction`s. Two elements that differ
semantically (e.g. age in years vs. age in months) map to **separate** undata elements,
potentially connected by a conversion `MappingFunction`.

`DynamicSchema` objects intended for downstream use are composed from **undata elements**,
not source elements. Because the undata namespace is curated to be compact and internally
unambiguous, field names within such schemas are stable and collision-free.

### Human + Machine Curation Loop

The curation pipeline that seeds the undata space operates as follows:

```
1. Ingest source schemas  →  source DataElement records created under each SchemaSource
2. Curator calls POST /aliases/detect?cross_source_only=true
     →  system returns embedding-similarity + semantic_graph structural candidates
          across source elements from different schemas
3. Curator reviews each candidate pair:
     Semantically identical (same entity + property + unit)
       →  POST /elements  (source_id = undata)  →  canonical element created
       →  POST /mappings  (identity, sssom:exactMatch)  from each source element to it
     Semantically related but distinct (e.g. years vs. months)
       →  POST /elements  twice  (separate undata elements)
       →  POST /mappings  (conversion, sssom:narrowMatch or closeMatch)
     Not related  →  dismiss; no undata element created
4. DynamicSchema for downstream use composed from undata elements
```

The machine provides ranked candidates; the human makes all semantic decisions. The
alias detection system is the machine-side tool; the curation endpoints are the
human-side tool. Neither acts without the other.

### Compactness Principle

The undata space is kept as compact as possible: no two undata elements should have
the same `semantic_graph` fingerprint (same entity set + property + unit + domain).
The service **enforces this server-side** at element creation time: if a `POST /elements`
request targets `source_id = undata_source_id` and provides a `semantic_graph` whose
`(sorted entity labels, property.label, unit.label)` triple exactly matches an existing
active undata element, the server MUST reject the request with HTTP 409
`{"error": "semantic_duplicate", "existing_id": "...", "existing_uri": "..."}`.
Running `POST /aliases/detect` filtered to the undata source (`source_id={undata_id}`)
remains the mechanism for auditing near-duplicate compactness over time.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Persistent Data Element Storage (Priority: P1)

A platform administrator ingests neuroscience schemas from BIDS, DANDI, openMINDS,
and NWB. All normalized data elements, their metadata, and their provenance are durably
stored and survive service restarts. Any component in the system can retrieve a data
element by identifier, by source schema, or by keyword at any time.

**Why this priority**: Every other feature — the frontend explorer, the mapping registry,
the migration API — depends on a reliable, queryable store for data elements. Without
it nothing else can function.

**Independent Test**: After storing a set of data elements via the ingestion interface,
stop and restart the service, then retrieve those elements and confirm all metadata is
intact.

**Acceptance Scenarios**:

1. **Given** a normalized data element with name, type, description, cardinality,
   allowed values, and source provenance, **When** a client stores it, **Then** it is
   assigned a stable unique identifier and all fields are persisted without loss.

2. **Given** a stored data element, **When** the service is restarted, **Then** the
   element is still retrievable with all original metadata intact.

3. **Given** a bulk set of data elements from a single ingestion run, **When** stored,
   **Then** all elements can be retrieved individually by identifier or as a collection
   filtered by source schema.

4. **Given** a data element that already exists (same name and source schema), **When**
   an updated version is stored, **Then** the previous version is preserved in history
   and the current version is updated; no data is silently overwritten.

5. **Given** the element store, **When** a client queries by keyword against element
   names and descriptions, **Then** matching elements are returned ranked by relevance.

---

### User Story 2 — Mapping Registry (Priority: P2)

An integration engineer registers a mapping function between two data elements —
specifying the function signature, input slots, output slot, and any parameters —
and later retrieves, updates, or removes mappings from the registry. The registry
is the single source of truth for all declared element-level transformations including
auto-detected identity/alias mappings.

**Why this priority**: The mapping registry is the operational backbone for both the
migration API and the frontend. It must exist as a persistent, queryable store before
those features can be built.

**Independent Test**: Register a mapping function, restart the service, retrieve the
mapping, confirm all fields are intact, then delete it and confirm it is gone.

**Acceptance Scenarios**:

1. **Given** a function signature `target = f(input_a, input_b, params)` with valid
   references to stored data elements, **When** a client registers the mapping,
   **Then** it is stored with a unique identifier, linked to the relevant element
   records, and immediately queryable.

2. **Given** a registered mapping, **When** a client queries mappings by target element,
   **Then** all mappings that produce that element are returned.

3. **Given** a registered mapping, **When** a client queries mappings by source element,
   **Then** all mappings that consume that element as an input are returned.

4. **Given** an attempt to register a mapping that would create a circular dependency
   (direct or transitive), **When** the client submits it, **Then** the service rejects
   it with a clear error describing the cycle.

5. **Given** a curator has run alias detection and confirmed two elements as semantically
   identical, **When** they register an alias group for those elements, **Then** identity
   `MappingFunction` records are created for each pair, flagged as `function_type: identity`
   in the registry, and the group is queryable as an alias group.

6. **Given** a registered mapping, **When** a client updates its function expression
   or parameters, **Then** the previous version is preserved in history and the update
   is recorded with a timestamp and author.

---

### User Story 3 — Audit Trail and Provenance (Priority: P3)

A data steward needs to understand how the system's knowledge base evolved: which
elements were added, changed, or removed, when, and by whom. Every mutation to data
elements and mappings is traceable through an audit log.

**Why this priority**: Provenance and auditability are required for scientific
reproducibility and for diagnosing integration errors. They are non-negotiable in
research data infrastructure.

**Independent Test**: Perform a sequence of create, update, and delete operations on
data elements and mappings, then query the audit log and confirm each operation is
recorded with timestamp, actor, and change description.

**Acceptance Scenarios**:

1. **Given** any create, update, or delete operation on a data element or mapping,
   **When** the operation completes, **Then** an audit log entry is created recording:
   operation type, affected record identifier, timestamp, and actor identity.

2. **Given** the audit log, **When** a client queries the full history of a specific
   data element, **Then** all versions of that element are returned in chronological
   order with diffs between consecutive versions.

3. **Given** a data element that has been deleted, **When** a client queries its history,
   **Then** the deletion event is recorded and previous versions remain retrievable.

---

### User Story 4 — Identity, Access Control, and User Profiles (Priority: P2)

A researcher authenticates with their institutional or community identity (Globus,
GitHub, or university SSO via InCommon) and receives access to the system calibrated
to their role. An administrator can grant roles, register source ownership, issue
API keys for programmatic access, and revoke access when needed. Every write to the
system is traceable to a verified real-world identity.

**Why this priority**: Without authenticated actor identity, audit provenance is
meaningless and the system cannot enforce data stewardship boundaries. Shared with
US2 priority P2 — both must be complete before the service can be considered trustworthy
for multi-user operation.

**Independent Test**: Authenticate via mock OIDC provider, confirm `UserProfile` is
created. Issue an API key. Use the key to create a data element; confirm audit log
records the verified identity. Attempt the same operation with a revoked key and
confirm HTTP 401. Assign `viewer` role to a second user; confirm that user cannot
create elements (HTTP 403). Assign `owner` membership on a source to the viewer;
confirm the viewer can now create elements for that source.

**Acceptance Scenarios**:

1. **Given** a user authenticating via an external OIDC provider for the first time,
   **When** authentication succeeds, **Then** a `UserProfile` is created with the
   external identity's `sub`, `iss`, `email`, and `display_name`.

2. **Given** an authenticated user with an active profile, **When** they request an
   API key, **Then** a token is issued, its hash stored in `api_key` bound to their
   profile, and the plaintext token returned once only.

3. **Given** a Bearer token in a write request, **When** the service processes the
   request, **Then** actor identity is derived from the token (not the request body)
   and recorded in the audit log and version records.

4. **Given** a `viewer`-role user attempting to create a data element, **When** the
   request is submitted, **Then** it is rejected with HTTP 403 (`insufficient_role`).

5. **Given** a `viewer`-role user who holds `owner` membership on a `SchemaSource`,
   **When** they create a data element from that source, **Then** the request succeeds
   (ReBAC source ownership grants curator-equivalent access for that source).

6. **Given** an admin revokes a user's API key, **When** a subsequent request uses
   that key, **Then** it is rejected with HTTP 401.

---

### User Story 5 — Dynamic Schema Composition, URI Persistence, and Semantic Provenance (Priority: P2)

A data engineer assembles a reusable schema by composing stored data elements into a
named, versioned object. The composed schema receives a stable URI at creation. Minor
metadata corrections (description fixes, reordering) preserve the URI and are recorded
as version updates. When a composition changes so fundamentally that it represents a
different semantic artefact, the engineer creates a superseding schema — the old URI
remains resolvable and carries a `superseded_by` pointer to the replacement. Each
member element carries its own `semantic_graph` (entities, property, unit) making the
schema's full semantic content navigable without resolving every individual element URI.
Nested elements (object-typed fields with child elements) are supported; each child
retains its own independent URI.

**Why this priority**: Persistent, lineage-aware URIs are the mechanism by which
external references in publications, pipelines, and data archives remain traceable
even as schemas evolve. Without provenance links between old and new URIs, downstream
consumers cannot reconstruct what a reference meant at a prior point in time.

**Independent Test**: Create 4 elements (one object-typed with 2 children), each with
a `semantic_graph`. POST /schemas → confirm `uri`. PUT /schemas/{id} to fix description
→ same `uri`, `version_num` incremented. POST /schemas/{id}/supersede with a new
element set → new URI returned; GET old schema → `superseded_by` set. Separately: POST
/elements/{id}/supersede changing `unit` from Celsius to Fahrenheit → new element URI;
old element gains `superseded_by`; both are resolvable.

**Acceptance Scenarios**:

1. **Given** stored data elements each with a `semantic_graph`, **When** a curator
   POSTs a named schema composition, **Then** a `DynamicSchema` is created with a
   globally unique URI, `version_num = 1`, and `superseded_by = null`.

2. **Given** a `DynamicSchema` receiving a description correction, **When** a curator
   PUTs the update, **Then** the `uri` is unchanged, `version_num` increments, and the
   audit log records the UPDATE with the actor's identity and a diff.

3. **Given** a `DynamicSchema` requiring a semantically distinct replacement, **When** a
   curator POSTs `/schemas/{id}/supersede` with a new composition, **Then** a new
   `DynamicSchema` is created with a new URI; the old schema's `superseded_by` is set;
   both old and new schemas remain resolvable at their respective URIs.

4. **Given** a `DataElement` representing `temperature_water_celsius`, **When** a curator
   POSTs `/elements/{id}/supersede` specifying `temperature_water_fahrenheit` (same
   subject entity, same property, different unit), **Then** a new `DataElement` is
   created with a new URI and a `semantic_graph` reflecting the Fahrenheit unit; the old
   element gains `superseded_by`; both remain resolvable; a `MappingFunction` between
   them MAY be registered to express the conversion relationship.

5. **Given** two elements `temperature_water` and `temperature_milk` (same property and
   unit, different subject entities), **When** stored, **Then** they are distinct
   `DataElement` records with distinct URIs and distinct `semantic_graph.entities`; they
   MUST NOT be merged even if their names or descriptions appear similar.

6. **Given** an object-typed `DataElement` with child element references, **When** a
   client GETs the element, **Then** `children` is returned with each child's `uri`,
   `field_name`, `position`, and `semantic_graph`; circular parent-child references are
   rejected with HTTP 400.

---

### User Story 6 — Undata Curation and Downstream Integration (Priority: P2)

A curator ingests elements from multiple neuroscience schemas, uses the alias detection
system to identify semantically equivalent elements across sources, and creates a compact
undata canonical vocabulary by mapping those source elements to curated undata elements.
Downstream developers — database designers, pipeline authors, library maintainers — build
their systems against the undata vocabulary, using the persistent URIs as stable anchors
and the mappings to trace back to source representations when needed.

**Why this priority**: Without the canonical undata space, every downstream consumer
must independently resolve cross-source naming conflicts. With it, that work is done
once and the result is shared infrastructure.

**Independent Test**: Ingest BIDS `age` and DANDI `age` elements (both years, human
participant). Call `POST /aliases/detect?cross_source_only=true` — confirm both appear
as a candidate pair with similarity ≥ 0.88. Create a undata canonical element
`undata::age_years`. Register identity mappings from both source elements to it. Query
`GET /elements?source_id={undata_id}` — confirm canonical element present. Query
`GET /mappings?target_element_id={undata_age_id}` — confirm both source mappings
visible. Compose a DynamicSchema from the undata element — confirm URI assigned.
Downstream: retrieve the undata element by URI; follow `superseded_by` if set.

**Acceptance Scenarios**:

1. **Given** two source elements (`BIDS::age`, `DANDI::age`) that measure the same
   concept with the same unit, **When** a curator calls `POST /aliases/detect` with
   `cross_source_only=true`, **Then** the pair is returned as a candidate with a
   similarity score and a semantic_graph structural comparison showing matching
   `property.label` and `unit.label`.

2. **Given** a confirmed semantic equivalence, **When** a curator creates a undata
   canonical element (`source_id = undata_source_id`) and registers identity
   `MappingFunction`s from each source element to it, **Then** both source elements
   are resolvable by their own URIs and queryable via
   `GET /mappings?target_element_id={undata_element_id}`.

3. **Given** a undata canonical element, **When** a curator composes a
   `DynamicSchema` from one or more undata elements, **Then** the schema is assigned
   a stable URI; each element's `field_alias ?? normalize(source_local_id)` is unique
   within the schema; and `GET /schemas/{id}` returns `element_uri` for every member.

4. **Given** a downstream developer querying the undata vocabulary, **When** they call
   `GET /elements?source_id={undata_id}`, **Then** they receive a paginated list of
   canonical elements, each with `uri`, `semantic_graph`, `unit`, and `superseded_by`
   (null for active elements).

5. **Given** a undata element that has been superseded, **When** a downstream pipeline
   resolves the original URI via `GET /elements/{id}`, **Then** the response includes
   `superseded_by` pointing to the replacement URI, enabling the pipeline to update
   its field mapping without the original URI becoming unresolvable.

6. **Given** a downstream developer needing to convert data from source representation
   to undata canonical form, **When** they query `GET /mappings?target_element_id=
   {undata_element_id}`, **Then** they receive all registered source→undata mappings
   including the `expression_type`, `expression`, and `sssom_predicate`, sufficient
   to perform or delegate the transformation.

---

### User Story 7 — Unit Symbol Standardization (Priority: P2)

A data curator creates a data element with a unit of measurement. The service validates
the unit symbol against the CMIXF-12 grammar and auto-resolves the QUDT ontology URI from
a bundled vocabulary. Unit enrichment is non-blocking: elements are always created
regardless of resolution outcome. Curators can query which units are unresolvable to
identify gaps in ontology coverage.

**Why this priority**: Standardised unit symbols and ontology URIs are required for
semantic interoperability across neuroscience schemas. Without them, `"kg"` and
`"kilogram"` remain disconnected strings. QUDT URIs enable downstream SPARQL queries
and linked-data integration.

**Independent Test**: POST an element with `semantic_graph.unit = {label: "kilogram",
symbol: "kg"}` → response includes `unit.cmixf_valid=true`, `unit.external_uri` pointing
to QUDT `unit:KiloGM`, `unit.qudt_unresolvable=false`. POST with `symbol: "???"` →
`cmixf_valid=false`, `qudt_unresolvable=true`. GET `/units` returns paginated list.
GET `/units/unresolvable` returns only elements with `qudt_unresolvable=true`.

**Acceptance Scenarios**:

1. **Given** a data element with `semantic_graph.unit.symbol = "kg"`, **When** it is
   created, **Then** the service sets `unit.cmixf_valid=true`, `unit.external_uri=
   "http://qudt.org/vocab/unit/KiloGM"`, and `unit.qudt_unresolvable=false` in the
   stored version.

2. **Given** a data element with `semantic_graph.unit.symbol = "???"` (invalid),
   **When** it is created, **Then** the element is still created successfully;
   `unit.cmixf_valid=false` and `unit.qudt_unresolvable=true` are set; no 4xx error
   is returned (enrichment is non-blocking).

3. **Given** a data element with `semantic_graph.unit.label = "year"` and no symbol,
   **When** it is created, **Then** `unit.external_uri` resolves to QUDT `unit:YR` via
   label lookup; `unit.cmixf_valid=null` (no symbol to validate).

4. **Given** stored elements with unit data, **When** a client calls `GET /units`,
   **Then** a paginated list of distinct unit nodes is returned, each with `label`,
   `symbol`, `cmixf_valid`, `qudt_uri`, `qudt_unresolvable`, and `element_count`.

5. **Given** elements whose units could not be resolved, **When** a client calls
   `GET /units/unresolvable`, **Then** only units with `qudt_unresolvable=true` are
   returned, each including `element_ids` for follow-up curation.

---

### Edge Cases

- What happens when a client attempts to store a data element with a name that
  conflicts with an existing element from a different source schema? The element MUST
  be stored with its full provenance; the conflict MUST be flagged as a potential alias
  or collision (to be resolved by mapping rules), not silently merged.
- What happens when a bulk ingestion partially fails (some elements succeed, some fail)?
  The service MUST return a partial-success report identifying which elements were stored
  and which failed; it MUST NOT silently drop failed elements.
- What happens when the store reaches its capacity limit? The service MUST return a
  capacity error before data loss occurs; it MUST NOT silently discard data.
- What happens when two clients concurrently update the same data element? The service
  MUST handle concurrent writes safely and report a conflict to one of the clients
  rather than allowing a silent last-write-wins overwrite.

---

## Requirements *(mandatory)*

### Functional Requirements

**Data Element Store**

- **FR-001**: Service MUST provide create, read, update, and delete operations for
  data elements.
- **FR-002**: Each data element record MUST store: unique identifier, name, data type,
  description, cardinality (required/optional, single/multi-valued), allowed values
  (if enumerated), source schema reference, schema version, and ingestion timestamp.
- **FR-003**: Service MUST support retrieval of data elements by: unique identifier,
  source schema, data type, keyword search (name and description), alias group,
  unit of measurement (exact label match on `semantic_graph.unit.label`),
  semantic entity subject label, measured property label, and superseded status
  (default excludes superseded elements; opt-in to include them).
- **FR-004**: Service MUST preserve all historical versions of a data element on update;
  clients MUST be able to retrieve any historical version by identifier and version number.
- **FR-005**: Service MUST detect and flag name collisions (same name, different source
  schemas with incompatible types or descriptions) without merging them.

**Mapping Registry**

- **FR-006**: Service MUST provide create, read, update, and delete operations for
  mapping function registrations.
- **FR-007**: Each mapping record MUST store: unique identifier, function type
  (identity or custom), input slot references, output slot reference, parameter schema,
  function expression or reference, and creation/modification timestamps.
- **FR-008**: Service MUST support retrieval of mappings by: source element, target
  element, function type, and source/target schema pair.
- **FR-009**: Service MUST validate at registration time that all referenced slots exist
  in the data element store; referencing a non-existent slot MUST be rejected.
- **FR-010**: Service MUST detect and reject circular mapping dependencies (direct and
  transitive) at registration time.
- **FR-011**: Service MUST preserve all historical versions of a mapping on update.

**Audit Trail & Provenance (PROV-O)**

- **FR-012**: Service MUST record a provenance record for every mutation (create, update,
  delete) on data elements, mappings, and schemas. Each record MUST be modelled internally
  as a PROV-O `Activity` with: the affected resource as `prov:Entity`, the actor as
  `prov:Agent` (`wasAssociatedWith`), the previous version as `used`, and the new version
  as `wasGeneratedBy`. System-generated inferences (e.g. mapping suggestions) MUST be
  attributed to a dedicated system `prov:Agent`.
- **FR-013**: Provenance records MUST include: resource type, resource URI, operation type,
  timestamp, actor identity (human or system), `prov:startedAtTime`, `prov:endedAtTime`,
  and a diff of changed fields.
- **FR-014**: Service MUST expose `GET /{resource}/{id}/provenance` returning a
  JSON-LD document conforming to the PROV-O vocabulary (`Content-Type: application/ld+json`).
  The full ordered mutation history MUST be reconstructable from this endpoint.

**Alias Detection & Mapping Inference**

- **FR-017**: Service MUST expose an on-demand alias detection endpoint that runs
  embedding-based similarity search and semantic graph structural comparison across stored
  data elements. Detection MUST NOT run automatically on element create or update; it is
  triggered exclusively by explicit client request.

  **Alias semantics**: Two elements are aliases (`skos:exactMatch`) if and only if their
  `semantic_graph` structures are identical (same entities, property, and unit — label/name
  differences are permitted). The alias detection response MUST include a
  `semantic_graph_overlap` object per candidate pair.

  **Mapping inference**: When two elements share the same `property` and `entity` values
  but differ in `unit` (or other non-identity semantic differences), the endpoint MUST
  include a `suggested_mapping` object: `{function_type, rationale, confidence}` derived
  from semantic graph pattern matching. Inferred mappings are attributed to the system
  agent (`actor: "system"`) and assigned `status="pending_curation"` — they are NOT
  registered automatically unless the caller provides a `confidence_threshold` parameter
  AND the candidate's `confidence` meets or exceeds that threshold.

- **FR-018**: The alias detection response MUST follow the same paginated envelope used by
  all other list endpoints (`total`, `limit`, `offset`, `items`). Each item MUST include:
  both element identifiers and URIs, `similarity_score`, `sssom_predicate` (only
  `skos:exactMatch` for true aliases), `semantic_graph_overlap` (with `property_match`,
  `unit_match`, `entity_labels_match`, `domain_match`), and — when applicable —
  `suggested_mapping: {function_type, rationale, confidence}`.

**Security**

- **FR-019**: All write endpoints (POST, PUT, DELETE) MUST require a valid Bearer token;
  requests without a token or with an invalid token MUST be rejected with HTTP 401.
- **FR-020**: The actor identity recorded in audit log entries and version records MUST
  be derived from the validated Bearer token, not from any caller-supplied field.
  Request body fields `created_by` / `updated_by` are NOT accepted; actor is server-derived.
- **FR-021**: API keys MUST be issued only to users with an active `UserProfile`; each
  key is stored as a cryptographic hash in the `api_key` table bound to the issuing
  user's profile. The token registry MUST support revocation by setting `revoked_at`;
  revoked tokens MUST be rejected with HTTP 401 on all subsequent requests.

**Identity & Authorization**

- **FR-022**: Service MUST integrate with an external OIDC/OAuth2 federation hub
  (e.g., Keycloak) that itself federates Globus, GitHub, and InCommon/SAML identity
  providers. On first successful external authentication, a `UserProfile` record MUST
  be created linking the external identity (`external_sub`, `external_iss`) to a local
  user ID with `email` and `display_name`.
- **FR-023**: Service MUST implement RBAC with four roles: `admin` (full access including
  user and token management), `curator` (create/update/delete elements, mappings,
  and aliases), `contributor` (create and update elements for their assigned sources;
  no direct mapping or alias write access in v1), `viewer` (read-only; all GET
  endpoints). Role assignments are stored in a `user_role` join table.
- **FR-024**: Service MUST implement ReBAC for source-level resource access: a user
  assigned `owner` or `contributor` role on a `SchemaSource` (via a `source_membership`
  table) has curator-equivalent write access on elements from that source, regardless of
  their global RBAC role.
- **FR-025**: Every write operation MUST authorize the requesting actor against both their
  global RBAC role and any applicable `source_membership` relationship. Unauthorized
  operations MUST return HTTP 403 with the reason (`insufficient_role` or
  `not_source_member`).
- **FR-026**: Service MUST provide endpoints for user profile management
  (`GET /users/me`, `GET /users/{id}`) and API key self-management
  (`POST /tokens`, `DELETE /tokens/{id}`). Admins MUST additionally be able to list all
  users (`GET /users`), assign roles (`PUT /users/{id}/roles`), and revoke any token.

**Persistent Identity (URIs) and Semantic Change Policy**

- **FR-027**: Every `DataElement` MUST be assigned a globally unique, dereferenceable
  URI at creation time. That URI is stable so long as the element's **semantic identity**
  is unchanged. A **semantic change** — defined as any modification to the element's
  measured property, unit of measurement, subject entity, or data type — requires the
  creation of a new `DataElement` with a new URI via `POST /elements/{id}/supersede`.
  The superseded element retains its URI and gains a `superseded_by` pointer to the
  replacement; the replacement gains a `supersedes` back-reference. Minor corrections
  (typo fixes in description, rewording that preserves original meaning, adding synonyms
  or external URI references to the semantic graph) do NOT constitute semantic changes
  and are handled as ordinary version updates with no URI change.

  **Semantic change criteria** — a change IS semantic if it alters any of:
  - `data_type` (e.g. `string` → `number`)
  - `unit` within the semantic graph (e.g. Celsius → Fahrenheit; temperature of water
    in Celsius and temperature of water in Fahrenheit are **distinct elements** because
    they are not interchangeable without conversion)
  - Any `entity` label or type in the semantic graph (e.g. "water" → "milk"; temperature
    of water and temperature of milk are **distinct elements** because they describe
    different physical subjects even if the property and unit are identical)
  - The measured `property` in the semantic graph (e.g. "temperature" → "pH")
  - The semantic `domain` (e.g. Material → BioSample)

  **Non-semantic (minor) changes** — a change is NOT semantic if it only modifies:
  - Wording in `description` or `name` without altering the original meaning
  - `context` or `external_uri` annotations in the semantic graph
  - `required` or `multivalued` flags
  - `constraints` such as min/max bounds or regex patterns that do not change the
    conceptual type, unit, or subject

- **FR-028**: Every `MappingFunction` MUST be assigned a globally unique, dereferenceable
  URI at creation time that is stable across all version updates and soft-deletes. The URI
  MUST be resolvable via `GET /mappings/{id}`. This makes every transformation persistently
  identifiable for provenance and reproducibility.
- **FR-029**: Service MUST support construction of `DynamicSchema` objects that compose
  a named, ordered set of `DataElement` references into a schema. Each `DynamicSchema`
  MUST be assigned a globally unique, dereferenceable URI at creation and MUST retain that
  URI across minor membership and metadata updates. When the semantic scope of a schema
  changes significantly, a curator MAY create a new superseding schema via
  `POST /schemas/{id}/supersede`; the old URI gains a `superseded_by` pointer and both
  remain resolvable. The `version_num` field provides optimistic concurrency control;
  full mutation history is recorded in the audit log.

**Semantic Graph per Element**

- **FR-031**: Every `DataElement` version MUST carry a `semantic_graph` structure
  (stored as JSONB) that encodes a small knowledge graph representing the entities,
  property, unit, and relations captured by the element. This structure is the
  authoritative source for semantic change detection and for alias/similarity enrichment.
  The `semantic_graph` MUST conform to the following schema:

  ```json
  {
    "entities": [
      {
        "label": "water",
        "type": "Material",
        "role": "subject",
        "external_uri": "http://purl.obolibrary.org/obo/CHEBI_15377"
      }
    ],
    "property": {
      "label": "temperature",
      "type": "PhysicalProperty",
      "external_uri": "http://purl.obolibrary.org/obo/PATO_0000146"
    },
    "unit": {
      "label": "degree Celsius",
      "symbol": "°C",
      "external_uri": "http://qudt.org/vocab/unit/DEG_C"
    },
    "relations": [
      { "subject": "water", "predicate": "hasProperty", "object": "temperature" }
    ],
    "domain": "Material",
    "range_type": "xsd:decimal",
    "context": "Temperature of a water sample measured in degrees Celsius"
  }
  ```

  Fields `entities`, `property`, and `unit` are required when applicable (i.e., for
  numeric and typed elements); `relations`, `domain`, `range_type`, and `context` are
  optional. `external_uri` on any node is optional but SHOULD reference a well-known
  ontology term (PATO, CHEBI, QUDT, schema.org) when available.

  The `unit.label` and all `entity.label` values are the primary semantic discriminators:
  `temperature_water_celsius` and `temperature_water_fahrenheit` share the same
  `property` and `entity` but differ in `unit` — they MUST be stored as separate
  `DataElement` records with separate URIs. `temperature_water` and `temperature_milk`
  share the same `property` and `unit` but differ in their subject `entity` — they MUST
  likewise be stored as separate `DataElement` records.

**Two-Tier Canonical Architecture**

- **FR-032**: The service MUST pre-seed a `SchemaSource` record with `name="undata"`,
  `format="canonical"`, and `is_active=true` at startup if one does not already exist.
  This source serves as the undata canonical namespace. All curator-created canonical
  elements MUST reference this source via `source_id`. The `"undata"` source is
  never updated or deleted by the ingestion pipeline.

- **FR-033**: The alias detection endpoint (FR-017) MUST support a `cross_source_only`
  boolean filter (default `false`). When `cross_source_only=true`, only candidate
  pairs where the two elements belong to **different** `SchemaSource` records are
  returned. This is the primary machine-side tool for identifying source elements
  that should map to the same undata canonical element. Each candidate pair in the
  response MUST include a `semantic_graph_overlap` object summarising which fields
  match (`property_match: bool`, `unit_match: bool`, `entity_labels_match: bool`,
  `domain_match: bool | null` — `null` when `domain` is absent from both elements'
  semantic graphs, otherwise a boolean comparison) to assist the human curator's decision.

- **FR-034**: The undata canonical space MUST be kept compact. When a curator confirms
  that two or more source elements are semantically equivalent, they MUST all be mapped
  to a **single** undata canonical element — not to separate undata elements. The
  service MUST support detection of potential compactness violations by allowing
  `POST /aliases/detect` to be filtered to `source_id={undata_source_id}`, surfacing
  any two undata elements whose semantic_graph overlap is high enough to suggest
  redundancy. Enforcement is a curation responsibility; the service provides the
  detection tooling.

**Nested Schemas**

- **FR-030**: `DataElement` records MUST support nesting. An element whose `data_type`
  is `"object"` MUST carry a `schema_ref` FK to a `DynamicSchema` — the element's
  value is an instance of that named schema. An element whose `data_type` is `"array"`
  MAY carry a `schema_ref` (homogeneous array of schema instances) or an `items_type`
  (homogeneous array of a primitive type). Anonymous inline structures (where the
  nested schema has no independent identity) use `DataElementChild` with a `position`
  field. Each child element retains its own independent URI. Nested lookups MUST be
  traversable via `GET /elements/{id}`. Circular `schema_ref` references MUST be
  rejected with HTTP 400.

**LinkML Import / Export**

- **FR-035**: Service MUST expose `GET /schemas/{id}/linkml` returning a LinkML YAML
  `SchemaDefinition` for the requested `DynamicSchema`. The response MUST include a
  `X-Roundtrip-Fidelity` header (0.0–1.0) and a `X-Roundtrip-Loss` header listing
  known loss points (e.g. `slot_versioning`, `uri_stability_policy`, `prov_o`).
- **FR-036**: Service MUST expose `POST /schemas/import/linkml` accepting a LinkML YAML
  body and returning a `RoundtripResult` (`{fidelity_score, loss_points, schema_id}`).
  Elements are created from LinkML `SlotDefinition`s; classes become `DynamicSchema`
  records; `is_a` and `mixins` are mapped to the schema inheritance model. Loss points
  that prevent import MUST return HTTP 422 with the specific loss point identified.

**System Meta-model**

- **FR-037**: The project MUST maintain a self-describing LinkML YAML meta-model at
  `docs/undata-metamodel.yaml` that formally defines all core concepts:
  `DataElement`, `SemanticGraph`, `SemanticGraphEntity`, `SemanticGraphProperty`,
  `SemanticGraphUnit`, `MappingFunction`, `DynamicSchema`, `ProvenanceRecord`,
  `AliasGroup`, `SchemaSource`. Each class and slot MUST carry `class_uri` / `slot_uri`
  referencing well-known ontology terms (PROV-O, SKOS, schema.org, OBI) where applicable.
  The meta-model MUST be versioned (CalVer) and a GitHub Actions workflow MUST render
  it via `gen-doc` (LinkML doc generator) and publish the output alongside the
  JupyterBook at every push to `main`.

**Reliability**

- **FR-015**: Service MUST handle concurrent writes to the same record safely; concurrent
  conflict MUST be reported to the client, not silently resolved.
- **FR-016**: Bulk ingestion operations MUST be atomic per element (individual element
  failures MUST NOT affect other elements) and MUST return a per-element status report.

### Key Entities

- **DataElement**: Persistent normalized representation of a schema field. Versioned. Carries a `superseded_by` pointer when replaced by a semantically distinct successor.
- **DataElementVersion**: A point-in-time snapshot of a DataElement, forming a history chain. Carries a `semantic_graph` JSONB encoding the entities, property, unit, and relations the element represents.
- **MappingFunction**: Registered transformation between data elements. Versioned.
- **MappingFunctionVersion**: A point-in-time snapshot of a MappingFunction.
- **AliasGroup**: A named set of DataElements linked by identity mappings.
- **AuditLog**: An immutable record of a single mutation event.
- **SchemaSource**: Reference record for an ingested source schema with version/hash.
  One special instance — `name="undata"`, `format="canonical"` — is pre-seeded at
  startup and serves as the canonical namespace for curated cross-source elements.
- **DynamicSchema**: A named, versioned composition of `DataElement` references with a
  persistent URI; represents a schema constructed at runtime from stored elements.
- **DataElementChild**: Join table recording anonymous inline parent-child nesting between
  `DataElement` records, with a `position` for ordered nesting. Used only when the nested
  structure has no independent `DynamicSchema` identity. Named object-typed elements use
  `schema_ref` instead.
- **UserProfile**: Local user record linked to an external IdP identity (`external_sub`,
  `external_iss`, `email`, `display_name`); created on first successful OIDC login.
- **APIKey**: Hashed Bearer token bound to a `UserProfile`; carries `issued_at`,
  `revoked_at`, and optional `scopes`; used for programmatic API access.
- **UserRole**: RBAC role assignment joining `UserProfile` to a role enum
  (`admin`, `curator`, `contributor`, `viewer`).
- **SourceMembership**: ReBAC resource relationship joining `UserProfile` to
  `SchemaSource` with a role (`owner`, `contributor`); grants source-scoped write access.

---

## Assumptions

- The backend is accessed exclusively through a well-defined API; direct data store
  access by external clients is not permitted.
- All write operations require a valid Bearer token (API key). Token issuance is
  available only to users with an active `UserProfile` authenticated via an external
  OIDC/OAuth2 federation hub (Keycloak federating Globus, GitHub, InCommon/SAML).
  The backend validates every write request's token, rejects invalid or missing tokens
  with HTTP 401, and derives the actor identity from the validated token — `created_by`
  and `updated_by` fields in request bodies are NOT accepted; actor is always server-derived.
  Access to specific write operations is further governed by RBAC roles and ReBAC
  source membership relationships.
- The service does not execute mapping functions itself — it stores their definitions.
  Execution is the responsibility of the migration API (spec 004).
- "Keyword search" covers substring and stemmed matching via full-text (GIN tsvector)
  across element names and descriptions. Embedding-based (cosine similarity) search
  is implemented **for alias/duplicate detection only** via `POST /aliases/detect`;
  it is not exposed as a general element search mechanism in v1.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of data elements from a full four-schema ingestion run are stored and
  retrievable by identifier with no data loss.
- **SC-002**: All historical versions of updated data elements are retrievable; no version
  is silently overwritten.
- **SC-003**: Circular dependency detection rejects 100% of circular mapping registrations
  in a defined test suite.
- **SC-004**: Keyword search returns all elements whose name or description contains the
  query term (100% recall on exact-match queries).
- **SC-005**: Every mutation operation produces an audit log entry; the audit log for a
  10-operation sequence is complete and accurate with 100% fidelity.
- **SC-006**: Concurrent write conflicts are detected and reported (not silently lost) in
  100% of tested concurrent-update scenarios.
- **SC-007**: Every `DataElement`, `MappingFunction`, and `DynamicSchema` created in a
  test run retains its original URI after a service restart and across all version
  updates; no URI changes unless `POST /{id}/supersede` is explicitly called.
- **SC-008**: A complete supersession lifecycle (element A superseded by A') produces:
  A with `superseded_by = A'.uri` and `deleted_at` set, A' with `supersedes = A.uri`
  and a distinct URI, both resolvable via GET, and both audit entries recorded in the
  same transaction — validated in 100% of test scenarios.
- **SC-009**: Every `DataElementVersion` for a numeric or typed element stored through
  the API carries a non-null `semantic_graph` structure (per FR-031 "when applicable");
  the `unit` field on the version row matches `semantic_graph.unit.label` (or is null
  if no unit node is present) in 100% of test cases. Categorical/boolean elements
  where no unit or entity relationship applies MAY store `semantic_graph: null`.
- **SC-010**: A `DynamicSchema` URI is unchanged after `PUT /schemas/{id}` (membership
  update) and is distinct from the URI of any schema created via
  `POST /schemas/{id}/supersede`; validated in 100% of test scenarios.
- **SC-011**: After ingesting BIDS and DANDI source elements and running the curation
  workflow, `GET /elements?source_id={undata_id}` returns at least one canonical element
  with identity mappings visible via `GET /mappings?target_element_id={id}`; the undata
  element's `semantic_graph` matches the shared structure of its source equivalents.
- **SC-012**: `POST /aliases/detect` with `cross_source_only=true` returns only
  candidate pairs from different source schemas; each pair includes a
  `semantic_graph_overlap` object; pairs from the same source are absent from the
  response in 100% of test scenarios.
