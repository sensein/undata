# Data Model: System Tutorials

**Branch**: `009-tutorials` | **Date**: 2026-03-11

---

## Entities

### New (tutorials infrastructure)

**`TutorialConfig`** (runtime, not persisted — from env vars + defaults)
- `backend_url: str` — default `http://localhost:8002`
- `migration_url: str` — default `http://localhost:8004`
- `api_key: str` — default: dev seeded key (64-char hex)
- `api_headers: dict` — `{"X-API-Key": api_key}`

**`ServiceHealthState`** (runtime, computed per pytest session)
- `backend_available: bool`
- `migration_available: bool`

---

### Existing (used but not modified)

The tutorials exercise all existing backend and ingestion data models. Key entities used:

| Entity | Source | Tutorial(s) |
|--------|--------|-------------|
| `SchemaSource` | backend `schema_source` table | T01, T02, T03 |
| `DataElement` | backend `data_element` table | T02, T03, T04, T05 |
| `SchemaClass` | backend `schema_class` table | T04, T05 |
| `MappingFunction` | backend `mapping_function` table | T04 |
| `AliasGroup` | backend `alias_group` table | T04 |
| `DynamicSchema` | backend `dynamic_schema` table | T05 |
| `RoundtripResult` | ingestion `undata.roundtrip` | T06 |
| `MigrationPathway` | migration-api | T07 |
| `MigrationJob` | migration-api | T07 |

---

## Tutorial File Structure

```text
tutorials/
├── pyproject.toml              # uv project: nbmake, ipykernel, httpx
├── conftest.py                 # pytest fixtures: urls, api_key, skip helpers
├── README.md                   # How to run; environment variables reference
├── 01_getting_started.ipynb    # Start services, auth, health check
├── 02_ingest_schemas.ipynb     # CLI ingest: BIDS + DANDI → backend
├── 03_browse_elements.ipynb    # List/filter/get elements via REST
├── 04_mappings_aliases.ipynb   # Mappings, alias groups, detect-aliases CLI
├── 05_linkml_export.ipynb      # generate-schema CLI → YAML export
├── 06_schema_roundtrip.ipynb   # Offline roundtrip validation
└── 07_data_migration.ipynb     # Diff + pathway + batch migration
```

---

## Environment Variable Contract

| Variable | Default | Required By |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost:8002` | T01–T05, T07 |
| `MIGRATION_URL` | `http://localhost:8004` | T07 |
| `API_KEY` | `a1b2c3d4e5f6...` (64 chars) | T01–T05, T07 |
| `INGESTION_DIR` | `../ingestion` | T02, T05 |

---

## conftest.py Fixture Graph

```
session-scoped
├── backend_url       → str (from BACKEND_URL env)
├── migration_url     → str (from MIGRATION_URL env)
├── api_key           → str (from API_KEY env)
├── api_headers       → dict {"X-API-Key": api_key}
├── backend_available → bool (health check, cached)
└── migration_available → bool (health check, cached)

function-scoped
└── (none — all state created and deleted within each notebook cell)
```

---

## Notebook-Level Skip Protocol

Each notebook's second cell (code) follows this contract:

```python
# Standard skip cell — present in every service-dependent notebook
import os, httpx
_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8002")
try:
    httpx.get(f"{_BACKEND_URL}/health", timeout=2.0).raise_for_status()
except Exception as _e:
    import pytest
    pytest.skip(f"Backend unavailable: {_e}")
```

Tutorial 06 (roundtrip) omits this cell entirely — it has no service dependency.

---

## Cleanup Contract

Each tutorial that creates backend data MUST clean up in its final cell:

```python
# Cleanup: delete any resources created by this tutorial
# (soft-delete via DELETE /api/v1/... endpoints)
# Goal: tutorials are idempotent — re-running produces the same result
```

Resources created and deleted within each tutorial:
- T01: API key (optional — uses pre-seeded key by default)
- T02: No cleanup needed (ingestion is idempotent via `source_name`)
- T03: No writes
- T04: Mapping functions and alias groups created → deleted at end
- T05: Generated YAML file deleted from `/tmp/`
- T07: Migration pathway → deleted at end
