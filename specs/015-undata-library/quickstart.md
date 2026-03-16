# Quickstart Validation: undata-library v2

## Scenario 1: Content Hash Determinism
```bash
# Same semantic graph → same hash every time
uv run python -c "
from undata_library.hashing import compute_semantic_hash
h1 = compute_semantic_hash({'data_type': 'integer', 'unit': 'year', 'ontology_term': 'NCIT:C124353'})
h2 = compute_semantic_hash({'ontology_term': 'NCIT:C124353', 'data_type': 'integer', 'unit': 'year'})
assert h1 == h2, 'Hash must be deterministic regardless of key order'
print(f'PASS: {h1.short_key}')
"
```

## Scenario 2: Validate Element File
```bash
uv run undata-library validate elements/age_x7k2m9.yaml
# Expected: OK elements/age_x7k2m9.yaml
```

## Scenario 3: Compute Hash
```bash
uv run undata-library hash elements/age_x7k2m9.yaml
# Expected: attribute=age key=x7k2m9 sha256=a1b2c3... uri=https://schema.undata.live/elements/age_x7k2m9
```

## Scenario 4: Ingest from Raw Schemas
```bash
uv run undata-library ingest --source bids --path ../ingestion/schemas/
# Expected: Ingested N elements, M schemas. K merged with existing.
```

## Scenario 5: Cross-Source Dedup
```bash
# After ingesting bids + nwb + dandi:
grep -l "source: bids" elements/*.yaml | head -5
# Elements with multiple provenance entries = cross-source matches
uv run python -c "
import yaml
from pathlib import Path
multi = 0
for f in Path('elements').glob('*.yaml'):
    d = yaml.safe_load(f.read_text())
    if len(d.get('provenance', [])) > 1:
        multi += 1
print(f'{multi} elements have multiple provenance entries (cross-source)')
"
```

## Scenario 6: Index Reflects Dedup
```bash
uv run undata-library index
head -5 index.yaml
# element_count should be < 9629 (deduplicated)
```
