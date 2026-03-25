# Data Model: Library Storage Abstraction

## StorageBackend Protocol

```
StorageBackend
  ├── entities: EntityStore       # CRUD for elements, schemas, values, valuesets
  ├── flags: FlagStore            # Curation flag lifecycle
  └── runs: RunStore              # Pipeline run summaries
```

## EntityStore

Manages the four core entity types. Each entity is a dict with `semantic`, `provenance`, and `ontology_annotations` fields.

**Operations**:

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| read | entity_type, identifier | dict or None | Load single entity by hash or filename |
| write | entity_type, data, identifier? | identifier | Write entity, return its identifier |
| list | entity_type, filters? | iterator[dict] | List entities with optional filtering |
| exists | entity_type, identifier | bool | Check if entity exists |
| delete | entity_type, identifier | bool | Remove entity |
| merge_provenance | entity_type, identifier, provenance[] | dict | Append provenance to existing entity |
| count | entity_type, filters? | int | Count matching entities |
| find_by_hash | entity_type, short_key | dict or None | Lookup by content-addressed hash prefix |

**Entity types**: `elements`, `schemas`, `values`, `valuesets`

**Filters**: `source` (from provenance), `has_annotations` (bool), `data_type` (elements only)

## FlagStore

Manages curation flag lifecycle.

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| write_flag | CurationFlag | identifier | Create new flag |
| read_flags | status?, flag_type? | list[CurationFlag] | List flags with optional filtering |
| resolve_flag | flag_id, action, resolved_by, note? | CurationFlag or None | Update flag status |

## RunStore

Manages pipeline execution records.

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| save_summary | RunSummary | identifier | Save run record |
| load_previous | source | RunSummary or None | Load most recent run for source |
| list_runs | source?, limit? | list[RunSummary] | List run history |

## StagingArea

Wraps a StorageBackend for temporary entity storage during pipeline execution. Created per pipeline run, cleaned up after commit.

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| create | run_id | StagingArea | Initialize staging workspace |
| write_entity | entity_type, data | Path or identifier | Write with UUID identifier |
| cleanup | | None | Remove all staged entities |

## FileBackend

Implements StorageBackend using YAML files in a directory tree.

```
base_dir/
├── elements/         name_key.yaml (committed) or uuid.yaml (staging)
├── schemas/          name_key.yaml or uuid.yaml
├── values/           name_key.yaml or uuid.yaml
├── valuesets/        name_key.yaml or uuid.yaml
├── transforms/       src_to_tgt_key.yaml
├── curation-flags/   {uuid}.yaml
├── runs/             {timestamp}-{source}.yaml
└── .staging/{run_id}/
    ├── elements/     uuid.yaml
    ├── schemas/      uuid.yaml
    ├── values/       uuid.yaml
    └── valuesets/    uuid.yaml
```

## Entity Structure (unchanged)

All four entity types share:

```yaml
semantic:
  # type-specific fields (data_type, properties, label, members, etc.)
  ontology_annotations:
    - term_uri: str
      term_label: str
      ontology: str
      mapping_relation: str   # skos:exactMatch, closeMatch, etc.
      match_level: str
      score: float
      model: str
      primary: bool
provenance:
  - source: str
    class: str
    name: str
    description: str
    generated_at: str
    attributed_to: str
    activity: str
sha256: str                   # computed at commit time
```

## State Transitions

```
[New Entity]
  ↓ ingest_source()
[Staged] ── uuid filename, no sha256
  ↓ enrich_elements()
[Staged + Enriched] ── ontology_annotations added in-place
  ↓ align_elements()
[Staged + Aligned] ── cross-source annotations transferred
  ↓ commit_staged()
[Committed] ── content-addressed filename, sha256 set
  ↓ curator review
[Curated] ── all flags resolved, status: curated
```
