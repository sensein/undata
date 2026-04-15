# Data Model: Data Export, Import & Download Portal

## New Entities

### ExportManifest (JSON file, not DB table)

Included in every export archive as `manifest.json`.

| Field | Type | Description |
|-------|------|-------------|
| version | string | Version tag (e.g., "v2026.03.31" or "nightly-2026-03-31") |
| format_version | string | Export format version (e.g., "1.0") for compatibility checks |
| timestamp | string (ISO 8601) | When the export was created |
| entity_counts | object | {elements, schemas, values, valuesets, transforms, flags, runs} |
| has_embeddings | boolean | Whether embeddings.parquet is included |
| checksum | string | SHA-256 of the compressed archive |
| source_system | string | "undata" identifier |

### Release (DB table)

Tracks available downloads on the download page.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| version | string | Version tag (unique) |
| release_type | string | "nightly" or "versioned" |
| file_path | string | Path to the compressed archive on disk |
| file_size | bigint | Size in bytes |
| entity_counts | JSONB | {elements, schemas, values, valuesets, transforms, flags, runs} |
| download_count | integer | Number of times downloaded |
| created_at | timestamp | When the release was created |

## Relationships

- Release → export archive file (file_path)
- ExportManifest → entity counts (embedded in archive)
- Release.entity_counts mirrors ExportManifest.entity_counts

## State Transitions

- Nightly releases: auto-created by scheduled task, auto-expired after 30 days
- Versioned releases: manually tagged by admin, permanent
