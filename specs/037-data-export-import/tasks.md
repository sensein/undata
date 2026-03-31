# Tasks: Data Export, Import & Download Portal

**Input**: Design documents from `/specs/037-data-export-import/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Release DB model, shared export format utilities

- [ ] T001 Add Release DB model to backend/src/db/models.py — version, release_type, file_path, file_size, entity_counts, download_count, created_at
- [ ] T002 Add Release Strawberry GraphQL type and ExportResult type in backend/src/graphql/types.py
- [ ] T003 Create export directory config — EXPORT_DIR env var defaulting to /app/exports, ensure directory exists in backend/src/main.py

**Checkpoint**: DB model exists, export directory configured

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Manifest generation and archive utilities shared by export and import

- [ ] T004 Create manifest utility — generate_manifest(output_dir, version, entity_counts) → writes manifest.json with version, format_version, timestamp, entity_counts, source_system in library/src/undata_library/manifest.py
- [ ] T005 Create archive utility — compress_directory(source_dir) → .tar.gz, compute_checksum(archive_path) → sha256 in library/src/undata_library/archive.py
- [ ] T006 Create validate_manifest(manifest_path) → check format_version compatibility, entity_counts present in library/src/undata_library/manifest.py

**Checkpoint**: Can generate manifests and compress/decompress archives

---

## Phase 3: User Story 1 — Full Database Export (Priority: P1) 🎯 MVP

**Goal**: Export all entity types + embeddings + manifest to portable directory

**Independent Test**: `uv run undata-library export-full --output /tmp/export` produces directory with YAML files for all 7 entity types + manifest.json + embeddings.parquet

- [ ] T007 [US1] Extend export.py to fetch valuesets via GraphQL browseValuesets query in library/src/undata_library/export.py
- [ ] T008 [US1] Extend export.py to fetch transforms via GraphQL browseTransforms query in library/src/undata_library/export.py
- [ ] T009 [US1] Extend export.py to fetch curation flags via GraphQL curationQueue query (all statuses) in library/src/undata_library/export.py
- [ ] T010 [US1] Extend export.py to fetch run summaries via GraphQL runSummaries query in library/src/undata_library/export.py
- [ ] T011 [US1] Add embedding export — query all entities with embeddings, save as parquet (sha256, entity_type, vector) in library/src/undata_library/export.py
- [ ] T012 [US1] Add manifest generation and optional compression to export flow in library/src/undata_library/export.py
- [ ] T013 [US1] Add `export-full` CLI command — --output, --version, --compress flags in library/src/undata_library/cli.py
- [ ] T014 [US1] Add backend export_service.py — export via DatabaseBackend (direct DB, not API) for server-side export in backend/src/services/export_service.py
- [ ] T015 [US1] Add exportRegistry GraphQL mutation in backend/src/graphql/schema.py wired to export_service
- [ ] T016 [US1] Add unit test: export produces correct directory structure with all entity types in library/tests/test_export_full.py

**Checkpoint**: Full export produces all 7 entity types + embeddings + manifest

---

## Phase 4: User Story 2 — Full Database Import & Restore (Priority: P1)

**Goal**: Import export into empty or populated database with clear mode

**Independent Test**: Import an export directory → entity counts match exported counts

- [ ] T017 [US2] Extend import_service.py to restore embeddings from parquet during import in backend/src/services/import_service.py
- [ ] T018 [US2] Add `--clear` mode to import_service — truncate all entity tables before import in backend/src/services/import_service.py
- [ ] T019 [US2] Extend import_lib.py to handle all entity types (valuesets, transforms via API) in library/src/undata_library/import_lib.py
- [ ] T020 [US2] Add `import-full` CLI command — --path, --clear, --backend-url flags in library/src/undata_library/cli.py
- [ ] T021 [US2] Add unit test: import from export directory restores correct entity counts in library/tests/test_import_full.py

**Checkpoint**: Import restores all entity types with correct counts; clear mode works

---

## Phase 5: User Story 3 — Round-Trip Integrity Test (Priority: P1)

**Goal**: Automated test verifying export → clear → import preserves all data

**Independent Test**: `uv run undata-library test-roundtrip` passes with zero differences

- [ ] T022 [US3] Implement round-trip test — export, record counts+sample checksums, truncate DB, import, re-query, compare in library/src/undata_library/roundtrip_test.py
- [ ] T023 [US3] Add `test-roundtrip` CLI command — --backend-url flag in library/src/undata_library/cli.py
- [ ] T024 [US3] Add pytest integration test that runs the round-trip (requires running backend) in backend/tests/test_roundtrip.py

**Checkpoint**: Round-trip test passes with zero entity count differences

---

## Phase 6: User Story 4 — Public Download Portal (Priority: P2)

**Goal**: Download page with nightly + versioned releases

**Independent Test**: Visit /downloads → see release list with download links

- [ ] T025 [US4] Add GraphQL resolvers for releases query and tagRelease mutation in backend/src/graphql/resolvers.py
- [ ] T026 [US4] Wire releases query and tagRelease mutation into GraphQL schema in backend/src/graphql/schema.py
- [ ] T027 [US4] Implement nightly_export.py background task — scheduled daily, exports, compresses, creates Release record in backend/src/services/nightly_export.py
- [ ] T028 [US4] Add static file serving for export archives at /api/downloads/{filename} in backend/src/main.py
- [ ] T029 [US4] Add releases GraphQL query in frontend/graphql/queries.ts
- [ ] T030 [US4] Create downloads page — list releases with version, type, size, entity counts, download link in frontend/app/downloads/page.tsx
- [ ] T031 [US4] Add "Downloads" link to sidebar in frontend/components/Sidebar.tsx

**Checkpoint**: Download page lists nightly + versioned releases with working download links

---

## Phase 7: User Story 5 — Admin Import via UI (Priority: P2)

**Goal**: Admin can upload and import a compressed archive via web interface

**Independent Test**: Upload .tar.gz via admin page → import completes with correct entity counts

- [ ] T032 [US5] Add POST /api/admin/import endpoint — accept multipart upload, extract, validate manifest, import in backend/src/main.py
- [ ] T033 [US5] Create admin import page — upload form, manifest preview, import button with clear checkbox, progress display in frontend/app/admin/import/page.tsx
- [ ] T034 [US5] Add admin import link to sidebar admin section in frontend/components/Sidebar.tsx

**Checkpoint**: Admin can upload archive and trigger import with entity count preview

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verification, cleanup

- [ ] T035 Run quickstart.md validation — verify export, import, round-trip, download page, admin import
- [ ] T036 [P] Verify nightly export produces archive in configured directory
- [ ] T037 [P] Verify download page renders releases correctly
- [ ] T038 Verify round-trip test passes in CI-compatible mode

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup
- **US1 Export (Phase 3)**: Depends on Foundational — MVP
- **US2 Import (Phase 4)**: Depends on US1 (needs export to test import)
- **US3 Round-Trip (Phase 5)**: Depends on US1 + US2
- **US4 Download Portal (Phase 6)**: Depends on US1 (needs export for releases)
- **US5 Admin Import (Phase 7)**: Depends on US2 (needs import working)
- **Polish (Phase 8)**: Depends on all stories

### Parallel Opportunities

- T007, T008, T009, T010 (US1 entity type exports) — all extend same file but different sections
- T025, T027 (US4 backend) can run in parallel
- T036, T037 (polish verification) — independent checks

---

## Implementation Strategy

### MVP First (US1)

1. Setup + Foundational → manifest + archive utilities
2. US1 → full export with all entity types
3. **STOP and VALIDATE**: export produces correct directory structure

### Incremental Delivery

1. Setup + Foundational → infrastructure
2. US1 → full export (MVP)
3. US2 → full import with clear mode
4. US3 → round-trip integrity test
5. US4 → download portal with nightly exports
6. US5 → admin import via UI
7. Polish → verification

---

## Notes

- Export via CLI uses GraphQL API (fetches from running backend)
- Export via backend service uses DatabaseBackend directly (faster, no API overhead)
- Import always uses import_service.py (direct DB writes) for speed
- Nightly exports overwrite previous nightly; versioned releases are permanent
- Archives use .tar.gz for cross-platform compatibility
