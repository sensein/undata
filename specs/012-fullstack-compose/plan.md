# Implementation Plan: Full-Stack Docker Compose

**Branch**: `012-fullstack-compose` | **Date**: 2026-03-15 | **Spec**: spec.md

## Summary

Root-level `docker-compose.yml` consolidating 7 services (PostgreSQL, Redis, Keycloak,
backend, migration-api, frontend, Meilisearch) with shared networking, health checks,
and a seed script. Frontend gets a multi-stage Dockerfile.

## Technical Context

**Dependencies**: Docker 24+, Docker Compose v2
**Reuses**: `backend/Dockerfile`, `migration-api/Dockerfile`, `backend/keycloak/realm-export.json`
**New**: `frontend/Dockerfile`, root `docker-compose.yml`, `.env.example`, `scripts/seed.sh`

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity | ✅ | Single compose file; reuses existing Dockerfiles |
| II. TDD | ✅ | Health checks serve as smoke tests |
| VI. Env Isolation | ✅ | All services containerized; no host deps |

## Project Structure

```text
(repo root)
├── docker-compose.yml          ← NEW: full-stack orchestration
├── .env.example                ← NEW: all env vars documented
├── scripts/seed.sh             ← NEW: populate sample data
├── frontend/Dockerfile         ← NEW: multi-stage Node build
├── backend/Dockerfile          (existing)
└── migration-api/Dockerfile    (existing)
```

## Service Architecture

| Service | Image | Port | Depends On | Health Check |
|---------|-------|------|------------|-------------|
| db | pgvector/pgvector:pg16 | 5432 | — | pg_isready |
| redis | redis:7-alpine | 6379 | — | redis-cli ping |
| keycloak | quay.io/keycloak/keycloak:26 | 8080 | db | /health/ready |
| meilisearch | getmeili/meilisearch:v1 | 7700 | — | curl /health |
| backend | build ./backend | 8002 | db, keycloak | curl /api/v1/sources |
| migration-api | build ./migration-api | 8004 | db, redis | curl /health |
| frontend | build ./frontend | 3000 | backend, meilisearch | curl / |

## Frontend Dockerfile Design

```dockerfile
# Stage 1: deps
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

# Stage 2: build
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN corepack enable && pnpm build

# Stage 3: serve
FROM node:22-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

Requires `output: "standalone"` in `next.config.ts`.
