# Feature Specification: Migration UI

**Feature Branch**: `013-migration-ui`
**Created**: 2026-03-15
**Status**: Draft
**Input**: Expose the 004-migration-api endpoints in the 003-schema-explorer frontend.

---

## Overview

Add migration pathway visualization and execution UI to the Schema Explorer frontend.
Users can browse migration pathways, view schema diffs, trigger migrations, and track
async job progress — all from the browser.

---

## User Scenarios & Testing

### User Story 1 — Browse Migration Pathways (Priority: P1)

A data engineer wants to see all available migration pathways between schema versions.

**Acceptance Scenarios**:

1. **Given** pathways exist in the migration-api, **When** user visits `/migrations`,
   **Then** a list of pathways shows source schema, target schema, and step count.
2. **Given** a pathway, **When** user clicks it, **Then** a detail view shows each step
   with its transformation expression and function type.

### User Story 2 — Execute a Migration (Priority: P2)

A data engineer wants to run a migration on sample data to verify correctness.

**Acceptance Scenarios**:

1. **Given** a pathway detail page, **When** user clicks "Run Migration" and provides
   sample JSON input, **Then** the migration-api job is submitted and a job ID returned.
2. **Given** a running job, **When** user views the job status page, **Then** progress,
   status (pending/running/completed/failed), and result are shown.
3. **Given** a completed job, **When** user views results, **Then** the transformed output
   is displayed alongside the original input for comparison.

### User Story 3 — View Schema Diff (Priority: P2)

A data engineer wants to compare two schema versions to understand what changed.

**Acceptance Scenarios**:

1. **Given** two schema versions, **When** user navigates to `/migrations/diff?a={id}&b={id}`,
   **Then** added, removed, and modified fields are highlighted.

---

## Requirements

### Functional Requirements

- **FR-001**: `/migrations` page MUST list pathways from `GET /api/v1/pathways`.
- **FR-002**: `/migrations/[id]` MUST show pathway steps with transformation details.
- **FR-003**: "Run Migration" MUST submit to `POST /api/v1/migrations/execute` and poll status.
- **FR-004**: Job status MUST poll `GET /api/v1/migrations/jobs/{id}` every 2 seconds.
- **FR-005**: Schema diff MUST use `GET /api/v1/schemas/diff?a={id}&b={id}`.
- **FR-006**: All new pages MUST have stable, shareable URLs.

### Non-Functional Requirements

- **NFR-001**: Job polling MUST stop after 5 minutes (timeout).
- **NFR-002**: Migration UI MUST require authentication (contributor role).

### Key Entities

- `frontend/app/migrations/page.tsx` — pathway list
- `frontend/app/migrations/[id]/page.tsx` — pathway detail + run
- `frontend/app/migrations/diff/page.tsx` — schema diff
- `frontend/lib/api/migrations.ts` — extended API client
- `frontend/components/PathwayCard.tsx`, `MigrationJobStatus.tsx`, `SchemaDiff.tsx`

---

## Success Criteria

- **SC-001**: Pathway list renders from migration-api within 2 seconds.
- **SC-002**: Migration execution submits and shows live status updates.
- **SC-003**: Schema diff highlights added/removed/modified fields correctly.
