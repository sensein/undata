# Quickstart: Migration API
**Feature**: 004-migration-api | **Date**: 2026-03-07

## Prerequisites

- 002-schema-backend running: `curl http://localhost:8002/health`
- 001-neuro-schema-integration ingested: at least BIDS and DANDI elements present
- Redis running (for async jobs): `docker compose up -d redis`

---

## 1. Start the service

```bash
docker compose up -d migration-api
curl http://localhost:8004/health
# Expected: { "status": "ok", "version": "2026.03.0" }
```

---

## 2. Construct a dynamic schema

```bash
# Get element IDs from the backend first
BIDS_ELEMENTS=$(curl -s "http://localhost:8002/api/v1/elements?source_name=BIDS&limit=5" \
  | python3 -c "import sys,json; ids=[e['id'] for e in json.load(sys.stdin)['items']]; print(','.join(ids))")

curl -X POST http://localhost:8004/api/v1/schemas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"QuickstartSchema\",
    \"version\": \"2026.03.0\",
    \"classes\": [{ \"name\": \"SubjectMetadata\", \"element_ids\": [\"${BIDS_ELEMENTS//,/\",\"}\"] }],
    \"save\": true
  }"
```

---

## 3. Register a migration pathway

```bash
# Assume mapping IDs exist from alias detection (001)
MAPPING_ID=$(curl -s "http://localhost:8002/api/v1/mappings?function_type=identity&limit=1" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

curl -X POST http://localhost:8004/api/v1/pathways \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"bids-to-dandi-quickstart\",
    \"source_schema_id\": \"<bids-schema-id>\",
    \"target_schema_id\": \"<dandi-schema-id>\",
    \"direction\": \"forward\",
    \"steps\": [{ \"position\": 0, \"mapping_id\": \"$MAPPING_ID\" }]
  }"
```

---

## 4. Run a migration

```bash
curl -X POST http://localhost:8004/api/v1/migrate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pathway_id": "<pathway-id>",
    "records": [{ "id": "test-1", "data": { "subject_age": 28 } }],
    "direction": "forward"
  }'
```

Expected: `overall_status: "PASS"`, `output` contains mapped field, `report` shows step applied.

---

## 5. Schema diff

```bash
curl -X POST http://localhost:8004/api/v1/diff \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "source_schema_id": "<bids-schema-id>", "target_schema_id": "<dandi-schema-id>" }'
```

---

## Validation Checklist

- [ ] `GET /health` returns 200
- [ ] Schema construction with valid element IDs returns linkml_yaml
- [ ] Schema construction with unknown element IDs returns 422 with `unknown_ids`
- [ ] Pathway registration returns 201 with `inverse_pathway_id` where applicable
- [ ] Migration execution returns a report accounting for all input fields
- [ ] Migration on a BROKEN pathway returns 409 with `broken_step`
- [ ] Batch of 3 records: single failure does not prevent other 2 from completing
- [ ] Schema diff returns coverage assessment and draft pathway
- [ ] Large request (>100 records) returns 202 with job_id; polling returns progress
