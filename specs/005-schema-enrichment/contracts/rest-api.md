# REST API Contract: Schema Enrichment

**Feature**: `005-schema-enrichment` | **Date**: 2026-03-09
**Base**: `http://localhost:8002/api/v1`
**Auth**: Bearer token (`Authorization: Bearer <api_key>`) required on all write endpoints.

---

## Schema Classes

### `GET /api/v1/schemas/{schema_id}/classes`

Returns all `SchemaClass` records associated with the schema's source.

**Response 200**:
```json
{
  "schema_id": "uuid",
  "classes": [
    {
      "id": "uuid",
      "class_name": "Subject",
      "description": "...",
      "parent_class_id": null,
      "elements": [
        {
          "element_id": "uuid",
          "name": "subject_id",
          "data_type": "string",
          "element_kind": "scalar",
          "required": true,
          "position": 0
        },
        {
          "element_id": "uuid",
          "name": "sex",
          "data_type": "string",
          "element_kind": "enumeration",
          "required": false,
          "allowed_values": ["M", "F", "O"],
          "position": 1
        }
      ]
    }
  ]
}
```

**Errors**: 404 if schema not found.

---

### `GET /api/v1/schemas/{schema_id}/resolved`

Returns the fully resolved schema with all inherited and mixin elements, in
C3 MRO order. Each element includes a `source_schema` annotation.

**Query params**:
- `include_provenance_mixin` (bool, default false): if true and schema has
  ProvenanceMixin, include its 4 elements in the response.

**Response 200**:
```json
{
  "schema_id": "uuid",
  "name": "ExtendedSubjectSchema",
  "mro": ["ExtendedSubjectSchema", "BaseSubjectSchema", "ProvenanceMixin"],
  "elements": [
    {
      "element_id": "uuid",
      "name": "study_id",
      "data_type": "string",
      "element_kind": "scalar",
      "required": true,
      "source_schema": "ExtendedSubjectSchema",
      "override": false
    },
    {
      "element_id": "uuid",
      "name": "subject_id",
      "data_type": "string",
      "element_kind": "scalar",
      "required": true,
      "source_schema": "BaseSubjectSchema",
      "override": false
    },
    {
      "element_id": "uuid",
      "name": "prov_created_by",
      "data_type": "string",
      "element_kind": "scalar",
      "required": true,
      "source_schema": "ProvenanceMixin",
      "override": false
    }
  ]
}
```

**Errors**: 404, 409 (circular inheritance detected — should be prevented at
write time but guard here too).

---

### `GET /api/v1/schemas/{schema_id}/inheritance-tree`

Returns the full ancestor + mixin graph as an adjacency list.

**Response 200**:
```json
{
  "schema_id": "uuid",
  "nodes": [
    {"id": "uuid", "name": "ExtendedSubject", "is_mixin": false},
    {"id": "uuid", "name": "BaseSubject", "is_mixin": false},
    {"id": "uuid", "name": "ProvenanceMixin", "is_mixin": true}
  ],
  "edges": [
    {"from": "ExtendedSubject", "to": "BaseSubject", "type": "inherits"},
    {"from": "ExtendedSubject", "to": "ProvenanceMixin", "type": "mixin", "position": 0}
  ]
}
```

---

### `PUT /api/v1/schemas/{schema_id}/parent`

Set or change the parent schema for inheritance.

**Request body**:
```json
{"parent_id": "uuid or null"}
```

**Response 200**: Updated DynamicSchema record.

**Errors**:
- `409 Conflict` — would create a cycle.
- `422 Unprocessable Entity` — `parent_id` depth would exceed 20.
- `404` — parent schema not found.

---

### `POST /api/v1/schemas/{schema_id}/mixins`

Attach a mixin schema to a base schema.

**Request body**:
```json
{"mixin_id": "uuid", "position": 0}
```

**Response 201**: Created `SchemaMixin` record.

**Errors**:
- `400` — target schema is not marked `is_mixin = true`.
- `409` — would create a cycle or mixin already attached.

---

### `DELETE /api/v1/schemas/{schema_id}/mixins/{mixin_id}`

Detach a mixin from a base schema.

**Response 204**: No content.

**Errors**: 404 if mixin relationship not found.

---

### `POST /api/v1/schemas/{schema_id}/provenance-mixin`

Attach the system `ProvenanceMixin` to a schema (shorthand for
`POST /mixins` with the ProvenanceMixin's system ID).

**Response 201**: `{"attached": true, "mixin_id": "system-uuid"}`.

---

### `DELETE /api/v1/schemas/{schema_id}/provenance-mixin`

Detach the ProvenanceMixin from a schema.

**Response 204**: No content.

---

## Schema Changelog & Provenance

### `GET /api/v1/schemas/{schema_id}/changelog`

Paginated history of schema mutations.

**Query params**: `page` (default 1), `size` (default 20), `breaking_only` (bool).

**Response 200**:
```json
{
  "schema_id": "uuid",
  "total": 14,
  "page": 1,
  "size": 20,
  "entries": [
    {
      "id": "uuid",
      "operation": "ADD_ELEMENT",
      "actor_id": "uuid",
      "actor_name": "Jane Doe",
      "timestamp": "2026-03-09T12:00:00Z",
      "activity_type": "schema_edit",
      "diff": {"added": [{"element_id": "uuid", "name": "sex"}]},
      "breaking": false,
      "semantic_boundary_crossed": false,
      "reason": null
    }
  ]
}
```

---

### `GET /api/v1/schemas/{schema_id}/provenance`

Returns schema provenance as W3C PROV-DM JSON-LD.

**Response 200** (`Content-Type: application/ld+json`):
```json
{
  "@context": "http://www.w3.org/ns/prov",
  "@graph": [
    {
      "@type": "prov:Entity",
      "@id": "https://undata.io/schemas/{schema_id}",
      "prov:wasGeneratedBy": {"@id": "urn:activity:{latest_log_id}"},
      "prov:wasAttributedTo": {"@id": "urn:agent:{actor_id}"},
      "prov:wasDerivedFrom": {"@id": "https://undata.io/schemas/{parent_id}"}
    },
    {
      "@type": "prov:Activity",
      "@id": "urn:activity:{latest_log_id}",
      "prov:startedAtTime": "2026-03-09T12:00:00Z",
      "prov:endedAtTime": "2026-03-09T12:00:01Z"
    },
    {
      "@type": "prov:Agent",
      "@id": "urn:agent:{actor_id}",
      "foaf:name": "Jane Doe"
    }
  ]
}
```

---

## Validation Rules

### `GET /api/v1/elements/{element_id}/validation-rules`

Return all active (non-deleted) ValidationRule records for an element.

**Response 200**:
```json
{
  "element_id": "uuid",
  "rules": [
    {
      "id": "uuid",
      "rule_type": "enum_set",
      "rule_value": {"values": ["M", "F", "O"]},
      "severity": "error",
      "description": "Biological sex",
      "created_at": "2026-03-09T10:00:00Z",
      "created_by": "uuid"
    },
    {
      "id": "uuid",
      "rule_type": "range",
      "rule_value": {"min": 0, "max": 120},
      "severity": "warning",
      "description": null,
      "created_at": "2026-03-09T10:01:00Z",
      "created_by": "uuid"
    }
  ]
}
```

---

### `POST /api/v1/elements/{element_id}/validation-rules`

Attach a new ValidationRule to an element.

**Request body**:
```json
{
  "rule_type": "enum_set",
  "rule_value": {"values": ["M", "F", "O"]},
  "severity": "error",
  "description": "Biological sex"
}
```

**Response 201**: Created ValidationRule record + initial `ValidationRuleChange`
with `operation=CREATE`, `breaking=false`.

**Errors**:
- `409` — rule of this `rule_type` already exists for this element (one active
  rule per type per element).
- `422` — `rule_value` schema invalid for the given `rule_type`.

---

### `PUT /api/v1/elements/{element_id}/validation-rules/{rule_id}`

Update an existing ValidationRule. Returns the updated rule plus breaking
change classification.

**Request body**:
```json
{
  "rule_value": {"values": ["M", "F"]},
  "reason": "Removing 'O' per updated data dictionary"
}
```

**Response 200**:
```json
{
  "rule": {
    "id": "uuid",
    "rule_type": "enum_set",
    "rule_value": {"values": ["M", "F"]},
    "severity": "error"
  },
  "change": {
    "id": "uuid",
    "operation": "UPDATE",
    "old_value": {"values": ["M", "F", "O"]},
    "new_value": {"values": ["M", "F"]},
    "breaking": true,
    "reason": "Removing 'O' per updated data dictionary",
    "timestamp": "2026-03-09T12:05:00Z"
  }
}
```

---

### `DELETE /api/v1/elements/{element_id}/validation-rules/{rule_id}`

Soft-delete a ValidationRule (sets `deleted_at`). Records a
`ValidationRuleChange` with `operation=DELETE`, `breaking=false` (removing a
rule is always non-breaking — it relaxes constraints).

**Response 200**:
```json
{
  "deleted": true,
  "change": {
    "operation": "DELETE",
    "breaking": false,
    "timestamp": "2026-03-09T12:06:00Z"
  }
}
```

---

## Schema Classes — Management

### `POST /api/v1/sources/{source_id}/classes`

Create a `SchemaClass` for a source.

**Request body**:
```json
{
  "class_name": "Subject",
  "description": "An experimental subject",
  "parent_class_id": null
}
```

**Response 201**: Created SchemaClass record.

---

### `GET /api/v1/sources/{source_id}/classes`

List all SchemaClass records for a source.

**Response 200**: `{"classes": [{...}]}`

---

### `POST /api/v1/sources/{source_id}/classes/{class_id}/elements`

Add a DataElement to a SchemaClass (creates `SchemaClassElement`).

**Request body**: `{"element_id": "uuid", "position": 0}`

**Response 201**: `{"class_id": "...", "element_id": "...", "position": 0}`

---

## Error Responses

All endpoints use the standard error envelope:

```json
{
  "error": "short_code",
  "message": "Human-readable description",
  "detail": {}
}
```

| HTTP Status | `error` code | Meaning |
|-------------|-------------|---------|
| 400 | `invalid_request` | Malformed body or bad parameter |
| 401 | `unauthorized` | Missing or invalid Bearer token |
| 403 | `forbidden` | Authenticated but lacking permission |
| 404 | `not_found` | Resource not found |
| 409 | `conflict` | Cycle detected / duplicate / constraint violated |
| 422 | `validation_error` | rule_value schema invalid; depth > 20 |
| 500 | `internal_error` | Unexpected server error |
