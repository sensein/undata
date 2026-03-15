# Tasks: Full-Stack Docker Compose

**Feature**: `012-fullstack-compose` | **Branch**: `012-fullstack-compose`

---

- [X] T001 Create `frontend/Dockerfile`: multi-stage (deps → build → runner) with Node 22 alpine, standalone output, non-root user
- [X] T002 Add `output: "standalone"` to `frontend/next.config.ts`
- [X] T003 Create root `docker-compose.yml` with 8 services: db (pgvector:pg16), redis (7-alpine), keycloak (24.0), meilisearch (v1), backend, migration-api, celery-worker, frontend; shared network, health checks, env var substitution
- [X] T004 Create root `.env.example` documenting all env vars with defaults
- [X] T005 Create `scripts/seed.sh`: populate sample source + 5 elements via backend API
- [ ] T006 Verify `docker compose up -d` starts all services healthy (SC-001)
- [ ] T007 Verify `http://localhost:3000` loads frontend (SC-002)
- [ ] T008 Verify `http://localhost:8002/api/v1/sources` returns JSON (SC-003)
- [ ] T009 Verify `docker compose down -v` cleans up (SC-004)
- [X] T010 Commit and push
