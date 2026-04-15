# Implementation Plan: Migration UI

**Branch**: `013-migration-ui` | **Date**: 2026-03-15 | **Spec**: spec.md

## Summary

Extend the Next.js frontend with 3 new routes (`/migrations`, `/migrations/[id]`,
`/migrations/diff`) to expose the 004-migration-api. Pathway browsing, async job
execution with polling, and schema diff visualization.

## Technical Context

**Stack**: TypeScript, Next.js 15.x, @tanstack/react-query (existing frontend)
**Backend**: 004-migration-api on port 8004
**New deps**: None (reuses existing frontend dependencies)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity | ✅ | 3 new pages + 3 components; extends existing frontend |
| II. TDD | ✅ | Vitest component tests + Playwright E2E |
| III. API-First | ✅ | Consumes documented migration-api REST endpoints |

## Project Structure (new files)

```text
frontend/
├── app/migrations/
│   ├── page.tsx              # Pathway list
│   ├── [id]/page.tsx         # Pathway detail + run migration
│   └── diff/page.tsx         # Schema diff view
├── components/
│   ├── PathwayCard.tsx       # Pathway summary card
│   ├── MigrationJobStatus.tsx # Polling job tracker
│   └── SchemaDiff.tsx        # Field-level diff view
├── lib/api/
│   └── migrations.ts         # Extended: pathways, jobs, diff endpoints
└── tests/
    ├── unit/
    │   ├── PathwayCard.test.tsx
    │   └── SchemaDiff.test.tsx
    └── e2e/
        └── migrations.spec.ts
```

## API Integration

| Frontend Call | Migration-API Endpoint | Method |
|--------------|----------------------|--------|
| List pathways | `/api/v1/pathways` | GET |
| Pathway detail | `/api/v1/pathways/{id}` | GET |
| Execute migration | `/api/v1/migrations/execute` | POST |
| Job status | `/api/v1/migrations/jobs/{id}` | GET |
| Schema diff | `/api/v1/schemas/diff?a={id}&b={id}` | GET |

Frontend proxy will route `/api/migration/**` → `http://localhost:8004/api/**`.
