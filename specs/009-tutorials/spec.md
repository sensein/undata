# Feature Specification: System Tutorials

**Feature Branch**: `009-tutorials`
**Created**: 2026-03-11
**Status**: Draft
**Input**: "create a set of tutorials to show how the system should be used and ensure that these tutorials run against the services"

## Overview

A set of self-contained, executable Jupyter notebooks in `tutorials/` that walk through
every major workflow in the undata system — from starting services and ingesting schemas to
running migrations. Each notebook:

- Is human-readable narrative documentation
- Is machine-executable via `pytest --nbmake` against live services
- Skips automatically when the required services are unavailable
- Uses environment variables for service URLs and auth tokens (no secrets in files)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Getting Started (Priority: P1)

A new developer has just cloned the repo. They want step-by-step instructions to start the
backend, get an API key, and confirm the system is working.

**Independent Test**: `pytest --nbmake tutorials/01_getting_started.ipynb` — passes when
backend + Keycloak are running; auto-skips when offline.

**Acceptance Scenarios**:

1. **Given** a fresh Docker environment, **When** the developer follows `01_getting_started.ipynb`,
   **Then** all cells execute without error, health checks return `{"status": "ok"}`, and an API
   key is created.

2. **Given** backend is not running, **When** `pytest --nbmake` is run, **Then** the notebook
   is skipped with message "Backend service unavailable".

---

### User Story 2 — Schema Ingestion via CLI (Priority: P1)

A developer wants to push BIDS and DANDI schemas into the backend using the ingestion CLI
and verify the elements are stored.

**Independent Test**: `pytest --nbmake tutorials/02_ingest_schemas.ipynb` — requires backend
running + ingestion package installed.

**Acceptance Scenarios**:

1. **Given** the backend is running, **When** `02_ingest_schemas.ipynb` is executed, **Then**
   the `undata ingest bids` and `undata ingest dandi` commands complete without error and the
   backend confirms elements were stored.

2. **Given** elements have been ingested, **When** the notebook lists elements for source "BIDS",
   **Then** at least one element is returned.

---

### User Story 3 — Browse and Search Elements (Priority: P1)

A developer wants to query the element catalog — list, filter, get details, and explore
semantic similarity between elements across sources.

**Independent Test**: `pytest --nbmake tutorials/03_browse_elements.ipynb`

**Acceptance Scenarios**:

1. **Given** ingested elements exist, **When** `GET /api/v1/elements/` is called, **Then**
   a paginated list with at least one element is returned.

2. **Given** elements exist, **When** alias detection is run, **Then** candidate alias pairs
   are returned with similarity scores.

---

### User Story 4 — Schema Classes and Element Mappings (Priority: P2)

A developer wants to define relationships between elements from different sources — creating
schema classes, cross-source mappings, and alias groups.

**Independent Test**: `pytest --nbmake tutorials/04_mappings_aliases.ipynb`

**Acceptance Scenarios**:

1. **Given** two elements from different sources, **When** a mapping function is created
   between them, **Then** `GET /api/v1/mappings/{id}` returns the mapping with both elements.

2. **Given** semantically similar elements, **When** an alias group is created, **Then**
   `GET /api/v1/aliases/` includes the group.

---

### User Story 5 — LinkML Schema Export (Priority: P2)

A developer wants to generate a unified LinkML YAML schema from all ingested elements.

**Independent Test**: `pytest --nbmake tutorials/05_linkml_export.ipynb`

**Acceptance Scenarios**:

1. **Given** ingested elements, **When** `undata generate-schema --output /tmp/unified.yaml`
   is run, **Then** a valid YAML file is produced with slots and classes.

2. **Given** the generated schema, **When** it is loaded via `LinkMLAdapter`, **Then**
   elements are extractable.

---

### User Story 6 — Schema Roundtrip Validation (Priority: P2)

A developer has a custom JSON Schema or LinkML YAML and wants to validate import fidelity
— no backend required.

**Independent Test**: `pytest --nbmake tutorials/06_schema_roundtrip.ipynb` — runs offline,
no services needed.

**Acceptance Scenarios**:

1. **Given** a simple JSON Schema file, **When** `roundtrip_json_schema(path)` is called,
   **Then** `fidelity_score >= 0.8` and results are printed.

2. **Given** `undata roundtrip <path>` CLI, **When** run on a valid schema, **Then** output
   shows `PASS` or `FAIL` with fidelity score and exits with the correct code.

---

### User Story 7 — Data Migration (Priority: P3)

A developer wants to diff two schema versions, define a migration pathway, and execute a
batch migration — using the migration API.

**Independent Test**: `pytest --nbmake tutorials/07_data_migration.ipynb` — requires backend
+ migration-api + Redis running.

**Acceptance Scenarios**:

1. **Given** two schema sources in the backend, **When** `POST /api/v1/diff` is called,
   **Then** a diff result is returned showing added/removed elements.

2. **Given** a migration pathway, **When** a batch migration job is submitted, **Then** the
   job ID is returned and status is queryable.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide 7 Jupyter notebooks in `tutorials/` covering getting
  started, ingestion, browse/search, mappings, export, roundtrip, and migration.
- **FR-002**: Each notebook MUST run without error via `pytest --nbmake` when the required
  services are available.
- **FR-003**: Each notebook MUST skip automatically when required services are unreachable
  (via conftest.py fixture checking service health endpoints).
- **FR-004**: Service URLs and API tokens MUST be configurable via environment variables
  (`BACKEND_URL`, `MIGRATION_URL`, `API_KEY`); defaults to localhost.
- **FR-005**: Tutorial 06 (roundtrip) MUST run fully offline — no service connectivity required.
- **FR-006**: A `tutorials/conftest.py` MUST provide `backend_url`, `migration_url`, `api_key`,
  and `backend_available`/`migration_available` fixtures.
- **FR-007**: A `tutorials/README.md` MUST document how to run all tutorials and what
  environment variables are needed.
- **FR-008**: `tutorials/pyproject.toml` MUST declare `nbmake`, `httpx`, and `jupyter`/
  `ipykernel` as dev dependencies, managed by `uv`.
- **FR-009**: Tutorials MUST use `httpx` for HTTP calls (already a project dependency).
- **FR-010**: All notebook code MUST pass `ruff check` when extracted as Python.

### Non-Functional Requirements

- **NFR-001**: Each notebook MUST complete within 60 seconds when services respond normally
  (no blocking waits, no polling loops).
- **NFR-002**: Notebooks MUST be readable without execution — all expected outputs described
  in markdown cells.
- **NFR-003**: No secrets, real tokens, or credentials MUST appear in committed notebook files.

### Key Entities

- **`tutorials/conftest.py`**: pytest fixtures providing service config and skip logic.
- **`tutorials/pyproject.toml`**: standalone dependency declaration for tutorial environment.
- **`tutorials/*.ipynb`**: one notebook per user story.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pytest --nbmake tutorials/01_getting_started.ipynb` passes with backend running.
- **SC-002**: `pytest --nbmake tutorials/06_schema_roundtrip.ipynb` passes with no services.
- **SC-003**: All 7 notebooks complete without error when full stack is running.
- **SC-004**: `pytest --nbmake tutorials/` skips gracefully (not fails) when backend is down.
- **SC-005**: `ruff check` passes on all Python extracted from notebook code cells.
- **SC-006**: Each notebook is ≤ 60 s execution time under normal service load.
