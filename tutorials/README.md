# undata Tutorials

Interactive Jupyter notebooks that walk through every major undata workflow, from starting
services to running data migrations. Each notebook is executable as a pytest test via
`pytest --nbmake`, and automatically skips when required services are unavailable.

## Prerequisites

- **Docker + Docker Compose** — for the backend, PostgreSQL, and Keycloak
- **`uv`** — Python package manager (`pip install uv` or see https://docs.astral.sh/uv/)
- **Backend service** running at `http://localhost:8002` (required for T01–T05, T07)
- **Migration API** running at `http://localhost:8004` (required for T07 only)

## Quick Start

```bash
# 1. Start backend services
cd ../backend && docker compose up -d && cd ../tutorials

# 2. Set up tutorials environment
uv sync

# 3. Run all tutorials
uv run pytest --nbmake -v
```

## Run a Single Tutorial

```bash
uv run pytest --nbmake 01_getting_started.ipynb -v
```

## Run the Offline Tutorial (no services needed)

```bash
uv run pytest --nbmake 06_schema_roundtrip.ipynb -v
```

## Interactive Mode (Jupyter Lab)

```bash
uv run jupyter lab
# Open any .ipynb file in the browser
# Kernel: Python 3 (tutorials venv)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost:8002` | Schema backend base URL |
| `MIGRATION_URL` | `http://localhost:8004` | Migration API base URL |
| `API_KEY` | `qs005testtoken...` (quickstart dev key) | Bearer token for authentication |
| `INGESTION_DIR` | `../ingestion` | Path to the ingestion package |

Override for a staging environment:

```bash
BACKEND_URL=https://undata-staging.example.org \
API_KEY=<your-key> \
uv run pytest --nbmake -v
```

## Tutorials

| Notebook | Title | Services Required | Est. Time | Offline? |
|----------|-------|-------------------|-----------|----------|
| `01_getting_started.ipynb` | Getting Started | backend | 5 min | No |
| `02_ingest_schemas.ipynb` | Ingest Schemas via CLI | backend | 10 min | No |
| `03_browse_elements.ipynb` | Browse and Search Elements | backend | 5 min | No |
| `04_mappings_aliases.ipynb` | Schema Classes and Element Mappings | backend | 10 min | No |
| `05_linkml_export.ipynb` | LinkML Schema Export | backend | 5 min | No |
| `06_schema_roundtrip.ipynb` | Schema Roundtrip Validation | **none** | 3 min | **Yes** |
| `07_data_migration.ipynb` | Data Migration | backend + migration-api | 15 min | No |

## Build the Documentation Site

The tutorials can be rendered as a static HTML documentation site using
[Jupyter Book](https://jupyterbook.org/). The notebooks are rendered with their
pre-computed outputs — no services are required at build time.

```bash
# From tutorials/
uv sync
uv run jupyter-book build .

# Open the result (macOS)
open _build/html/index.html
```

The site is output to `tutorials/_build/html/` (gitignored).

## Running in CI

Tutorials auto-skip when services are unavailable. A minimal CI job that validates the
offline tutorial (T06) requires no services:

```bash
cd tutorials
uv sync
uv run pytest --nbmake 06_schema_roundtrip.ipynb -v
```

Full stack CI (all 7 tutorials) requires the backend stack to be running before pytest.
