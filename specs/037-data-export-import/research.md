# Research: Data Export, Import & Download Portal

## R1: Current Export/Import Coverage

| Entity Type | Export | Import (API) | Import (DB) | Gap |
|-------------|--------|--------------|-------------|-----|
| Elements | Yes | Yes | Yes | None |
| Schemas | Yes | Yes | Yes | None |
| Values | Yes | Yes | Yes | None |
| ValueSets | No | No | Yes | Export + API import missing |
| Transforms | No | No | Yes | Export + API import missing |
| Curation Flags | No | No | Yes | Export missing |
| Run Summaries | No | No | Yes | Export missing |
| Embeddings | No | No | No | Not exported/imported at all |
| Ontology Sources | No | No | No | New entity — no export/import |

**Decision**: Extend both export.py and import_lib.py to cover all entity types. Use the backend's import_service.py as the reference for the complete registry format. Add embedding export as parquet alongside YAML entities.

## R2: Export Format

**Decision**: Use the existing registry directory structure (matches pipeline output and seed data format) plus an embeddings parquet and a manifest JSON:

```
undata-registry-v2026.03.31/
├── manifest.json           # version, timestamp, entity counts, format version, checksum
├── elements/               # one YAML per element
├── schemas/                # one YAML per schema
├── values/                 # one YAML per value
├── valuesets/              # one YAML per valueset
├── transforms/             # one YAML per transform
├── curation-flags/         # one YAML per flag
├── runs/                   # one YAML per run summary
├── ontology-sources.yaml   # list of registered ontology sources
└── embeddings.parquet      # all entity embeddings (sha256, vector)
```

**Rationale**: This format is already consumed by `import_service.py` for seed data. Adding manifest and embeddings makes it self-describing and complete.

## R3: Round-Trip Test Strategy

**Decision**: The round-trip test will:
1. Use the running Docker stack (or a test database)
2. Export via the new `export-full` CLI command
3. Clear the database via SQL truncate (not Docker volume removal — too slow for CI)
4. Import via `import_service.py` (direct DB, not API — faster)
5. Compare entity counts and sample field checksums

**Rationale**: Docker volume removal + rebuild takes minutes. SQL truncate + reimport takes seconds.

## R4: Nightly Export Scheduling

**Decision**: Use a background asyncio task (same pattern as discovery_service) that runs daily, exports to a configured directory, compresses, and updates a releases.json file that the download page reads.

**Rationale**: No external scheduler (cron) needed. The backend already runs background tasks.

## R5: Download Page

**Decision**: A simple frontend page that reads `releases.json` from a known URL and lists available downloads. Files served directly from the export directory via a static file endpoint on the backend.

**Rationale**: No CDN needed at current scale (~2300 entities, <100MB compressed).
