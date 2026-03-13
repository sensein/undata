# REST API Contract: Schema Backend Service
**Feature**: 002-schema-backend | **Date**: 2026-03-08

Base URL: `/api/v1`
Content-Type: `application/json`
Auth: Bearer token (API key) required on **all write endpoints and user-specific reads**.
Read endpoints (`GET /elements`, `GET /mappings`, etc.) are unauthenticated.
Actor identity is **always server-derived from the validated token** — request bodies
MUST NOT include `created_by` or `updated_by` fields; they are ignored if present.

---

## Common Patterns

### Pagination (all list endpoints)
```
?limit=50&offset=0
```
Response wraps items in:
```json
{ "total": 1234, "limit": 50, "offset": 0, "items": [ ... ] }
```

### Optimistic concurrency (all PUT/DELETE)
Request body must include `"version_num": <current>`.
On mismatch: `409 Conflict` with `"expected": <current>, "actual": <stored>`.

### Error envelope
```json
{ "error": "short_code", "message": "Human-readable detail", "details": { ... } }
```

---

## Authentication & Identity

### `GET /auth/login`
Redirect to Keycloak OIDC authorization endpoint.
Query params: `provider` — optional hint (`globus`, `github`, `incommon`).
Response `302`: redirect to Keycloak with `state` and `nonce` cookies set.

### `GET /auth/callback`
OIDC authorization code callback. Exchanges code for token, validates JWT (RS256 + JWKS),
upserts `UserProfile` from `sub`+`iss` claims, creates session.
Response `302`: redirect to frontend.
Error `401`: invalid state or token validation failure.

### `POST /auth/logout`
Invalidates server-side session.
Response `200`: `{ "status": "logged_out" }`

---

## User Profiles

### `GET /users/me`
Returns the authenticated user's profile.
Response: `UserProfile`

`UserProfile`:
```json
{
  "id": "uuid",
  "email": "user@institution.edu",
  "display_name": "Alice Researcher",
  "roles": ["curator"],
  "source_memberships": [
    { "source_id": "uuid", "source_name": "BIDS", "role": "owner" }
  ],
  "created_at": "2026-03-08T00:00:00Z",
  "last_login_at": "2026-03-08T00:00:00Z",
  "is_active": true
}
```

### `GET /users` *(admin only)*
List all user profiles.
Response: `PaginatedList<UserProfileSummary>`

### `GET /users/{id}` *(admin only)*
Response: `UserProfile`

### `PUT /users/{id}/roles` *(admin only)*
Assign or replace global RBAC roles.
Body: `{ "roles": ["curator"] }`
Response `200`: `UserProfile`

### `PUT /users/{id}/sources/{source_id}` *(admin only)*
Set source membership role for a user.
Body: `{ "role": "owner" }`
Response `200`: `{ "user_id": "uuid", "source_id": "uuid", "role": "owner" }`

### `DELETE /users/{id}/sources/{source_id}` *(admin only)*
Remove source membership.
Response `200`.

---

## API Keys (Tokens)

### `GET /tokens`
List the authenticated user's active API keys (token hashes not returned).
Response: `PaginatedList<APIKeySummary>`

`APIKeySummary`:
```json
{
  "id": "uuid",
  "label": "ingestion-pipeline",
  "issued_at": "2026-03-08T00:00:00Z",
  "last_used_at": "2026-03-08T01:00:00Z",
  "revoked_at": null
}
```

### `POST /tokens`
Issue a new API key for the authenticated user.
Body: `{ "label": "ingestion-pipeline" }`
Response `201`:
```json
{
  "id": "uuid",
  "label": "ingestion-pipeline",
  "token": "<64-char hex — returned once only>",
  "issued_at": "2026-03-08T00:00:00Z"
}
```

### `DELETE /tokens/{id}`
Revoke an API key. Users may revoke their own keys; admins may revoke any key.
Response `200`: `{ "id": "uuid", "revoked_at": "..." }`

### `GET /tokens` *(admin: all users)*
Admin may pass `?user_id=<uuid>` to list another user's keys.

---

## Schema Sources

### `GET /sources`
List all registered schema sources.
Response: `PaginatedList<SchemaSourceSummary>`

### `POST /sources`
Register a new schema source.
```json
{
  "name": "BIDS",
  "format": "yaml",
  "url": "https://github.com/bids-standard/bids-specification",
  "version_tag": "1.9.0",
  "content_hash": "sha256:abc123..."
}
```
Response `201`: `SchemaSource`

### `GET /sources/{id}`
Response: `SchemaSource`

### `PUT /sources/{id}`
Update metadata (not format). Body: partial update + `version_num`.
Response `200`: `SchemaSource`

---

## Data Elements

### `GET /elements`
Search and filter data elements.
Query params:
- `q` — keyword search (name + description)
- `source_id` — filter by schema source UUID
- `data_type` — filter by type string
- `unit` — filter by unit label (e.g. `?unit=Celsius`)
- `subject` — filter by entity subject label in semantic graph (e.g. `?subject=water`)
- `property` — filter by property label in semantic graph (e.g. `?property=temperature`)
- `has_aliases` — `true`/`false`
- `has_mappings` — `true`/`false`
- `include_superseded` — `true`/`false` (default `false`; when `false` superseded elements are excluded)
- `limit`, `offset`

Response: `PaginatedList<DataElementSummary>`

`DataElementSummary`:
```json
{
  "id": "uuid",
  "uri": "https://undata.io/elements/uuid",
  "name": "subject_age",
  "data_type": "number",
  "description": "Age of the research subject in years",
  "required": false,
  "multivalued": false,
  "source": { "id": "uuid", "name": "BIDS" },
  "unit": "years",
  "alias_count": 3,
  "mapping_count": 2,
  "version_num": 1,
  "superseded_by": null
}
```

### `POST /elements`
Create a single data element. Actor identity is derived from the Bearer token.
```json
{
  "name": "temperature_water_celsius",
  "data_type": "number",
  "description": "Temperature of a water sample in degrees Celsius",
  "required": false,
  "multivalued": false,
  "allowed_values": null,
  "constraints": { "minimum": -273.15 },
  "source_id": "uuid",
  "source_local_id": "water-temp-c",
  "semantic_graph": {
    "entities": [{ "label": "water", "type": "Material", "role": "subject",
                   "external_uri": "http://purl.obolibrary.org/obo/CHEBI_15377" }],
    "property": { "label": "temperature", "type": "PhysicalProperty",
                  "external_uri": "http://purl.obolibrary.org/obo/PATO_0000146" },
    "unit": { "label": "degree Celsius", "symbol": "°C",
              "external_uri": "http://qudt.org/vocab/unit/DEG_C",
              "cmixf_valid": true, "qudt_unresolvable": false },
    "relations": [{ "subject": "water", "predicate": "hasProperty", "object": "temperature" }],
    "domain": "Material",
    "range_type": "xsd:decimal",
    "context": "Temperature of a water sample measured in degrees Celsius"
  }
}
```
Note: `semantic_graph` is optional (may be `null` for categorical/boolean elements where
unit and entity relationships are not applicable). The `unit` field on the response is
extracted server-side from `semantic_graph.unit.label` — do NOT send `unit` directly.

**Unit enrichment**: The server automatically enriches `semantic_graph.unit` at write time:
- `external_uri`: auto-resolved QUDT URI (clients SHOULD NOT send this)
- `cmixf_valid`: set by the server after validating `symbol` against cmixf-12 grammar
- `qudt_unresolvable`: set to `true` if the server could not resolve a QUDT URI

Clients SHOULD provide `symbol` in cmixf format when known (e.g. `°C`, `kg`, `ms`).
For units without a cmixf symbol (e.g. "year"), providing only `label` is acceptable —
the server will attempt QUDT resolution via label lookup.
Response `201`: `DataElement`
Error `403`: actor lacks `contributor` role (or higher) and has no `owner`/`contributor` membership on `source_id`.

### `POST /elements/bulk`
Bulk create (atomic per element, partial success allowed). Actor from Bearer token.
Body: `{ "elements": [ ... ] }`
Response `207 Multi-Status`:
```json
{
  "succeeded": [ { "index": 0, "id": "uuid", "uri": "https://undata.io/elements/uuid" }, ... ],
  "failed": [ { "index": 2, "error": "duplicate_key", "message": "..." }, ... ]
}
```

### `GET /elements/{id}`
Full element detail.
`DataElement`:
```json
{
  "id": "uuid",
  "uri": "https://undata.io/elements/uuid",
  "name": "temperature_water_celsius",
  "data_type": "number",
  "description": "Temperature of a water sample in degrees Celsius",
  "required": false,
  "multivalued": false,
  "allowed_values": null,
  "constraints": { "minimum": -273.15 },
  "unit": "degree Celsius",
  "semantic_graph": {
    "entities": [
      { "label": "water", "type": "Material", "role": "subject",
        "external_uri": "http://purl.obolibrary.org/obo/CHEBI_15377" }
    ],
    "property": { "label": "temperature", "type": "PhysicalProperty",
                  "external_uri": "http://purl.obolibrary.org/obo/PATO_0000146" },
    "unit": { "label": "degree Celsius", "symbol": "°C",
              "external_uri": "http://qudt.org/vocab/unit/DEG_C",
              "cmixf_valid": true, "qudt_unresolvable": false },
    "relations": [
      { "subject": "water", "predicate": "hasProperty", "object": "temperature" }
    ],
    "domain": "Material",
    "range_type": "xsd:decimal",
    "context": "Temperature of a water sample measured in degrees Celsius"
  },
  "source": { "id": "uuid", "name": "BIDS", "version_tag": "1.9.0" },
  "source_local_id": "water-temp-c",
  "superseded_by": null,
  "supersedes": null,
  "children": [
    { "id": "uuid", "uri": "https://undata.io/elements/uuid2", "field_name": "unit", "position": 0 }
  ],
  "alias_groups": [ { "id": "uuid", "name": "...", "member_count": 3 } ],
  "mappings_as_input": [ { "id": "uuid", "uri": "https://undata.io/mappings/uuid", "output_name": "temperature_water_fahrenheit" } ],
  "mappings_as_output": [ { "id": "uuid", "uri": "https://undata.io/mappings/uuid", "function_type": "custom" } ],
  "version_num": 1,
  "created_at": "2026-03-07T00:00:00Z",
  "deleted_at": null
}
```

### `PUT /elements/{id}`
Update element content. Creates a new version. Actor identity is derived from the
Bearer token — `updated_by` is NOT accepted in the request body.
Body: updatable fields + `version_num` (optimistic lock).
Updatable fields: `name`, `data_type`, `description`, `required`, `multivalued`,
`allowed_values`, `constraints`, `semantic_graph`.
Response `200`: `DataElement`

### `DELETE /elements/{id}`
Soft-delete. Actor identity is derived from the Bearer token — `deleted_by` is NOT
accepted in the request body.
Body: `{ "version_num": <current> }`.
Response `200`: `{ "id": "uuid", "deleted_at": "..." }`
Side effect: all MappingFunctions referencing this element are set to `status: broken`.

### `POST /elements/{id}/supersede`
Create a semantically distinct replacement element. The existing element is
soft-deprecated (`deleted_at` set, `superseded_by` → new element's id). The new element
is created with a new UUID and a new URI. Requires `curator` role or source
`owner`/`contributor` membership.
Body: full `DataElementCreate` payload plus required `supersede_reason` field:
```json
{
  "name": "temperature_water_fahrenheit",
  "data_type": "number",
  "description": "Temperature of a water sample in degrees Fahrenheit",
  "required": false,
  "multivalued": false,
  "constraints": { "minimum": -459.67 },
  "source_id": "uuid",
  "source_local_id": "water-temp-f",
  "semantic_graph": {
    "entities": [{ "label": "water", "type": "Material", "role": "subject" }],
    "property": { "label": "temperature", "type": "PhysicalProperty" },
    "unit": { "label": "degree Fahrenheit", "symbol": "°F",
              "external_uri": "http://qudt.org/vocab/unit/DEG_F",
              "cmixf_valid": true, "qudt_unresolvable": false },
    "relations": [{ "subject": "water", "predicate": "hasProperty", "object": "temperature" }],
    "domain": "Material",
    "range_type": "xsd:decimal"
  },
  "supersede_reason": "Unit changed from Celsius to Fahrenheit — semantic change"
}
```
Response `201`: `DataElement` (new element with new URI, `supersedes` = old element URI).
The old element is simultaneously updated: `superseded_by` = new element id, `deleted_at` set.
Both audit entries (SUPERSEDE on old, CREATE on new) are written in the same transaction.

### `GET /elements/{id}/history`
Full version history, oldest first.
Response: `List<DataElementVersion>`

---

## Mappings

### `GET /mappings`
Query params: `source_element_id`, `target_element_id`, `function_type`, `status`, `limit`, `offset`
Response: `PaginatedList<MappingFunctionSummary>`

### `POST /mappings`
Register a mapping function. Actor identity from Bearer token; requires `curator` role
or source `owner`/`contributor` membership on the output element's source.
```json
{
  "function_type": "custom",
  "input_element_ids": ["uuid-a", "uuid-b"],
  "output_element_id": "uuid-c",
  "description": "Convert age_years + age_unit → age_days",
  "expression": "input_0 * (365 if input_1 == 'years' else 1)",
  "expression_type": "python_expr",
  "parameter_schema": null,
  "sssom_predicate": "skos:relatedMatch"
}
```
Response `201`: `MappingFunction`
Error `422 Unprocessable`: if any `input_element_id` or `output_element_id` not found.
Error `409 Conflict`: if registration would create a circular dependency
  — includes `"cycle_path": ["uuid-c", "uuid-a"]` in details.

### `GET /mappings/{id}`
Response: `MappingFunction` (full detail with input elements, output element, versions)

### `PUT /mappings/{id}`
Update expression/description. Creates a new version.
Response `200`: `MappingFunction`

### `DELETE /mappings/{id}`
Soft-delete. Response `200`.

### `GET /mappings/{id}/history`
Response: `List<MappingFunctionVersion>`

---

## Alias Groups

### `GET /aliases`
Query params: `element_id` (filter by member), `limit`, `offset`
Response: `PaginatedList<AliasGroupSummary>`

### `POST /aliases`
Create alias group manually. Actor from Bearer token; requires `curator` role.
```json
{
  "name": "subject-age-group",
  "element_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "sssom_predicate": "skos:exactMatch",
  "detection_method": "manual"
}
```
Response `201`: `AliasGroup`
Side effect: creates identity `MappingFunction` records for all element pairs (cycle-checked).

### `POST /aliases/detect`
On-demand similarity-based alias detection. Computes embeddings cosine similarity and
returns candidate alias pairs above the configured threshold. Does **not** create any
alias groups or mappings — caller reviews results and manually calls `POST /aliases`.
Requires `curator` role or higher.
```json
{
  "source_id": "uuid",
  "threshold": 0.88,
  "cross_source_only": true,
  "limit": 50,
  "offset": 0
}
```
All fields optional: omit `source_id` to scan all elements; omit `threshold` to use the
`ALIAS_SIMILARITY_THRESHOLD` env var default (0.88); `cross_source_only` (default `false`)
restricts results to pairs whose two elements belong to **different** `SchemaSource` records —
use this when curating the undata canonical space.

Response `200`: `PaginatedList<AliasCandidatePair>`

`AliasCandidatePair`:
```json
{
  "element_a": { "id": "uuid", "name": "subject_age", "source": "BIDS" },
  "element_b": { "id": "uuid", "name": "participant_age", "source": "DANDI" },
  "similarity_score": 0.94,
  "suggested_predicate": "skos:exactMatch",
  "semantic_graph_overlap": {
    "property_match": true,
    "unit_match": true,
    "entity_labels_match": false,
    "domain_match": null
  }
}
```
`semantic_graph_overlap` is computed from the `semantic_graph` JSONB of each element's
current version. `domain_match` is `null` when `domain` is absent from both graphs,
otherwise a boolean. Always present in response (never omitted).

### `GET /aliases/{id}`
Response: `AliasGroup` with full member list.

### `PUT /aliases/{id}`
Add or remove members. Body: `{ "add": ["uuid"], "remove": ["uuid"], "version_num": 1 }`
Response `200`: `AliasGroup`

### `DELETE /aliases/{id}`
Delete alias group (does not delete member elements or identity mappings).
Response `200`.

---

## Dynamic Schemas

### `GET /schemas`
List all dynamic schemas.
Query params: `q` (name search), `element_id` (filter to schemas containing element), `limit`, `offset`
Response: `PaginatedList<DynamicSchemaSummary>`

`DynamicSchemaSummary`:
```json
{
  "id": "uuid",
  "uri": "https://undata.io/schemas/uuid",
  "name": "NWB session schema",
  "element_count": 12,
  "version_num": 2
}
```

### `POST /schemas`
Create a dynamic schema from a named set of element references.
Requires `curator` role or source `owner`/`contributor` membership on all referenced elements' sources.
```json
{
  "name": "NWB session schema",
  "description": "Fields required for an NWB session record",
  "elements": [
    { "element_id": "uuid", "position": 0, "field_alias": null },
    { "element_id": "uuid2", "position": 1, "field_alias": "subject_age_years" }
  ]
}
```
Response `201`: `DynamicSchema`

`DynamicSchema`:
```json
{
  "id": "uuid",
  "uri": "https://undata.io/schemas/uuid",
  "name": "NWB session schema",
  "description": "...",
  "superseded_by": null,
  "supersedes": null,
  "elements": [
    {
      "element_id": "uuid",
      "element_uri": "https://undata.io/elements/uuid",
      "element_name": "temperature_water_celsius",
      "element_unit": "degree Celsius",
      "element_superseded_by": null,
      "position": 0,
      "field_alias": null
    }
  ],
  "version_num": 1,
  "created_at": "2026-03-08T00:00:00Z",
  "updated_at": "2026-03-08T00:00:00Z"
}
```

### `GET /schemas/{id}`
Response: `DynamicSchema` (full detail with all element references and their URIs).

### `PUT /schemas/{id}`
Add or remove element references. Body: `{ "add": [...], "remove": ["uuid"], "version_num": 1 }`.
Response `200`: `DynamicSchema`. Creates a new internal snapshot; URI is unchanged.

### `DELETE /schemas/{id}`
Soft-delete. Response `200`.

### `POST /schemas/{id}/supersede`
Create a semantically distinct replacement schema. The existing schema is soft-deprecated
(`deleted_at` set, `superseded_by` → new schema's id). Requires `curator` role.
Body: full `DynamicSchemaCreate` payload plus required `supersede_reason`:
```json
{
  "name": "NWB session schema v2",
  "description": "Extended NWB session with thermal measurements",
  "elements": [ { "element_id": "uuid-new", "position": 0 } ],
  "supersede_reason": "Added temperature_water_fahrenheit; scope changed"
}
```
Response `201`: `DynamicSchema` (new schema, new URI, `supersedes` = old schema URI).
Old schema simultaneously gains `superseded_by` and `deleted_at`. Both audit entries
written in the same transaction.

---

## Audit Log

### `GET /audit`
Query params: `record_type`, `record_id`, `operation`, `actor`, `from`, `to`, `limit`, `offset`
Response: `PaginatedList<AuditEntry>`

`AuditEntry`:
```json
{
  "id": "uuid",
  "record_type": "DataElement",
  "record_id": "uuid",
  "operation": "UPDATE",
  "actor_id": "uuid",
  "actor_display_name": "Alice Researcher",
  "timestamp": "2026-03-07T12:00:00Z",
  "version_num": 2,
  "diff": { "description": { "old": "...", "new": "..." } }
}
```

---

## Units

Read-only inspection endpoints for unit symbols used across active elements. No authentication
required. Unit resolution (cmixf validation + QUDT lookup) happens automatically at element
create/update time — these endpoints expose the results.

### `GET /units`

Paginated list of distinct unit symbols used in active `DataElementVersion.semantic_graph.unit`
nodes, with their resolution status.

Query params:
- `resolved` — `true` | `false` | *(omit for all)*
- `limit`, `offset` — pagination

Response: `PaginatedList<UnitSummary>`

`UnitSummary`:
```json
{
  "label": "degree Celsius",
  "symbol": "°C",
  "cmixf_valid": true,
  "qudt_uri": "http://qudt.org/vocab/unit/DEG_C",
  "qudt_unresolvable": false,
  "element_count": 42
}
```

Fields:
- `label` — unit label from `semantic_graph.unit.label`
- `symbol` — unit symbol from `semantic_graph.unit.symbol` (may be null)
- `cmixf_valid` — `true` if symbol passed cmixf-12 validation; `false` if it did not; `null` if no symbol
- `qudt_uri` — resolved QUDT ontology URI; `null` if unresolvable
- `qudt_unresolvable` — `true` if resolution was attempted but failed; `false` otherwise
- `element_count` — number of active elements using this unit label

---

### `GET /units/unresolvable`

Convenience shortcut — equivalent to `GET /units?resolved=false`.

Returns only unit entries where `qudt_unresolvable = true`.

Response: `PaginatedList<UnitSummary>` (same shape as above).

---

### Unit enrichment in `SemanticGraphUnit`

The `unit` node inside `DataElementResponse.semantic_graph` includes the following
server-populated fields (in addition to client-supplied `label` and `symbol`):

```json
{
  "label": "year",
  "symbol": null,
  "external_uri": "http://qudt.org/vocab/unit/YR",
  "cmixf_valid": null,
  "qudt_unresolvable": false
}
```

```json
{
  "label": "some-nonstandard-unit",
  "symbol": "cux",
  "external_uri": null,
  "cmixf_valid": false,
  "qudt_unresolvable": true
}
```

Clients SHOULD NOT send `external_uri`, `cmixf_valid`, or `qudt_unresolvable` — they are
server-derived and any client-supplied values are silently ignored.

---

## HTTP Status Code Summary

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 207 | Multi-Status (bulk operations) |
| 302 | Redirect (OIDC login/callback) |
| 400 | Bad Request (malformed input) |
| 401 | Unauthorized (missing, invalid, or revoked Bearer token) |
| 403 | Forbidden (authenticated but insufficient role or source membership) |
| 404 | Not Found |
| 409 | Conflict (version mismatch or cycle detected) |
| 422 | Unprocessable Entity (referenced resource not found) |
| 500 | Internal Server Error |
