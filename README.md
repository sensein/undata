# undata

A unified neuroscience data element registry that harmonizes schemas across BIDS, NWB, DANDI, openMINDS, and AIND into a searchable, version-tracked system with provenance, mappings, and LinkML interoperability.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Ingestion   │────▶│   Backend    │◀────│ Migration API   │
│  (Python CLI)│     │ (FastAPI)    │     │ (FastAPI+Celery) │
└─────────────┘     └──────┬───────┘     └────────┬────────┘
                           │                      │
                    ┌──────┴───────┐        ┌─────┴─────┐
                    │  PostgreSQL  │        │   Redis    │
                    │  (pgvector)  │        └───────────┘
                    └──────────────┘
                           │
                    ┌──────┴───────┐     ┌─────────────┐
                    │   Frontend   │────▶│ Meilisearch  │
                    │  (Next.js)   │     └─────────────┘
                    └──────────────┘
```

| Service | Port | Description |
|---------|------|-------------|
| Backend | 8002 | Schema registry REST API (elements, schemas, mappings, provenance) |
| Migration API | 8004 | Async migration execution (pathways, jobs, schema diff) |
| Frontend | 3000 | Schema Explorer (search, graph, compare, contribute, migrations) |
| PostgreSQL | 5432 | Primary data store with pgvector for embeddings |
| Redis | 6379 | Celery task queue for migration jobs |
| Keycloak | 8080 | OIDC identity provider |
| Meilisearch | 7700 | Full-text search engine |

## Quick Start

```bash
# Clone
git clone https://github.com/sensein/undata.git
cd undata

# Start the full stack
cp .env.example .env
docker compose up -d

# Seed sample data
docker compose exec backend bash /app/scripts/seed.sh http://localhost:8002

# Open the frontend
open http://localhost:3000
```

## Project Structure

```
undata/
├── backend/          # Schema backend REST API (Python 3.14 / FastAPI / SQLAlchemy)
├── ingestion/        # Schema ingestion CLI (BIDS, NWB, DANDI, openMINDS, AIND adapters)
├── migration-api/    # Migration execution API (Python 3.12 / FastAPI / Celery / Redis)
├── frontend/         # Schema Explorer UI (TypeScript / Next.js 15 / React / Cytoscape.js)
├── library/          # Flat-file schema library (LinkML YAML with versioning + validation CLI)
├── tutorials/        # 7 Jupyter notebooks + JupyterBook site
├── docs/             # Meta-model documentation (LinkML + MkDocs)
├── specs/            # Feature specifications (001-015)
├── scripts/          # Utility scripts (seed data)
├── docker-compose.yml  # Full-stack orchestration (8 services)
└── .github/workflows/  # CI/CD (lint, tests, image builds, Pages deploy)
```

## Development

### Backend

```bash
cd backend
docker compose up -d          # Start DB + Keycloak
uv sync                       # Install dependencies
uv run alembic upgrade head   # Run migrations
uv run uvicorn src.main:app --reload --port 8002
uv run pytest tests/ -v       # Run tests (276 tests)
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev          # Dev server at http://localhost:3000
pnpm test         # Unit tests (44 tests)
pnpm lint         # ESLint
pnpm build        # Production build
```

### Ingestion

```bash
cd ingestion
uv sync
uv run undata ingest bids dandi openminds nwb aind   # Ingest all schemas
uv run undata generate-schema --output unified.yaml   # Generate unified LinkML
uv run undata roundtrip unified.yaml                  # Validate roundtrip fidelity
```

### Library

```bash
cd library
uv sync
uv run undata-library validate elements/     # Validate YAML files
uv run undata-library diff elements/el.yaml  # Diff element versions
uv run undata-library export --backend-url http://localhost:8002 --output .
uv run undata-library index                  # Build index.yaml
```

### Tutorials

```bash
cd tutorials
uv sync
uv run jupyter-book build .     # Build documentation site
open _build/html/index.html     # View locally
```

## CI/CD

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `lint.yml` | All pushes | Ruff lint (ingestion + tutorials) |
| `frontend.yml` | frontend/ changes | ESLint + vitest + build |
| `backend-tests.yml` | PRs touching backend/ | PostgreSQL + pytest |
| `build-images.yml` | `v*` tags | Build + push to GHCR |
| `tutorials-site.yml` | main push (tutorials/) | JupyterBook → GitHub Pages |
| `metamodel-docs.yml` | main push (docs/) | MkDocs → GitHub Pages |
| `tutorials-offline.yml` | tutorials/ changes | Notebook execution tests |

## Features

15 features implemented across the system:

1. **Neuro Schema Integration** — 5 adapters (BIDS, NWB, DANDI, openMINDS, AIND)
2. **Schema Backend** — REST API with auth, versioning, unit standardization
3. **Schema Explorer** — Search, filter, element detail, relationship graph
4. **Migration API** — Async pathway execution with Celery
5. **Schema Enrichment** — Validation rules, MRO, provenance, soft-delete
6. **Dual-Path Adapters** — Code + file extraction modes
7. **End-to-End Pipeline** — Full ingestion + LinkML generation
8. **Schema Import Roundtrip** — JSON Schema + LinkML fidelity scoring
9. **Tutorials** — 7 interactive Jupyter notebooks
10. **JupyterBook** — Rendered tutorial documentation site
11. **Metamodel Provenance** — PROV-O JSON-LD, LinkML I/O, mapping accept
12. **Full-Stack Compose** — Single-command local development
13. **Migration UI** — Pathway browsing, job execution, schema diff
14. **Deployment Pipeline** — GHCR images, GitHub Pages, backend CI
15. **undata-library** — Standalone LinkML YAML library with CLI

## License

MIT
