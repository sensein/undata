# CLI Interface Contract: Neuroscience Schema Integration
**Feature**: 001-neuro-schema-integration | **Date**: 2026-03-07

The integration pipeline exposes a CLI tool (`undata`) and a Python library API.

---

## CLI Commands

### `undata ingest`

Ingest one or more neuroscience schemas and push normalized elements to the backend.

```
undata ingest [OPTIONS] SOURCE [SOURCE ...]

Arguments:
  SOURCE    Schema source identifier: "bids", "dandi", "openminds", "nwb"
            or a custom "name:format:path_or_url" triple

Options:
  --backend-url TEXT   Backend API base URL [default: http://localhost:8002/api/v1]
  --token TEXT         Bearer token for backend auth (or UNDATA_TOKEN env var)
  --version-tag TEXT   Override version tag for the source
  --dry-run            Parse and normalize elements but do not write to backend
  --output-format      "text" (default) | "json"
  --log-level          "DEBUG"|"INFO"|"WARNING" [default: INFO]

Examples:
  undata ingest bids dandi
  undata ingest bids --dry-run
  undata ingest "custom:yaml:/data/my-schema.yaml"
```

Exit codes:
- `0`: All sources ingested successfully
- `1`: One or more sources had failures (partial success reported)
- `2`: Fatal error (backend unreachable, auth failure)

stdout (text mode):
```
Ingesting BIDS schema v1.9.0...
  ✓ 312 elements submitted, 312 succeeded, 0 failed
Ingesting DANDI schema v0.6.4...
  ✓ 87 elements submitted, 87 succeeded, 0 failed
Total: 399 elements ingested in 12.3s
```

stdout (json mode):
```json
{
  "results": [
    { "source": "BIDS", "succeeded": 312, "failed": 0, "duration_s": 8.1 },
    { "source": "DANDI", "succeeded": 87, "failed": 0, "duration_s": 4.2 }
  ],
  "total_succeeded": 399,
  "total_failed": 0
}
```

---

### `undata detect-aliases`

Run alias detection over the elements currently stored in the backend and register
identity mappings for detected alias pairs.

```
undata detect-aliases [OPTIONS]

Options:
  --backend-url TEXT          Backend API base URL
  --token TEXT                Bearer token
  --threshold FLOAT           Cosine similarity threshold [default: 0.92]
  --dry-run                   Report candidates without registering mappings
  --output-format             "text" | "json" | "sssom-tsv"
  --source-filter TEXT        Only compare elements from these sources (comma-separated)

Examples:
  undata detect-aliases --dry-run
  undata detect-aliases --threshold 0.88 --output-format sssom-tsv > aliases.tsv
```

stdout (text mode):
```
Detected alias pairs (threshold=0.92):
  EXACT  subject_age (BIDS) ↔ participant_age (DANDI)  [score=1.00, skos:exactMatch]
  CLOSE  recording_session (NWB) ↔ session_id (BIDS)   [score=0.91, skos:closeMatch]
Total: 42 exact matches, 17 close matches registered.
```

---

### `undata generate-schema`

Generate a unified LinkML YAML schema from the elements stored in the backend.

```
undata generate-schema [OPTIONS]

Options:
  --backend-url TEXT     Backend API base URL
  --output FILE          Output YAML file path [default: stdout]
  --schema-id TEXT       LinkML schema URI [default: https://undata.org/schema/neuroscience]
  --schema-name TEXT     LinkML schema name [default: NeuroscienceUnified]
  --version TEXT         Schema version (CalVer) [default: auto from date]
  --include-sources      Comma-separated list (bids,dandi,openminds,nwb); all if omitted
  --format               "yaml" (default) | "json-ld"

Examples:
  undata generate-schema --output unified.yaml
  undata generate-schema --include-sources bids,dandi --format json-ld
```

stdout: LinkML YAML document (or JSON-LD)
stderr: progress messages

---

### `undata validate`

Validate a data file against the unified LinkML schema.

```
undata validate [OPTIONS] DATA_FILE

Arguments:
  DATA_FILE   Path to JSON or YAML data file to validate

Options:
  --schema FILE       Path to LinkML schema YAML [default: fetch from backend]
  --target-class TEXT  LinkML class to validate against [default: NeuroscienceDataset]
  --output-format      "text" (default) | "json"

Examples:
  undata validate subject_metadata.json
  undata validate dataset.yaml --target-class BIDSDataset
```

Exit codes: `0` = PASS, `1` = FAIL (validation errors), `2` = tool error

---

## Python Library API

```python
from undata.adapters import BIDSAdapter, DANDIAdapter, OpenMINDSAdapter, NWBAdapter
from undata.ingestion import IngestionPipeline
from undata.linkml_gen import LinkMLSchemaGenerator
from undata.alias_detection import AliasDetector

# Ingest
pipeline = IngestionPipeline(backend_url="http://localhost:8002/api/v1", token="...")
result = await pipeline.ingest(BIDSAdapter(), path_or_url="/data/bids-schema")

# Alias detection
detector = AliasDetector(backend_url="...", token="...", threshold=0.92)
candidates = await detector.detect()

# LinkML generation
generator = LinkMLSchemaGenerator(backend_url="...", schema_id="...", version="2026.03.0")
schema = await generator.generate()
schema.to_yaml("unified.yaml")
```
