# Data Model: Robust Ingestion Pipeline v2

## New Entities

### ParquetEntityStore (internal — not a DB table)

Container for bulk entity storage. One file per entity type per source.

| Field | Type | Description |
|-------|------|-------------|
| sha256 | string | Content hash (primary key) |
| file_name | string | Human-readable name |
| entity_type | string | element, schema, value, valueset |
| source | string | Source name (bids, nda, openneuro/ds000228) |
| semantic | string (JSON) | Serialized semantic identity dict |
| provenance | string (JSON) | Serialized provenance list |
| ontology_annotations | string (JSON) | Serialized annotation list |
| created_at | string (ISO 8601) | Creation timestamp |

### BatchRunSummary (extends RunSummary)

Summary for multi-dataset batch runs.

| Field | Type | Description |
|-------|------|-------------|
| datasets_attempted | integer | Total datasets/structures in batch |
| datasets_successful | integer | Successfully processed |
| datasets_failed | integer | Failed to clone/fetch |
| datasets_skipped | integer | No metadata found |
| per_dataset | list[dict] | Per-dataset entity counts and timing |

## Modified Entities

### ClassifiedEntity (add alias_hints)

| New Field | Type | Description |
|-----------|------|-------------|
| alias_hints | list[string] | Pre-verified alias references (e.g., "nda:structure1") |

### SemanticIdentity (range fields — already exist, audit for population)

| Field | Status | Description |
|-------|--------|-------------|
| response_options | Exists | List of ResponseOption dicts |
| min_value | Exists | Minimum value constraint |
| max_value | Exists | Maximum value constraint |
| pattern | Exists | Regex constraint |
| type_ref | Exists | URI of referenced Schema |

No new fields — these already exist in the model. The task is ensuring all adapters populate them.

## Relationships

- ParquetEntityStore → replaces directory of YAML files in FileBackend
- BatchRunSummary → extends RunSummary with batch-specific fields
- alias_hints → consumed by alignment step for high-confidence grouping
- response_options → links to ValueSet entities (via member sha256 matching)
- type_ref → links to Schema entities (via sha256)
