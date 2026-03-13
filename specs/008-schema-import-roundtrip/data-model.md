# Data Model: Generic Schema Import with Roundtrip Fidelity

**Branch**: `008-schema-import-roundtrip` | **Date**: 2026-03-11

## Entities

### Existing (unchanged)

**`NormalizedElement`** (`ingestion/src/undata/models.py`)
- `name: str`
- `data_type: str` — `"string"` | `"number"` | `"boolean"` | `"object"` | `"array"`
- `description: str`
- `required: bool`
- `multivalued: bool`
- `allowed_values: list[str] | None`
- `constraints: dict`
- `source_local_id: str` — unique within a source (format: `"<ClassName>.<field>"`)
- `source_name: str` — `"generic-json"` (new) or `"linkml"` (new)
- `extraction_path: str` — `"file"` for both new adapters
- `raw_metadata: dict` — original property dict from source schema

**`SchemaClassPayload`** (`ingestion/src/undata/models.py`)
- `class_name: str`
- `description: str`
- `element_source_local_ids: list[str]`
- `parent_class_name: str | None`
- `extraction_path: str` — `"file"` for both new adapters
- `schema_format: str | None` — `"json"` for GenericJSONSchemaAdapter; `"yaml"` for LinkMLAdapter

### New

**`RoundtripResult`** (`ingestion/src/undata/roundtrip.py`)
- `fidelity_score: float` — 0.0 (total loss) to 1.0 (perfect fidelity)
- `missing_classes: list[str]` — class names present in import but absent after re-import
- `missing_elements: list[str]` — element names present in import but absent after re-import
- `warnings: list[str]` — non-fatal issues (cycle detection, type coercion loss)

## Source Name Registry (extended)

| `source_name` | Adapter | Format |
|---|---|---|
| `"BIDS"` | BIDSAdapter | yaml |
| `"DANDI"` | DANDIAdapter | json / code |
| `"NWB"` | NWBAdapter | yaml / code |
| `"openMINDS"` | OpenMINDSAdapter | json-ld |
| `"aind"` | AINDAdapter | json-schema |
| `"generic-json"` | **GenericJSONSchemaAdapter** ← NEW | json |
| `"linkml"` | **LinkMLAdapter** ← NEW | yaml |

## Relationships

```
GenericJSONSchemaAdapter
  .load_file(path) → stores self._schema: dict
  .extract_elements() → list[NormalizedElement(source_name="generic-json")]
  .extract_classes()  → list[SchemaClassPayload(schema_format="json")]

LinkMLAdapter
  .load_file(path) → stores self._linkml_schema: SchemaDefinition
  .extract_elements() → list[NormalizedElement(source_name="linkml")]
  .extract_classes()  → list[SchemaClassPayload(schema_format="yaml")]

roundtrip_json_schema(path)
  → GenericJSONSchemaAdapter.extract_elements/classes
  → build SchemaDefinition (linkml_runtime)
  → yaml_dumper.dumps()
  → LinkMLAdapter.extract_elements/classes (from tempfile)
  → compare → RoundtripResult

roundtrip_linkml(path)
  → LinkMLAdapter.extract_elements/classes
  → yaml_dumper.dumps()
  → LinkMLAdapter.extract_elements/classes (from tempfile)
  → compare → RoundtripResult
```

## Type Mapping Tables

### JSON Schema `type` → `NormalizedElement.data_type`

| JSON Schema type | data_type | multivalued |
|---|---|---|
| `"string"` | `"string"` | false |
| `"integer"` | `"number"` | false |
| `"number"` | `"number"` | false |
| `"boolean"` | `"boolean"` | false |
| `"object"` | `"object"` | false |
| `"array"` | `"array"` | true |
| `null` / absent | `"string"` | false |
| `["string", "null"]` | `"string"` | false (null stripped) |

### LinkML `range` → `NormalizedElement.data_type`

| LinkML range | data_type |
|---|---|
| `"string"` / `"str"` / None | `"string"` |
| `"integer"` / `"int"` / `"float"` / `"double"` | `"number"` |
| `"boolean"` / `"bool"` | `"boolean"` |
| `"Any"` / `"anyuri"` / `"uriorcurie"` | `"object"` |
| any other class name | `"object"` |
| (slot.multivalued = True) | `"array"` (overrides range-based type) |
