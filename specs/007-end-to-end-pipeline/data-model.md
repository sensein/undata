# Data Model: End-to-End Schema Ingestion and LinkML Export

**Feature**: `007-end-to-end-pipeline` | **Date**: 2026-03-11

This feature adds no new database tables (all storage is in the existing backend).
The data model describes the new internal types used in the ingestion package.

---

## New Internal Types

### NWBNamespaceManifest (ingestion, internal)

Used by `NWBAdapter.load_file()` to represent a parsed `*.namespace.yaml` file.

```python
@dataclass
class NWBNamespaceManifest:
    """Parsed NWB namespace manifest (*.namespace.yaml)."""
    namespace_name: str       # e.g. "core"
    version: str              # e.g. "2.10.0"
    doc_files: list[str]      # relative paths of domain YAML files to load
    base_dir: Path | None     # parent directory (None if loaded from URL)
    base_url: str | None      # base URL for remote files (None if local)
```

Fields from `nwb.namespace.yaml`:
```yaml
namespaces:
  - name: core
    version: 2.10.0
    doc: [..., {source: nwb.base.yaml}, {source: nwb.file.yaml}, ...]
```

### DynamicSchemaNode (ingestion/linkml_gen.py, internal)

Used by `LinkMLSchemaGenerator._fetch_dynamic_schemas()` to hold one backend
DynamicSchema record before converting it to a `ClassDefinition`.

```python
@dataclass
class DynamicSchemaNode:
    id: str                   # UUID as string
    name: str                 # Schema name (becomes LinkML class name)
    is_mixin: bool            # True → ClassDefinition(mixin=True)
    parent_id: str | None     # UUID → ClassDefinition(is_a=<parent_name>)
    mixin_ids: list[str]      # UUIDs in position order → ClassDefinition(mixins=[...])
    element_slids: list[str]  # source_local_ids for elements in this schema
```

### LinkMLExportContext (ingestion/linkml_gen.py, internal)

Holds the full set of `DynamicSchemaNode` records indexed for fast lookup during
class generation.

```python
@dataclass
class LinkMLExportContext:
    nodes: dict[str, DynamicSchemaNode]  # id → node
    by_name: dict[str, DynamicSchemaNode]  # name → node (for is_a resolution)
    mixin_slot_sets: dict[str, set[str]]   # schema_name → slot names from MRO
```

---

## Schema Hierarchy (conceptual)

The exported LinkML YAML will encode the following hierarchy after this feature:

```
NeuroscienceDataset (abstract base)
├── BIDSDataset    (is_a: NeuroscienceDataset)
├── DANDIDataset   (is_a: NeuroscienceDataset)
├── NWBFile        (is_a: NeuroscienceDataset)
│   └── NWBTimeSeries  (is_a: NWBFile, from SchemaClassInheritance)
├── openMINDSDataset (is_a: NeuroscienceDataset)
└── AINDDataset    (is_a: NeuroscienceDataset)

ProvenanceMixin    (mixin: true)

DynamicSchema-level classes (emitted for each DynamicSchema in backend):
├── <schema_name>  (is_a: <parent_name> if parent_id set)
│                  (mixins: [ProvenanceMixin, ...] if mixin attached)
│                  (mixin: true if is_mixin=True)
```

---

## Backend API Dependencies (read-only)

| Generator Need | Backend Endpoint | Response Field |
|----------------|-----------------|----------------|
| List DynamicSchemas | `GET /schemas?limit=500` | `items[].{id, name, is_mixin}` |
| Inheritance graph | `GET /schemas/{id}/inheritance-tree` | `nodes[], edges[]` |
| Resolved elements (for dedup) | `GET /schemas/{id}/resolved` | `elements[].name` |
| Find ProvenanceMixin | `GET /schemas?q=ProvenanceMixin` | `items[0].{id, name, is_mixin}` |
| Elements for slots | `GET /elements?limit=500&page=N` | `items[].{name, data_type, ...}` |

---

## NWB Schema YAML Format

The NWB HDMF YAML format (used by `load_file()`):

```yaml
# nwb.namespace.yaml (manifest format)
namespaces:
  - name: core
    version: 2.10.0
    doc:
      - source: nwb.base.yaml
      - source: nwb.file.yaml
      - source: nwb.ecephys.yaml
      # ...

# nwb.base.yaml (domain format)
groups:
  - neurodata_type_def: TimeSeries
    neurodata_type_inc: NWBDataInterface
    doc: "General purpose time series"
    attributes:
      - name: data
        dtype: numeric
        doc: "The data values"
      - name: timestamps
        dtype: float32
        doc: "Timestamps for samples"
    datasets:
      - name: data
        doc: "Data values"
```

Mapping to `NormalizedElement`:
- `neurodata_type_def` → `source_local_id` (class identity)
- `neurodata_type_inc` → `SchemaClassPayload.parent_class_name`
- Each `attribute` → `NormalizedElement` with name, data_type (from dtype), description (from doc)
- Each `dataset` → `NormalizedElement` with multivalued=True
