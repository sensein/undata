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

- **FR-001**: `element` table MUST have `semantic_hash` (CHAR(64), PK or unique),
  `uri` (content-addressed `{attr}_{key}`), `semantic` (JSONB: ontology_term,
  data_type, unit, constraints), `created_at`.
- **FR-002**: `element_provenance` table MUST have FK to `element.semantic_hash`,
  `source`, `class`, `name`, `description`, `required`, `multivalued`, `added_at`.
- **FR-003**: `value_concept` table MUST have `semantic_hash`, `uri`, `semantic`
  (JSONB: ontology_term, value_type, label), `created_at`.
- **FR-004**: `value_provenance` table MUST have FK to `value_concept`, `source`,
  `raw_value`, `added_at`.
- **FR-005**: `schema_shape` table MUST have `semantic_hash`, `uri`, `semantic`
  (JSONB: properties list, subclass_of, mixins), `created_at`.
- **FR-006**: `schema_provenance` table MUST have FK to `schema_shape`, `source`,
  `name`, `description`, `added_at`.
- **FR-007**: `element_mapping` table MUST have `source_element_uri`, `target_element_uri`,
  `function_type`, `expression`, `expression_type`, `sssom_predicate`, `confidence`,
  `created_at`.
- **FR-008**: `hash_registry` table (optional cache) MAY store `short_key` → `semantic_hash`
  for fast URI resolution.

**API Endpoints**

- **FR-009**: `POST /api/v1/elements` MUST accept `{semantic, provenance}` body,
  compute content hash, return existing element if hash matches (append provenance),
  or create new element. Return content-addressed URI.
- **FR-010**: `GET /api/v1/elements` MUST return list with `{semantic, provenance, uri}`
  structure. Support filters: `source`, `data_type`, `ontology_term`, `name`.
- **FR-011**: `GET /api/v1/elements/{uri}` MUST return single element with full
  provenance list.
- **FR-012**: `POST /api/v1/values` MUST accept `{semantic, provenance}`, deduplicate
  by content hash. Return content-addressed URI.
- **FR-013**: `GET /api/v1/values` MUST return list with semantic + provenance.
- **FR-014**: `POST /api/v1/schemas` MUST accept `{semantic, provenance}`, deduplicate
  by property-set hash.
- **FR-015**: `GET /api/v1/schemas` MUST return list with property URIs + provenance.
- **FR-016**: `POST /api/v1/mappings` MUST accept source_element_uri, target_element_uri,
  function_type, expression, expression_type.
- **FR-017**: `GET /api/v1/mappings` MUST support filter by source_element or
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
  `data_element_version` records into new `element` + `element_provenance` tables
  using content-addressed hashing.
- **FR-027**: Migration MUST preserve all existing data — no data loss.
- **FR-028**: Migration MUST handle duplicate elements (same semantic hash from
  different sources) by merging provenance.

### Non-Functional Requirements

- **NFR-001**: Content hash computation MUST add < 10ms latency per element write.
- **NFR-002**: `GET /api/v1/elements` MUST return within 200ms for up to 10,000 elements.
- **NFR-003**: Alembic migration of existing data MUST complete within 5 minutes.
- **NFR-004**: All existing backend tests MUST continue to pass (adapted for new schema).

---

## Assumptions

- The library package (`undata-library`) is added as a backend dependency via
  `pyproject.toml`.
- Existing backend features (auth, RBAC, audit log, QUDT unit resolution) are
  preserved — only the element/mapping data model changes.
- The `DynamicSchema` entity in the backend maps to `schema_shape` in the library.
- The migration-api (004) continues to work — its `MappingFunction` maps to the
  new `element_mapping` table.
- Frontend changes are incremental — existing pages continue to work during
  transition.

---

## Success Criteria

- **SC-001**: `POST /api/v1/elements` with same semantic graph twice returns same URI.
- **SC-002**: `undata-library export` from backend produces valid v2 YAML.
- **SC-003**: `undata-library import` into fresh backend creates all elements.
- **SC-004**: Frontend element detail shows semantic + provenance structure.
- **SC-005**: Alembic migration completes with zero data loss.
- **SC-006**: All backend tests pass after migration.
