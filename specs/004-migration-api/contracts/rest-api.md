# REST API Contract: Migration API
**Feature**: 004-migration-api | **Date**: 2026-03-07

Base URL: `/api/v1`  |  Port: `8004`
Content-Type: `application/json`
Auth: Bearer JWT on all endpoints.

---

## Dynamic Schema Construction

### `POST /schemas`

Construct and optionally save a dynamic LinkML schema.

Request:
```json
{
  "name": "MyExperimentSchema",
  "version": "2026.03.0",
  "classes": [
    {
      "name": "SubjectMetadata",
      "element_ids": ["uuid-1", "uuid-2", "uuid-3"]
    }
  ],
  "save": true
}
```

Response `200` (synchronous, ≤50 elements):
```json
{
  "schema_id": "uuid",
  "name": "MyExperimentSchema",
  "version": "2026.03.0",
  "linkml_yaml": "id: ...\nname: ...\n...",
  "linkml_jsonld": "{ \"@context\": ... }",
  "status": "published"
}
```

Response `202` (asynchronous, >50 elements):
```json
{ "job_id": "uuid", "status": "pending", "poll_url": "/api/v1/jobs/uuid" }
```

Error `422`: unresolved element IDs listed in `details.unknown_ids`.
Error `409`: name collision — details include conflicting elements with resolution options.

### `GET /schemas/{id}`
Response: stored `DynamicSchema` record with `linkml_yaml`.

### `GET /schemas/{id}/versions`
Response: list of all saved versions for this schema name.

---

## Migration Pathways

### `POST /pathways`

Register a migration pathway.

Request:
```json
{
  "name": "BIDS-1.9-to-DANDI-0.6",
  "source_schema_id": "uuid",
  "target_schema_id": "uuid",
  "direction": "forward",
  "steps": [
    { "position": 0, "mapping_id": "uuid-mapping-a" },
    { "position": 1, "mapping_id": "uuid-mapping-b" }
  ]
}
```

Response `201`: `MigrationPathway` with `inverse_pathway_id` if automatically derived.
Error `422`: unknown mapping_id(s) in steps.
Error `409`: pathway with same source+target+direction already exists — includes
existing pathway ID for disambiguation.

### `GET /pathways`
Query params: `source_schema_id`, `target_schema_id`, `direction`, `status`
Response: `PaginatedList<PathwaySummary>`

### `GET /pathways/{id}`
Response: full `MigrationPathway` with all steps resolved.

### `PUT /pathways/{id}`
Update steps or name. Validates no broken mappings result.

### `DELETE /pathways/{id}`
Soft-delete. Does not delete constituent mappings.

### `POST /pathways/compose`

Compose two pathways (A→B + B→C → A→C).

Request:
```json
{ "pathway_a_id": "uuid", "pathway_b_id": "uuid", "save": true }
```

Response `200`: composed `MigrationPathway` (or `202` if large).
Error `422`: intermediate schema mismatch (B's target ≠ C's source).

---

## Migration Execution

### `POST /migrate`

Execute a migration for one or more records.

Request:
```json
{
  "pathway_id": "uuid",
  "records": [
    { "id": "record-1", "data": { "subject_age": 28, "session_id": "ses-01" } }
  ],
  "direction": "forward",
  "include_passthrough": true
}
```

Response `200` (synchronous, ≤100 records):
```json
{
  "results": [
    {
      "record_id": "record-1",
      "status": "PASS",
      "output": { "age": 28, "session": "ses-01" },
      "report": {
        "overall_status": "PASS",
        "steps_applied": [
          {
            "position": 0,
            "mapping_id": "uuid",
            "output_element": "age",
            "input_values": { "subject_age": 28 },
            "output_value": 28,
            "status": "OK"
          }
        ],
        "unmapped_fields": [],
        "passthrough_fields": [],
        "validation_result": { "status": "PASS", "violations": [] },
        "duration_ms": 12
      }
    }
  ],
  "summary": { "total": 1, "passed": 1, "failed": 0 }
}
```

Response `202` (asynchronous, >100 records): `{ "job_id": "uuid", ... }`
Error `409`: pathway is BROKEN — includes `broken_step` details.
Error `404`: pathway not found.

---

## Schema Diff

### `POST /diff`

Compute schema compatibility report.

Request:
```json
{ "source_schema_id": "uuid", "target_schema_id": "uuid" }
```

Response `200`: `SchemaDiff`
```json
{
  "source_schema_id": "uuid",
  "target_schema_id": "uuid",
  "coverage": "PARTIAL",
  "added": [ { "element_id": "uuid", "name": "dandiset_id", "schema_id": "uuid" } ],
  "removed": [ { "element_id": "uuid", "name": "bids_version" } ],
  "renamed": [
    { "source_element": { "name": "subject_age" }, "target_element": { "name": "age" }, "alias_group_id": "uuid" }
  ],
  "type_changed": [],
  "constraint_changed": [],
  "description_changed": [],
  "draft_pathway": {
    "covered_steps": 12,
    "total_source_elements": 15,
    "gap_elements": ["bids_version"]
  }
}
```

---

## Async Jobs

### `GET /jobs/{id}`
```json
{
  "job_id": "uuid",
  "job_type": "batch_migration",
  "status": "running",
  "progress": 42,
  "result": null,
  "error": null,
  "created_at": "2026-03-07T12:00:00Z",
  "completed_at": null
}
```

### `DELETE /jobs/{id}`
Cancel a pending or running job.

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK (sync result) |
| 201 | Created (pathway registered) |
| 202 | Accepted (async job started) |
| 404 | Not Found |
| 409 | Conflict (broken pathway, duplicate pathway, name collision) |
| 422 | Unprocessable (unknown IDs, schema mismatch) |
| 500 | Internal Server Error |
