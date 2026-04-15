# Quickstart: 028 Storage Abstraction Validation

## QS-001: All existing tests pass unchanged
```bash
cd library && uv run pytest tests/ -v
# Expected: 343+ tests pass, 0 failures, 0 modifications to test files
```

## QS-002: FileBackend satisfies protocol
```python
from undata_library.storage import StorageBackend, FileBackend
fb = FileBackend(Path("/tmp/qs002"))
assert isinstance(fb, StorageBackend)  # structural subtyping check
```

## QS-003: Pipeline with explicit backend matches default
```bash
# Default (implicit file backend)
undata-library pipeline --source bids --output-dir /tmp/qs003a
# Explicit backend (same result)
# Internally: FileBackend("/tmp/qs003b") passed to pipeline functions
undata-library pipeline --source bids --output-dir /tmp/qs003b
diff -r /tmp/qs003a /tmp/qs003b
# Expected: no differences
```

## QS-004: Mock backend works with pipeline functions
```python
from undata_library.storage import MockBackend
mock = MockBackend()
# Call enrich_elements with mock — should not touch file system
stats = enrich_elements(staging=mock, ...)
assert mock.write_count > 0
assert not any(Path("/tmp").glob("*.yaml"))  # no files created
```

## QS-005: Adapter produces LinkML, extractor classifies
```python
from undata_library.adapters.bids import BIDSAdapter
adapter = BIDSAdapter()
schema_def = adapter.to_linkml(source_path)
# schema_def is a LinkML SchemaDefinition, not [ClassifiedEntity]
assert hasattr(schema_def, 'classes')
assert hasattr(schema_def, 'slots')
```

## QS-006: Pipeline order is extract→enrich→align→commit
```bash
undata-library pipeline --source bids --output-dir /tmp/qs006
# Verify align runs before commit in output:
# [1/5] Extracting...
# [2/5] Enriching...
# [3/5] Aligning...        ← before commit
# [4/5] Committing...
# [5/5] Generating transforms...
```

## QS-007: Cross-source annotation transfer before commit
```bash
undata-library pipeline --source openminds --output-dir /tmp/qs007
undata-library pipeline --source nwb --output-dir /tmp/qs007
# NWB entities should have annotations transferred from openMINDS
# during align step, before commit computes hashes
grep "ontology_annotations" /tmp/qs007/elements/*nwb* | head -3
# Expected: annotations present (transferred from openMINDS)
```

## QS-008: Entity counts within 5% of baseline
```bash
undata-library pipeline --source bids --output-dir /tmp/qs008
# Count committed entities
ls /tmp/qs008/elements/*.yaml | wc -l   # baseline: ~585
ls /tmp/qs008/schemas/*.yaml | wc -l    # baseline: ~214
ls /tmp/qs008/values/*.yaml | wc -l     # baseline: ~494
ls /tmp/qs008/valuesets/*.yaml | wc -l  # baseline: varies
```
