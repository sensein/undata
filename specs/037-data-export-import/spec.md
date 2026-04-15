# Feature Specification: Data Export, Import & Download Portal

**Feature Branch**: `037-data-export-import`
**Created**: 2026-03-31
**Status**: Draft
**Input**: Full database export/restore capability with LinkML + embedding formats, round-trip integrity testing, public download portal (nightly + versioned releases), and admin import functionality.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Full Database Export (Priority: P1)

As a system administrator, I need to export the entire registry (all elements, schemas, values, valuesets, transforms, curation flags, ontology annotations, and embeddings) to portable formats — so the data can be backed up, migrated, or shared with collaborators.

**Why this priority**: Without reliable export, the system is a single point of failure. Export is the foundation for backup, download portal, and import.

**Independent Test**: Run the export command → produces a directory with LinkML YAML files for all entities plus a binary embedding file → file count matches entity count in database.

**Acceptance Scenarios**:

1. **Given** a populated registry, **When** the export command runs, **Then** it produces a directory containing: one YAML file per entity (elements/, schemas/, values/, valuesets/, transforms/), curation flags, run summaries, ontology source metadata, and a binary embedding index file.
2. **Given** the export, **When** inspecting the YAML files, **Then** each file is valid LinkML-compatible YAML with semantic, provenance, ontology_annotations, and sha256 fields matching the database content.
3. **Given** the export, **When** the embedding file is loaded, **Then** it contains one vector per entity that had embeddings in the database, in a format optimized for fast loading (parquet or numpy).
4. **Given** the export, **When** a version tag is provided, **Then** the export directory is named with the version (e.g., `undata-registry-v2026.03.31/`) and includes a manifest file listing entity counts, export timestamp, and version.

---

### User Story 2 — Full Database Import & Restore (Priority: P1)

As a system administrator, I need to import an exported registry into a fresh database — restoring all entities, annotations, embeddings, and metadata — so the system can be rebuilt from scratch or migrated to a new environment.

**Why this priority**: Import completes the backup/restore cycle and enables deployment reproducibility.

**Independent Test**: Export the database → clear all Docker volumes → import the export → verify entity counts match and sample entities are identical.

**Acceptance Scenarios**:

1. **Given** an export directory, **When** the import command runs against an empty database, **Then** all entities are created with correct sha256 hashes, provenance, annotations, and embeddings.
2. **Given** the import, **When** comparing entity counts before export and after import, **Then** the counts match exactly for all entity types.
3. **Given** the import, **When** querying a random sample of 10 elements via the API, **Then** each element's fields (data_type, unit, pattern, ontology_annotations, provenance) match the exported YAML content.
4. **Given** a populated database, **When** import runs with `--clear` flag, **Then** all existing data is deleted before import (full restore mode).

---

### User Story 3 — Round-Trip Integrity Test (Priority: P1)

As a developer, I need an automated test that exports the database, clears all state, imports the export, and verifies data integrity — so I can trust that the export/import cycle preserves all data without loss or corruption.

**Why this priority**: Without round-trip verification, export/import may silently lose data. This test must run in CI.

**Independent Test**: Run the round-trip test → it exports, clears DB, imports, compares → test passes with zero differences.

**Acceptance Scenarios**:

1. **Given** the round-trip test script, **When** executed, **Then** it: exports the database to a temp directory, records entity counts and sample checksums, clears the database, imports the export, re-queries entity counts and checksums, and asserts they match.
2. **Given** the round-trip test, **When** any entity field is lost during export/import, **Then** the test fails with a specific diff showing which field was lost.
3. **Given** the round-trip test, **When** embeddings are included in the export, **Then** the import restores them and the search functionality works identically before and after.

---

### User Story 4 — Public Download Portal (Priority: P2)

As a researcher, I need a download page on the website where I can access nightly snapshots and versioned releases of the registry data — so I can use the data offline, in my own tools, or cite a specific version in publications.

**Why this priority**: CivicDB provides TSV/CSV downloads for reproducibility. The registry must be equally accessible.

**Independent Test**: Visit the download page → see a list of available releases (nightly + versioned) → click a release → download starts as a compressed archive.

**Acceptance Scenarios**:

1. **Given** the download page, **When** a user visits it, **Then** they see: the latest nightly export (auto-generated), any versioned releases (manually tagged by admin), file sizes, entity counts, and download links.
2. **Given** a nightly export, **When** the scheduled job runs, **Then** it exports the database, compresses the directory, uploads it to the download location, and updates the download page metadata.
3. **Given** a versioned release, **When** an admin tags a release (e.g., "v2026.03"), **Then** the export is archived with the version tag and listed permanently on the download page.
4. **Given** the download page, **When** a user downloads an archive, **Then** it contains the full registry in LinkML YAML format plus a README with schema documentation and import instructions.

---

### User Story 5 — Admin Import via UI (Priority: P2)

As a curator or admin, I need to import a registry export through the web interface — uploading a compressed archive and triggering the import — so I can restore data without command-line access.

**Why this priority**: Not all curators have SSH access. A web-based import enables self-service restore.

**Independent Test**: Log in as admin → go to admin/import → upload a compressed export archive → import completes → entity counts displayed.

**Acceptance Scenarios**:

1. **Given** the admin import page, **When** an admin uploads a compressed archive (.tar.gz or .zip), **Then** the system extracts it, validates the structure, and shows a preview of entity counts before importing.
2. **Given** the import preview, **When** the admin clicks "Import", **Then** the system imports all entities with progress indication and reports success/failure with entity counts.
3. **Given** the import, **When** the `--clear` option is selected, **Then** existing data is deleted before import (with a confirmation dialog).
4. **Given** the import, **When** a non-admin user attempts import, **Then** the action is denied with an appropriate error message.

---

### Edge Cases

- What happens when the export is interrupted mid-way? Partial exports are marked as incomplete in the manifest; import refuses incomplete exports.
- What happens when importing into a non-empty database without `--clear`? Entities are merged using the existing upsert logic (sha256 match = merge provenance).
- What happens when the export format changes between versions? The manifest includes a format version number; import validates compatibility before proceeding.
- What happens when embeddings are missing from the export? Import succeeds without embeddings; search functionality is degraded until embeddings are recomputed.
- What happens when the compressed archive is corrupted? Import fails with a checksum validation error before any data is written.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support exporting the entire registry to a directory of LinkML-compatible YAML files (one file per entity) organized by entity type.
- **FR-002**: The export MUST include embeddings in an optimized binary format (parquet or numpy) alongside the YAML entity files.
- **FR-003**: The export MUST include a manifest file with: entity counts per type, export timestamp, format version, and sha256 checksum of the archive.
- **FR-004**: The system MUST support importing an export directory into an empty or populated database, restoring all entities, annotations, and embeddings.
- **FR-005**: The import MUST support a `--clear` mode that deletes all existing data before importing (full restore).
- **FR-006**: A round-trip integrity test MUST verify that export → clear → import produces an identical database (entity counts, field values, and sample checksums match).
- **FR-007**: The system MUST generate nightly export snapshots automatically (scheduled background task).
- **FR-008**: An admin MUST be able to tag a versioned release that is permanently archived on the download page.
- **FR-009**: A public download page MUST list available exports (nightly + versioned) with file sizes, entity counts, and direct download links.
- **FR-010**: The admin import page MUST allow uploading a compressed archive, previewing entity counts, and triggering import with optional `--clear` mode.
- **FR-011**: Import MUST validate the export structure and format version before writing any data; incompatible formats MUST be rejected.
- **FR-012**: Both export and import MUST be available as CLI commands AND via the web interface (admin-only for import).

### Key Entities

- **ExportManifest**: Metadata for an export — version, timestamp, entity counts, format version, checksum, export type (nightly/versioned/manual).
- **Release**: A versioned or nightly export available for download — version tag, export timestamp, file path/URL, file size, entity counts, download count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Export of the full registry (2000+ entities) completes in under 5 minutes.
- **SC-002**: Import of a full export into an empty database completes in under 10 minutes (including embedding restoration).
- **SC-003**: The round-trip integrity test passes with zero differences across all entity types.
- **SC-004**: The download page lists at least one nightly snapshot and any versioned releases within 24 hours of the first scheduled export.
- **SC-005**: A compressed export archive is smaller than 100MB for the current registry size (~2300 entities).
- **SC-006**: Admin import via UI supports archives up to 500MB.

## Scope Boundaries

### In Scope

- Full database export to LinkML YAML + embedding parquet
- Full database import with merge and clear modes
- Round-trip integrity test (export → clear → import → verify)
- Nightly scheduled export snapshots
- Versioned release tagging by admin
- Public download page with nightly + versioned releases
- Admin import via web UI with upload and preview
- CLI commands for export and import
- Manifest file with checksums and entity counts

### Out of Scope

- Incremental/differential export (only full exports)
- Real-time replication or streaming export
- Export to formats other than LinkML YAML (e.g., RDF, JSON-LD — future)
- Cross-registry federation or merge between two independent registries

## Assumptions

- The existing `import_service.py` handles entity upsert (merge by sha256) and can be reused for import
- The existing library `export.py` provides the base for the export command
- Nightly exports are stored on the same server as the application (local filesystem or mounted volume)
- The download page serves files directly from the export directory (no external CDN needed for current scale)
- Compressed archives use .tar.gz format for cross-platform compatibility

## Dependencies

- Feature 029 (Backend service) — provides GraphQL API and database models
- Feature 036 (Knowledge Service) — provides ontology source metadata and embedding infrastructure
- Feature 032 (Authentication) — provides admin role for import operations
