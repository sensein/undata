# Data Model: Schema Enrichment

**Feature**: `005-schema-enrichment` | **Date**: 2026-03-09

---

## Entity Relationship Overview

```
DataElement (existing)
  │  ├── element_kind (new column)
  │  └──< ValidationRule >──< ValidationRuleChange
  │
  ├──< SchemaClassElement >── SchemaClass ──< SchemaClass (parent_class_id)
  │
  └──< SchemaEnumeration (new, replaces allowed_values JSON for enum kind)

DynamicSchema (existing, extended)
  │  ├── parent_id FK (new: single-parent inheritance)
  │  └──< SchemaMixin (new: ordered mixin list)
  │
  ├──< SchemaChangeLog (new: PROV-DM provenance)
  └── ProvenanceMixin (system-seeded DynamicSchema, attached via SchemaMixin)

SchemaClass ──< SchemaClassElement >── DataElement
```

**Unchanged entities** (carry forward from 002): `SchemaSource`, `DataElement`,
`DataElementVersion`, `DataElementChild`, `DynamicSchema`, `DynamicSchemaElement`,
`AliasGroup`, `AliasGroupMember`, `MappingFunction`, `MappingInput`,
`MappingFunctionVersion`, `AuditLog`, `UserProfile`, `APIKey`.

---

## New / Extended Entities

### `DataElement` — new columns `element_kind` and `node_kind`

Two new classification columns on the existing `DataElement` table:

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `element_kind` | TEXT | NOT NULL DEFAULT 'scalar' | `scalar`, `enumeration`, `complex`, `array` — describes the *value shape* |
| `node_kind` | TEXT | NOT NULL DEFAULT 'field' | `field`, `class`, `mixin` — describes the *structural role* |

**`element_kind` derivation** (set at element creation / update):
- `allowed_values` non-empty → `enumeration`
- `data_type = 'object'` → `complex`
- `data_type = 'array'` or `multivalued = true` → `array`
- Otherwise → `scalar`

**`node_kind` semantics**:
- `field` — a leaf data element (default)
- `class` — a schema class template; always has `data_type = 'object'`;
  child fields stored via `DataElementChild`; can be inherited via
  `SchemaClassInheritance`
- `mixin` — a reusable field bundle; same mechanics as `class` but
  intended for composition rather than standalone use

> **Design note**: Using `DataElement` for class nodes (rather than a
> separate `SchemaClass` table) keeps classes inside the unified URI
> scheme, so alias detection and mapping machinery can operate on classes
> just as on leaf fields. This follows the recommendation from research Q6.

Existing rows backfilled by migration (all `node_kind = 'field'`).

---

### SchemaClassInheritance

Records the `is_a` / mixin inheritance between schema class nodes
(DataElements with `node_kind = 'class'` or `'mixin'`). This is *not*
the same as `DynamicSchema` inheritance — it tracks the class hierarchy
*within a source schema* (e.g. NWB `NWBFile is_a NWBContainer`).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `parent_class_id` | UUID | FK → DataElement NOT NULL | Parent class (`node_kind IN ('class','mixin')`) |
| `child_class_id` | UUID | FK → DataElement NOT NULL | Child / inheriting class |
| `relationship_type` | TEXT | NOT NULL DEFAULT 'is_a' | `is_a` or `mixin` |
| **PK** | | `(parent_class_id, child_class_id)` | |

**Query: all fields of class X including inherited**:
```sql
WITH RECURSIVE ancestors AS (
  SELECT child_class_id AS class_id
  WHERE child_class_id = :target_class_id
  UNION ALL
  SELECT sci.parent_class_id
  FROM schema_class_inheritance sci
  JOIN ancestors a ON sci.child_class_id = a.class_id
)
SELECT de.id, de.uri, dec.field_name, dec.position
FROM data_element_child dec
JOIN data_element de ON de.id = dec.child_id
WHERE dec.parent_id IN (SELECT class_id FROM ancestors)
  AND de.deleted_at IS NULL
ORDER BY dec.position;
```

---

### SchemaEnumeration

First-class record for each enumeration value belonging to an enumeration
DataElement. Supersedes the `allowed_values` JSONB array for `element_kind =
'enumeration'` elements (the JSONB is retained for backwards compat).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `element_id` | UUID | FK → DataElement NOT NULL | Must have `element_kind = 'enumeration'` |
| `value` | TEXT | NOT NULL | The allowed string value |
| `label` | TEXT | | Human-readable label |
| `description` | TEXT | | Optional description |
| `position` | INT | NOT NULL | Display ordering |
| **Unique** | | `(element_id, value)` | |

---

### ValidationRule

A typed constraint attached to a DataElement.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `element_id` | UUID | FK → DataElement NOT NULL | |
| `rule_type` | TEXT | NOT NULL | `enum_set`, `range`, `pattern`, `type_constraint`, `cardinality` |
| `rule_value` | JSONB | NOT NULL | Type-specific payload (see below) |
| `severity` | TEXT | NOT NULL DEFAULT 'error' | `error`, `warning`, `info` |
| `description` | TEXT | | Why this rule exists |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `created_by` | UUID | FK → UserProfile NOT NULL | |
| `deleted_at` | TIMESTAMPTZ | | Soft delete |
| **Unique** | | `(element_id, rule_type)` where `deleted_at IS NULL` | One active rule per type per element |

**`rule_value` JSONB schemas by `rule_type`**:

| `rule_type` | `rule_value` structure | Example |
|------------|----------------------|---------|
| `enum_set` | `{"values": ["v1","v2",...]}` | `{"values":["M","F","O"]}` |
| `range` | `{"min": N, "max": N}` (either optional) | `{"min":0,"max":120}` |
| `pattern` | `{"regex": "..."}` | `{"regex":"^[A-Z]{2}[0-9]{3}$"}` |
| `type_constraint` | `{"type": "string\|number\|boolean\|..."}` | `{"type":"integer"}` |
| `cardinality` | `{"min_count": N, "max_count": N}` | `{"min_count":1,"max_count":5}` |

---

### ValidationRuleChange

Immutable audit record of every ValidationRule mutation. Stores the breaking
change classification.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `rule_id` | UUID | FK → ValidationRule NOT NULL | |
| `element_id` | UUID | FK → DataElement NOT NULL | Denormalised for fast element-scoped queries |
| `operation` | TEXT | NOT NULL | `CREATE`, `UPDATE`, `DELETE` |
| `old_value` | JSONB | | `null` on CREATE |
| `new_value` | JSONB | | `null` on DELETE |
| `breaking` | BOOLEAN | NOT NULL | True if change narrows constraints |
| `actor_id` | UUID | FK → UserProfile NOT NULL | |
| `timestamp` | TIMESTAMPTZ | NOT NULL | |
| `reason` | TEXT | | Optional curator-provided justification |

---

### `DynamicSchema` — new columns

Extends the existing table with inheritance support.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `parent_id` | UUID | FK → DynamicSchema, nullable | Single-parent inheritance; NULL = root schema |
| `is_mixin` | BOOLEAN | NOT NULL DEFAULT FALSE | Marks this schema as a mixin (can be embedded but not used standalone) |
| `is_system` | BOOLEAN | NOT NULL DEFAULT FALSE | System-reserved schemas (ProvenanceMixin); immutable by non-admin |

**Cycle invariant**: `parent_id` must not create a cycle. Enforced at write
time via recursive CTE check. Max depth 20 (enforced in service layer).

---

### SchemaMixin

Records which mixin schemas are applied to a base schema. Order determines
C3 MRO precedence.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `schema_id` | UUID | FK → DynamicSchema NOT NULL | The base schema |
| `mixin_id` | UUID | FK → DynamicSchema NOT NULL | The mixin (`is_mixin = true`) |
| `position` | INT | NOT NULL | Mixin application order (lower = earlier = higher precedence) |
| **PK** | | `(schema_id, mixin_id)` | |

**Invariant**: `mixin_id.is_mixin = true`. Cycle check applies (a mixin
cannot reference the base schema through any transitive path).

---

### SchemaChangeLog

Append-only log of every schema-level mutation. Provides W3C PROV-DM
`Activity` semantics.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `schema_id` | UUID | FK → DynamicSchema NOT NULL | |
| `version_num` | INT | NOT NULL | Schema version after this change; computed at insert time as `SELECT COALESCE(MAX(version_num), 0) + 1 FROM schema_change_log WHERE schema_id = :id` |
| `operation` | TEXT | NOT NULL | `CREATE`, `ADD_ELEMENT`, `REMOVE_ELEMENT`, `UPDATE_PARENT`, `ADD_MIXIN`, `REMOVE_MIXIN`, `RULE_CHANGE` |
| `actor_id` | UUID | FK → UserProfile NOT NULL | PROV-DM `Agent` |
| `timestamp` | TIMESTAMPTZ | NOT NULL | PROV-DM `generatedAtTime` |
| `activity_type` | TEXT | NOT NULL | `schema_edit`, `ingestion`, `mixin_attach`, etc. |
| `diff` | JSONB | | `{added: [...], removed: [...], changed: {...}}` |
| `breaking` | BOOLEAN | NOT NULL DEFAULT FALSE | True if any element removal or rule narrowing |
| `semantic_boundary_crossed` | BOOLEAN | NOT NULL DEFAULT FALSE | True if breaking AND affected elements have data downstream |
| `reason` | TEXT | | Optional curator justification (PROV-DM `rdfs:comment`) |

**W3C PROV-DM JSON-LD serialisation** (served by `GET /api/v1/schemas/{id}/provenance`):

```json
{
  "@context": "http://www.w3.org/ns/prov",
  "@graph": [
    {
      "@type": "prov:Entity",
      "@id": "https://undata.io/schemas/{schema_id}",
      "prov:wasGeneratedBy": {"@id": "activity/{log_id}"},
      "prov:wasAttributedTo": {"@id": "agent/{actor_id}"}
    },
    {
      "@type": "prov:Activity",
      "@id": "activity/{log_id}",
      "prov:startedAtTime": "{timestamp}",
      "prov:endedAtTime": "{timestamp}",
      "rdfs:comment": "{reason}"
    },
    {
      "@type": "prov:Agent",
      "@id": "agent/{actor_id}",
      "foaf:name": "{display_name}"
    }
  ]
}
```

---

## ProvenanceMixin — System-Seeded Schema

The `ProvenanceMixin` is a `DynamicSchema` record seeded at startup with
`is_system = true`, `is_mixin = true`, `name = "ProvenanceMixin"`.

Its four DataElements (seeded under the `undata` SchemaSource):

| Element `source_local_id` | `data_type` | `required` | Semantic |
|--------------------------|-------------|------------|---------|
| `prov_created_by` | string | true | prov:wasAttributedTo (actor ID / display name) |
| `prov_created_at` | string | true | prov:generatedAtTime (ISO 8601) |
| `prov_modified_at` | string | false | prov:invalidatedAtTime (ISO 8601) |
| `prov_derived_from` | string | false | prov:wasDerivedFrom (source URI or ID) |

---

## Migrations Summary

| Migration | Description |
|-----------|-------------|
| 0004 | Add `element_kind`, `node_kind` to `data_elements`; backfill from `allowed_values`/`data_type`; add `agent_type` to `user_profiles`; add `caused_by_activity_id` to `audit_log` |
| 0005 | Add `parent_id`, `is_mixin`, `is_system` columns to `dynamic_schemas` |
| 0006 | Create `schema_class_inheritance`, `schema_enumerations` tables |
| 0007 | Create `validation_rules`, `validation_rule_changes` tables |
| 0008 | Create `schema_mixins`, `schema_change_log` tables |
| 0009 | Seed `ProvenanceMixin` system schema and its 4 DataElements |
