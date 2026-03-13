# Research: Dynamic Schema Construction and Migration API
**Feature**: 004-migration-api | **Date**: 2026-03-07

---

## Decision 1: Mapping Function Expression Format

**Decision**: Two-tier expression system:
- **Tier 1 — Identity / simple arithmetic**: `simpleeval` library for safe evaluation
  of Python-like arithmetic expressions (no imports, no side effects).
  Example: `"input_0 * 365"`, `"input_0 + ' ' + input_1"`.
- **Tier 2 — Complex transforms**: Named Python callables registered as plugins.
  Stored as module path references (`"undata.transforms.neuro.age_to_days"`);
  executed in a restricted environment via `RestrictedPython`.

**Why not raw `eval()`**: Security risk; arbitrary code execution.
**Why not JSONata**: Good for JSON transformation but unfamiliar in the Python
neuroscience ecosystem; harder to test.
**Why not YARRRML/R2RML**: Designed for RDF/SPARQL mapping, not data element
transformation.

**SSSOM integration**: Every mapping function carries an SSSOM predicate
(`skos:exactMatch`, `skos:relatedMatch`, etc.) capturing the semantic relationship
type. SSSOM TSV export of the mapping registry is supported.

---

## Decision 2: Migration Pathway Storage

**Decision**: Store pathways as ordered lists of mapping function IDs in the
backend (002-schema-backend). The migration API itself is stateless — it fetches
pathway definitions from the backend, executes them, and returns results.

Pathway record (stored in backend, extended schema):
```json
{
  "id": "uuid",
  "name": "BIDS-1.9-to-DANDI-0.6",
  "source_schema_id": "uuid",
  "target_schema_id": "uuid",
  "direction": "forward",
  "steps": [
    { "position": 0, "mapping_id": "uuid" },
    { "position": 1, "mapping_id": "uuid" }
  ],
  "status": "active",
  "inverse_pathway_id": "uuid | null"
}
```

The backend (002) needs a new `/pathways` resource for this. The migration API
treats the backend as its persistence layer.

---

## Decision 3: Dynamic Schema Construction

**Decision**: Use `linkml-runtime` `SchemaDefinition` API (same as 001-neuro-schema-
integration) to build schemas programmatically. Fetch element definitions from the
backend, construct `SlotDefinition` and `ClassDefinition` objects, serialize to YAML.

Class grouping syntax in the API request:
```json
{
  "name": "MyExperimentSchema",
  "version": "2026.03.0",
  "classes": [
    {
      "name": "SubjectMetadata",
      "element_ids": ["uuid-1", "uuid-2", "uuid-3"]
    }
  ]
}
```

---

## Decision 4: Async Job Queue for Large Operations

**Decision**: Celery 5.x with Redis as broker for construction requests exceeding
50 elements or migration batches exceeding 100 records.

Small requests (≤50 elements, ≤100 records): synchronous, inline response.
Large requests: return `202 Accepted` with a job ID; poll `GET /jobs/{id}`.

Redis is already available in the deployment stack (used by backend for caching).

---

## Decision 5: Migration Execution Safety

**Decision**: Per-record isolation — each record's transformation runs in a try/except
block. Failure on one record is captured in the report; remaining records continue.

Expression evaluation: `simpleeval` for Tier 1 expressions. Maximum 10,000
evaluation steps (simpleeval's `EvalWithCompoundTypes` limit). RestrictedPython for
Tier 2 plugin callables.

No sandboxing of I/O at OS level (overkill for neuroscience schema transforms, which
are pure data transformations with no I/O). Tier 2 callables must be reviewed before
registration — marked as `trust_level: reviewed`.

---

## Technology Summary

| Concern | Choice | Version |
|---------|--------|---------|
| Language | Python | 3.12 |
| API framework | FastAPI | 0.111+ |
| Tier 1 expressions | simpleeval | 1.0+ |
| Tier 2 callables | RestrictedPython | 7.x |
| Async jobs | Celery + Redis | 5.x / 7.x |
| LinkML schema build | linkml-runtime | 1.8+ |
| Backend client | httpx async | 0.27+ |
| SSSOM export | sssom-utils | 0.15+ |
| Testing | pytest, pytest-asyncio, httpx | latest |
