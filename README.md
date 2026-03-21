# undata

A unified neuroscience data element registry that harmonizes schemas across BIDS, NWB, DANDI, openMINDS, and AIND into a searchable, version-tracked system with provenance, mappings, and LinkML interoperability.

## Why undata Exists

### The Problem

Neuroscience data lives in five major schema ecosystems — BIDS, NWB, DANDI, openMINDS, and AIND — each with its own vocabulary, types, units, and constraints. The same real-world concept (e.g., "subject age") appears differently in each:

| Source | Name | Type | Unit | Representation |
|--------|------|------|------|----------------|
| BIDS | `age` | float | years | bare numeric field |
| NWB | `age` | string | ISO 8601 | duration string |
| DANDI | `age` | PropertyValue | — | structured object with BirthReference/GestationalReference |
| AIND | `subject.age` | number | — | nested JSON Schema property |

This fragmentation means:
- **No shared vocabulary** — researchers who combine data from multiple sources must build ad-hoc mappings manually, with no systematic way to discover what exists across all sources.
- **Identity conflation** — existing systems conflate *what a data element is* (type, unit, constraints) with *where it came from* (source name, description). The same concept from two sources looks like two different things; two different concepts with the same name look identical.
- **Invisible transformations** — when data moves between formats, there is no record of what changed, who decided it, or whether it's reversible.

### The Solution

undata solves these problems with three architectural innovations:

1. **Content-addressed identity** — Each data element's identity is the SHA-256 hash of its semantic graph (ontology term + data type + unit + constraints). Same concept from any source = same hash = automatic deduplication. Different type or unit = different hash = distinct element. Identity is stable, dereferenceable, and independent of any source's naming.

2. **Identity ≠ Provenance separation** — Each element has one semantic identity block (hashed) and N provenance entries (not hashed). Cross-source elements naturally merge when semantically identical, while preserving full lineage via W3C PROV-O metadata (who ingested it, when, from where, derived from what).

3. **Ingest → Enrich → Align pipeline** — Automated extraction from all 5 sources, followed by embedding-based ontology alignment (`"{class} {name}: {description}"` → precomputed vectors in parquet) and alias detection with SKOS mapping relations — all tracked with provenance.

The result is a canonical registry where every neuroscience data concept has a single stable URI, full cross-source provenance, and semantic relationships (exact match, close match, broad/narrow match) to related concepts — making neuroscience data FAIR (Findable, Accessible, Interoperable, Reusable).

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
├── migration-api/    # Migration execution API (Python 3.12 / FastAPI / Celery / Redis)
├── frontend/         # Schema Explorer UI (TypeScript / Next.js 15 / React / Cytoscape.js)
├── library/          # Schema library CLI + adapters (Python package — no data files in git)
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

### Library

The library CLI handles all ingestion, enrichment, and alignment. Registry output (elements, schemas, transforms) is written to `~/.local/share/undata/registry/` by default (configurable via `--output-dir` or `$UNDATA_REGISTRY_DIR`). Output is **not** committed to git — it's generated data.

```bash
cd library
uv sync
uv run undata-library pipeline --source bids   # Full pipeline: ingest → enrich → align → transform
uv run undata-library pipeline --source nwb     # Each source auto-downloads from its upstream repo
uv run undata-library ontology refresh          # Bulk download ontologies from OBO Foundry
uv run undata-library validate-ingestion        # Validate all output
uv run undata-library cache list                # Show cached source downloads
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

18 features implemented across the system:

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
15. **undata-library** — Standalone flat-file library with CLI
16. **Value Concepts** — Categorical values as content-addressed semantic entities
17. **Backend–Library Alignment** — Content-addressed element model in backend
18. **Rich Data Model** — reproschema alignment, semantic embeddings, ingest→enrich→align pipeline

## License

MIT
