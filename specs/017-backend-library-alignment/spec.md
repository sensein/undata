# Feature Specification: Backend–Library Alignment

**Feature Branch**: `017-backend-library-alignment`
**Created**: 2026-03-17
**Status**: Draft
**Input**: Align the backend (002) Postgres schema and API with the content-addressed
RDF property model from undata-library (015v2/016). The library becomes both a Python
dependency used inside the backend and an export/import format for the backend's data.

---

## Overview

Replace the backend's flat `data_element` / `data_element_version` tables with
tables that mirror the library's content-addressed model: `element` (semantic hash
as identity), `element_provenance`, `value_concept`, `schema_shape`, and `mapping`
with transform expressions. The backend API returns semantic + provenance structures.
The frontend renders cross-source provenance. The library CLI exports/imports
through the backend API.

### Architecture After Alignment

```
┌─────────────────────────────────────────────────────┐
│  undata-library (Python package)                     │
│  ├─ models.py (SemanticIdentity, ProvenanceEntry, …)│
│  ├─ hashing.py (content-addressed identity)          │
│  └─ extractors/ (BIDS, NWB, DANDI, AIND, openMINDS) │
└──────────────┬───────────────────────┬──────────────┘
               │ imported by           │ CLI tools
               ▼                       ▼
┌──────────────────────┐   ┌──────────────────────────┐
│  Backend (FastAPI)    │   │  Library CLI             │
│  ├─ Postgres tables   │   │  ├─ validate             │
│  │  (mirrors library) │   │  ├─ ingest (→ backend)   │
│  ├─ API endpoints     │◄──│  ├─ export (← backend)   │
│  └─ Auth (Keycloak)   │   │  ├─ import (→ backend)   │
└──────────┬───────────┘   │  └─ hash, diff, index    │
           │                └──────────────────────────┘
           ▼
┌──────────────────────┐
│  Frontend (Next.js)   │
│  ├─ Element detail    │
│  │  (semantic+prov)   │
│  ├─ Value concepts    │
│  ├─ Cross-source view │
│  └─ Mapping explorer  │
└──────────────────────┘
```

---

## Requirements

### Functional Requirements

**Database Schema**

- **FR-001**: `element_v2` table MUST have integer PK (`id`), `semantic_hash`
  (CHAR(64), unique, indexed), `uri` (VARCHAR(255), unique), `semantic` (JSONB:
  ontology_term, data_type, unit, constraints), `created_at` with server_default.
  Integer PK for FK join performance; semantic_hash for content-addressed lookup.
- **FR-002**: `element_provenance_v2` table MUST have integer FK to `element_v2.id`,
  `source`, `class_` (avoid reserved word), `name`, `description`, `required`,
  `multivalued`, `added_at`. Unique constraint on (element_id, source, name) to
  prevent duplicate provenance entries.
- **FR-003**: `value_concept_v2` table MUST have integer PK, `semantic_hash`
  (CHAR(64), unique), `uri`, `semantic` (JSONB: ontology_term, value_type, label),
  `created_at`.
- **FR-004**: `value_provenance_v2` table MUST have integer FK to `value_concept_v2.id`,
  `source`, `raw_value`, `added_at`. Unique on (value_concept_id, source, raw_value).
- **FR-005**: `schema_shape_v2` table MUST have integer PK, `semantic_hash`
  (CHAR(64), unique), `uri`, `semantic` (JSONB: properties list, subclass_of, mixins),
  `created_at`.
- **FR-006**: `schema_provenance_v2` table MUST have integer FK to `schema_shape_v2.id`,
  `source`, `name`, `description`, `added_at`.
- **FR-007**: `element_mapping_v2` table MUST have integer PK, `source_element_uri`,
  `target_element_uri`, `function_type`, `expression`, `expression_type`,
  `sssom_predicate`, `confidence`, `attributed_to`, `created_at`.
- **FR-008**: No `hash_registry` table needed — the library manages the hash
  registry file; backend resolves URIs via `element_v2.uri` column index.

**API Endpoints**

- **FR-009**: `POST /api/v2/elements` MUST accept `{semantic, provenance}` body,
  compute content hash. Return 201 if new element created; 200 if existing element
  found and provenance merged; 200 (no-op) if provenance already present. Return
  422 for invalid semantic block. Response body always: `{uri, semantic, provenance[]}`.
- **FR-010**: `GET /api/v2/elements` MUST return list with `{semantic, provenance, uri}`
  structure. Support filters: `source`, `data_type`, `ontology_term`, `name`.
- **FR-011**: `GET /api/v2/elements/{uri}` MUST return single element with full
  provenance list.
- **FR-012**: `POST /api/v2/values` MUST accept `{semantic, provenance}`, deduplicate
  by content hash. Return content-addressed URI.
- **FR-013**: `GET /api/v2/values` MUST return list with semantic + provenance.
- **FR-014**: `POST /api/v2/schemas` MUST accept `{semantic, provenance}`, deduplicate
  by property-set hash.
- **FR-015**: `GET /api/v2/schemas` MUST return list with property URIs + provenance.
- **FR-016**: `POST /api/v2/mappings` MUST accept source_element_uri, target_element_uri,
  function_type, expression, expression_type.
- **FR-017**: `GET /api/v2/mappings` MUST support filter by source_element or
  target_element URI.

**Backend–Library Integration**

- **FR-018**: Backend MUST depend on `undata-library` package and import
  `undata_library.models` and `undata_library.hashing` directly.
- **FR-019**: `undata-library export --backend-url URL` MUST produce valid v2 YAML
  files from the backend API.
- **FR-020**: `undata-library import --backend-url URL` MUST load v2 YAML files
  into the backend via API.
- **FR-021**: `undata-library ingest --source NAME --backend-url URL` MUST extract
  from raw schemas and write directly to backend API (not just local files).

**Frontend**

- **FR-022**: Element detail page MUST show semantic identity block (ontology_term,
  data_type, unit, constraints) and provenance list (source, class, name per source).
- **FR-023**: Elements list MUST support filter by source, showing cross-source
  badge for elements with >1 provenance source.
- **FR-024**: Value concepts page MUST show label, ontology_term, and raw_value
  per source.
- **FR-025**: Mapping detail MUST show source/target elements, function_type,
  expression, and bidirectional link.

**Migration**

- **FR-026**: Alembic migration MUST transform existing `data_element` +
  `data_element_version` records into `element_v2` + `element_provenance_v2` tables
  using content-addressed hashing. Migration MUST join `schema_source` table to
  populate `provenance.source` from the source name. Class name derived from
  `source_local_id` (e.g., `"bids.columns.age"` → class=`"columns"`).
- **FR-027**: Migration MUST preserve all existing data — no data loss.
- **FR-028**: Migration MUST handle duplicate elements (same semantic hash from
  different sources) by merging provenance.

### Non-Functional Requirements

- **NFR-001**: Content hash computation MUST add < 10ms latency per element write.
- **NFR-002**: `GET /api/v2/elements` MUST return within 200ms for up to 10,000 elements.
- **NFR-003**: Alembic migration of existing data MUST complete within 5 minutes.
- **NFR-004**: All existing backend tests MUST continue to pass (adapted for new schema).

---

## Assumptions

- The library package (`undata-library`) is added as a backend dependency:
  path dependency (`../library`) for local dev, editable install in Dockerfile
  (`COPY ../library /library && pip install -e /library`), installed before
  backend in CI workflows.
- Existing backend features (auth, RBAC, audit log, QUDT unit resolution) are
  preserved — only the element/mapping data model changes.
- The `DynamicSchema` entity in the backend maps to `schema_shape` in the library.
- The migration-api (004) continues to work — its `MappingFunction` maps to the
  new `element_mapping` table.
- Frontend changes are incremental — existing pages continue to work during
  transition.

---

## Success Criteria

- **SC-001**: `POST /api/v2/elements` with same semantic graph twice returns same URI.
- **SC-002**: `undata-library export` from backend produces valid v2 YAML.
- **SC-003**: `undata-library import` into fresh backend creates all elements.
- **SC-004**: Frontend element detail shows semantic + provenance structure.
- **SC-005**: Alembic migration completes with zero data loss.
- **SC-006**: All backend tests pass after migration.
