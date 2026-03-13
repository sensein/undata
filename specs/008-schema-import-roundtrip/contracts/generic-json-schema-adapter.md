# Contract: GenericJSONSchemaAdapter

**Module**: `undata.adapters.json_schema`
**Class**: `GenericJSONSchemaAdapter`
**Implements**: `SchemaAdapter` protocol (see `adapters/base.py`)

## Interface

```python
class GenericJSONSchemaAdapter:
    source_name: str = "generic-json"
    source_format: str = "json"

    def load_file(self, path_or_url: str) -> None: ...
    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]: ...
    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]: ...
    def get_version_info(self) -> dict: ...
```

## Preconditions

- `load_file()` MUST be called before `extract_elements()` or `extract_classes()`.

## Postconditions / Invariants

### `load_file(path_or_url: str)`
- If `path_or_url == ""`: raises `ValueError`.
- If file does not exist: raises `FileNotFoundError`.
- If file is valid JSON: stores parsed schema; logs INFO with property count.
- If file is invalid JSON: raises `json.JSONDecodeError`.

### `extract_elements(mode="file") -> list[NormalizedElement]`
- Returns empty list if schema has no `properties` (no error).
- Each element has `source_name="generic-json"` and `extraction_path="file"`.
- Each `source_local_id` format: `"<title>.<field_name>"` (title = schema `title` or `"Root"`).
- For `$defs`/`definitions` entries with `properties`: additional elements with
  `source_local_id = "<def_name>.<field_name>"`.
- For fields with `$ref` to `#/$defs/<name>`: `data_type` derived from the referenced entry's
  `type` if present, otherwise `"object"`.
- Circular `$ref` (`depth >= 5`, i.e., max 4 recursive resolutions): element included with
  `data_type="object"`, WARN logged with message `"Circular $ref detected at depth {depth}"`.
- `allowed_values` populated from `enum` if present.
- `required` set from schema-level `required` array.

### `extract_classes(mode="file") -> list[SchemaClassPayload]`
- Returns one `SchemaClassPayload` for the root schema (using `title` or `"Root"`).
- Returns one additional `SchemaClassPayload` per `$defs`/`definitions` entry with properties.
- `schema_format="json"`, `extraction_path="file"`.

### `get_version_info() -> dict`
- Returns `{"version_tag": "local", "content_hash": "<sha256-hex>"}`.
- `content_hash` is SHA-256 of the raw file bytes.

## Error Catalog

| Condition | Exception | Message pattern |
|---|---|---|
| Empty path | `ValueError` | `"path_or_url is required"` |
| File not found | `FileNotFoundError` | (propagated from `open()`) |
| Invalid JSON | `json.JSONDecodeError` | (propagated from `json.load()`) |
| Circular $ref (`depth >= 5`) | WARN log only | `"Circular $ref detected at depth {n}"` — returns `"object"` |
