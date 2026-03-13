# Contract: SchemaAdapter Protocol v2 (006-dual-path-adapters)

**Version**: 2.0.0
**Date**: 2026-03-10
**Breaking from**: SchemaAdapter Protocol v1 (005-schema-enrichment)

---

## Overview

Every ingestion adapter MUST conform to the `SchemaAdapter` Protocol defined in
`ingestion/src/undata/adapters/base.py`. This document specifies the v2 contract
including the dual-path `load_code()` / `load_file()` extension.

---

## Protocol Interface

```python
from typing import Protocol, Literal, runtime_checkable
from undata.models import NormalizedElement, SchemaClassPayload

ExtractionMode = Literal["code", "file", "both"]


@runtime_checkable
class SchemaAdapter(Protocol):
    # Required class-level attributes
    source_name: str          # Display name: "BIDS", "DANDI", "NWB", "openMINDS", "aind"
    source_format: str        # Storage format: "yaml", "json", "json-ld", "json-schema"

    def load(self, path_or_url: str) -> None:
        """Deprecated compatibility shim. Delegates to load_file(path_or_url).
        Will be removed in Protocol v3.
        """
        ...

    def load_code(self) -> None:
        """Load schema via Python library introspection.

        Post-condition: adapter is ready to call extract_elements("code").
        Raises:
            ImportError: if the required library is not installed.
                         Message MUST name the missing package.
        """
        ...

    def load_file(self, path_or_url: str) -> None:
        """Load schema from a local path (file or directory) or remote URL.

        Post-condition: adapter is ready to call extract_elements("file").
        Raises:
            ValueError: if path_or_url is empty and the adapter has no well-known default.
        """
        ...

    def extract_elements(self, mode: ExtractionMode = "code") -> list[NormalizedElement]:
        """Return normalized data elements from the loaded schema.

        mode="code": uses data loaded by load_code()
        mode="file": uses data loaded by load_file()
        mode="both": merges both; requires both load_code() and load_file() to have been called
                     (or calls them internally if source_path is set)

        Returns:
            list[NormalizedElement] with extraction_path field set to mode value
            (or "code"/"file" for single-path elements in "both" mode)

        Raises:
            RuntimeError: if the required load method has not been called for the mode.
        """
        ...

    def extract_classes(self, mode: ExtractionMode = "code") -> list[SchemaClassPayload]:
        """Return class/category groupings from the loaded schema.

        Same mode semantics as extract_elements().

        Returns:
            list[SchemaClassPayload] with extraction_path: "code" | "file" | "both"
            and schema_format: "code" | "json" | "yaml" | "jsonld"
        """
        ...

    def get_version_info(self) -> dict:
        """Return version and content hash for SchemaSource registration.

        Returns:
            {
                "version_tag": str,     # e.g., "0.6.7", "1.8.2", "local"
                "content_hash": str,    # SHA-256 hex digest of schema content
            }
        """
        ...
```

---

## Per-Adapter Conformance Requirements

### BIDSAdapter

| Method | Implementation |
|--------|---------------|
| `load_code()` | Calls `bidsschematools.schema.load_schema()` (no path); raises `ImportError` if unavailable |
| `load_file(path)` | Reads `{path}/objects/metadata.yaml` (or `{path}` if file); falls back to raw YAML if bidsschematools unavailable |
| `extract_elements(mode)` | Dispatches to code or file fields; "both" merges |
| `extract_classes(mode)` | Groups fields by name prefix; `schema_format="code"` or `"yaml"` |

### DANDIAdapter

| Method | Implementation |
|--------|---------------|
| `load_code()` | Introspects `dandischema.models` via `inspect.getmembers`; raises `ImportError` if unavailable |
| `load_file(path)` | Reads JSON Schema `$defs` from `releases/{ver}/*.json` files in directory; raises `ValueError` if path empty |
| `extract_elements(mode)` | Dispatches to Pydantic model fields or JSON Schema properties |
| `extract_classes(mode)` | One class per Pydantic model / JSON Schema root; `schema_format="code"` or `"json"` |

### NWBAdapter

| Method | Implementation |
|--------|---------------|
| `load_code()` | Calls `pynwb.get_type_map()` and enumerates namespace registry types; raises `ImportError` if unavailable |
| `load_file(path)` | Reads NWB namespace YAML; traverses `includes:` to load sub-files; raises `ValueError` if path empty |
| `extract_elements(mode)` | Dispatches to hdmf spec attrs/datasets or YAML parsed groups |
| `extract_classes(mode)` | One class per neurodata_type; `schema_format="code"` or `"yaml"` |

### OpenMINDSAdapter

| Method | Implementation |
|--------|---------------|
| `load_code()` | Iterates `openminds.registry.registry["types"]["latest"]`; deduplicates vs "v4"; raises `ImportError` if unavailable |
| `load_file(path)` | Reads single `.schema.omi.json` file OR globs `*.schema.omi.json` in directory |
| `load_turtle(path)` | (Optional, not in Protocol) Reads `.ttl` via `rdflib`; populates same internal state as `load_file()` |
| `extract_elements(mode)` | Dispatches to openminds Property objects or JSON-LD properties |
| `extract_classes(mode)` | One class per type; `schema_format="code"` or `"jsonld"` |

### AINDAdapter

| Method | Implementation |
|--------|---------------|
| `load_code()` | Introspects `aind_data_schema.models` Pydantic models; raises `ImportError` immediately on Python 3.14+ |
| `load_file(path)` | Reads JSON Schema files from directory; uses bundled fixtures if path empty |
| `extract_elements(mode)` | Dispatches to Pydantic model fields or pre-exported JSON Schema properties |
| `extract_classes(mode)` | One class per schema file / Pydantic model; `schema_format="code"` or `"json"` |

---

## Error Contract

| Situation | Exception | Message requirement |
|-----------|-----------|---------------------|
| `load_code()` called but library missing | `ImportError` | MUST name the package: `"dandischema is required..."` |
| `load_file("")` called with no path and no default | `ValueError` | MUST describe required path format |
| `extract_elements("file")` before `load_file()` | `RuntimeError` | MUST name the missing prior call |
| `extract_elements("code")` before `load_code()` | `RuntimeError` | MUST name the missing prior call |
| Type conflict in "both" mode | No exception; `ERROR` log + disambiguated IDs | `"Type conflict for {slid}: code={type1} file={type2}"` |
| Element in code-only or file-only | No exception; `WARN` log | `"Element {slid} only in {path} path"` |

---

## CLI Contract

```
undata ingest <source> [options]

Options:
  --extraction-mode [code|file|both]   Default: "code"
  --source-path PATH                   Required when --extraction-mode=file or both
  --backend-url URL
  --token TOKEN
  --version-tag TAG
  --dry-run
  --output-format [text|json]
```

**Validation rules**:
- If `--extraction-mode file` and `--source-path` not given AND adapter has no well-known default → exit 2 with error message
- If `--extraction-mode code` → `--source-path` ignored (warning emitted if provided)
- If `--extraction-mode both` → `--source-path` used for file path; code path must be importable

---

## Breaking Changes from Protocol v1

| Change | Impact |
|--------|--------|
| `SchemaClassPayload.extraction_path` semantics: format-specific ("yaml"/"json"/"jsonld") → path-type ("code"/"file"/"both") | Tests asserting format-specific values must update; backend accepts both |
| New required methods: `load_code()`, `load_file()`, updated `extract_elements(mode)`, `extract_classes(mode)` | All adapters must implement |
| New optional field `SchemaClassPayload.schema_format` | Backward-compatible (optional, None default) |

---

## Test Scenarios

### T-PROTO-01: BIDSAdapter.load_code() returns elements without local files

```python
# Given: bidsschematools installed; no local path provided
adapter = BIDSAdapter()
adapter.load_code()
elements = adapter.extract_elements("code")
assert len(elements) > 0
assert all(el.source_name == "BIDS" for el in elements)
classes = adapter.extract_classes("code")
assert all(c.extraction_path == "code" for c in classes)
assert all(c.schema_format == "code" for c in classes)
```

### T-PROTO-02: DANDIAdapter.load_file() parses release directory

```python
# Given: a directory of DANDI JSON Schema release files
adapter = DANDIAdapter()
adapter.load_file("./tests/fixtures/dandi/releases/0.6.7/")
elements = adapter.extract_elements("file")
assert len(elements) > 0
assert all(c.extraction_path == "file" for c in adapter.extract_classes("file"))
assert all(c.schema_format == "json" for c in adapter.extract_classes("file"))
```

### T-PROTO-03: load_code() raises ImportError when library missing

```python
# Given: library is not installed (monkeypatched)
import builtins, unittest.mock as mock
original_import = builtins.__import__
def no_dandischema(name, *args, **kwargs):
    if "dandischema" in name:
        raise ImportError(f"No module named '{name}'")
    return original_import(name, *args, **kwargs)

with mock.patch("builtins.__import__", side_effect=no_dandischema):
    adapter = DANDIAdapter()
    with pytest.raises(ImportError, match="dandischema"):
        adapter.load_code()
```

### T-PROTO-04: extract_elements("both") merges and deduplicates

```python
# Given: both code and file paths loaded with overlapping elements
adapter = DANDIAdapter()
adapter.load_code()
adapter.load_file("./tests/fixtures/dandi/releases/0.6.7/")
elements = adapter.extract_elements("both")
slids = [el.source_local_id for el in elements]
# No duplicates (unless type conflict → disambiguated with .code/.file suffix)
assert len(slids) == len(set(slids)) or all(
    (s.endswith(".code") or s.endswith(".file"))
    for s in slids if slids.count(s) > 1
)
```

### T-PROTO-05: Type conflict produces disambiguated IDs + ERROR log

```python
# Given: same SLID with different data_type in code vs file (fixture-based)
# Then: both preserved with .code/.file suffix; ERROR logged
```

### T-PROTO-06: Protocol conformance — all adapters implement SchemaAdapter v2

```python
from undata.adapters.base import SchemaAdapter
from undata.adapters.bids import BIDSAdapter
from undata.adapters.dandi import DANDIAdapter
# ... etc
for cls in [BIDSAdapter, DANDIAdapter, NWBAdapter, OpenMINDSAdapter, AINDAdapter]:
    assert isinstance(cls(), SchemaAdapter)
```
