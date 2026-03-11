# Feature Specification: Schema Enrichment — Classes, Validation, Inheritance & Provenance

**Feature Branch**: `005-schema-enrichment`
**Created**: 2026-03-09
**Status**: Draft
**Input**: Schema analysis, validation rules, backend class hierarchy, inheritance/mixin support, provenance tracking

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Schema Class Analysis (Priority: P1)

A schema curator runs the ingestion pipeline and afterwards wants a structured
view of each ingested schema's information model: which *classes* exist (e.g.
`Subject`, `Session`, `Acquisition`), which *data elements* belong to each
class, which elements are *enumerations* (constrained to a fixed value set),
and which elements are *complex types* (nested objects or arrays of objects).

**Why this priority**: Without understanding the class structure of ingested
schemas, all downstream work (validation rules, inheritance, provenance) is
building on an undefined foundation.

**Independent Test**: After ingesting BIDS + AIND schemas the caller can
`GET /api/v1/schemas/{id}/classes` and receive a list of class records each
containing their member elements; enumeration elements show `allowed_values`;
object/array elements link to child DataElement records.

**Acceptance Scenarios**:

1. **Given** BIDS schema ingested, **When** `GET /api/v1/schemas/{bids_schema_uuid}/classes`,
   **Then** response lists classes (e.g. `Metadata`, `Sidecar`) with their
   member elements; each element includes `data_type`, `required`, and
   `allowed_values` if enum.
2. **Given** AIND Subject schema ingested, **When** querying its classes,
   **Then** `subject_id` (required string) and `subject_details` (required
   complex object) appear under the `Subject` class; `subject_details` links to
   child element records via `DataElementChild`.
3. **Given** an element with `allowed_values = ["M","F","O"]`, **When** it is
   analysed, **Then** it is tagged as `element_kind = "enumeration"` and a
   `SchemaEnumeration` record is created with the three members.
4. **Given** an element with `data_type = "object"`, **When** it is analysed,
   **Then** it is tagged `element_kind = "complex"` and child DataElements
   appear under `DataElementChild`.

---

### User Story 2 — Validation Rules with Semantic Breaking-Change Detection (Priority: P2)

A schema curator attaches typed validation rules to data elements (min/max
values, regex patterns, enum sets, type constraints, cardinality) and receives
automatic breaking-change classification whenever a rule is modified — so they
know whether existing data would still conform.

**Why this priority**: Validation rules are the mechanism that makes schemas
enforceable; breaking-change detection protects downstream datasets.

**Independent Test**: `POST /api/v1/elements/{id}/validation-rules` creates a
rule; `PUT` narrowing an `enum_set` rule returns `breaking: true` in the
response; `PUT` widening it returns `breaking: false`.

**Acceptance Scenarios**:

1. **Given** a DataElement exists, **When** `POST /api/v1/elements/{id}/validation-rules`
   with `{"rule_type": "enum_set", "rule_value": {"values": ["M","F","O"]}}`, **Then** a
   `ValidationRule` record is created and returned with a stable `id`.
2. **Given** existing `enum_set` rule `{"values": ["M","F","O"]}`, **When** `PUT` replaces
   it with `{"values": ["M","F"]}` (narrowing), **Then** response includes `"breaking": true`
   and a `ValidationRuleChange` record is stored.
3. **Given** existing `range` rule `{"min": 0, "max": 120}`, **When** `PUT`
   changes it to `{"min": 0, "max": 150}` (widening), **Then** response includes
   `"breaking": false`.
4. **Given** existing `type_constraint` rule `{"type": "string"}`, **When** `PUT` changes
   it to `{"type": "number"}`, **Then** response includes `"breaking": true`.
5. **Given** `GET /api/v1/elements/{id}/validation-rules`, **Then** all attached
   rules are returned ordered by `rule_type`.

---

### User Story 3 — Schema Inheritance, Mixins & MRO Resolution (Priority: P3)

A schema curator defines inheritance relationships between schemas
(`ChildSchema extends ParentSchema`) and applies mixin schemas (a schema can
include any number of mixins). The system resolves the full field set using
Python's C3 MRO algorithm and exposes the resolved schema via a dedicated
endpoint.

**Why this priority**: Inheritance and mixins are the reuse mechanisms that
prevent duplicate element definitions across schemas; MRO resolution is the
prerequisite for correct validation and LinkML export.

**Independent Test**: Create `BaseSchema` with 2 elements, `ExtendedSchema`
inheriting from it with 1 new element, and attach the system `ProvenanceMixin`
(which has **4** provenance fields); `GET /api/v1/schemas/{extended}/resolved`
returns all 7 elements in MRO order with no duplicates.

**Acceptance Scenarios**:

1. **Given** `ChildSchema` has `parent_id = ParentSchema.id`, **When**
   `GET /api/v1/schemas/{child}/resolved`, **Then** response contains all
   elements from parent + child with `source_schema` annotation on each.
2. **Given** `SchemaA` includes `MixinB` and `MixinC`, **When**
   `GET /api/v1/schemas/{A}/resolved`, **Then** elements from B and C appear
   with correct precedence (C3 MRO: A → B → C) and no duplicates.
3. **Given** circular inheritance attempted (A → B → A), **When** `PUT`
   setting `parent_id`, **Then** `409 Conflict` is returned.
4. **Given** an element name appears in both parent and child, **When** resolved,
   **Then** the child's definition takes precedence (override).
5. **Given** `GET /api/v1/schemas/{id}/inheritance-tree`, **Then** full
   ancestor/mixin graph returned as adjacency list.

---

### User Story 4 — Schema Provenance & ProvenanceMixin (Priority: P4)

Every schema mutation is recorded with W3C PROV-DM provenance (who, what,
when, why). Curators can attach a `ProvenanceMixin` to any schema; when data
is stored using that schema, standard provenance fields
(`prov:createdBy`, `prov:createdAt`, `prov:modifiedAt`, `prov:wasDerivedFrom`)
are automatically included as declared DataElements.

**Why this priority**: Provenance is a fundamental scientific requirement;
without it data lineage cannot be audited or reproduced.

**Independent Test**: After updating a schema, `GET /api/v1/schemas/{id}/changelog`
returns an entry with `actor_id`, `timestamp`, `diff`, and `breaking` flag.
A schema with the ProvenanceMixin applied has 4 extra provenance elements when
its resolved view is fetched.

**Acceptance Scenarios**:

1. **Given** schema is updated (element added), **When**
   `GET /api/v1/schemas/{id}/changelog`, **Then** entry shows `operation=ADD_ELEMENT`,
   `actor_id`, `timestamp`, `diff={added: [{element_id, name}]}`,
   `breaking=false`.
2. **Given** `POST /api/v1/schemas/{id}/provenance-mixin` attaches the mixin,
   **When** `GET /api/v1/schemas/{id}/resolved`, **Then** 4 provenance elements
   appear (`prov_created_by`, `prov_created_at`, `prov_modified_at`,
   `prov_derived_from`) with `source_schema = "ProvenanceMixin"`.
3. **Given** a rule is changed and classified breaking, **When**
   `GET /api/v1/schemas/{id}/changelog`, **Then** entry has `breaking=true` and
   `semantic_boundary_crossed=true`.
4. **Given** `GET /api/v1/schemas/{id}/provenance` (W3C PROV-DM JSON-LD format),
   **Then** response contains `prov:Entity`, `prov:Activity`, `prov:Agent`
   nodes conforming to W3C PROV-DM spec.

---

### Edge Cases

- What happens when an element with complex type (`object`) has child elements
  that are themselves complex? (Recursive nesting — must not infinite-loop;
  maximum nesting depth is 10 levels; deeper structures are rejected with a
  logged `ValueError`)
- What happens when a mixin is deleted while schemas still reference it?
  (Soft delete only; schemas retain their resolved elements snapshot)
- What if two mixins define the same element name with different types?
  (C3 MRO determines which wins; tie-breaking logs a `WARNING` in the changelog)
- What if a `parent_id` update would create a depth > 20? (Reject with 422)
- What if `ValidationRule` is attached to a `DataElement` that is later deleted?
  (Soft delete of element cascades to soft delete of its rules)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST analyse ingested schemas and extract `SchemaClass`
  records grouping DataElements by their source class (e.g. `Subject`,
  `Session`, `Acquisition`).
- **FR-002**: System MUST tag DataElements with `element_kind` ∈
  `{scalar, enumeration, complex, array}` and store `SchemaEnumeration`
  members for enumeration elements. The legacy `allowed_values` JSONB column
  on `DataElement` is retained for backward compatibility; `SchemaEnumeration`
  rows are the authoritative representation going forward. A future migration
  will drop `allowed_values` once all consumers have migrated.
- **FR-003**: System MUST represent complex-type DataElements via existing
  `DataElementChild` with `element_kind = complex` on the parent.
- **FR-004**: System MUST provide `GET /api/v1/schemas/{id}/classes` returning
  class records with member element summaries.
- **FR-005**: System MUST provide `POST`, `GET`, `PUT`, `DELETE` endpoints for
  `ValidationRule` records attached to a DataElement
  (`/api/v1/elements/{id}/validation-rules`).
- **FR-006**: System MUST classify every ValidationRule mutation as `BREAKING`
  or `NON_BREAKING` using the semantic rules:
  - Enum narrowing (removing values) → BREAKING
  - Enum widening (adding values) → NON_BREAKING
  - Range narrowing (tighter min/max) → BREAKING
  - Range widening → NON_BREAKING
  - Type change → BREAKING (always)
  - Pattern addition → BREAKING; pattern removal → NON_BREAKING
  - Cardinality — increasing required minimum or decreasing allowed maximum → BREAKING;
    loosening cardinality (lower min or higher max) → NON_BREAKING
- **FR-007**: System MUST store `ValidationRuleChange` records whenever a rule
  is mutated, capturing `old_value`, `new_value`, `breaking`, `actor_id`.
- **FR-008**: System MUST support a `parent_id` FK on `DynamicSchema` enabling
  single-parent schema inheritance.
- **FR-009**: System MUST support `SchemaMixin` records (M:N schema↔mixin with
  position ordering) and enforce DAG invariant (no cycles).
- **FR-010**: System MUST resolve the full MRO (C3 linearization) for any schema
  and expose `GET /api/v1/schemas/{id}/resolved` returning deduplicated ordered
  elements with `source_schema` annotation.
- **FR-011**: System MUST enforce that a schema's own elements override inherited
  ones of the same `source_local_id`.
- **FR-012**: System MUST record a `SchemaChangeLog` entry for every schema
  mutation (element add/remove, parent change, mixin change) with W3C PROV-DM
  fields: `actor_id`, `timestamp`, `activity_type`, `diff`, `breaking`
  (boolean), `semantic_boundary_crossed` (boolean — `true` when a breaking
  rule change affects elements that belong to an active schema, indicating a
  downstream compatibility boundary has been crossed).
- **FR-013**: System MUST expose `GET /api/v1/schemas/{id}/changelog` (paginated)
  and `GET /api/v1/schemas/{id}/provenance` (W3C PROV-DM JSON-LD).
- **FR-014**: System MUST provide a system-reserved `ProvenanceMixin` schema
  (auto-seeded at startup) containing 4 DataElements:
  `prov_created_by` (string, required), `prov_created_at` (string/ISO8601,
  required), `prov_modified_at` (string/ISO8601), `prov_derived_from` (string).
- **FR-015**: System MUST provide `POST /api/v1/schemas/{id}/provenance-mixin`
  and `DELETE /api/v1/schemas/{id}/provenance-mixin` to attach/detach the
  ProvenanceMixin.

### Key Entities

- **SchemaClass** *(implemented as `DataElement` with `node_kind='class'`)*:
  A named grouping of DataElements within a source schema (e.g. `Subject` in AIND).
  Classes are stored as DataElement rows so they benefit from the same URI,
  alias-detection, and mapping machinery as leaf fields. Class-to-class inheritance
  is recorded in the `SchemaClassInheritance` join table.
- **SchemaEnumeration**: A named set of allowed string values belonging to an
  enumeration DataElement (replaces the unstructured `allowed_values` JSONB).
- **ValidationRule**: A typed rule record attached to a DataElement.
  `rule_type` ∈ `{enum_set, range, pattern, type_constraint, cardinality}`;
  `rule_value` JSONB; `severity` ∈ `{error, warning, info}`.
- **ValidationRuleChange**: Immutable audit of a rule mutation; records
  `old_value`, `new_value`, `breaking`, `actor_id`, `timestamp`.
- **SchemaMixin**: Join table linking a DynamicSchema (base) to another
  DynamicSchema (mixin) with `position` ordering.
- **SchemaChangeLog**: Append-only log of schema-level mutations; each entry
  records W3C PROV-DM provenance fields.
- **ProvenanceMixin** (system schema): Pre-seeded DynamicSchema providing 4
  standard provenance DataElements; immutable by non-admin users.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `GET /api/v1/schemas/{id}/classes` returns class list with member
  elements within 500 ms for schemas with ≤ 200 elements.
- **SC-002**: ValidationRule breaking-change classification is 100% accurate
  against the 6 semantic rules defined in FR-006.
- **SC-003**: `GET /api/v1/schemas/{id}/resolved` for a 3-level deep inheritance
  chain completes in < 200 ms.
- **SC-004**: `GET /api/v1/schemas/{id}/changelog` returns accurate provenance
  entries for 100% of mutations performed during the test run.
- **SC-005**: ProvenanceMixin attaches to any schema and its 4 elements appear
  correctly in the resolved view within 1 API call.
- **SC-006**: Circular inheritance is rejected with HTTP 409 in 100% of test
  cases.
