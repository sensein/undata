# Tasks: Migration UI

**Feature**: `013-migration-ui` | **Branch**: `013-migration-ui`

---

- [X] T001 Add migration-api rewrite to `frontend/next.config.ts` (`/api/migration/**` → port 8004)
- [X] T002 Add migration types to `frontend/lib/types.ts` (PathwaySummary, PathwayDetail, PathwayStep, MigrationJob, SchemaDiffResult)
- [X] T003 Create `frontend/lib/api/migration.ts`: migrationFetch helper + getPathways, getPathway, executeMigration, getJobStatus, getSchemaDiff
- [X] T004 Create `frontend/components/PathwayCard.tsx`: source→target names, step count badge, link to detail
- [X] T005 Create `frontend/components/MigrationJobStatus.tsx`: polling job tracker with progress bar, error/output display
- [X] T006 Create `frontend/components/SchemaDiff.tsx`: added/removed/modified field highlighting
- [X] T007 Create `frontend/components/PathwayList.tsx`: react-query driven pathway list
- [X] T008 Create `frontend/components/PathwayDetail.tsx`: steps table, JSON input textarea, run button, job status
- [X] T009 Create `frontend/components/SchemaDiffPage.tsx`: UUID inputs + compare button + diff display
- [X] T010 Create `/migrations` page with PathwayList
- [X] T011 Create `/migrations/[id]` page with PathwayDetail
- [X] T012 Create `/migrations/diff` page with SchemaDiffPage (Suspense-wrapped)
- [X] T013 Add "Migrations" nav link to layout.tsx
- [X] T014 Write PathwayCard unit test (5 tests: names, step count, singular, link, date)
- [X] T015 Write SchemaDiff unit test (6 tests: names, added, removed, modified, identical, a11y labels)
- [X] T016 Fix lint errors (React compiler purity rules in MigrationJobStatus)
- [X] T017 Verify: lint clean, 44/44 vitest, build passes (10 routes)
- [X] T018 Commit and push
