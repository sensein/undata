# Data Model: Dual-Path Schema Adapters (006)

**Date**: 2026-03-10

---

## Updated Entities

### ExtractionMode

```python
from typing import Literal
ExtractionMode = Literal["code", "file", "both"]
```

| Value | Meaning |
|-------|---------|
| `"code"` | Use library introspection only (default for backward compatibility) |
| `"file"` | Use schema file parsing only; requires `source_path` |
| `"both"` | Run both paths; merge + deduplicate by `source_local_id` |

---

### NormalizedElement (unchanged)

No changes. The `extraction_path` concept belongs to `SchemaClassPayload`, not `NormalizedElement`.
(NormalizedElement describes a data field; SchemaClassPayload describes a class/group grouping.)

---

### SchemaClassPayload (updated)

```python
@dataclass
class SchemaClassPayload:
    """Class/category grouping extracted from a schema adapter.

    extraction_path: which extraction path produced this class
      "code"   — library introspection (dandischema, bidsschematools, hdmf, etc.)
      "file"   — schema file parsing (JSON/YAML/JSON-LD)
      "both"   — present in both paths (after merge, deduplicated)

    schema_format: the specific format used (informational, for debugging)
      "json"   — JSON Schema (DANDI file-path, AIND)
      "yaml"   — YAML GroupSpec (NWB) or BIDS YAML objects
      "jsonld" — JSON-LD / .schema.omi.json (openMINDS)
      "code"   — Python library introspection (all adapters code-path)
    """
    class_name: str
    description: str
    element_source_local_ids: list[str] = field(default_factory=list)
    parent_class_name: str | None = None
    extraction_path: str = "file"     # NEW default: "file" (was "json")
    schema_format: str | None = None  # NEW: informational format tag
```

**Migration impact**: Backend stores `extraction_path` as informational; no schema change required.
Existing test fixtures that assert `extraction_path="yaml"` etc. will need updating to `"file"`.

---

### AdapterResult (new — pipeline wrapper, NOT adapter return type)

```python
@dataclass
class AdapterResult:
    """Pipeline-level wrapper combining adapter outputs with conflict metadata.

    NOT returned directly by extract_elements() or extract_classes() — those methods
    return list[NormalizedElement] and list[SchemaClassPayload] respectively, matching
    the Protocol contract. AdapterResult is constructed by IngestionPipeline or caller
    code that runs both paths and needs a single envelope with conflict information.
    """
    elements: list[NormalizedElement]
    classes: list[SchemaClassPayload]
    mode_used: str              # "code" | "file" | "both"
    conflicts: list[dict]       # entries with source_local_id + conflict_type + detail
```

`conflicts` entry structure:
```python
{
    "source_local_id": str,
    "conflict_type": "type_mismatch",   # only type_mismatch in v1
    "code_data_type": str,
    "file_data_type": str,
    "code_element_id": str,             # disambiguated SLID: original + ".code"
    "file_element_id": str,             # disambiguated SLID: original + ".file"
}
```

---

## Updated SchemaAdapter Protocol

```python
from typing import Protocol, runtime_checkable, Literal

ExtractionMode = Literal["code", "file", "both"]


@runtime_checkable
class SchemaAdapter(Protocol):
    source_name: str
    source_format: str

    # --- Legacy compatibility shim (deprecated, calls load_file) ---
    def load(self, path_or_url: str) -> None:
        """Deprecated: use load_code() or load_file() instead."""
        ...

    # --- Dual-path loading ---
    def load_code(self) -> None:
        """Load schema via Python library introspection.
        Raises ImportError if the required library is not installed.
        """
        ...

    def load_file(self, path_or_url: str) -> None:
        """Load schema from a local directory/file path or URL.
        Raises ValueError if path_or_url is empty and no default exists.
        """
        ...

    # --- Extraction (mode-dispatched) ---
    def extract_elements(self, mode: ExtractionMode = "code") -> list[NormalizedElement]:
        """Return all normalized data elements from the loaded schema.
        mode='both' merges code-path and file-path results.
        """
        ...

    def extract_classes(self, mode: ExtractionMode = "code") -> list[SchemaClassPayload]:
        """Return class/category groupings extracted from the loaded schema.
        mode='both' merges code-path and file-path results.
        """
        ...

    def get_version_info(self) -> dict:
        """Return version_tag and content_hash for SchemaSource registration."""
        ...
```

---

## Merge Algorithm (mode="both")

```
Input:
  code_elements: list[NormalizedElement]   # from load_code() + extract_elements()
  file_elements: list[NormalizedElement]   # from load_file() + extract_elements()
  merge_strategy: Literal["code", "file"] = "code"   # winner on conflict

Algorithm:
  code_map = {el.source_local_id: el for el in code_elements if el.source_local_id}
  file_map = {el.source_local_id: el for el in file_elements if el.source_local_id}
  all_ids = code_map.keys() | file_map.keys()

  merged = []
  conflicts = []
  for slid in all_ids:
    in_code = slid in code_map
    in_file = slid in file_map
    if in_code and in_file:
      code_el = code_map[slid]
      file_el = file_map[slid]
      if code_el.data_type != file_el.data_type:
        # Type conflict → ERROR log, emit both with suffixed IDs
        conflicts.append({"source_local_id": slid, "conflict_type": "type_mismatch", ...})
        code_copy = replace(code_el, source_local_id=slid + ".code")
        file_copy = replace(file_el, source_local_id=slid + ".file")
        merged.extend([code_copy, file_copy])
      else:
        # Compatible → emit winner, tag extraction_path="both"
        winner = code_el if merge_strategy == "code" else file_el
        merged.append(replace(winner, extraction_path="both"))
    elif in_code:
      WARN log: "Element {slid} only in code path"
      merged.append(code_el)          # extraction_path remains "code"
    else:
      WARN log: "Element {slid} only in file path"
      merged.append(file_el)          # extraction_path remains "file"

Output:
  merged: list[NormalizedElement]   (extraction_path per element)
  conflicts: list[dict]
```

Same algorithm applies to `extract_classes(mode="both")`, keying on `SchemaClassPayload.class_name`.

---

## State Transitions

```
Adapter state machine:

  Initial
    │
    ├─→ load_code() called → state: LOADED_CODE
    ├─→ load_file(path) called → state: LOADED_FILE
    └─→ load(path) called → alias for load_file(path) → state: LOADED_FILE

  LOADED_CODE
    ├─→ extract_elements("code") → returns code elements
    ├─→ extract_elements("file") → ERROR: not loaded
    └─→ extract_elements("both") → requires also calling load_file()

  LOADED_FILE
    ├─→ extract_elements("file") → returns file elements
    ├─→ extract_elements("code") → ERROR: not loaded
    └─→ extract_elements("both") → requires also calling load_code()

  LOADED_BOTH (after load_code() + load_file())
    ├─→ extract_elements("code") → code elements only
    ├─→ extract_elements("file") → file elements only
    └─→ extract_elements("both") → merged + deduplicated
```

**Simplification**: For v1, `extract_elements("both")` will call `load_code()` + `load_file()`
internally if only one path has been loaded, rather than requiring explicit prior calls. The
`source_path` attribute must be set before calling `extract_elements("both")`.

---

## Per-Adapter Schema Format Map

| Adapter | Code-path library | File-path format | `schema_format` (code) | `schema_format` (file) |
|---------|-------------------|-----------------|------------------------|------------------------|
| BIDS | bidsschematools | YAML objects dir | `"code"` | `"yaml"` |
| DANDI | dandischema | JSON Schema 2020-12 | `"code"` | `"json"` |
| NWB | hdmf + pynwb | YAML GroupSpec | `"code"` | `"yaml"` |
| openMINDS | openminds-python | .schema.omi.json | `"code"` | `"jsonld"` |
| AIND | aind-data-schema (3.12 only) | JSON Schema | `"code"` | `"json"` |
