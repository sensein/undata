# Contract: Provenance API

**Feature**: 011-metamodel-provenance
**Date**: 2026-03-12

---

## GET /elements/{element_id}/provenance

Returns the PROV-O provenance history for a `DataElement`.

### Request

```
GET /api/v1/elements/{element_id}/provenance
Authorization: Bearer <token>
Accept: application/ld+json
```

### Response 200

```json
{
  "@context": "https://www.w3.org/ns/prov.jsonld",
  "@graph": [
    {
      "@id": "https://undata.org/elements/{uuid}",
      "@type": "prov:Entity",
      "prov:wasGeneratedBy": { "@id": "https://undata.org/activities/{audit_id}" },
      "prov:wasAttributedTo": { "@id": "https://undata.org/agents/{user_id}" }
    },
    {
      "@id": "https://undata.org/activities/{audit_id}",
      "@type": "prov:Activity",
      "prov:startedAtTime": { "@value": "2026-03-12T10:00:00Z", "@type": "xsd:dateTime" },
      "prov:endedAtTime":   { "@value": "2026-03-12T10:00:01Z", "@type": "xsd:dateTime" },
      "prov:wasAssociatedWith": { "@id": "https://undata.org/agents/{user_id}" }
    },
    {
      "@id": "https://undata.org/agents/{user_id}",
      "@type": "prov:Agent",
      "prov:label": "Test User"
    }
  ]
}
```

### Response 404

```json
{ "detail": "element not found" }
```

---

## GET /schemas/{schema_id}/provenance

Returns the PROV-O provenance history for a `DynamicSchema`, including version
derivation chain.

### Request

```
GET /api/v1/schemas/{schema_id}/provenance
Authorization: Bearer <token>
Accept: application/ld+json
```

### Response 200

```json
{
  "@context": "https://www.w3.org/ns/prov.jsonld",
  "@graph": [
    {
      "@id": "https://undata.org/schemas/{uuid_v2}",
      "@type": "prov:Entity",
      "prov:wasDerivedFrom": { "@id": "https://undata.org/schemas/{uuid_v1}" },
      "prov:wasGeneratedBy": { "@id": "https://undata.org/activities/{changelog_id}" }
    },
    {
      "@id": "https://undata.org/schemas/{uuid_v1}",
      "@type": "prov:Entity"
    },
    {
      "@id": "https://undata.org/activities/{changelog_id}",
      "@type": "prov:Activity",
      "prov:startedAtTime": { "@value": "2026-03-12T11:00:00Z", "@type": "xsd:dateTime" },
      "prov:wasAssociatedWith": { "@id": "https://undata.org/agents/{user_id}" }
    }
  ]
}
```

### Response Headers

```
Content-Type: application/ld+json
```

---

## Error Codes

| HTTP | `detail`              | Condition                     |
|------|-----------------------|-------------------------------|
| 404  | `element not found`   | `element_id` does not exist   |
| 404  | `schema not found`    | `schema_id` does not exist    |
| 401  | `unauthorized`        | Missing/invalid Bearer token  |
| 403  | `forbidden`           | Insufficient role              |
