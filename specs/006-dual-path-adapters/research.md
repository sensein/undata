# Research: Dual-Path Schema Adapters (006)

**Phase**: 0 — Resolve unknowns before design
**Date**: 2026-03-10

---

## 1. Current Adapter State

| Adapter | Current `load()` path | `extraction_path` in `extract_classes()` |
|---------|----------------------|------------------------------------------|
| BIDS | bidsschematools (code) or raw YAML fallback | `"yaml"` |
| DANDI | dandischema Pydantic introspection | `"code"` |
| NWB | raw YAML file (file-based only) | `"yaml"` |
| openMINDS | raw JSON-LD file (file-based only) | `"jsonld"` |
| AIND | pre-exported JSON Schema files | `"json"` |

**Key insight**: The current design conflates the format (yaml/json/jsonld) with the path (code/file).
The new design separates them: `extraction_path` becomes `"code"`, `"file"`, or `"both"` per FR-003,
while format details are retained in `raw_metadata` or `version_info`.

---

## 2. Per-Adapter Research Findings

### 2.1 DANDI

**Code path** (existing):
```python
import dandischema.models as dm
import inspect, pydantic

models = [cls for _, cls in inspect.getmembers(dm, inspect.isclass)
          if issubclass(cls, pydantic.BaseModel) and cls is not pydantic.BaseModel]
# → Dandiset, PublishedDandiset, Asset, PublishedAsset + all referenced types
```
- Version: `dandischema.__version__`
- `publish_model_schemata(output_dir)` generates the JSON Schema releases from these Pydantic models

**File path** (new):
- Release URL: `https://raw.githubusercontent.com/dandi/schema/master/releases/{version}/dandiset.json`
- Format: JSON Schema draft 2020-12; `$defs` block with 40+ reusable types
- Entry files: `dandiset.json`, `asset.json`, `published-dandiset.json`, `published-asset.json`
- `context.json` is NOT a schema — it is the JSON-LD @context (skip it)
- No `$id` at the root; properties + `$defs` pattern only
- File-based releases ARE generated from the Pydantic models — structural equivalence expected

**Decision**: `DANDIAdapter.load_code()` = current `load()` implementation.
`DANDIAdapter.load_file(path_or_url)` = new JSON Schema parser reading `releases/` directory.
Version tag for file path = directory name (e.g., `"0.6.7"`).

---

### 2.2 BIDS

**Code path** (new):
```python
import bidsschematools.schema as bst
schema = bst.load_schema()          # loads bundled schema (no path needed)
fields = dict(schema.objects.metadata)
# schema.objects.entities, schema.rules, etc. also available
```
- `load_schema()` with no argument loads the bundled schema; with a path it loads from that directory
- Version: `bidsschematools.__version__`
- The current `BIDSAdapter.load("")` already does this — rename to `load_code()`

**File path** (existing — already implemented):
```python
import yaml
data = yaml.safe_load(open("objects/metadata.yaml"))
fields = data.get("objects", {}).get("metadata", {})
```
- BIDS schema YAML directory structure:
  ```
  bids-schema/src/schema/
  ├── objects/
  │   ├── metadata.yaml      ← primary metadata fields
  │   ├── entities.yaml      ← entity definitions
  │   ├── columns.yaml
  │   └── ...
  ├── rules/
  └── ...
  ```
- The current `BIDSAdapter.load(path)` already does raw YAML fallback

**Decision**: Split existing `load()` into `load_code()` (bidsschematools bundled) and
`load_file(path)` (raw YAML directory). Both already implemented; just expose as named methods.

---

### 2.3 NWB

**Code path** (new):
```python
from pynwb import get_type_map
type_map = get_type_map()
ns_catalog = type_map.namespace_catalog
ns = ns_catalog.get_namespace("core")
for type_name in ns.get_registered_types():
    spec = ns.get_spec(type_name)  # GroupSpec or DatasetSpec
    # spec.data_type_def, spec.data_type_inc, spec.doc, spec.attributes, spec.datasets
```
- hdmf uses `data_type_def`/`data_type_inc` in Python (= `neurodata_type_def`/`neurodata_type_inc` in YAML)
- `pynwb.get_type_map()` registers NWB core + hdmf-common namespaces at import time
- Version: via `pynwb.__version__` or `ns.get_namespace_version()`
- Note: env var `PYNWB_NO_CACHE_DIR=1` forces re-parse from YAML if needed

**File path** (existing):
- NWB namespace YAML entry: `core/nwb.namespace.yaml`
- Reads `groups` from each module YAML (e.g., `nwb.ecephys.yaml`)
- hdmf-common-schema is a git submodule; when fetching remote, must also fetch from `hdmf-dev/hdmf-common-schema`
- Current `NWBAdapter.load(path)` reads a single YAML file's `groups:` block — this is sufficient for file mode if pointed at a namespace YAML that aggregates all groups

**Decision**: `NWBAdapter.load_file(path)` = current `load(path)` with improvements to walk
the namespace YAML includes. `NWBAdapter.load_code()` = new pynwb/hdmf namespace introspection.

---

### 2.4 openMINDS

**Code path** (new):
```python
from openminds.registry import registry
for type_uri, cls in registry["types"]["latest"].items():
    # cls.__name__, cls.type_, cls.properties (list of Property objects)
    # Property: name, types, path (URI), required, multiple, min_items, max_items
```
- Registry has duplicate entries: "latest" and "v4" map to the same types — deduplicate by type URI
- `cls.type_` = `"https://openminds.om-i.org/types/TypeName"`
- Properties are `.path` URI-keyed; label from property name or URI last segment

**File path** (existing):
- openMINDS uses `.schema.omi.json` format — NOT standard JSON Schema, NOT JSON-LD
- Property keys are full URIs; internal fields prefixed with `_`
- Current `OpenMINDSAdapter.load(path)` reads a single `.schema.omi.json` file

**Decision**: `OpenMINDSAdapter.load_file(path)` = extend current `load()` to handle directory
of `.schema.omi.json` files (glob `*.schema.omi.json`) in addition to single file.
`OpenMINDSAdapter.load_code()` = new openminds-python registry introspection.

**Note on Turtle**: The spec (FR-008) mentions Turtle support. The openMINDS project itself
does not publish `.ttl` files in its main schema repo — they use `.schema.omi.json`. Turtle
support SHOULD be implemented as a separate file-path variant using `rdflib` (which is already
a project dependency) but is NOT required for core openMINDS file-path support.

---

### 2.5 AIND

**Code path** (new, gated on Python 3.12):
```python
# aind-data-schema uses pyo3-ffi Rust extension; Python 3.14 incompatible
import aind_data_schema.models as adm
import inspect, pydantic

models = [cls for _, cls in inspect.getmembers(adm, inspect.isclass)
          if issubclass(cls, pydantic.BaseModel) and cls is not pydantic.BaseModel]
```
- Pattern identical to DANDI adapter — same Pydantic model introspection
- MUST raise `ImportError` on Python 3.14 (no silent fallback)
- The pyproject.toml for `ingestion/` targets Python 3.12; the AIND code path is only accessible there

**File path** (existing):
- Pre-exported JSON Schema files in `tests/fixtures/aind/`
- Current `AINDAdapter.load(path)` reads the JSON Schema directory — becomes `load_file(path)`

**Decision**: `AINDAdapter.load_file(path)` = current `load(path)` implementation.
`AINDAdapter.load_code()` = new Pydantic introspection, raises `ImportError` if unavailable.

---

## 3. Merge & Deduplication (FR-015 to FR-017)

**Algorithm**: When `mode="both"`:
1. Run `load_code()` → `code_elements`
2. Run `load_file(path)` → `file_elements`
3. Build dict `{source_local_id: element}` for each path
4. Iterate union of all source_local_ids:
   - In both → set `extraction_path="both"`, emit once (code wins by default)
   - Code only → set `extraction_path="code"`, emit WARN log
   - File only → set `extraction_path="file"`, emit WARN log
   - Same SLID, different data_type → log ERROR, emit both with `.code`/`.file` suffix

**Winner configuration**: Default `"code"` wins; configurable via `merge_strategy` parameter.

---

## 4. ExtractionMode Design

**Decision**:
```python
ExtractionMode = Literal["code", "file", "both"]
```

- `"code"` — default for backward compatibility with DANDI adapter
- `"file"` — requires `source_path` argument (or adapter has well-known default)
- `"both"` — runs both paths, merges results

**CLI integration** (FR-018, FR-019):
```bash
undata ingest bids --extraction-mode file --source-path ./bids-schema/src/schema/
undata ingest dandi --extraction-mode both --source-path ./releases/0.6.7/
undata ingest nwb --extraction-mode code   # uses pynwb bundled namespace
```

---

## 5. SchemaClassPayload.extraction_path Update

**Current**: format-specific values ("json", "yaml", "jsonld", "code")
**New**: path-type values ("code", "file", "both")

**Migration**: Existing tests and backend store `extraction_path` as informational only
(no enforcement per spec assumption). The value change from "yaml"/"json"/"jsonld" to "file"
is backward-compatible in the backend but constitutes a breaking change in the ingestion API.

**Decision**: Update `SchemaClassPayload.extraction_path` default from `"json"` to `"file"`.
Keep the format information in a new optional `schema_format` field (`"json"`, `"yaml"`, `"jsonld"`, `"code"`).
This separates the two concerns cleanly.

---

## 6. Late-Arriving Research Corrections

### Python Version Compatibility (critical)

- `bidsschematools` v1.2.1 declares Python 3.9–3.13 only (3.14 not yet in classifiers)
- BUT: the ingestion package runs on Python 3.14 (`requires-python = ">=3.14"`), and
  existing BIDS adapter tests pass — so `bidsschematools` works on 3.14 in practice
  (it is a pure-Python package; classifiers lag behind Python pre-release cycles)
- `aind-data-schema` has a `pyo3-ffi` Rust C extension that genuinely fails to compile
  on Python 3.14 — this is a real incompatibility, not just a missing classifier

### AIND File-Path Source (canonical URLs)

The best stable file-path source for AIND schemas is the `/schemas/` directory
committed directly in the GitHub repo (NOT the private S3 bucket):
```
https://raw.githubusercontent.com/AllenNeuralDynamics/aind-data-schema/main/schemas/subject_schema.json
```
Pinnable to a tag/SHA. 9 schema files available:
`acquisition_schema.json`, `data_description_schema.json`, `instrument_schema.json`,
`metadata_schema.json`, `model_schema.json`, `procedures_schema.json`,
`processing_schema.json`, `quality_control_schema.json`, `subject_schema.json`

### AIND Code-Path Enumeration

Use `DataCoreModel.__subclasses__()` (recursive) rather than `inspect.getmembers`:
```python
from aind_data_schema.base import DataCoreModel

def _get_all_subclasses(cls):
    result = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_get_all_subclasses(sub))
    return result

models = _get_all_subclasses(DataCoreModel)
```
This is the same approach used by `aind_data_schema.utils.json_writer.SchemaWriter.get_schemas()`.

---

## 7. Alternatives Considered

| Question | Decision | Alternatives Rejected |
|----------|----------|-----------------------|
| Single `load()` with mode param vs explicit `load_code()`/`load_file()` | Explicit methods (FR-001) | Single `load(mode=...)` — less explicit, harder to Protocol-check |
| `extraction_path` = "code"/"file"/"both" vs format-specific | "code"/"file"/"both" + `schema_format` field | Keep format-only — loses mode information for "both" merge |
| Merge in adapter vs merge in pipeline | Adapter-level `extract_elements(mode="both")` | Pipeline merge — requires pipeline to know adapter internals |
| Turtle/RDF support scope | `rdflib` via separate `load_turtle()` method | Embedded in `load_file()` — too implicit; Turtle is rare and opt-in |
| AIND code path on Python 3.14 | Hard `ImportError`, no fallback | Silent fallback to file — obscures intent (spec says no silent fallback) |
