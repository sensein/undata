# undata Development Guidelines

**Iteration 2** — clean rebuild based on lessons from brainstorm v1 (features 001-027).
See [VISION.md](VISION.md) for the full project vision and blueprint.

## Core Rules

1. **No deprecation, no backwards compatibility, no migration.** This system has
   never been deployed. Any code can be rewritten from scratch at any time. Never
   add shims, deprecated fields, version suffixes (/api/v2/), or migration paths.
   Delete old code directly.

2. **Always use `uv run`.** Never invoke `python3` or `pip` directly. Use
   `uv run python`, `uv run ruff`, `uv run pytest`, etc.

3. **Never expose tokens.** Load secrets from `.env` via python-dotenv. Never
   inline in shell commands, source code, or agent output.

4. **Deliver a built car.** Every change should leave the system in a working
   state. If you add a backend endpoint, it should be callable. If you add a
   frontend page, it should render with real data. No stub-only PRs.

## Project Structure

```text
undata/
├── library/          # Core pipeline engine (Python, no DB deps)
├── backend/          # FastAPI + Strawberry GraphQL + PostgreSQL
├── frontend/         # Next.js + Apollo Client + Tailwind
├── specs/            # Feature specifications (brainstorm v1 reference)
├── VISION.md         # Project vision and iteration 2 blueprint
└── docker-compose.yml
```

## Developer Setup

```bash
# Start all services locally (database, backend, frontend)
docker compose up -d

# Or run individual components for development:

# Library (standalone, no services needed)
cd library && uv run pytest tests/ -v
cd library && uv run undata-library pipeline --source bids

# Backend (needs PostgreSQL)
cd backend && uv run pytest tests/ -v

# Frontend (needs backend running)
cd frontend && pnpm install && pnpm dev    # http://localhost:3000
cd frontend && pnpm exec playwright test   # E2E tests

# Full test suite (what CI runs)
cd library && uv run pytest tests/ -v
cd backend && uv run pytest tests/ -v
cd frontend && pnpm test && pnpm exec playwright test
```

## Service Ports

| Service | Port |
|---------|------|
| Frontend (Next.js) | 3000 |
| Backend (FastAPI/GraphQL) | 8002 |
| PostgreSQL | 5432 |
| Keycloak (IdP) | 8080 |
| Redis (task queue) | 6379 |

## Code Style

```
Python: ruff format + ruff check (pyproject.toml), type hints required
TypeScript: strict mode, eslint + prettier
```

## Architecture Summary

- **Library** is the engine — all pipeline logic lives here
- **Backend** is a thin service layer calling library functions, storing in DB
- **Frontend** talks only to the backend via GraphQL — no file reading
- **StorageBackend protocol** — library functions work with files (CLI) or DB (backend)
- **Task manager** — long-running operations (pipeline, ontology indexing) are async tasks
- Pipeline order: extract → enrich → align → commit → transform
- All entities enter as "staged", become "curated" through curator review
