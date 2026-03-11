# Research: Schema Inheritance, Semantic Versioning, and Provenance Tracking
**Feature**: 002-schema-backend | **Date**: 2026-03-09
**Scope**: Three deep-dive topics relevant to future undata schema enrichment features.

---

## Topic 1: Schema Inheritance and Mixin Patterns

### Background

Neuroscience schemas (BIDS, openMINDS, NWB, DANDI) use class hierarchies where
a base `Participant` class may be extended by `HumanParticipant` and `AnimalParticipant`,
each adding or narrowing fields. The question is how to represent these hierarchies
in schema exchange formats and in a relational PostgreSQL database.

### 1.1 How Frameworks Handle Inheritance

#### JSON Schema (draft 7 / 2020-12)

JSON Schema has no native concept of class inheritance. Composition is expressed via
boolean schema combinators:

- **`allOf`**: The instance must be valid against all listed subschemas. Used to
  approximate single inheritance — a child schema uses `allOf: [{"$ref": "#/Parent"}]`
  plus its own additional constraints. This is the most common inheritance simulation.
  OpenAPI 3.0 relies on this heavily.
- **`anyOf`**: Valid against one or more subschemas. Used for union types / polymorphic
  fields (e.g., a field that may be either a `HumanParticipant` or `AnimalParticipant`).
- **`oneOf`**: Valid against exactly one subschema. Stricter than `anyOf`; used when
  the alternatives are mutually exclusive. Has poor tooling support because validators
  must evaluate all branches.
- **`$ref` + `unevaluatedProperties`** (draft 2019-09+): The modern approach for
  true merging semantics. `allOf` + `unevaluatedProperties: false` enforces that no
  additional properties beyond those defined in any `allOf` branch are allowed.

**Limitations**: JSON Schema `allOf` does not express _inheritance_ semantically — it
expresses _conjunction_. Tooling must infer the parent-child relationship from structure.
No support for abstract classes, mixin constraints, or ordered resolution.

#### OpenAPI 3.x

OpenAPI 3.0 uses `allOf` for inheritance and adds the semantic annotation
`discriminator.propertyName` to identify which field distinguishes subtypes:

```yaml
Participant:
  type: object
  properties:
    species: { type: string }

HumanParticipant:
  allOf:
    - $ref: '#/components/schemas/Participant'
    - type: object
      properties:
        education_level: { type: string }
  x-parent: Participant   # non-standard extension

discriminator:
  propertyName: species
  mapping:
    human: '#/components/schemas/HumanParticipant'
    mouse: '#/components/schemas/AnimalParticipant'
```

OpenAPI 3.1 aligns fully with JSON Schema 2020-12, enabling `$ref` alongside sibling
keywords. Still no formal mixin semantics — mixins are approximated by listing multiple
`$ref`s inside `allOf`.

**Tooling gap**: Most OpenAPI code generators (e.g., `openapi-generator`, `datamodel-code-generator`)
flatten `allOf` references into a merged object rather than generating actual class hierarchies.
The parent-child relationship is lost in generated code.

#### LinkML (Linked data Modeling Language)

LinkML has first-class, explicit inheritance concepts designed for scientific data:

- **`is_a`**: Single parent class. The child inherits all slots (fields), and a slot
  can be narrowed (more restrictive range) in the child. Only one `is_a` parent allowed
  per class — single inheritance at the class level.
- **`mixins`**: A list of additional classes that contribute slots without being the
  `is_a` parent. A class can reference multiple mixins. Mixin classes can themselves
  have `is_a` and `mixins`. This is explicit multiple inheritance for field composition.
- **`abstract: true`**: Marks a class that cannot be instantiated directly — must be
  subclassed. Directly analogous to Python abstract base classes.
- **Slot narrowing**: A child can override a slot's `range` to a more specific type,
  add `required: true` where the parent had it optional, or further restrict
  `multivalued`.
- **Slot propagation**: All inherited slots from `is_a` and `mixins` are fully
  resolved at schema compilation time by `linkml-runtime`'s `SchemaView`. Tools that
  consume LinkML schemas work with the flattened resolved view.

Example relevant to undata:
```yaml
classes:
  NamedThing:
    abstract: true
    slots: [id, name, description]

  Identifiable:
    mixin: true
    slots: [uri, created_at]

  DataElement:
    is_a: NamedThing
    mixins: [Identifiable]
    slots: [data_type, required, unit]

  QuantitativeElement:
    is_a: DataElement
    slot_usage:
      unit:
        required: true  # narrowed from optional to required
```

LinkML compiles to JSON Schema, OWL, Python dataclasses, and SQL DDL. The `is_a`
hierarchy maps to Python class inheritance; `mixins` map to Python multiple inheritance
(MRO-compatible). The SQL target uses single-table or joined-table inheritance.

#### Pydantic v2

Pydantic uses standard Python class inheritance:

- **Single inheritance**: `class Child(Parent): ...` — inherits all fields.
  Validators, field defaults, and model config are inherited and can be overridden.
- **Multiple inheritance / mixins**: Python MRO (C3 linearisation) applies.
  Mixin classes typically define `model_config` or validator methods rather than fields,
  to avoid ambiguity in field ordering. Field-bearing mixins work but must be used carefully.
- **`model_rebuild()`**: When forward-referenced classes are involved, Pydantic v2
  requires explicit rebuild calls to resolve the MRO.
- **Discriminated unions**: `Annotated[Union[HumanParticipant, AnimalParticipant], Field(discriminator='species')]`
  — Pydantic v2's preferred pattern for polymorphism. Extremely fast (no branch evaluation)
  because the discriminator field routes to the correct type immediately.

Pydantic does **not** have a concept of abstract classes — Python's `ABC` mechanism
can be combined but Pydantic ignores it for validation purposes.

**Relevance to undata**: The existing `schemas.py` uses Pydantic v2 request/response
models. If schema class hierarchies need to be expressed in API responses (e.g., a
`GET /elements` response that discriminates between `QuantitativeElement` and
`CategoricalElement`), discriminated unions are the right tool. The ORM layer
(`db.py`) can use SQLAlchemy's polymorphic patterns independently.

### 1.2 Storing Inherited Schema Hierarchies in PostgreSQL

Three classical strategies exist for mapping a class hierarchy to relational tables.
The choice depends on query patterns, depth of hierarchy, and whether the hierarchy is
stable or user-defined (extensible).

#### Strategy A: Single-Table Inheritance (STI) — One table, all columns, discriminator column

```sql
CREATE TABLE data_element (
  id UUID PRIMARY KEY,
  element_type TEXT NOT NULL,  -- discriminator: 'quantitative', 'categorical', 'boolean'
  -- shared fields
  name TEXT,
  description TEXT,
  -- quantitative-only
  unit TEXT,
  min_value NUMERIC,
  max_value NUMERIC,
  -- categorical-only
  allowed_values JSONB,
  -- boolean-only
  -- (no extra fields)
);
```

**Pros**:
- One table — no JOINs ever. Simple queries. FastAPI+SQLAlchemy STI maps directly via
  `__mapper_args__ = {'polymorphic_on': element_type, 'polymorphic_identity': 'quantitative'}`.
- Adding a new subtype requires only an `ALTER TABLE ADD COLUMN` (nullable).
- Full-text and vector search stays on one table (important for `name_embedding` similarity).

**Cons**:
- Sparse columns: most rows have NULL in most subtype-specific columns. At 200k elements
  with ~5 subtypes, this is manageable but inelegant.
- No NOT NULL enforcement on subtype columns (cannot enforce `unit NOT NULL` for
  quantitative elements at the DB level without check constraints).
- Schema discovery is opaque — looking at DDL doesn't reveal which columns apply to
  which subtypes.

**When to use**: Hierarchy is shallow (1–2 levels), subtypes are few and stable,
queries frequently join data from multiple subtypes together.

#### Strategy B: Class Table Inheritance (CTI, "Joined Table") — One table per class, JOINs for subtype

```sql
CREATE TABLE element_base (
  id UUID PRIMARY KEY,
  element_type TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE element_quantitative (
  id UUID PRIMARY KEY REFERENCES element_base(id),
  unit TEXT NOT NULL,
  min_value NUMERIC,
  max_value NUMERIC
);

CREATE TABLE element_categorical (
  id UUID PRIMARY KEY REFERENCES element_base(id),
  allowed_values JSONB NOT NULL
);
```

SQLAlchemy supports this natively via `__tablename__` on a subclass + `__mapper_args__
= {'polymorphic_identity': ..., 'inherit_condition': ...}`.

**Pros**:
- DB-level constraints per subtype (NOT NULL for subtype-specific columns).
- Clean DDL — immediately legible which columns belong to which type.
- Base-type queries (list all elements, fetch by name) hit only the base table.

**Cons**:
- Every subtype fetch requires a JOIN. For `SELECT *` on a polymorphic collection, the
  ORM issues N JOINs or a UNION — expensive at 200k rows under async load.
- Schema evolution (adding a new subtype) requires `CREATE TABLE` + migration. More
  friction for extensible/user-defined hierarchies.
- pgvector HNSW index must live on the base table — OK, but must be planned.

**When to use**: Hierarchy is stable, subtype fields are numerous and benefit from NOT
NULL enforcement, queries are predominantly single-subtype (e.g., "fetch all quantitative
elements with unit = Celsius").

#### Strategy C: Adjacency List (for class hierarchy metadata only, not column storage)

An adjacency list stores the _hierarchy relationship_ as data, not as schema:

```sql
CREATE TABLE schema_class (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  parent_id UUID REFERENCES schema_class(id),  -- NULL for root classes
  is_abstract BOOLEAN NOT NULL DEFAULT FALSE,
  is_mixin BOOLEAN NOT NULL DEFAULT FALSE,
  source_id UUID REFERENCES schema_source(id)
);

CREATE TABLE schema_class_slot (
  class_id UUID REFERENCES schema_class(id),
  slot_name TEXT NOT NULL,
  slot_definition JSONB NOT NULL,  -- range, required, multivalued, constraints
  overrides_parent BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (class_id, slot_name)
);
```

With `WITH RECURSIVE` CTE, the full resolved slot set for any class (including all
inherited and mixin slots) can be computed at query time:

```sql
WITH RECURSIVE class_hierarchy AS (
  SELECT id, parent_id, 0 AS depth FROM schema_class WHERE id = $class_id
  UNION ALL
  SELECT sc.id, sc.parent_id, ch.depth + 1
  FROM schema_class sc
  JOIN class_hierarchy ch ON sc.id = ch.parent_id
)
SELECT cs.* FROM schema_class_slot cs
JOIN class_hierarchy ch ON cs.class_id = ch.id
ORDER BY ch.depth DESC;  -- parent slots first; child overrides shadow them
```

**This is the recommended approach for storing schema class hierarchies in undata**
because:
- The hierarchy itself is data (BIDS schema has its own class tree, LinkML's class tree,
  DANDI's class tree — all stored as rows).
- The number of classes is bounded (~100–1000 per source schema, not 200k like elements).
- Mixin relationships are easily modelled with a second `schema_class_mixin` join table
  `(class_id, mixin_id, position)`.
- PostgreSQL `WITH RECURSIVE` resolves arbitrary-depth hierarchies correctly; already
  proven by the existing cycle detection pattern.

#### Closure Table (alternative to adjacency list)

A closure table stores every ancestor-descendant pair explicitly:

```sql
CREATE TABLE schema_class_closure (
  ancestor_id UUID REFERENCES schema_class(id),
  descendant_id UUID REFERENCES schema_class(id),
  depth INT NOT NULL,
  PRIMARY KEY (ancestor_id, descendant_id)
);
```

**Pros**: O(1) ancestor/descendant lookup without recursion; ideal if hierarchy traversal
is on the hot path.

**Cons**: Must be maintained on every insert/update/delete to the hierarchy (trigger or
application logic). At ~1000 classes with typical depth 5–10, the closure table has
at most ~10k rows — overhead is small. If the class hierarchy is read-far-more-than-written
(true for ingested source schemas), this is a good trade.

**Recommendation**: Start with adjacency list (simpler to maintain correctly) and migrate
to closure table if hierarchy traversal becomes a query bottleneck.

#### Nested Sets (not recommended)

Nested sets encode left/right bounds for subtree containment queries. Very fast for
subtree reads but extremely expensive for writes (every INSERT to the middle of the tree
requires updating O(N) rows). Unsuitable for schemas that are updated incrementally
during ingestion.

### 1.3 Decision and Rationale

**Decision**: For storing source schema class hierarchies, use an **adjacency list**
(`schema_class` table with `parent_id` self-FK and a `schema_class_mixin` join table).
Resolve inheritance at ingestion time via `WITH RECURSIVE` CTE (same pattern as cycle
detection). For the `DataElement` type distinction (quantitative vs. categorical vs.
boolean), use **single-table inheritance** with a `element_type` discriminator column
and JSONB overflow — this preserves the existing schema and keeps pgvector HNSW on one
table.

**Rationale**:
- Schema classes are rare, relatively static objects (stored once per schema ingestion).
  An adjacency list with `WITH RECURSIVE` resolution is the simplest correct model.
- `DataElement` rows are the hot path (200k rows, frequent vector search). Single-table
  inheritance avoids JOIN overhead on the embedding similarity path.
- The existing `DataElementChild` join table already handles _structural_ nesting
  (parent-child field relationships). Schema class hierarchies are _type_ hierarchies
  — these are separate concerns and should not be conflated.

**Alternatives considered**:
- Class Table Inheritance for `DataElement` subtypes: rejected because JOIN overhead
  on the 200k-row HNSW search path is too costly; JSONB `constraints` column already
  handles subtype-specific validation metadata.
- Materialized view of the class hierarchy (flattened on write): useful optimization
  but premature; introduce after adjacency list proves slow.

---

## Topic 2: Schema Semantic Versioning — Breaking vs. Non-Breaking Changes

### Background

When a `DataElementVersion` is updated (e.g., `allowed_values` narrows from
`["yes", "no", "unknown"]` to `["yes", "no"]`), downstream consumers may silently
break if they sent `"unknown"` and now fail validation. The system needs a principled
taxonomy of schema changes to decide: is this a new version of the same element
(URI preserved), or a semantic change requiring supersession (new URI)?

### 2.1 Breaking Change Taxonomy

A **breaking change** is any schema modification that can cause a previously-valid
instance to become invalid, or cause a previously-invalid instance to become valid
in a way that corrupts semantics. Breaking changes require a new schema version
with consumer notification; in undata's case, they trigger supersession (new URI).

#### Definitely Breaking

| Change | Reason |
|--------|--------|
| Narrowing `allowed_values` (remove enum value) | Documents/datasets using the removed value now fail validation |
| Adding a new required field (`required: false` → `required: true`) | All existing instances missing that field become invalid |
| Changing `data_type` (string → integer, string → boolean) | Existing string values fail type check |
| Changing `unit` (years → months) | Numeric values have different semantic meaning; consumers compute wrong results |
| Removing a field entirely | Consumers referencing the field receive null/error |
| Narrowing `constraints.minimum` upward | Values in `[old_min, new_min)` now rejected |
| Narrowing `constraints.maximum` downward | Values in `(new_max, old_max]` now rejected |
| Adding a `constraints.pattern` (regex) | Existing values not matching the pattern now fail |
| Changing `multivalued: true` → `false` | Arrays now rejected where they were valid |

#### Non-Breaking (backward-compatible)

| Change | Reason |
|--------|--------|
| Expanding `allowed_values` (add enum value) | New value is accepted; old values still valid |
| Making a required field optional (`required: true` → `false`) | Existing instances remain valid |
| Adding an optional field | Instances without the field remain valid |
| Relaxing `constraints.minimum` downward | More values accepted |
| Relaxing `constraints.maximum` upward | More values accepted |
| Removing a `constraints.pattern` | More values accepted |
| Changing `multivalued: false` → `true` | Scalar instances remain valid (now also accept arrays) |
| Updating `description` text | No effect on validation |
| Changing `name` (display label only, URI unchanged) | Structural identity unchanged |
| Adding `external_uri` annotation to `semantic_graph` node | Additive metadata only |
| Adding `unit.symbol` where previously absent | Additive |
| Correcting `unit.external_uri` to point to correct QUDT entry | Additive correction |

#### Ambiguous / Context-dependent

| Change | Breaking in some contexts |
|--------|--------------------------|
| Widening `allowed_values` | Non-breaking for validation; can break downstream enum-based code generators that produce exhaustive switch statements |
| Changing `unit` label from "years" to "year" (synonym) | Non-breaking semantically if QUDT URI is stable; breaking if consumers compare `unit.label` as a string |
| Changing `constraints.pattern` to an equivalent regex | Non-breaking logically; breaking for consumers that embed the regex literally |
| `required: false` → `true` in a DynamicSchema context | Breaking for DynamicSchema consumers even if not breaking for the base DataElement |

### 2.2 What Existing Frameworks Use

#### OpenAPI / Swagger Diff Tools

- **`openapi-diff`** (Tufin, Java): Full OpenAPI 3.x diff engine. Classifies changes
  as `NON_BREAKING`, `COMPATIBLE` (additive), or `BREAKING`. Detects: removed paths,
  changed response schemas, removed request parameters, added required request body
  fields, changed security schemes.
- **`oasdiff`** (Go, actively maintained as of 2024): CLI and GitHub Action.
  Generates a structured changelog and a breaking-change report. Used by Stripe, Twilio,
  and other API-first companies for CI gates.
- **`bump-my-version` + `major-version-checker`**: Simpler tools that trigger SemVer
  major bump on breaking change detection.

None of these tools operate on JSON Schema directly at the field-constraint level —
they work at the HTTP API (path/parameter/response body) level.

#### JSON Schema Diff

- **`json-schema-diff`** (npm `json-schema-diff` / `json-schema-diff-validator`):
  Computes the set of instances that satisfy schema A but not schema B (the "added"
  set) and vice versa (the "removed" set). If the removed set is non-empty, the
  change is breaking. This is the mathematically rigorous definition.
  - Python equivalent: no mature published library as of 2025. Implementations are
    bespoke.
- **`jsondiff`** (Python): Structural diff of JSON documents (not schemas). Can diff
  two JSONB `constraints` blobs, but does not understand schema semantics.

#### GraphQL

GraphQL has the most mature breaking-change detection ecosystem because the SDL is a
strongly-typed schema format (not just validation):

- **`graphql-inspector`**: CLI + CI integration. Classifies schema changes as
  `BREAKING`, `DANGEROUS` (potentially breaking), or `NON_BREAKING`. Rules:
  removing a type/field/argument = BREAKING; adding a non-null argument = BREAKING;
  adding a nullable argument = NON_BREAKING; deprecating a field = NON_BREAKING.
- **`rover` (Apollo)**: Schema registry with automatic breaking-change detection as
  part of schema check workflow.

GraphQL's type system (no `anyOf`, strict nullability, no pattern constraints) makes
breaking-change detection tractable. JSON Schema's open-world semantics make full
formal analysis NP-hard in the general case.

### 2.3 Python Libraries for Schema Diff

| Library | Scope | Status (2025) |
|---------|-------|---------------|
| `jsonpatch` (Python) | JSON Patch RFC 6902 — structural diff/apply | Active; works on `constraints` JSONB blobs |
| `deepdiff` (Python) | Deep Python object diff; produces structured change report | Active; used in undata's `AuditLog.diff` |
| `datamodel-code-generator` | Generates Pydantic from JSON Schema; not a diff tool | Active |
| `jsonschema-diff` (npm, no Python port) | Schema-semantic diff | npm only |
| `json-schema-diff` (Rust `json_schema_diff` crate) | Set-theoretic diff | Rust only |
| `openapi-pydantic` | Pydantic models for OpenAPI documents; not a diff tool | Active |

**Conclusion**: No production-ready Python library performs schema-semantic diff (set-theoretic
analysis of which instances are added/removed). The practical approach is a **rule-based
classifier** applied to structured JSON diffs.

### 2.4 Recommended Approach for undata

**Decision**: Implement a rule-based `SchemaDiffClassifier` service that operates on
the JSONB diff between two `DataElementVersion` rows. Classify each field change using
the taxonomy above. Return a structured report: `{breaking_changes: [...], non_breaking_changes: [...], ambiguous: [...]}`.
Use this report as advisory input to the curator's supersession decision — never automate
the supersession decision itself (per the existing Decision 13 in `research.md`).

**Breaking-change detection rules (implementation sketch)**:

```python
def classify_change(field: str, old_val, new_val) -> ChangeClass:
    if field == "data_type" and old_val != new_val:
        return BREAKING
    if field == "unit" and old_val != new_val:
        return BREAKING  # semantic change
    if field == "required" and old_val == False and new_val == True:
        return BREAKING
    if field == "multivalued" and old_val == True and new_val == False:
        return BREAKING
    if field == "allowed_values":
        removed = set(old_val or []) - set(new_val or [])
        if removed:
            return BREAKING  # narrowing
        return NON_BREAKING  # expanding
    if field in ("constraints",):
        return classify_constraint_change(old_val, new_val)
    if field in ("description", "name"):
        return NON_BREAKING
    ...
```

**Rationale**:
- The rule-based approach is transparent, testable, and sufficient for the expected
  change patterns in neuroscience metadata schemas.
- Full set-theoretic analysis (Rust/WASM) would add build complexity without meaningful
  benefit at the ≤200k element scale.
- GraphQL-inspector-style CI gates on schema changes are not needed for this API because
  schema changes go through curator review, not automated merges.

**Alternatives considered**:
- Full set-theoretic JSON Schema diff via subprocess call to a Rust binary: adds
  compilation dependency and IPC overhead; premature.
- Embedding the `openapi-diff` Java tool via `subprocess`: JVM startup cost; unacceptable
  for inline request-time classification.
- Using `deepdiff` alone: `deepdiff` tells you _what_ changed but not _whether_ it is
  breaking. Wrapping it with semantic rules is the same as the recommended approach.

---

## Topic 3: Provenance Tracking Models

### Background

User Story 3 ("Audit Trail and Provenance") already has a working implementation
(`AuditLog` table + `DataElementVersion.created_by`). The question is whether undata's
current model is aligned with formal provenance standards (W3C PROV-DM, PAV) and what
minimum additional fields would make provenance queryable and interoperable.

### 3.1 W3C PROV-DM

PROV-DM (Provenance Data Model, W3C Recommendation 2013) defines three core concepts
and six primary relations:

**Core concepts**:
- **Entity**: A thing with identity at a point in time. In undata: `DataElement`,
  `DataElementVersion`, `DynamicSchema`, `MappingFunction`.
- **Activity**: Something that occurred over a period of time and caused entities to
  be created or modified. In undata: a `CREATE`, `UPDATE`, or `DELETE` operation
  recorded in `AuditLog`.
- **Agent**: A person, software, or organization responsible for activities. In undata:
  `UserProfile` (human) or a pipeline process (software agent).

**Primary relations**:
| Relation | PROV-DM Name | Meaning | undata mapping |
|----------|-------------|---------|----------------|
| Entity ← Activity | `wasGeneratedBy` | Activity produced this entity | `DataElementVersion` ← `AuditLog(operation=CREATE)` |
| Entity ← Entity | `wasDerivedFrom` | Entity derived from another | `DataElement.superseded_by` (inverse: new element `wasDerivedFrom` old) |
| Activity ← Agent | `wasAssociatedWith` | Agent performed activity | `AuditLog.actor_id` → `UserProfile` |
| Entity ← Agent | `wasAttributedTo` | Entity attributed to agent | `DataElementVersion.created_by` → `UserProfile` |
| Activity ← Entity | `used` | Activity used this entity | `MappingInput` (mapping activity used input elements) |
| Activity ← Activity | `wasInformedBy` | Activity informed by prior | Not currently modelled; relevant for bulk ingestion pipelines |

**Minimum essential PROV-DM fields** for undata's entities:

```
Entity (DataElementVersion):
  prov:entity          = uri (already: DataElement.uri)
  prov:generatedAtTime = created_at (already: DataElementVersion.created_at)
  prov:wasAttributedTo = created_by → UserProfile (already: DataElementVersion.created_by)
  prov:wasDerivedFrom  = superseded_by (already: DataElement.superseded_by; inverse direction)

Activity (AuditLog row):
  prov:activity        = AuditLog.id
  prov:startedAtTime   = AuditLog.timestamp (already)
  prov:wasAssociatedWith = AuditLog.actor_id → UserProfile (already)
  prov:used            = AuditLog.record_id (already; the entity the activity acted on)

Agent (UserProfile):
  prov:agent           = UserProfile.id
  prov:type            = prov:Person (human via OIDC) or prov:SoftwareAgent (pipeline API key)
```

**Gap analysis**: The existing model satisfies PROV-DM's minimum requirements.
The one missing field is distinguishing `prov:Person` from `prov:SoftwareAgent` in
`UserProfile` — currently both humans and pipeline processes use the same `UserProfile`
schema. Adding `agent_type: TEXT ('person' | 'software')` to `UserProfile` and
`api_key.label` documentation would close this gap.

**PROV-O (OWL ontology)**: PROV-O is the OWL 2 encoding of PROV-DM. The existing HTTP
URI scheme (`{UNDATA_BASE_URL}/elements/{uuid}`) is already aligned with PROV-O's
expectation of dereferenceable URIs. A JSON-LD `@context` overlay mapping
`DataElementVersion` to `prov:Entity`, `AuditLog` to `prov:Activity`, and `UserProfile`
to `prov:Agent` would produce PROV-O compliant output with no data model changes.

### 3.2 PAV Ontology (Provenance, Authoring and Versioning)

PAV (Ciccarese & Soiland-Reyes, 2013; widely used in biomedical informatics,
BioPortal, NCATS) is a lightweight OWL ontology that sits above PROV-O:

| PAV property | Meaning | undata mapping |
|-------------|---------|----------------|
| `pav:createdBy` | Original author (first CREATE) | `DataElementVersion.created_by` (version 1 only) |
| `pav:createdOn` | Creation timestamp | `DataElement.created_at` |
| `pav:authoredBy` | Intellectual contributor (may differ from technical creator) | Not currently tracked; would be a future enhancement |
| `pav:contributedBy` | Person who made a specific version | `DataElementVersion.created_by` |
| `pav:contributedOn` | Timestamp of specific version | `DataElementVersion.created_at` |
| `pav:version` | Human-readable version string | `DataElementVersion.version_num` (integer) |
| `pav:previousVersion` | Link to prior version entity | Reconstructable via `element_id` + `version_num - 1` join |
| `pav:derivedFrom` | Lineage for content (not just supersession) | `DataElement.superseded_by` (complementary) |
| `pav:importedFrom` | Source of ingested content | `DataElement.source_id` → `SchemaSource.url` |
| `pav:retrievedFrom` | URL of the remote resource | `SchemaSource.url` (already) |
| `pav:retrievedOn` | When ingested | `SchemaSource.ingested_at` (already) |
| `pav:sourceAccessedAt` | Timestamp of remote retrieval | Same as `ingested_at` for current ingestion design |

**Key PAV insight for undata**: `pav:importedFrom` + `pav:retrievedFrom` + `pav:retrievedOn`
are directly covered by `SchemaSource` fields. This is strong alignment — the
`SchemaSource` entity is effectively a PAV-compliant provenance record for all elements
ingested from it.

**PAV vs. PROV-DM**: PAV is more specific to digital artifacts with version lineage;
PROV-DM is a general framework. PAV reuses PROV-O classes (`pav:createdBy` is a
sub-property of `prov:wasAttributedTo`). Both can be expressed simultaneously on the
same resources.

### 3.3 How Scientific Platforms Track Schema Provenance

#### DANDI (DANDI Archive, NWB/Neurodata)

- Schema versioned via `dandischema` Python package on PyPI; each release has a SemVer
  tag that corresponds to a JSON Schema draft.
- Dandiset metadata records carry `schemaVersion` (a string matching the package version)
  and `dateCreated` / `dateModified` timestamps.
- The Dandiset itself is the provenance unit — individual field provenance is not tracked.
  No PROV-O alignment as of dandischema 0.6.x.
- `created` / `modified` fields on `Dandiset` map to `pav:createdOn` / `pav:contributedOn`
  but are not formally annotated as such.

#### openMINDS

- Schemas live in the `openMINDS` GitHub organisation; each schema module
  (`openMINDS_core`, `openMINDS_SANDS`, etc.) has its own SemVer.
- Instances carry `@type` (the schema class URI) and `@id` (a persistent IRI, typically
  a KG node UUID).
- `openMINDS` uses a `v3` metadata framework where every instance explicitly carries
  its schema version via the `@type` IRI (e.g., `https://openminds.ebrains.eu/core/v4.0/Subject`).
  Version is embedded in the type URI — a breaking schema change requires a new type URI.
- No explicit PROV-DM/PAV annotation in the schemas, but the type-URI-as-version-indicator
  is functionally equivalent to the undata supersession pattern.

#### BIDS (Brain Imaging Data Structure)

- Schema lives in `bids-standard/bids-specification`; `bidsschematools` parses it at runtime.
- No formal provenance tracking of schema evolution in the schema files themselves.
  Change history is in Git commits only.
- BIDS uses `DatasetDescription.json` with a `BIDSVersion` field — the only provenance
  pointer for datasets.

**Key finding**: None of BIDS, DANDI, or openMINDS implement field-level provenance
tracking. They track schema-level versions (which version of the overall schema was used)
but not the provenance of individual field definitions. undata's `DataElementVersion`
model with `created_by`, `created_at`, and the `SchemaSource` provenance chain
represents a materially more fine-grained provenance model than any of the three sources it ingests from.

### 3.4 Mapping PROV-DM to Relational Tables

#### Minimal PROV-DM schema (additions to current model)

The current undata schema satisfies PROV-DM with one structural gap and two annotation gaps:

**Structural gap**: No explicit `prov:Activity` table distinct from `AuditLog`. The
`AuditLog` table _is_ the activity table — its schema already satisfies `prov:Activity`
requirements. No new table needed.

**Annotation gap 1**: `UserProfile` does not distinguish `prov:Person` from
`prov:SoftwareAgent`. Recommendation: add `agent_type TEXT NOT NULL DEFAULT 'person'`
to `UserProfile` with values `'person'` | `'software'`. Pipeline API keys would be
associated with a `software` agent profile.

**Annotation gap 2**: No explicit `prov:wasInformedBy` relation between consecutive
`AuditLog` activities in a bulk ingestion run. Recommendation: add optional
`caused_by_activity_id UUID REFERENCES audit_log(id)` to `AuditLog` for linking
ingestion-triggered activities to their parent pipeline activity. Nullable; set only
for bulk ingestion flows.

#### Full PROV-O JSON-LD context overlay (no DB changes required)

```json
{
  "@context": {
    "prov": "http://www.w3.org/ns/prov#",
    "pav": "http://purl.org/pav/",
    "DataElementVersion": "prov:Entity",
    "AuditLog": "prov:Activity",
    "UserProfile": "prov:Agent",
    "created_by": "prov:wasAttributedTo",
    "created_at": "prov:generatedAtTime",
    "actor_id": "prov:wasAssociatedWith",
    "timestamp": "prov:startedAtTime",
    "uri": "@id",
    "source_id": {"@id": "pav:importedFrom", "@type": "@id"},
    "version_num": "pav:version",
    "superseded_by": {"@id": "prov:wasDerivedFrom", "@type": "@id"}
  }
}
```

This context, injected when `Accept: application/ld+json` is requested, produces
PROV-O / PAV compliant linked data from existing response fields with zero data model changes.

### 3.5 Decision and Rationale

**Decision**: The existing undata provenance model (AuditLog + DataElementVersion.created_by
+ DataElement.superseded_by + SchemaSource as import record) is functionally aligned with
PROV-DM and PAV. Three targeted enhancements are recommended:

1. Add `agent_type TEXT DEFAULT 'person'` to `UserProfile` to distinguish human from
   software agents (closes PROV-DM `prov:type` gap; requires Alembic migration 0004).
2. Add `caused_by_activity_id UUID REFERENCES audit_log(id)` (nullable) to `AuditLog`
   for bulk-ingestion pipeline traceability (closes `prov:wasInformedBy`; same migration).
3. Expose a `GET /elements/{id}/provenance` endpoint that returns a PROV-O compatible
   JSON-LD document assembled from existing DB fields — no schema changes required,
   just a new router + response serializer.

**Rationale**:
- Items 1 and 2 require a single Alembic migration and minimal service changes.
- Item 3 gives the system formal interoperability with PROV-O-aware tools (e.g., ProvStore,
  PROV Toolbox, OpenPROV) without mandating external dependencies.
- Full RDF triple store for provenance is rejected: PROV-O JSON-LD serialization from
  existing PostgreSQL rows achieves the same queryable provenance at zero operational cost.

**Alternatives considered**:
- Adopting W3C PROV-O as the primary storage model (store raw RDF triples): rejected —
  adds Blazegraph/Virtuoso operational dependency; existing relational model is strictly
  richer for the query patterns (element search, alias detection, version history).
- Using `prov-py` (Python PROV library, W3C PROV implementors group): useful for
  serializing PROV documents but not needed for storage; can be used as a serialization
  helper in the `/provenance` endpoint if adopted.
- DANDI-style schema-level versioning only (no field provenance): rejected — undata's
  value proposition is precisely field-level provenance across sources; schema-only
  versioning loses this.

---

## Summary Table

| Topic | Decision | Key Rationale |
|-------|----------|---------------|
| Schema class hierarchy storage | Adjacency list (`schema_class` + `schema_class_mixin`) + `WITH RECURSIVE` resolution | Classes are data; ~1000 rows per source; recursion pattern already proven by cycle detection |
| DataElement type distinction | Single-table inheritance with `element_type` discriminator + JSONB overflow | Keeps HNSW index on one table; avoids JOIN on the 200k-row hot path |
| Breaking change classification | Rule-based `SchemaDiffClassifier` applied to JSONB diff of `DataElementVersion` fields | Transparent, testable; no Python library for set-theoretic schema diff exists |
| Provenance standard alignment | PROV-DM / PAV via JSON-LD overlay; two small model additions | Existing model already covers >90% of PROV-DM without changes |
| Recommended new additions | `UserProfile.agent_type`, `AuditLog.caused_by_activity_id`, `GET /elements/{id}/provenance` | Closes formal gaps; single Alembic migration |

---

## References

- W3C PROV-DM: https://www.w3.org/TR/prov-dm/
- W3C PROV-O: https://www.w3.org/TR/prov-o/
- PAV Ontology: http://purl.org/pav/ (Ciccarese & Soiland-Reyes, 2013)
- LinkML Specification: https://linkml.io/linkml-model/docs/
- JSON Schema Combining: https://json-schema.org/understanding-json-schema/reference/combining
- OpenAPI Discriminator: https://spec.openapis.org/oas/v3.1.0#discriminator-object
- `oasdiff`: https://github.com/Tufin/oasdiff
- `graphql-inspector`: https://the-guild.dev/graphql/inspector
- SSSOM (Simple Standard for Sharing Ontological Mappings): https://mapping-commons.github.io/sssom/
- QUDT Ontology: https://qudt.org/
- dandischema: https://github.com/dandi/dandischema
- openMINDS: https://openminds.ebrains.eu/
