# Quickstart: Schema Backend Service
**Feature**: 002-schema-backend | **Date**: 2026-03-08

---

## Prerequisites

- Docker and Docker Compose installed
- Python 3.12 (for running tests locally without Docker)

---

## 1. Start the service

```bash
# From the repository root — starts backend, db, and Keycloak
docker compose up -d backend db keycloak

# Verify the service is healthy
curl http://localhost:8002/health
# Expected: { "status": "ok", "version": "2026.03.0" }

# Verify Keycloak is up (may take ~30s)
curl http://localhost:8080/health/ready
# Expected: { "status": "UP" }
```

---

## 1a. Obtain an API key (first-time setup)

```bash
# In a browser: log in via the mock OIDC provider (dev mode)
open http://localhost:8002/api/v1/auth/login

# After redirect back, issue an API key
curl -X POST http://localhost:8002/api/v1/tokens \
  -H "Cookie: $SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{ "label": "quickstart" }'
# Response: { "token": "<64-char hex — copy this>", "id": "uuid", ... }

# Export for remaining steps
export TOKEN="<token from above>"
```

---

## 2. Register a schema source

```bash
curl -X POST http://localhost:8002/api/v1/sources \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BIDS",
    "format": "yaml",
    "url": "https://github.com/bids-standard/bids-specification",
    "version_tag": "1.9.0",
    "content_hash": "sha256:placeholder"
  }'
```

---

## 3. Create a data element

```bash
SOURCE_ID="<id from step 2>"

curl -X POST http://localhost:8002/api/v1/elements \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"subject_age\",
    \"data_type\": \"number\",
    \"description\": \"Age of the research subject in years\",
    \"required\": false,
    \"multivalued\": false,
    \"constraints\": {\"minimum\": 0},
    \"source_id\": \"$SOURCE_ID\",
    \"source_local_id\": \"sub-age\"
  }"
# Note: actor identity is derived server-side from the Bearer token; no created_by field
```

---

## 4. Search elements

```bash
# Keyword search
curl "http://localhost:8002/api/v1/elements?q=age&limit=10"

# Filter by source
curl "http://localhost:8002/api/v1/elements?source_id=$SOURCE_ID"
```

---

## 5. Register a mapping (identity)

```bash
ELEMENT_A="<id of subject_age from BIDS>"
ELEMENT_B="<id of participant_age from DANDI>"

curl -X POST http://localhost:8002/api/v1/mappings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"function_type\": \"identity\",
    \"input_element_ids\": [\"$ELEMENT_A\"],
    \"output_element_id\": \"$ELEMENT_B\",
    \"description\": \"subject_age and participant_age are the same concept\",
    \"expression\": \"input_0\",
    \"expression_type\": \"identity\",
    \"sssom_predicate\": \"skos:exactMatch\"
  }"
# Note: actor identity from Bearer token; no created_by field
```

---

## 6. Run on-demand alias detection

```bash
# Scan all elements for similarity candidates (returns paginated AliasCandidatePair list)
curl -X POST http://localhost:8002/api/v1/aliases/detect \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "threshold": 0.88, "limit": 10, "offset": 0 }'
# Expected: { "total": N, "items": [{ "element_a": {...}, "element_b": {...}, "similarity_score": 0.94, ... }] }
```

---

## 7. Create a dynamic schema

```bash
curl -X POST http://localhost:8002/api/v1/schemas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"BIDS participant schema\",
    \"description\": \"Core BIDS participant fields\",
    \"elements\": [
      { \"element_id\": \"$SOURCE_ID\", \"position\": 0, \"field_alias\": null }
    ]
  }"
# Response: { "id": "uuid", "uri": "http://localhost:8002/schemas/<uuid>", "name": "...", ... }

# Retrieve via URI
SCHEMA_ID="<id from above>"
curl http://localhost:8002/api/v1/schemas/$SCHEMA_ID
```

---

## 7a. View audit trail

```bash
curl "http://localhost:8002/api/v1/audit?record_type=DataElement&limit=5"
# Each entry includes: operation, actor_id (UUID), actor_display_name (from token), timestamp, diff
```

---

## 8. Cross-source alias detection for curation

```bash
# Register a second source (DANDI) and create a similar element
curl -X POST http://localhost:8002/api/v1/sources \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"DANDI","format":"json-schema","version_tag":"0.6.4","content_hash":"sha256:placeholder"}'
DANDI_SOURCE_ID="<id from above>"

curl -X POST http://localhost:8002/api/v1/elements \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"participant_age\",
    \"data_type\": \"number\",
    \"description\": \"Age of the research participant in years\",
    \"required\": false,
    \"multivalued\": false,
    \"source_id\": \"$DANDI_SOURCE_ID\",
    \"source_local_id\": \"participant-age\",
    \"semantic_graph\": {
      \"entities\": [{\"label\": \"study participant\", \"type\": \"Person\", \"role\": \"subject\"}],
      \"property\": {\"label\": \"age\", \"type\": \"biological\"},
      \"unit\": {\"label\": \"year\", \"symbol\": \"yr\"}
    }
  }"
DANDI_AGE_ID="<id from above>"

# Detect cross-source alias candidates (curator-only)
curl -X POST http://localhost:8002/api/v1/aliases/detect \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"threshold": 0.88, "cross_source_only": true, "limit": 10, "offset": 0}'
# Expected: items contain { "element_a": {...}, "element_b": {...},
#   "similarity_score": 0.94,
#   "semantic_graph_overlap": { "property_match": true, "unit_match": true,
#                                "entity_labels_match": false, "domain_match": true } }
```

---

## 9. Create a canonical undata element

```bash
# The "undata" SchemaSource is pre-seeded at startup — fetch its ID
UNDATA_SOURCE=$(curl -s "http://localhost:8002/api/v1/sources?name=undata" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

# Create a canonical element representing "age in years" for any study participant
curl -X POST http://localhost:8002/api/v1/elements \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"age_years\",
    \"data_type\": \"number\",
    \"description\": \"Age of a study participant in years\",
    \"required\": false,
    \"multivalued\": false,
    \"source_id\": \"$UNDATA_SOURCE\",
    \"source_local_id\": \"age_years\",
    \"semantic_graph\": {
      \"entities\": [{\"label\": \"study participant\", \"type\": \"Person\", \"role\": \"subject\"}],
      \"property\": {\"label\": \"age\", \"type\": \"biological\"},
      \"unit\": {\"label\": \"year\", \"symbol\": \"yr\"}
    }
  }"
UNDATA_AGE_ID="<id from above>"
```

---

## 10. Register source → undata identity mappings

```bash
BIDS_AGE_ID="<id from step 3>"

# BIDS subject_age → undata age_years
curl -X POST http://localhost:8002/api/v1/mappings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"function_type\": \"identity\",
    \"input_element_ids\": [\"$BIDS_AGE_ID\"],
    \"output_element_id\": \"$UNDATA_AGE_ID\",
    \"description\": \"BIDS subject_age is semantically identical to undata age_years\",
    \"expression_type\": \"identity\",
    \"sssom_predicate\": \"skos:exactMatch\"
  }"

# DANDI participant_age → undata age_years
curl -X POST http://localhost:8002/api/v1/mappings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"function_type\": \"identity\",
    \"input_element_ids\": [\"$DANDI_AGE_ID\"],
    \"output_element_id\": \"$UNDATA_AGE_ID\",
    \"description\": \"DANDI participant_age is semantically identical to undata age_years\",
    \"expression_type\": \"identity\",
    \"sssom_predicate\": \"skos:exactMatch\"
  }"
```

---

## 11. Downstream vocabulary and traceability queries

```bash
# Downstream consumers: list all undata canonical elements
curl "http://localhost:8002/api/v1/elements?source_id=$UNDATA_SOURCE"

# Compose a DynamicSchema from undata elements only
curl -X POST http://localhost:8002/api/v1/schemas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Participant demographics (undata)\",
    \"description\": \"Canonical participant fields for cross-study alignment\",
    \"elements\": [
      { \"element_id\": \"$UNDATA_AGE_ID\", \"position\": 0, \"field_alias\": null }
    ]
  }"

# Trace back to source representations via mappings
curl "http://localhost:8002/api/v1/mappings?target_element_id=$UNDATA_AGE_ID"
# Expected: items include BIDS and DANDI identity mappings with their source elements
```

---

## 12. Run the test suite

```bash
# Requires a running PostgreSQL + Keycloak (or use Docker Compose test profile)
docker compose run --rm test pytest tests/ -v
```

---

## Validation Checklist

After completing the steps above, confirm:

- [ ] `GET /health` returns `{ "status": "ok" }` with HTTP 200
- [ ] OIDC login flow completes and session cookie is set
- [ ] `POST /tokens` returns a 64-char hex token (shown once only)
- [ ] Source registration returns a UUID and `version_tag` is stored
- [ ] Element creation returns a UUID and a `uri` of the form `http://localhost:8002/elements/<uuid>`; `version_num` is 1; audit `actor_id` is the token owner's user profile UUID
- [ ] Two elements with the same `name` but different `source_id` values are stored as distinct records with distinct URIs
- [ ] Keyword search for "age" returns the created element
- [ ] Identity mapping is created without error; response includes `uri` field; `created_by` field in request body is ignored
- [ ] Alias group is auto-created for the identity mapping
- [ ] `POST /aliases/detect` returns paginated `AliasCandidatePair` list
- [ ] `POST /schemas` creates a DynamicSchema with a stable `uri`; `PUT /schemas/{id}` changes membership but `uri` is unchanged
- [ ] Audit log shows CREATE entries for source, element, and mapping with `actor_id` (UUID) and `actor_display_name`
- [ ] Attempt to register a circular mapping returns HTTP 409 with `cycle_path`
- [ ] Soft-delete an element; confirm it no longer appears in search results
- [ ] Retrieve deleted element by ID; confirm `deleted_at` is set
- [ ] Request with revoked token returns HTTP 401
- [ ] `viewer`-role user attempting POST /elements returns HTTP 403
- [ ] `GET /sources?name=undata` returns the pre-seeded canonical source on a fresh deployment (SC-012)
- [ ] `POST /aliases/detect` with `cross_source_only=true` returns only cross-source pairs; each pair includes a `semantic_graph_overlap` object with `property_match`, `unit_match`, `entity_labels_match`, `domain_match` fields (FR-033)
- [ ] Creating a canonical element under the `"undata"` source succeeds and its URI is of the form `http://localhost:8002/elements/<uuid>` (FR-032)
- [ ] `GET /elements?source_id=<undata-id>` returns only canonical elements; BIDS and DANDI elements do not appear (SC-011)
- [ ] `GET /mappings?target_element_id=<undata-element-id>` returns BIDS and DANDI identity mappings (SC-011)

---

## Service Ports (Docker Compose)

| Service | Port |
|---------|------|
| Backend API | 8002 |
| Keycloak | 8080 |
| PostgreSQL | 5432 (internal) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `ALIAS_SIMILARITY_THRESHOLD` | `0.88` | Cosine similarity threshold for alias detection |
| `LOG_LEVEL` | `INFO` | Structured log level |
| `SECRET_KEY` | — | Session signing secret (required in production) |
| `KEYCLOAK_URL` | `http://keycloak:8080` | Keycloak base URL |
| `KEYCLOAK_REALM` | `undata` | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | — | OIDC client ID registered in Keycloak |
| `KEYCLOAK_CLIENT_SECRET` | — | OIDC client secret (required in production) |
| `TOKEN_CACHE_TTL_SECONDS` | `300` | API key LRU cache TTL (revocation lag upper bound) |
| `UNDATA_BASE_URL` | `http://localhost:8002` | Base URL used when minting persistent URIs for elements, mappings, and schemas |
