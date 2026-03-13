# Quickstart: Schema Enrichment Validation Checklist

**Feature**: `005-schema-enrichment` | **Date**: 2026-03-09

Prerequisites: 002-schema-backend is running at `http://localhost:8002`,
AIND + BIDS schemas have been ingested via `001-neuro-schema-integration`.

---

## 1. Schema Class Analysis

```bash
TOKEN="<api_key>"

# Get class list for the BIDS schema
BIDS_SCHEMA_ID=$(curl -s "$BASE/schemas" -H "Authorization: Bearer $TOKEN" \
  | jq -r '.items[] | select(.name=="BIDS") | .id')

curl -s "$BASE/schemas/$BIDS_SCHEMA_ID/classes" \
  -H "Authorization: Bearer $TOKEN" | jq '.classes[].class_name'
# Expected: ["Metadata", "Sidecar", ...]

# Verify enumeration elements have allowed_values
curl -s "$BASE/schemas/$BIDS_SCHEMA_ID/classes" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.classes[].elements[] | select(.element_kind == "enumeration") | .name'
# Expected: ["Handedness", "Sex", ...]
```

**Expected**: At least 2 classes returned; at least 1 enumeration element.

---

## 2. Validation Rules — Attach, Narrow (Breaking), Widen (Non-Breaking)

```bash
# Find subject_age element
AGE_EL=$(curl -s "$BASE/elements?name=subject_age" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.items[0].id')

# Attach a range rule
curl -s -X POST "$BASE/elements/$AGE_EL/validation-rules" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rule_type":"range","rule_value":{"min":0,"max":120},"severity":"error"}'
# Expected: 201, rule.id returned

RULE_ID=$(curl -s "$BASE/elements/$AGE_EL/validation-rules" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.rules[0].id')

# Narrow range → breaking
curl -s -X PUT "$BASE/elements/$AGE_EL/validation-rules/$RULE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rule_value":{"min":0,"max":100}}'
# Expected: 200, change.breaking = true

# Widen range → non-breaking
curl -s -X PUT "$BASE/elements/$AGE_EL/validation-rules/$RULE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rule_value":{"min":0,"max":150}}'
# Expected: 200, change.breaking = false
```

---

## 3. Schema Inheritance

```bash
# Create base schema
BASE_SCHEMA=$(curl -s -X POST "$BASE/schemas" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"BaseSubjectSchema","description":"Base"}' | jq -r '.id')

# Create child schema
CHILD_SCHEMA=$(curl -s -X POST "$BASE/schemas" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"ExtendedSubjectSchema"}' | jq -r '.id')

# Set parent
curl -s -X PUT "$BASE/schemas/$CHILD_SCHEMA/parent" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"parent_id\": \"$BASE_SCHEMA\"}"
# Expected: 200

# Get resolved schema (should include parent elements)
curl -s "$BASE/schemas/$CHILD_SCHEMA/resolved" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.mro, .elements | length'
# Expected: mro has 2 entries; elements count >= parent elements

# Test cycle prevention
curl -s -X PUT "$BASE/schemas/$BASE_SCHEMA/parent" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"parent_id\": \"$CHILD_SCHEMA\"}"
# Expected: 409 Conflict
```

---

## 4. ProvenanceMixin

```bash
# Attach ProvenanceMixin to child schema
curl -s -X POST "$BASE/schemas/$CHILD_SCHEMA/provenance-mixin" \
  -H "Authorization: Bearer $TOKEN"
# Expected: 201, attached: true

# Resolved schema now includes provenance elements
curl -s "$BASE/schemas/$CHILD_SCHEMA/resolved" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '[.elements[] | select(.source_schema == "ProvenanceMixin") | .name]'
# Expected: ["prov_created_by","prov_created_at","prov_modified_at","prov_derived_from"]
```

---

## 5. Schema Changelog & Provenance

```bash
# Retrieve changelog after mutations above
curl -s "$BASE/schemas/$CHILD_SCHEMA/changelog" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.entries | length, .[0].operation'
# Expected: length >= 2; first operation = "CREATE"

# W3C PROV-DM JSON-LD
curl -s "$BASE/schemas/$CHILD_SCHEMA/provenance" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '."@graph" | length'
# Expected: >= 3 (Entity, Activity, Agent nodes)
```

---

## Integration with 001-neuro-schema-integration

After running `undata ingest bids aind --dry-run=false`:

```bash
# All AIND classes extracted
curl -s "$BASE/schemas/$AIND_SCHEMA_ID/classes" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.classes | map(.class_name)'
# Expected: ["Subject","Acquisition","DataDescription","Procedures","Instrument"]

# AIND subject_id has ValidationRule from ingestion
curl -s "$BASE/elements/$SUBJECT_ID_EL/validation-rules" \
  -H "Authorization: Bearer $TOKEN" | jq '.rules | length'
# Expected: >= 1
```

---

## Test Matrix Summary

| Scenario | Endpoint | Expected |
|----------|----------|----------|
| List classes | GET /schemas/{id}/classes | 200, ≥ 1 class |
| Resolved schema | GET /schemas/{id}/resolved | 200, MRO list |
| Set parent | PUT /schemas/{id}/parent | 200 |
| Cycle rejected | PUT /schemas/{id}/parent | 409 |
| Attach mixin | POST /schemas/{id}/mixins | 201 |
| Attach ProvenanceMixin | POST /schemas/{id}/provenance-mixin | 201 |
| Create rule | POST /elements/{id}/validation-rules | 201 |
| Narrow rule (breaking) | PUT /elements/{id}/validation-rules/{id} | 200, breaking=true |
| Widen rule (non-breaking) | PUT /elements/{id}/validation-rules/{id} | 200, breaking=false |
| Delete rule | DELETE /elements/{id}/validation-rules/{id} | 200, breaking=false |
| Changelog | GET /schemas/{id}/changelog | 200, ≥ 1 entry |
| PROV-DM JSON-LD | GET /schemas/{id}/provenance | 200, ld+json |
