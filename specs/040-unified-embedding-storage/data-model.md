# Data Model: Unified Embedding & Storage

## Modified Entity Schema (Parquet)

All entities stored in Parquet with this unified schema:

| Column | Type | Description |
|--------|------|-------------|
| sha256 | string | Content-addressed hash (identity) |
| file_name | string | Human-readable name |
| source | string | Source name (bids, nda, openneuro/ds000228) |
| semantic | string (JSON) | Serialized semantic identity dict |
| provenance | string (JSON) | Serialized provenance list |
| ontology_annotations | string (JSON) | Serialized annotation list |
| embedding | string (JSON) | 384-dim float vector, JSON-serialized |
| created_at | string (ISO 8601) | Creation timestamp |

## Embedding Text Construction

The embedding vector is computed from a comprehensive text representation:

```
{provenance_class} {provenance_name}: {description}
type={data_type} unit={unit} pattern={pattern}
range={min_value}–{max_value}
annotations: {ann_label_1} ({ann_relation}), {ann_label_2} ({ann_relation})
sources: {source_1}, {source_2}
```

Fields used (in priority order):
1. **provenance.name** — the element's name from its source
2. **semantic.description** or **provenance.description** — what it means
3. **semantic.data_type** — what type of data
4. **semantic.unit** — unit of measurement
5. **ontology_annotations[].term_label** — ontology concepts it maps to
6. **provenance[].source** — where it comes from

## Store Interface

```
EntityStore(base_dir: Path)
  # Core CRUD
  read(entity_type, sha256) → dict | None
  write(entity_type, entity, identifier?) → str
  write_batch(entity_type, entities, source) → int
  list(entity_type, source?, **filters) → Iterator[dict]
  count(entity_type, source?) → int
  exists(entity_type, sha256) → bool
  find_by_hash(entity_type, prefix) → dict | None

  # Bulk access
  dataframe(entity_type, source?) → pa.Table

  # Index
  build_index(entity_type) → Path
```

## Removed Components

- `FileEntityStore` — replaced by ParquetStore
- `write_staged_entity` — replaced by write_batch
- `iter_staged` YAML path — replaced by ParquetStore.list
- `yaml_to_parquet` — no longer needed (never YAML)
- `safe_load_yaml` in entity pipeline paths — no YAML to load
