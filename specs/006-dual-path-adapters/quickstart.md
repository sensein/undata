# Quickstart: Dual-Path Adapter Validation (006)

**Date**: 2026-03-10
**Purpose**: Developer walkthrough to validate each adapter in each mode locally.

---

## Prerequisites

```bash
cd ingestion
uv sync          # installs bidsschematools, dandischema, hdmf, pynwb, openminds
uv run pytest tests/ -v   # should show 128+ tests PASS
```

---

## Scenario 1: File-path extraction (US1 — P1)

### 1a. DANDI — pinned release v0.6.7

```python
from undata.adapters.dandi import DANDIAdapter

adapter = DANDIAdapter()
adapter.load_file("./tests/fixtures/dandi/releases/0.6.7/")
elements = adapter.extract_elements("file")
classes = adapter.extract_classes("file")

print(f"Elements: {len(elements)}")
print(f"Classes: {len(classes)}")
assert all(c.extraction_path == "file" for c in classes)
assert all(c.schema_format == "json" for c in classes)
# Sample: "Dandiset.name", "Asset.path" etc
print([e.source_local_id for e in elements[:3]])
```

### 1b. BIDS — local schema checkout

```bash
# Clone bids-spec (or use a local copy)
# git clone https://github.com/bids-standard/bids-specification /tmp/bids-spec
```

```python
from undata.adapters.bids import BIDSAdapter

adapter = BIDSAdapter()
adapter.load_file("/tmp/bids-spec/src/schema/")
elements = adapter.extract_elements("file")
classes = adapter.extract_classes("file")

print(f"Elements: {len(elements)}")     # Should be ~100+ BIDS metadata fields
assert all(c.extraction_path == "file" for c in classes)
assert all(c.schema_format == "yaml" for c in classes)
```

### 1c. NWB — local nwb-schema

```python
from undata.adapters.nwb import NWBAdapter

adapter = NWBAdapter()
adapter.load_file("/tmp/nwb-schema/core/nwb.namespace.yaml")
elements = adapter.extract_elements("file")
classes = adapter.extract_classes("file")

print(f"Elements: {len(elements)}")
assert all(c.extraction_path == "file" for c in classes)
assert all(c.schema_format == "yaml" for c in classes)
```

### 1d. openMINDS — single file or directory

```python
from undata.adapters.openminds import OpenMINDSAdapter

# Single file (current behavior, promoted to load_file)
adapter = OpenMINDSAdapter()
adapter.load_file("./tests/fixtures/openminds/File.schema.omi.json")
elements = adapter.extract_elements("file")
assert len(elements) > 0
assert all(c.extraction_path == "file" for c in adapter.extract_classes("file"))

# Directory (new: glob *.schema.omi.json)
adapter2 = OpenMINDSAdapter()
adapter2.load_file("./tests/fixtures/openminds/")
elements2 = adapter2.extract_elements("file")
print(f"Directory elements: {len(elements2)}")
```

### 1e. AIND — custom directory

```python
from undata.adapters.aind import AINDAdapter

adapter = AINDAdapter()
adapter.load_file("./tests/fixtures/aind/")
elements = adapter.extract_elements("file")
assert len(elements) > 0
classes = adapter.extract_classes("file")
assert all(c.extraction_path == "file" for c in classes)
assert all(c.schema_format == "json" for c in classes)
```

---

## Scenario 2: Code-path extraction (US2 — P2)

### 2a. BIDS — bundled bidsschematools schema

```python
from undata.adapters.bids import BIDSAdapter

adapter = BIDSAdapter()
adapter.load_code()   # no path needed; uses bidsschematools bundled schema
elements = adapter.extract_elements("code")
classes = adapter.extract_classes("code")
print(f"BIDS code elements: {len(elements)}")
assert all(c.extraction_path == "code" for c in classes)
assert all(c.schema_format == "code" for c in classes)
```

### 2b. NWB — hdmf namespace registry

```python
from undata.adapters.nwb import NWBAdapter

adapter = NWBAdapter()
adapter.load_code()   # pynwb.get_type_map(); no file needed
elements = adapter.extract_elements("code")
classes = adapter.extract_classes("code")
print(f"NWB types: {len(classes)}")
assert all(c.extraction_path == "code" for c in classes)
```

### 2c. openMINDS — registry introspection

```python
from undata.adapters.openminds import OpenMINDSAdapter

adapter = OpenMINDSAdapter()
adapter.load_code()   # openminds.registry["types"]["latest"]
elements = adapter.extract_elements("code")
print(f"openMINDS types (code): {len(adapter.extract_classes('code'))}")
# Should be ~200+ types
```

### 2d. AIND — Pydantic introspection (Python 3.12 only)

```python
# Run in Python 3.12 environment only
from undata.adapters.aind import AINDAdapter
import sys

adapter = AINDAdapter()
if sys.version_info >= (3, 14):
    import pytest
    with pytest.raises(ImportError, match="aind.data.schema"):
        adapter.load_code()
else:
    adapter.load_code()
    elements = adapter.extract_elements("code")
    print(f"AIND code elements: {len(elements)}")
```

### 2e. DANDI — existing Pydantic path (renamed to load_code)

```python
from undata.adapters.dandi import DANDIAdapter

adapter = DANDIAdapter()
adapter.load_code()   # was load(""); introspects dandischema.models
elements = adapter.extract_elements("code")
print(f"DANDI code elements: {len(elements)}")
assert all(c.extraction_path == "code" for c in adapter.extract_classes("code"))
```

---

## Scenario 3: Dual-path merge (US3 — P3)

### 3a. DANDI — both modes

```python
from undata.adapters.dandi import DANDIAdapter

adapter = DANDIAdapter()
adapter.load_code()
adapter.load_file("./tests/fixtures/dandi/releases/0.6.7/")

elements = adapter.extract_elements("both")
classes = adapter.extract_classes("both")

# Count by extraction_path
code_only = [e for e in elements if e.extraction_path == "code"]
file_only = [e for e in elements if e.extraction_path == "file"]
both = [e for e in elements if e.extraction_path == "both"]

print(f"Total: {len(elements)}")
print(f"  code-only: {len(code_only)}")
print(f"  file-only: {len(file_only)}")
print(f"  both: {len(both)}")

# SC-003: ≥ 95% overlap
overlap = len(both) / (len(both) + len(code_only) + len(file_only))
assert overlap >= 0.95, f"Overlap too low: {overlap:.1%}"
```

### 3b. Conflict detection

```python
# If there are any type conflicts, they appear as .code / .file suffixed SLIDs
conflict_ids = [e.source_local_id for e in elements
                if e.source_local_id.endswith(".code") or e.source_local_id.endswith(".file")]
print(f"Conflicts: {len(conflict_ids) // 2}")
# Should be 0 for stable releases
```

### 3c. BIDS — both modes (requires local clone)

```python
from undata.adapters.bids import BIDSAdapter

adapter = BIDSAdapter()
adapter.load_code()
adapter.load_file("/tmp/bids-spec/src/schema/")
elements = adapter.extract_elements("both")

overlap = len([e for e in elements if e.extraction_path == "both"]) / len(elements)
print(f"BIDS code↔file overlap: {overlap:.1%}")
assert overlap >= 0.95
```

---

## Scenario 4: CLI validation (FR-018/FR-019)

```bash
# File mode with source path
undata ingest dandi --extraction-mode file \
  --source-path ./tests/fixtures/dandi/releases/0.6.7/ \
  --dry-run

# Code mode (default)
undata ingest bids --extraction-mode code --dry-run

# Both mode
undata ingest dandi --extraction-mode both \
  --source-path ./tests/fixtures/dandi/releases/0.6.7/ \
  --dry-run

# Error: file mode without source path (adapter has no default)
undata ingest dandi --extraction-mode file  # should exit 2 with error
```

---

## Validation Checklist

- [ ] BIDSAdapter.load_code() returns > 50 elements without local files
- [ ] BIDSAdapter.load_file(path) returns elements with `extraction_path="file"`, `schema_format="yaml"`
- [ ] DANDIAdapter.load_file() returns elements from DANDI 0.6.7 JSON Schema release
- [ ] NWBAdapter.load_code() enumerates NWB types from hdmf registry without YAML files
- [ ] OpenMINDSAdapter.load_code() enumerates > 100 openMINDS types from registry
- [ ] AINDAdapter.load_code() raises ImportError on Python 3.14
- [ ] All adapters satisfy `isinstance(adapter, SchemaAdapter)` (Protocol conformance)
- [ ] extract_elements("both") on DANDI returns ≥ 95% overlap (SC-003)
- [ ] Type conflicts produce .code/.file suffixed IDs (no silent conflicts — SC-004)
- [ ] `undata ingest dandi --extraction-mode file --source-path <path> --dry-run` exits 0
- [ ] All 68 existing ingestion tests still pass (SC-006)
