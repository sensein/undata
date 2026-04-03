# Research: Unified Embedding & Storage

## R1: Eliminating YAML from the Pipeline

**Decision**: Replace all YAML file I/O in the pipeline with ParquetStore operations. The extraction stage writes directly to Parquet via `write_batch`. No individual YAML files are created.

**Rationale**: The current pipeline has three parallel paths (YAML files, Parquet files, iter_staged bridging both). This causes: slow I/O at scale, inconsistent state between formats, and complex code paths. A single format eliminates all of these.

**Key changes**:
1. `ingest_source` → collects entities in memory, calls `ParquetStore.write_batch` at the end
2. `enrich_all` → reads from ParquetStore, writes enriched entities back via `write_batch`
3. `commit_staged` → reads from ParquetStore, computes sha256, writes to registry ParquetStore
4. Cross-reference resolution → operates on in-memory DataFrames from Parquet

**What gets removed**: `write_staged_entity` (single YAML write), `safe_load_yaml` calls in pipeline, `yaml.dump` in commit, `iter_staged` YAML path, `yaml_to_parquet` conversion step.

## R2: Embedding Computation at Commit

**Decision**: Compute embeddings for ALL entity types during the commit step, after content-addressing but before writing to the registry. Store the embedding vector as a column in the entity Parquet file.

**Rationale**: Embeddings should reflect the final committed state (with sha256, resolved cross-references, and ontology annotations). Computing during commit ensures consistency — the embedding matches exactly what's stored.

**Embedding text construction** (comprehensive, not just name+description):
```
{class_name} {element_name}: {description}
type={data_type} unit={unit}
annotations: {annotation_label_1}, {annotation_label_2}
provenance: {source_1}/{class_1}, {source_2}/{class_2}
```

This ensures embeddings capture: what the entity is (name, description), what it measures (type, unit), how it's classified (ontology), and where it comes from (provenance).

## R3: Unified Store Interface

**Decision**: Consolidate `FileEntityStore`, `ParquetStore`, `iter_staged`, and direct YAML I/O into a single `EntityStore` class backed by ParquetStore.

**Interface**:
```
EntityStore(base_dir)
  read(entity_type, sha256) → dict | None
  write(entity_type, entity) → str
  write_batch(entity_type, entities, source) → int
  list(entity_type, source?, **filters) → Iterator[dict]
  count(entity_type, source?) → int
  exists(entity_type, sha256) → bool
  find_by_hash(entity_type, prefix) → dict | None
  update(entity_type, sha256, changes) → dict
  dataframe(entity_type, source?) → DataFrame  # New: direct access for cross-ref
```

**What gets removed**: `FileEntityStore` (YAML-backed), `iter_staged` function, `write_staged_entity` function, `safe_load_yaml` in entity paths.

**What remains**: `safe_load_yaml` for non-entity files (run summaries, config), YAML for human-readable seed data (optional debug export).

## R4: Backend Import Without Recomputation

**Decision**: The backend's `DatabaseBackend.write()` checks for `entity["embedding"]` before calling `compute_embedding()`. If present, uses it directly. The embedding service model is NOT loaded during import — only on demand for entities missing embeddings.

**Lazy model loading**: The `_get_model()` function in `embedding_service.py` already loads lazily. The fix is simply to check for pre-computed embeddings first. This was partially implemented in 039 but needs to be the enforced path.

## R5: Cross-Reference Resolution on Parquet

**Decision**: The `_resolve_cross_references` function currently reads/writes individual YAML files. Rewrite to:
1. Load all committed entities into DataFrames (one per type)
2. Build lookup dicts from DataFrames (name→sha256, label→sha256)
3. Apply resolutions in-memory
4. Write resolved DataFrames back to Parquet

**Performance**: For 7K entities, in-memory DataFrames are trivial (~50MB). For 1M+ entities, still feasible (~500MB).
