# Contract: LinkML Import/Export API

**Feature**: 011-metamodel-provenance
**Date**: 2026-03-12

---

## GET /schemas/{schema_id}/linkml

Exports a `DynamicSchema` as a LinkML YAML document.

### Request

```
GET /api/v1/schemas/{schema_id}/linkml
Authorization: Bearer <token>
Accept: application/yaml
```

### Response 200

```yaml
id: https://undata.org/schemas/{schema_id}
name: ExampleSchema
description: Exported by undata backend

prefixes:
  linkml: https://w3id.org/linkml/

imports:
  - linkml:types

classes:
  ExampleSchema:
    description: Example schema class
    slots:
      - age
      - name

slots:
  age:
    range: integer
    required: false
  name:
    range: string
    required: true
    aliases:
      - full_name
      - display_name
```

### Response Headers

```
Content-Type: application/yaml
X-Roundtrip-Fidelity: 0.87
```

Fidelity score interpretation:
- `1.0`: Lossless roundtrip possible
- `0.5–0.99`: Minor information loss (alias groups, PROV metadata, version comments)
- `< 0.5`: Significant structural transformation required

### Response 404

```json
{ "detail": "schema not found" }
```

---

## POST /schemas/import/linkml

Imports a LinkML YAML schema into the backend.

### Request

```
POST /api/v1/schemas/import/linkml
Authorization: Bearer <token>
Content-Type: application/yaml

<LinkML YAML body>
```

### Response 201

```json
{
  "schema_id": "a1b2c3d4-...",
  "fidelity_score": 0.92,
  "loss_points": [
    "slot_uri_unknown: age",
    "prov_metadata_ignored"
  ]
}
```

### Response 409

```json
{ "detail": "schema_uri_conflict" }
```

Returned when the `id` field in the LinkML YAML matches an existing `DynamicSchema` URI.

### Response 422

```json
{ "detail": "invalid_linkml_yaml", "message": "<parse error>" }
```

---

## PUT /mappings/{mapping_id}/accept

Accept a `pending_curation` mapping, optionally via a confidence threshold.

### Request

```
PUT /api/v1/mappings/{mapping_id}/accept?confidence_threshold=0.8
Authorization: Bearer <token>
```

### Response 200

```json
{
  "id": "...",
  "status": "active",
  "confidence_score": 0.91
}
```

### Response 422

Returned when `confidence_score < confidence_threshold`:
```json
{ "detail": "confidence_below_threshold", "confidence_score": 0.65, "threshold": 0.8 }
```

### Response 404

```json
{ "detail": "mapping not found" }
```
