# Quickstart: Robust Ingestion Pipeline v2

## Test Scenarios

### 1. Parquet Storage (US1)

```bash
# Run pipeline for a small source — should use YAML (< threshold)
uv run undata-library pipeline --source bids -o /tmp/test-registry
ls /tmp/test-registry/elements/  # Individual YAML files

# Run pipeline for NDA (large) — should use Parquet
uv run undata-library pipeline --source nda --all -o /tmp/test-registry
ls /tmp/test-registry/elements/  # Should see nda.parquet, not millions of files

# Query individual entity from Parquet
uv run undata-library inspect /tmp/test-registry/elements/nda.parquet --sha256 abc123
```

### 2. Batch Pipeline (US2, US5)

```bash
# Batch OpenNeuro — 10 datasets through full pipeline
uv run undata-library pipeline --source openneuro --batch 10 -o /tmp/test-registry
# Should show progress: [1/10] ds007615... → 24 entities (3s)

# Full NDA through pipeline
uv run undata-library pipeline --source nda --all -o /tmp/test-registry
# Should show progress and final summary
```

### 3. NDA Aliases (US3)

```bash
# Check that shared NDA elements have alias_hints
uv run python -c "
import pyarrow.parquet as pq
df = pq.read_table('/tmp/test-registry/elements/nda.parquet').to_pandas()
import json
for _, row in df.head(5).iterrows():
    sem = json.loads(row['semantic'])
    if 'alias_hints' in sem:
        print(f'{row[\"file_name\"]}: {len(sem[\"alias_hints\"])} aliases')
"
```

### 4. Element Range Display (US4)

```bash
# Start the system
docker compose up -d

# Navigate to an element with response_options
# → Should see "Values: M, F" with links to ValueSet
# Navigate to an element with min/max
# → Should see "Range: 0–100"
# Navigate to an element with type_ref
# → Should see linked schema name
```

### 5. Enrichment at Scale (US6)

```bash
# Run enrichment on full registry
uv run undata-library enrich -o ~/.cache/undata/registry
# Should complete <30 min, peak memory <8GB
# Species matches should be species-level, not genus-level
```
