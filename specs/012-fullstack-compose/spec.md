# Feature Specification: Full-Stack Docker Compose

**Feature Branch**: `012-fullstack-compose`
**Created**: 2026-03-15
**Status**: Draft
**Input**: Consolidate all services into a single `docker-compose.yml` at repo root for local development.

---

## Overview

Create a root-level `docker-compose.yml` that brings up the entire undata stack with a single
`docker compose up` command: backend, migration-api, frontend, PostgreSQL, Redis, Keycloak,
and Meilisearch. Includes a frontend Dockerfile, `.env.example`, and seed script.

---

## User Scenarios & Testing

### User Story 1 — One-Command Local Stack (Priority: P1)

A developer clones the repo and wants the full system running locally. They run
`docker compose up -d` from the repo root and all services start with correct networking.

**Acceptance Scenarios**:

1. **Given** a fresh clone, **When** `docker compose up -d` runs, **Then** all 7 services
   reach healthy status within 120 seconds.
2. **Given** the stack is running, **When** the developer visits `http://localhost:3000`,
   **Then** the Schema Explorer loads and can search elements (after seed).
3. **Given** the stack is running, **When** `docker compose down -v` runs, **Then** all
   containers and volumes are removed cleanly.

### User Story 2 — Seed Data (Priority: P2)

A developer wants test data populated so the frontend has content to display.

**Acceptance Scenarios**:

1. **Given** the stack is running, **When** `docker compose run --rm seed` executes,
   **Then** sample elements, schemas, and mappings are created via the backend API.
2. **Given** seed has run, **When** `pnpm run index-elements` runs in the frontend container,
   **Then** Meilisearch search returns results.

---

## Requirements

### Functional Requirements

- **FR-001**: Root `docker-compose.yml` MUST define services: `db`, `redis`, `keycloak`,
  `backend`, `migration-api`, `frontend`, `meilisearch`.
- **FR-002**: Frontend MUST have a multi-stage Dockerfile (Node 22 build + serve).
- **FR-003**: All services MUST use a shared Docker network with DNS service discovery.
- **FR-004**: Backend and migration-api MUST wait for `db` healthy check before starting.
- **FR-005**: `.env.example` at repo root MUST document all required environment variables.
- **FR-006**: A `seed` service MUST populate sample data via backend API calls.
- **FR-007**: Existing `backend/docker-compose.yml` and `migration-api/docker-compose.yml`
  MUST remain functional for standalone development.

### Non-Functional Requirements

- **NFR-001**: Full stack MUST start within 120 seconds on a machine with 16GB RAM.
- **NFR-002**: Total image size for all custom services MUST be under 2GB.

### Key Entities

- `docker-compose.yml` (repo root)
- `frontend/Dockerfile`
- `.env.example` (repo root)
- `scripts/seed.sh` (seed data script)

---

## Success Criteria

- **SC-001**: `docker compose up -d` from repo root starts all 7 services, all healthy.
- **SC-002**: `http://localhost:3000` loads the frontend.
- **SC-003**: `http://localhost:8002/api/v1/sources` returns JSON.
- **SC-004**: `docker compose down -v` cleans up all resources.
