# Feature Specification: Metamodel, Provenance & LinkML I/O

**Feature Branch**: `011-metamodel-provenance`
**Created**: 2026-03-12
**Status**: Draft
**Input**: Semantic data model principles — PROV-O provenance, schema_ref FK,
LinkML import/export, alias semantics, meta-model YAML

---

## Overview

Extend the undata schema backend with:

1. **schema_ref FK** — object-typed `DataElement` carries a foreign key to a
   `DynamicSchema`, replacing the anonymous `DataElementChild` for named types.
2. **PROV-O provenance endpoints** — `GET /{resource}/{id}/provenance` returns a
   W3C PROV-O JSON-LD document assembled from the existing `AuditLog` table.
3. **LinkML import/export** — `GET /schemas/{id}/linkml` and
   `POST /schemas/import/linkml` with fidelity scoring.
4. **Meta-model YAML** — `docs/undata-metamodel.yaml` describes the undata domain
   in LinkML; rendered via `gen-doc` + MkDocs; published via GitHub Actions.
5. **Pydantic PROV-O models** — generated from an OWL→LinkML conversion of the W3C
   PROV-O ontology via `gen-pydantic`; used for structured JSON-LD construction
   (no `prov` Python library).

---

## User Scenarios & Testing

### User Story 1 — Query Provenance for a Data Element (P1)

A data curator wants to know who created and modified a `DataElement`, when, and why.

**Independent Test**: `GET /elements/{id}/provenance` returns HTTP 200 with
`Content-Type: application/ld+json` containing a `prov:Bundle` with at least one
`prov:Activity`.

**Acceptance Scenarios**:

1. **Given** a `DataElement` with an `AuditLog` entry, **When** `GET
   /elements/{id}/provenance` is called, **Then** the response is a valid PROV-O
   JSON-LD document with `@context: "https://www.w3.org/ns/prov.jsonld"` and a
   `@graph` array containing `prov:Entity`, `prov:Activity`, and `prov:Agent` nodes.

2. **Given** a `DataElement` has been modified 3 times, **When** the provenance
   endpoint is called, **Then** 3 `prov:Activity` nodes are present, each with
   `prov:startedAtTime` and `prov:wasAssociatedWith` pointing to the acting agent.

3. **Given** an invalid `DataElement` id, **When** the provenance endpoint is called,
   **Then** HTTP 404 is returned.

---

### User Story 2 — Query Provenance for a Schema (P1)

A data curator wants to audit the lifecycle of a `DynamicSchema`, including version
changes and structural modifications.

**Independent Test**: `GET /schemas/{id}/provenance` returns HTTP 200 with
`Content-Type: application/ld+json` and `prov:wasDerivedFrom` chain between versions.

**Acceptance Scenarios**:

1. **Given** a `DynamicSchema` with multiple `SchemaChangeLog` entries, **When**
   `GET /schemas/{id}/provenance` is called, **Then** the response contains
   `prov:Entity` nodes for each version with `prov:wasDerivedFrom` linking them.

2. **Given** a schema change triggered a new URI (semantic graph changed), **Then**
   the provenance document includes two `prov:Entity` nodes with different `@id`
   values (old and new URI).

---

### User Story 3 — Export Schema as LinkML (P1)

A developer wants to export a `DynamicSchema` as a LinkML YAML that can be loaded
by `linkml_runtime`.

**Independent Test**: `GET /schemas/{id}/linkml` returns HTTP 200 with
`Content-Type: application/yaml` and a valid LinkML schema.

**Acceptance Scenarios**:

1. **Given** a `DynamicSchema` with 5 elements, **When** `GET /schemas/{id}/linkml`
   is called, **Then** the response is a valid LinkML YAML with `classes:` and
   `slots:` sections, and the `X-Roundtrip-Fidelity` header is present.

2. **Given** a schema with `schema_ref` (object-typed element), **When** exported,
   **Then** the referenced schema class appears as an `import` or inline `class`
   definition in the LinkML output.

3. **Given** a schema with alias groups, **When** exported, **Then** each slot's
   `aliases:` list includes all alias names.

---

### User Story 4 — Import Schema from LinkML (P2)

A developer wants to import a LinkML YAML into the undata backend.

**Independent Test**: `POST /schemas/import/linkml` with a valid LinkML YAML body
returns HTTP 201 and a `RoundtripResult`.

**Acceptance Scenarios**:

1. **Given** a valid LinkML YAML, **When** `POST /schemas/import/linkml` is called,
   **Then** HTTP 201 is returned with a `RoundtripResult` body containing
   `fidelity_score`, `loss_points`, and the created schema's `id`.

2. **Given** a LinkML YAML with unknown `slot_uri`, **When** imported, **Then** the
   `loss_points` list includes `"unknown_slot_uri"` but import succeeds.

3. **Given** a LinkML YAML that references an existing schema by URI, **When**
   imported, **Then** HTTP 409 is returned with `detail: "schema_uri_conflict"`.

---

### User Story 5 — Meta-model Documentation (P2)

A contributor wants to understand the undata data model from a machine-readable,
ontologically-anchored schema.

**Independent Test**: `uv run gen-doc docs/undata-metamodel.yaml -d docs/site/metamodel/`
exits 0 and produces `docs/site/metamodel/index.md`.

**Acceptance Scenarios**:

1. **Given** `docs/undata-metamodel.yaml` exists and is valid LinkML, **When**
   `gen-doc` runs, **Then** Markdown files are produced for each class.

2. **Given** the GitHub Actions workflow `metamodel-docs.yml`, **When** a push to
   `main` occurs, **Then** the meta-model site is published to GitHub Pages.

---

## Requirements

### Functional Requirements

- **FR-001**: `data_element` table MUST have a nullable `schema_ref UUID FK →
  dynamic_schema(id) ON DELETE SET NULL`.
- **FR-002**: When `value_type = "object"`, `schema_ref` MUST be set; API MUST
  return HTTP 422 if `schema_ref` is null for object-typed elements.
- **FR-003**: `DataElementChild` is retained ONLY for anonymous inline structures
  (no `schema_ref`); system MUST NOT create `DataElementChild` when a named
  `DynamicSchema` is the type.
- **FR-004**: `GET /elements/{id}/provenance` MUST return `application/ld+json`
  assembled from `AuditLog` entries using Pydantic PROV-O models.
- **FR-005**: `GET /schemas/{id}/provenance` MUST return `application/ld+json`
  assembled from `SchemaChangeLog` entries using Pydantic PROV-O models.
- **FR-006**: PROV-O JSON-LD MUST include `@context: "https://www.w3.org/ns/prov.jsonld"`.
- **FR-007**: PROV-O Pydantic models MUST be generated from `backend/data/prov-o.linkml.yaml`
  via `gen-pydantic`; the `prov` Python package MUST NOT be added as a dependency.
- **FR-008**: `GET /schemas/{id}/linkml` MUST return `application/yaml` with header
  `X-Roundtrip-Fidelity: <float 0.0–1.0>`.
- **FR-009**: `POST /schemas/import/linkml` MUST return HTTP 201 with a
  `RoundtripResult` JSON body (`fidelity_score`, `loss_points`, `schema_id`).
- **FR-010**: `docs/undata-metamodel.yaml` MUST be a valid LinkML YAML with
  `class_uri` and `slot_uri` anchors referencing established ontologies.
- **FR-011**: A GitHub Actions workflow MUST run `gen-doc` and publish to GitHub Pages
  on push to `main`.
- **FR-012**: `MappingFunction` MUST have a `status` field (`active` | `pending_curation`).
- **FR-013**: System-inferred mappings MUST be created with `status = "pending_curation"`
  and `attributed_to = "urn:undata:system"`.
- **FR-014**: `PUT /mappings/{id}/accept` MUST accept an optional
  `?confidence_threshold=<float>` query parameter; auto-accepts if mapping's
  `confidence_score >= threshold`.

### Non-Functional Requirements

- **NFR-001**: Provenance endpoint response time MUST be < 200ms p95.
- **NFR-002**: PROV-O JSON-LD MUST be valid per the W3C PROV-O specification.
- **NFR-003**: LinkML export MUST complete in < 500ms for schemas with ≤ 500 elements.
- **NFR-004**: `docs/undata-metamodel.yaml` MUST be kept in sync with the backend
  data model (reviewed on every schema migration).

### Key Entities

- **`data_element.schema_ref`**: FK to `dynamic_schema(id)`.
- **`MappingFunction.status`**: New column, enum `active`/`pending_curation`.
- **`backend/data/prov-o.linkml.yaml`**: Hand-curated PROV-O subset as LinkML.
- **`backend/src/models/prov_o.py`**: Generated Pydantic v2 models from PROV-O LinkML.
- **`backend/src/services/schema_changelog.py`**: Assembles PROV-O JSON-LD from `AuditLog` / `SchemaChangeLog` records (upgraded in US1/US2).
- **`backend/src/services/linkml_io.py`**: LinkML import/export service.
- **`docs/undata-metamodel.yaml`**: Self-describing meta-model in LinkML.
- **`.github/workflows/metamodel-docs.yml`**: gen-doc + MkDocs publish workflow.

---

## Success Criteria

- **SC-001**: `GET /elements/{id}/provenance` returns valid PROV-O JSON-LD.
- **SC-002**: `GET /schemas/{id}/provenance` returns valid PROV-O JSON-LD.
- **SC-003**: `GET /schemas/{id}/linkml` returns valid LinkML YAML.
- **SC-004**: `POST /schemas/import/linkml` creates a schema and returns `RoundtripResult`.
- **SC-005**: `uv run gen-doc docs/undata-metamodel.yaml` exits 0.
- **SC-006**: All backend tests pass (no regression on existing 39 tests).
- **SC-007**: Alembic flattened migration `2026_03_12_0001_initial_schema.py` applies cleanly on a fresh DB (`alembic upgrade head` exits 0).
- **SC-008**: `backend/src/models/prov_o.py` is generated (committed, not hand-written).

---

## Clarifications

### Session 2026-03-12

- Q: How should object-typed DataElements reference their schema type? → A: `schema_ref` FK to `DynamicSchema`; `DataElementChild` for anonymous inline only
- Q: Which provenance model should be used internally? → A: PROV-O with Activity/Entity/Agent; exposed as JSON-LD via `GET /{resource}/{id}/provenance`
- Q: What is the semantic scope of aliases vs mappings? → A: Aliases = `skos:exactMatch` only (same graph, different label); inferred mappings attributed to system, `pending_curation` by default, auto-accept via `confidence_threshold`
- Q: How should the backend model relate to LinkML? → A: LinkML is import/export surface only; backend stays PostgreSQL-native; `RoundtripResult` quantifies fidelity loss
- Q: What form should the meta-model take? → A: `docs/undata-metamodel.yaml` (LinkML YAML); rendered via `gen-doc` + MkDocs; published via GitHub Actions alongside JupyterBook
- Q: Should PROV-O use the `prov` Python library? → A: No — convert PROV-O OWL to LinkML, generate Pydantic models via `gen-pydantic`, hand-construct JSON-LD dicts
