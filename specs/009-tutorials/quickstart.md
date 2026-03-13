# Quickstart: Running the Tutorials

**Feature**: `009-tutorials` | **Date**: 2026-03-11

---

## Prerequisites

- Docker and Docker Compose (for backend + PostgreSQL + Keycloak)
- `uv` (Python package manager)
- Backend service running at `http://localhost:8002`
- Migration API running at `http://localhost:8004` (for Tutorial 07 only)

---

## Quick Start (All Tutorials)

```bash
# 1. Start backend services
cd backend && docker compose up -d && cd ..

# 2. Set up tutorials environment
cd tutorials
uv sync

# 3. Run all tutorials
uv run pytest --nbmake -v

# Expected output:
# tutorials/01_getting_started.ipynb PASSED
# tutorials/02_ingest_schemas.ipynb PASSED
# tutorials/03_browse_elements.ipynb PASSED
# tutorials/04_mappings_aliases.ipynb PASSED
# tutorials/05_linkml_export.ipynb PASSED
# tutorials/06_schema_roundtrip.ipynb PASSED
# tutorials/07_data_migration.ipynb SKIPPED (migration-api not running)
```

---

## Run a Single Tutorial

```bash
cd tutorials
uv run pytest --nbmake tutorials/01_getting_started.ipynb -v
```

---

## Run Offline Tutorial (no services)

```bash
cd tutorials
uv run pytest --nbmake tutorials/06_schema_roundtrip.ipynb -v
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost:8002` | Schema backend base URL |
| `MIGRATION_URL` | `http://localhost:8004` | Migration API base URL |
| `API_KEY` | `a1b2c3d4...` (dev key) | API key for authentication |
| `INGESTION_DIR` | `../ingestion` | Path to ingestion package |

Override for a staging environment:

```bash
BACKEND_URL=https://undata-staging.example.org \
API_KEY=<your-key> \
uv run pytest --nbmake -v
```

---

## Run Tutorials Interactively

```bash
cd tutorials
uv run jupyter lab
# Open any .ipynb file in the browser
# Kernel: Python 3 (tutorials venv)
```

---

## Service Status Check

```bash
# Verify backend is healthy
curl http://localhost:8002/health
# Expected: {"status": "ok", ...}

# Verify migration API is healthy
curl http://localhost:8004/health
# Expected: {"status": "ok"}
```

---

## QS-001: Smoke Test — Tutorial 01 (Backend Required)

```bash
cd backend && docker compose up -d
cd ../tutorials
uv sync
uv run pytest --nbmake tutorials/01_getting_started.ipynb -v
```

Expected: `PASSED` with health check confirmation and API key creation.

---

## QS-002: Smoke Test — Tutorial 06 (Offline)

```bash
cd tutorials
uv sync
uv run pytest --nbmake tutorials/06_schema_roundtrip.ipynb -v
```

Expected: `PASSED` — no services needed; tests roundtrip on bundled fixtures.

---

## QS-003: Full Stack Run

```bash
cd backend && docker compose up -d
cd ../migration-api && docker compose up -d
cd ../ingestion && uv sync
cd ../tutorials && uv sync
uv run pytest --nbmake -v --tb=short 2>&1 | tee tutorial-run.log
```

Expected: all 7 tutorials PASS (or SKIP if optional services unavailable).
