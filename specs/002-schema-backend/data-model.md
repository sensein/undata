# Data Model: Schema Backend Service
**Feature**: 002-schema-backend | **Date**: 2026-03-07

---

## Entity Relationship Overview

```
SchemaSource ──< DataElement ──< DataElementVersion
                      │
                      ├──< AliasGroupMember >── AliasGroup
                      │
                      └──< MappingInput >── MappingFunction ──< MappingFunctionVersion
                                                  │
                                              OutputElement

AuditLog records mutations to: DataElement, MappingFunction, AliasGroup, SchemaSource
```

---

## Entities

### SchemaSource

Represents a versioned neuroscience schema origin.

**Pre-seeded record**: A `SchemaSource` with `name="undata"` and `format="canonical"` is inserted
idempotently at service startup (Alembic lifespan hook). This record is the home namespace for all
curator-created canonical elements and DynamicSchemas. Source-space ingestion pipelines register
separate `SchemaSource` rows (e.g. `name="BIDS"`, `name="DANDI"`). Canonical elements are created
under the `"undata"` source by curators after cross-source alias detection confirms semantic
equivalence; they are never auto-merged from source elements.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `name` | TEXT | NOT NULL, UNIQUE | e.g. "BIDS", "DANDI" |
| `format` | TEXT | NOT NULL | "yaml", "json-ld", "json-schema" |
| `url` | TEXT | | Remote location |
| `version_tag` | TEXT | | e.g. "1.8.0" from source |
| `content_hash` | TEXT | NOT NULL | SHA-256 of raw schema content |
| `ingested_at` | TIMESTAMPTZ | NOT NULL | |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | |
| `metadata` | JSONB | | Arbitrary extra info |

---

### DataElement

Canonical record for a single data field extracted from a source schema. Carries only
stable identity fields; all versioned content is in `DataElementVersion`.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `uri` | TEXT | NOT NULL, UNIQUE | Globally unique, dereferenceable URI — e.g. `https://undata.io/elements/{id}` — assigned at creation; stable while semantic identity is unchanged |
| `source_id` | UUID | FK → SchemaSource | |
| `source_local_id` | TEXT | NOT NULL | Name/path within source schema (e.g. `person.age`, `animal.age`) |
| `current_version_id` | UUID | FK → DataElementVersion | Latest version |
| `version_num` | INT | NOT NULL DEFAULT 1 | Optimistic lock counter |
| `superseded_by` | UUID | FK → DataElement, nullable | Set when a semantic change creates a successor element; old element is soft-deprecated |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `deleted_at` | TIMESTAMPTZ | | Soft delete (also set on supersession) |
| **Unique** | | (source_id, source_local_id) | Same field name under different source contexts is a distinct element |

---

### DataElementVersion

Immutable snapshot of a DataElement's content at a point in time.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `element_id` | UUID | FK → DataElement | |
| `version_num` | INT | NOT NULL | 1-based, monotonic |
| `name` | TEXT | NOT NULL | Normalized element name |
| `data_type` | TEXT | NOT NULL | "string", "number", "boolean", "object", "array" |
| `description` | TEXT | | Human-readable description |
| `required` | BOOLEAN | NOT NULL | Is field required? |
| `multivalued` | BOOLEAN | NOT NULL | Is field multi-valued? |
| `allowed_values` | JSONB | | For enumeration types: `["val1","val2"]` |
| `constraints` | JSONB | | Min, max, pattern, etc. |
| `semantic_graph` | JSONB | | Structured knowledge graph for this version: `{entities, property, unit, relations, domain, range_type, context}`. See FR-031 for schema. Primary source for semantic change detection. |
| `unit` | TEXT | | Extracted from `semantic_graph.unit.label`; indexed for fast unit-based filtering (e.g. filter all elements in "Celsius") |
| `name_embedding` | VECTOR(384) | | For similarity search (all-MiniLM-L6-v2) |
| `description_embedding` | VECTOR(384) | | For alias detection |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `created_by` | UUID | FK → UserProfile NOT NULL | Actor identity (UUID, not plain string) |

*Note*: `VECTOR` type requires `pgvector` extension. Falls back to JSONB array if
extension unavailable.

**`semantic_graph` node types**:

| Node | Required fields | Purpose |
|------|----------------|---------|
| `entity` | `label`, `type`, `role` (`subject`/`object`) | Physical or conceptual entity (e.g. "water", "milk", "study participant") |
| `property` | `label`, `type` | What is being measured or described (e.g. "temperature", "age", "weight") |
| `unit` | `label` | Unit of measurement (e.g. "degree Celsius", "years"); absence implies dimensionless or categorical |
| `relation` | `subject`, `predicate`, `object` | Named edge in the mini-graph (e.g. `water hasProperty temperature`) |

`external_uri` on any node is optional but SHOULD reference a well-known ontology term
(PATO, CHEBI, QUDT, schema.org, OBI) when available.

**`unit` node — extended fields (server-populated)**:

The `unit` node in `semantic_graph` is enriched server-side at element create/update time.
Clients SHOULD provide `symbol` when known; the service adds `external_uri`, `cmixf_valid`,
and `qudt_unresolvable` automatically.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `label` | string | client | Human-readable name (e.g. "degree Celsius", "year") |
| `symbol` | string \| null | client | Unit symbol expression — validated against cmixf-12 grammar |
| `external_uri` | string \| null | **server** | QUDT ontology URI (e.g. `http://qudt.org/vocab/unit/DEG_C`); auto-resolved, never client-supplied in practice |
| `cmixf_valid` | bool \| null | **server** | `null` if no symbol; `true` if symbol parses cmixf-12; `false` if it does not |
| `qudt_unresolvable` | bool | **server** | `true` if symbol+label resolution against QUDT failed; `false` if resolved or if no unit provided |

**Resolution algorithm** (server-side, `UnitResolutionService.resolve()`):
1. If `symbol` provided → validate against cmixf-12 parser → set `cmixf_valid`
2. Try QUDT lookup by `ucumCode` match (most reliable)
3. Try QUDT lookup by `symbol` match (handles Unicode ↔ ASCII variants)
4. Try QUDT lookup by `label` English match (fallback for "year", "degree Celsius", etc.)
5. If any step finds a match → set `external_uri`, set `qudt_unresolvable = false`
6. If all steps fail → set `external_uri = null`, set `qudt_unresolvable = true`

**QUDT data source**: `VOCAB_QUDT-UNITS-ALL.ttl` bundled locally (pinned to QUDT v3.1.x);
loaded at startup via `rdflib`; in-memory index built on first load. No live network calls.

**Example enriched `unit` node**:
```json
{
  "label": "degree Celsius",
  "symbol": "°C",
  "external_uri": "http://qudt.org/vocab/unit/DEG_C",
  "cmixf_valid": true,
  "qudt_unresolvable": false
}
```

**Example unresolvable `unit` node**:
```json
{
  "label": "some-custom-unit",
  "symbol": "cux",
  "external_uri": null,
  "cmixf_valid": false,
  "qudt_unresolvable": true
}
```

---

### MappingFunction

Registered transformation between data elements.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `uri` | TEXT | NOT NULL, UNIQUE | Globally unique, dereferenceable URI — e.g. `https://undata.io/mappings/{id}` — assigned at creation; immutable |
| `function_type` | TEXT | NOT NULL | "identity" or "custom" |
| `output_element_id` | UUID | FK → DataElement | Target slot |
| `current_version_id` | UUID | FK → MappingFunctionVersion | |
| `version_num` | INT | NOT NULL DEFAULT 1 | Optimistic lock |
| `status` | TEXT | NOT NULL DEFAULT "active" | "active" or "broken" |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `deleted_at` | TIMESTAMPTZ | | Soft delete |

---

### MappingInput

Join table linking input DataElements to a MappingFunction (supports multi-input).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `mapping_id` | UUID | FK → MappingFunction | |
| `element_id` | UUID | FK → DataElement | |
| `position` | INT | NOT NULL | Argument order (0-based) |
| **PK** | | (mapping_id, element_id) | |

---

### MappingFunctionVersion

Immutable snapshot of a mapping's expression and parameters.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `mapping_id` | UUID | FK → MappingFunction | |
| `version_num` | INT | NOT NULL | |
| `description` | TEXT | | Human description of the transform |
| `expression` | TEXT | | Function body (Python expr / JSONPath) |
| `expression_type` | TEXT | NOT NULL | "python_expr", "jsonpath", "identity" |
| `parameter_schema` | JSONB | | JSON Schema for extra params |
| `inverse_mapping_id` | UUID | FK → MappingFunction, nullable | Back-reference to inverse |
| `sssom_predicate` | TEXT | | e.g. "skos:exactMatch" |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `created_by` | UUID | FK → UserProfile NOT NULL | Actor identity (UUID, not plain string); consistent with FR-020 and DataElementVersion |

---

### DataElementChild

Join table recording parent-child nesting relationships between DataElements.
A parent element with `data_type = "object"` or `"array"` may reference child elements.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `parent_id` | UUID | FK → DataElement NOT NULL | The container/object element |
| `child_id` | UUID | FK → DataElement NOT NULL | The nested field element |
| `position` | INT | NOT NULL | Ordering of fields within the parent (0-based) |
| `field_name` | TEXT | NOT NULL | Name of this child as it appears within the parent |
| **PK** | | (parent_id, child_id) | |

---

### DynamicSchema

A named, versioned composition of DataElement references with a persistent URI.
Represents a schema constructed at runtime from stored elements.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `uri` | TEXT | NOT NULL, UNIQUE | Globally unique, dereferenceable URI — e.g. `https://undata.io/schemas/{id}` — assigned at creation; stable while semantic scope is unchanged |
| `name` | TEXT | NOT NULL | Human-readable schema name |
| `description` | TEXT | | Optional description |
| `version_num` | INT | NOT NULL DEFAULT 1 | Optimistic lock counter |
| `superseded_by` | UUID | FK → DynamicSchema, nullable | Set when a semantically distinct replacement schema is created |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |
| `deleted_at` | TIMESTAMPTZ | | Soft delete (also set on supersession) |

---

### DynamicSchemaElement

Join table linking DataElements into a DynamicSchema (ordered membership).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `schema_id` | UUID | FK → DynamicSchema NOT NULL | |
| `element_id` | UUID | FK → DataElement NOT NULL | |
| `position` | INT | NOT NULL | Field order within the schema |
| `field_alias` | TEXT | | Override name for this element within the schema context |
| **PK** | | (schema_id, element_id) | |

---

### AliasGroup

A named set of DataElements considered semantically equivalent.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `name` | TEXT | | Optional human label |
| `sssom_predicate` | TEXT | NOT NULL DEFAULT "skos:exactMatch" | |
| `confidence` | FLOAT | | Similarity score if auto-detected |
| `detection_method` | TEXT | | "auto" or "manual" |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

---

### AliasGroupMember

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `alias_group_id` | UUID | FK → AliasGroup | |
| `element_id` | UUID | FK → DataElement | |
| **PK** | | (alias_group_id, element_id) | |

---

### AuditLog

Immutable record of every mutation.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `record_type` | TEXT | NOT NULL | "DataElement", "MappingFunction", "DynamicSchema", etc. |
| `record_id` | UUID | NOT NULL | ID of the affected record |
| `operation` | TEXT | NOT NULL | "CREATE", "UPDATE", "DELETE" |
| `actor_id` | UUID | FK → UserProfile NOT NULL | Identity of the requester (server-derived from Bearer token) |
| `timestamp` | TIMESTAMPTZ | NOT NULL | |
| `version_num` | INT | | Version after the operation |
| `diff` | JSONB | | JSON diff of changed fields |

---

### UserProfile

Local user record created on first successful OIDC login. Links external IdP identity
to a system-local UUID.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `external_sub` | TEXT | NOT NULL | `sub` claim from IdP token |
| `external_iss` | TEXT | NOT NULL | `iss` claim (Keycloak issuer URL) |
| `email` | TEXT | NOT NULL | From IdP profile |
| `display_name` | TEXT | NOT NULL | From IdP profile |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `last_login_at` | TIMESTAMPTZ | NOT NULL | Updated on each login |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Admin can deactivate |
| **Unique** | | (external_sub, external_iss) | One profile per IdP identity |

---

### APIKey

Hashed Bearer token bound to a `UserProfile`. Token plaintext returned once at
issuance; only its SHA-256 hash is stored.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `user_id` | UUID | FK → UserProfile NOT NULL | Owning user |
| `token_hash` | TEXT | NOT NULL, UNIQUE | `sha256(token_hex_32)` |
| `label` | TEXT | | Human-readable name (e.g., "ingestion-pipeline") |
| `scopes` | JSONB | | Reserved for future scope restrictions |
| `issued_at` | TIMESTAMPTZ | NOT NULL | |
| `last_used_at` | TIMESTAMPTZ | | Updated on each successful auth |
| `revoked_at` | TIMESTAMPTZ | | NULL = active |
| `revoked_by` | UUID | FK → UserProfile, nullable | Admin who revoked |

---

### UserRole

RBAC role assignment. A user may hold multiple roles; effective permission is the
maximum of all assigned roles.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `user_id` | UUID | FK → UserProfile NOT NULL | |
| `role` | TEXT | NOT NULL | `admin`, `curator`, `contributor`, `viewer` |
| `granted_at` | TIMESTAMPTZ | NOT NULL | |
| `granted_by` | UUID | FK → UserProfile NOT NULL | |
| **PK** | | (user_id, role) | |

---

### SourceMembership

ReBAC resource relationship granting source-scoped write access. Effective role for
a request touching elements from `source_id` is `max(global_role, membership_role)`.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `user_id` | UUID | FK → UserProfile NOT NULL | |
| `source_id` | UUID | FK → SchemaSource NOT NULL | |
| `role` | TEXT | NOT NULL | `owner`, `contributor` |
| `granted_at` | TIMESTAMPTZ | NOT NULL | |
| `granted_by` | UUID | FK → UserProfile NOT NULL | |
| **PK** | | (user_id, source_id) | |

---

## Indexes

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| `data_element` | `uri` | B-tree UNIQUE | URI lookup and deref |
| `data_element` | `superseded_by` | B-tree | Lineage forward-traversal |
| `data_element_version` | `unit` | B-tree | Filter by unit of measurement |
| `data_element_version` | `semantic_graph` | GIN jsonb_path_ops | Semantic graph field queries (property, unit, entity labels) |
| `data_element_version` | `name` | GIN tsvector | Full-text keyword search |
| `data_element_version` | `description` | GIN tsvector | Full-text keyword search |
| `data_element_version` | `name_embedding` | HNSW (pgvector) | Similarity search |
| `data_element` | `source_id` | B-tree | Filter by source |
| `data_element` | `deleted_at` | Partial (IS NULL) | Active elements only |
| `data_element_child` | `parent_id` | B-tree | Child traversal |
| `data_element_child` | `child_id` | B-tree | Reverse nesting lookup |
| `mapping_function` | `uri` | B-tree UNIQUE | URI lookup and deref |
| `mapping_function_version` | `created_by` | B-tree | Filter versions by actor |
| `mapping_input` | `element_id` | B-tree | Reverse mapping lookup |
| `dynamic_schema` | `uri` | B-tree UNIQUE | URI lookup and deref |
| `dynamic_schema` | `superseded_by` | B-tree | Lineage forward-traversal |
| `dynamic_schema_element` | `schema_id` | B-tree | Schema membership lookup |
| `dynamic_schema_element` | `element_id` | B-tree | Element-to-schema reverse lookup |
| `audit_log` | `(record_type, record_id)` | B-tree | History lookup |
| `audit_log` | `actor_id` | B-tree | Filter audit by user |
| `audit_log` | `timestamp` | B-tree | Chronological queries |
| `api_key` | `token_hash` | B-tree UNIQUE | Auth lookup on every request |
| `api_key` | `user_id` | B-tree | List user's keys |
| `user_role` | `user_id` | B-tree | Role check lookup |
| `source_membership` | `(user_id, source_id)` | B-tree | ReBAC check lookup |

---

## State Transitions

### DataElement lifecycle

```
CREATED → ACTIVE → UPDATED (new version, same URI) → ... → DELETED (soft)
                ↑_____________________________________________↑
        │
        └─ SUPERSEDED (semantic change → new DataElement with new URI)
               old.superseded_by = new.id; old.deleted_at set
```

**Minor update** (same URI, new version): description rewording, name typo fix,
`required`/`multivalued` change, `constraints` adjustment, `external_uri` annotation.

**Semantic update** (new URI, new DataElement): `data_type` change, `unit` change,
subject entity change, measured property change, domain change. Triggered via
`POST /elements/{id}/supersede`.

### MappingFunction status

```
ACTIVE → BROKEN  (when an input/output element is deleted)
BROKEN → ACTIVE  (when broken step is replaced via update)
```

### APIKey lifecycle

```
ACTIVE (revoked_at IS NULL) → REVOKED (revoked_at set by owner or admin)
```

### UserProfile status

```
ACTIVE (is_active = TRUE) → INACTIVE (admin sets is_active = FALSE)
INACTIVE → ACTIVE (admin re-activates)
```
