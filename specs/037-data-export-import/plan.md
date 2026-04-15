# Implementation Plan: Data Export, Import & Download Portal

**Branch**: `037-data-export-import` | **Date**: 2026-03-31 | **Spec**: [spec.md](spec.md)

## Summary

Complete export/import cycle: extend existing export to cover all entity types + embeddings, add manifest, round-trip integrity test, nightly scheduled exports, public download page, and admin import via UI.

## Technical Context

**Language/Version**: Python 3.14 (library + backend), TypeScript (frontend)
**Primary Dependencies**: PyYAML, pyarrow (parquet), tarfile (compression)
**Storage**: PostgreSQL 16, local filesystem for export archives
**Testing**: pytest (round-trip test), library unit tests
**Target Platform**: Web + CLI
**Project Type**: Full-stack
**Performance Goals**: Export <5 min, import <10 min, archive <100MB
**Scale/Scope**: ~2300 entities, ~5500 flags, ~8 transforms, ~3 runs

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Extends existing export.py and import_service.py; no new architecture |
| II. TDD | PASS | Round-trip integrity test is the core deliverable |
| III. API-First | PASS | GraphQL contracts + CLI commands + REST file endpoints |
| IV. Observability | PASS | Manifest tracks export metadata; download counts tracked |
| V. No Deprecation | PASS | Additive — extends existing commands |
| VI. Environment Isolation | PASS | No new dependencies beyond what's installed |
| VII. Developer Experience | PASS | CLI export/import + docker compose round-trip |
| VIII. Merge Before New Spec | PASS | 035+036 merged to main before this spec |

## Project Structure

```text
library/
├── src/undata_library/
│   ├── export.py             # Extend: add valuesets, transforms, flags, runs, embeddings, manifest
│   ├── import_lib.py         # Extend: add valuesets, transforms, flags, runs
│   └── cli.py                # Add: export-full, import-full, test-roundtrip commands

backend/
├── src/
│   ├── db/models.py          # Add: Release model
│   ├── graphql/
│   │   ├── types.py          # Add: Release, ExportResult types
│   │   ├── resolvers.py      # Add: releases, exportRegistry, tagRelease resolvers
│   │   └── schema.py         # Wire new queries/mutations
│   ├── services/
│   │   ├── export_service.py # NEW: full export with manifest + compression
│   │   └── nightly_export.py # NEW: background scheduled nightly export
│   └── main.py               # Add: static file serving for downloads, nightly task

frontend/
├── app/
│   ├── downloads/page.tsx    # NEW: public download page
│   └── admin/import/page.tsx # NEW: admin import upload page
├── components/
│   └── Sidebar.tsx           # Add: Downloads link
└── graphql/
    └── queries.ts            # Add: releases query
```

## Phases

### Phase 1: Full Export (US1)
- Extend export.py to fetch all entity types via GraphQL
- Add embedding export as parquet
- Add manifest.json generation
- Add compression (.tar.gz)
- CLI command: `export-full`

### Phase 2: Full Import (US2)
- Extend import to handle embeddings restoration
- Add `--clear` mode
- CLI command: `import-full`

### Phase 3: Round-Trip Test (US3)
- Automated test: export → truncate DB → import → compare counts + samples
- CLI command: `test-roundtrip`

### Phase 4: Download Portal (US4)
- Release DB model
- Nightly export background task
- Download page with release listing
- Static file serving for archives
- Admin release tagging

### Phase 5: Admin Import UI (US5)
- Upload endpoint (multipart form)
- Import preview (entity counts from manifest)
- Import trigger with progress
- Admin-only access control
