# Research: Schema Enrichment — Classes, Validation, Inheritance & Provenance

**Feature**: `005-schema-enrichment` | **Date**: 2026-03-09

---

## Q1: Schema Inheritance Storage — Adjacency List vs Closure Table vs Nested Sets

**Decision**: Adjacency list (`parent_id` FK on `DynamicSchema`) + recursive
CTE for MRO resolution.

**Rationale**:
- Adjacency list is the simplest structure (Principle I). A single nullable
  `parent_id` FK on `DynamicSchema` enables single-parent inheritance.
- PostgreSQL `WITH RECURSIVE` CTEs handle transitive ancestor queries in a
  single round-trip; no additional table needed.
- Depth is bounded at 20 levels (enforced at write time) — closure tables
  optimise for read-heavy, deep hierarchies (hundreds of levels), which is
  out of scope here.
- Nested sets require rewriting on every insert, which is prohibitive for
  dynamic schemas updated via API.
- Mixins (M:N) use a `schema_mixins` join table with `position` for ordering.
- C3 MRO is computed in Python application code (not SQL) for clarity and
  testability.

**Alternatives considered**:
- **Closure table**: Optimal for deep read queries but adds write complexity
  (insert ancestor rows on every schema create/update). Rejected: premature
  optimisation at ≤ 200 schemas.
- **Nested sets (MPTT)**: Efficient range queries but requires full rebalancing
  on insert/delete. Rejected: unsuitable for mutable schemas.

---

## Q2: Semantic Breaking Change Classification

**Decision**: Application-layer rule engine (Python dict comparison) classified
into BREAKING / NON_BREAKING per rule type.

**Semantic rules**:

| Rule Type | Narrowing → BREAKING | Widening → NON_BREAKING |
|-----------|---------------------|------------------------|
| `enum_set` | Remove values from set | Add values to set |
| `range` | Tighten min↑ or max↓ | Loosen min↓ or max↑ |
| `pattern` | Add new pattern constraint | Remove pattern constraint |
| `type_constraint` | Any type change | N/A (always BREAKING) |
| `cardinality` | Increase minimum, decrease maximum | Decrease minimum, increase maximum |

**Rationale**:
- Narrowing constraints = previously valid data may become invalid = BREAKING.
- Widening constraints = all previously valid data remains valid = NON_BREAKING.
- Type changes are always BREAKING (string→integer requires data transformation).
- This aligns with JSON Schema compatibility checking tools (openapi-diff,
  schemathesis) and semantic versioning best practices.

**Alternatives considered**:
- **schemathesis / openapi-diff libraries**: Focus on HTTP API contracts, not
  data element constraints. Out-of-scope tooling.
- **Full semantic reasoning (OWL/RDF)**: Over-engineered for field-level rules.
  Rejected per Principle I.

---

## Q3: Validation Rule Storage — JSONB vs Typed Tables

**Decision**: Single `validation_rules` table with `rule_type TEXT` +
`rule_value JSONB` columns (polymorphic JSONB pattern).

**Rationale**:
- Avoids schema explosion (5 rule types × potential future growth).
- `rule_value` JSONB with GIN index supports containment queries
  (e.g. find all elements where enum_set contains "M").
- Rule types are small in number (≤ 10 initially); JSONB validation is done
  in the application layer via Pydantic typed union discriminated on `rule_type`.
- Consistent with the existing `constraints` JSONB pattern in
  `DataElementVersion` (Principle I: extend, don't duplicate).

**Alternatives considered**:
- **Separate table per rule type** (range_rules, enum_rules, etc.): Clean
  relational schema but N joins per element lookup. Rejected: unnecessary
  complexity.
- **Store rules inside `DataElementVersion.constraints` JSONB**: Lacks
  first-class identity (no `id`, no mutation tracking). Rejected: cannot
  attach `ValidationRuleChange` audit records.

---

## Q3b: Validation Rules — Location: New Table vs Extending constraints JSONB

**Decision**: New `validation_rules` table (FK to `DataElement`) rather than
extending `DataElementVersion.constraints` JSONB.

**Rationale**:
- `DataElementVersion.constraints` JSONB is already in use for unstructured
  constraint hints from ingestion (LinkML `minimum_value`, `pattern`, etc.).
  This remains useful as an *ingestion-time snapshot*.
- A separate `ValidationRule` table is required because rules need:
  - A stable `id` for `ValidationRuleChange` audit FKs
  - Soft delete (`deleted_at`) lifecycle independent of element versions
  - `created_by` attribution per rule (not just per element version)
  - One-active-rule-per-type constraint (`UNIQUE (element_id, rule_type) WHERE deleted_at IS NULL`)
- The two coexist: `constraints` JSONB = ingestion-derived hint; `ValidationRule`
  rows = curator-asserted, auditable constraints.

**Alternatives considered**:
- Extend `DataElementVersion.constraints` only: cannot attach independent audit
  FK; no per-rule lifecycle. Rejected.

---

## Q4: Provenance Tracking — W3C PROV-DM vs AuditLog Extension

**Decision**: Extend the existing `AuditLog` with PROV-DM semantic fields
(`activity_type`, `reason`) + a new `SchemaChangeLog` table for schema-specific
provenance; expose `GET /api/v1/schemas/{id}/provenance` as W3C PROV-DM JSON-LD.

**Rationale**:
- The existing `AuditLog` already captures `actor_id`, `timestamp`, `operation`,
  `diff`. Adding `activity_type` and `reason` fields upgrades it to PROV-DM
  `Activity` semantics without a full schema rewrite.
- A separate `SchemaChangeLog` is preferred over re-using `AuditLog` for
  schema-specific metadata (breaking flag, diff structure differs from element
  mutations).
- W3C PROV-DM JSON-LD serialisation is produced by the API layer (no separate
  graph store required); entities/activities/agents are assembled from stored
  relational data.

**PROV-DM mapping**:

| PROV-DM Concept | Backend Record |
|----------------|----------------|
| `prov:Entity` | DynamicSchema (version) |
| `prov:Activity` | SchemaChangeLog entry |
| `prov:Agent` | UserProfile (actor) |
| `prov:wasGeneratedBy` | schema ← SchemaChangeLog |
| `prov:wasAttributedTo` | schema ← UserProfile |
| `prov:wasDerivedFrom` | parent/mixin schema |

**Three additional lightweight PROV-DM additions** (single migration, zero new tables):
1. `UserProfile.agent_type TEXT DEFAULT 'person'` — enables `prov:Person` vs
   `prov:SoftwareAgent` distinction (ingestion pipeline = software agent)
2. `AuditLog.caused_by_activity_id UUID FK → AuditLog` (nullable) — enables
   `prov:wasInformedBy` chain for bulk ingestion pipeline traceability
3. `GET /api/v1/elements/{id}/provenance` endpoint — returns PROV-O JSON-LD
   assembled from existing DB fields; zero additional storage cost

**Alternatives considered**:
- **Separate provenance graph DB (OpenLink Virtuoso, Apache Jena Fuseki)**:
  Full SPARQL support but massive operational overhead. Rejected: Principle I.
- **PAV ontology (Provenance, Authoring, Versioning)**: Superset of PROV-DM
  focused on content authoring. Useful in future; PROV-DM core is sufficient
  for v1.

---

## Q5: ProvenanceMixin Design

**Decision**: ProvenanceMixin is a system-reserved `DynamicSchema` record
(seeded at startup alongside the `undata` SchemaSource) with 4 pre-created
DataElements. Any schema can reference it via `SchemaMixin`.

**ProvenanceMixin elements**:

| Element Name | Type | Required | Semantics |
|-------------|------|----------|-----------|
| `prov_created_by` | string | yes | `prov:wasAttributedTo` — actor ID |
| `prov_created_at` | string (ISO8601) | yes | `prov:generatedAtTime` |
| `prov_modified_at` | string (ISO8601) | no | `prov:invalidatedAtTime` |
| `prov_derived_from` | string (URI) | no | `prov:wasDerivedFrom` — source URI |

**Rationale**: Encoding provenance as DataElements means every existing schema
mechanism (validation, LinkML export, alias detection) applies to provenance
fields automatically, with no special-casing.

---

## Q6: SchemaClass Representation

**Decision**: New `SchemaClass` table (`id`, `source_id`, `class_name`,
`description`, `parent_class_id`). Join table `SchemaClassElement` links
`SchemaClass` → `DataElement` (many-to-many with position). `DataElement`
gains `element_kind` column (`scalar`, `enumeration`, `complex`, `array`).

**Rationale**:
- `SchemaClass` captures the OOP-level grouping (e.g. `Subject`, `Session`)
  from source schemas. This is distinct from `DynamicSchema` (which is a
  curator-assembled collection). Source schemas have classes; curated schemas
  have compositions.
- `element_kind` is derived at ingestion time from `allowed_values` (→
  enumeration), `data_type=object` (→ complex), `data_type=array` (→ array),
  otherwise scalar.
- `SchemaEnumeration` table stores the individual allowed values with optional
  labels/descriptions — more structured than the `allowed_values` JSONB array.

**Alternatives considered**:
- **Use DynamicSchema as class representation**: Conflates source-schema classes
  with curated schemas. Rejected: semantic confusion.
- **Tag DataElements with `class_name` TEXT**: Flat; cannot model class
  inheritance within a source schema. Rejected: insufficient structure.

---

## Q7: MRO Resolution Algorithm

**Decision**: Python C3 linearization computed in the `SchemaService.resolve()`
method; result cached per `(schema_id, version_num)` in a simple in-memory
dict (max 256 entries, LRU eviction).

**Algorithm**:
1. Fetch `parent_id` and ordered `SchemaMixin` rows for the schema.
2. Recursively resolve each to its MRO list.
3. Apply C3 merge on `[own_elements] + [parent_mro] + [mixin_mros]`.
4. On name collision within a schema level: own elements win; earlier mixins
   win over later ones.
5. On cycle: raise `CycleError` (HTTP 409).

**Rationale**: C3 is the same algorithm Python uses for class MRO; it is
well-understood, deterministic, and handles diamond inheritance correctly.
Caching prevents repeated recursive DB queries for the same resolved schema.

**Alternatives considered**:
- **DFS with arbitrary tie-breaking**: Non-deterministic on diamond inheritance.
  Rejected.
- **PostgreSQL recursive CTE for full MRO**: Cannot implement C3 in SQL cleanly.
  Rejected.

---

## Q8: Multi-Path Schema Class Extraction (JSON vs. Code Introspection)

**Decision**: Each adapter implements `extract_classes()` using the natural
extraction path for its source format. Two paths are recognised; both must
produce the same `SchemaClassPayload` output type.

| Adapter | Source Format | Extraction Path | Natural Class Boundary |
|---------|--------------|-----------------|------------------------|
| BIDS | YAML (via bidsschematools) | **Structured-text parsing** — iterate YAML field definitions; group by implicit domain category | Metadata domain (e.g. `MRI`, `Behavioral`, `Physio`) |
| DANDI | Python Pydantic models | **Code-introspection** — iterate `BaseModel` subclasses via `inspect`; class name is the boundary | Pydantic model class (e.g. `Subject`, `BioSample`) |
| NWB | YAML group definitions | **Structured-text parsing** — iterate top-level `groups` array in YAML; `neurodata_type` is the boundary | Group `neurodata_type` (e.g. `TimeSeries`, `DynamicTable`) |
| openMINDS | JSON-LD templates | **JSON parsing** — one class per JSON-LD file; root `@type` is the class name | Root `@type` URI last segment (e.g. `Subject`, `TissueSample`) |
| AIND | JSON Schema fixtures | **JSON parsing** — one class per schema file; `title` or filename stem is the class name | Schema file stem (e.g. `Subject`, `Acquisition`) |

**Rationale**:
- DANDI and NWB source-of-truth *is* Python code / Python objects; reading
  the YAML or JSON Schema intermediary would lose structural fidelity. For DANDI,
  `inspect.getmembers()` already gives us Pydantic model introspection; we
  reuse it. For NWB the existing YAML-based `extract_elements()` already groups
  by `neurodata_type` — classes map directly to top-level group entries.
- BIDS, openMINDS, and AIND do not have a public Python API that exposes an
  object hierarchy; JSON/YAML parsing is the correct and only path.
- A single `SchemaClassPayload` dataclass covers both paths — the extraction
  mechanism is an adapter implementation detail; the contract to the ingestion
  pipeline is format-agnostic.

**Protocol extension**:
`extract_classes() -> list[SchemaClassPayload]` is added to the
`SchemaAdapter` Protocol. All five adapters MUST implement it. For adapters
where classes are trivial (e.g. openMINDS single-type files) a one-element
list is a valid implementation. Adapters that have no meaningful grouping
(pathological case) MAY return an empty list, but this is not expected for
any of the five current sources.

**`SchemaClassPayload` fields** (no change to existing definition, but
clarified intent):
```python
@dataclass
class SchemaClassPayload:
    class_name: str                          # canonical class identifier
    description: str                         # human-readable summary
    element_source_local_ids: list[str]      # ordered list of element IDs belonging to this class
    parent_class_name: str | None = None     # for source-schema inheritance (NWB group hierarchy)
    extraction_path: str = "json"            # "json"|"yaml"|"jsonld"|"code" — informational, not stored in DB
                                             # BIDS→"yaml", NWB→"yaml", openMINDS→"jsonld",
                                             # AIND→"json", DANDI→"code"
```

**Alternatives considered**:
- **Unified JSON Schema normalisation before class extraction**: All adapters
  already produce JSON Schema internally for `extract_elements()`; we could
  run `extract_classes()` on that normalised form. Rejected: DANDI class
  boundaries are only visible in the Pydantic model names, which are lost after
  JSON Schema expansion because field IDs are prefixed with the model name
  (e.g. `Subject.subject_id`) — we can split on `.`, but this is fragile. Direct
  code introspection is more robust for DANDI.
- **Store `extraction_path` in DB**: Adds a column with no query value.
  Rejected; it is an adapter implementation detail only.
