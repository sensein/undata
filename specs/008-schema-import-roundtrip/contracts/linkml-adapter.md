# Contract: LinkMLAdapter

**Module**: `undata.adapters.linkml_adapter`
**Class**: `LinkMLAdapter`
**Implements**: `SchemaAdapter` protocol

## Interface

```python
class LinkMLAdapter:
    source_name: str = "linkml"
    source_format: str = "yaml"

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
- If file does not exist: `FileNotFoundError` propagated from `yaml_loader`.
- Uses `linkml_runtime.loaders.yaml_loader.load(path, target_class=SchemaDefinition)`.
- Logs INFO with slot count and class count.

### `extract_elements(mode="file") -> list[NormalizedElement]`
- Returns one `NormalizedElement` per slot in `schema.slots`.
- `source_name="linkml"`, `extraction_path="file"`.
- `source_local_id = f"{schema.name}.{slot_name}"`.
- `data_type` derived from `slot.range` per the range mapping table in `data-model.md`.
- If `slot.multivalued is True`: `data_type="array"`.
- `required` from `slot.required` (default False if None).
- `description` from `slot.description` (empty string if None).
- Returns empty list if schema has no slots.

### `extract_classes(mode="file") -> list[SchemaClassPayload]`
- Returns one `SchemaClassPayload` per class in `schema.classes`.
- `schema_format="yaml"`, `extraction_path="file"`.
- `element_source_local_ids` = slots listed in `class_def.slots` (those present in
  `schema.slots`), formatted as `f"{schema.name}.{slot_name}"`.
- `parent_class_name = class_def.is_a` if set, else `None`.
- Returns empty list if schema has no classes.

### `get_version_info() -> dict`
- Returns `{"version_tag": schema.version or "local", "content_hash": "<sha256-hex>"}`.
- `content_hash` is SHA-256 of the raw YAML file bytes.

## Error Catalog

| Condition | Exception | Message pattern |
|---|---|---|
| Empty path | `ValueError` | `"path_or_url is required for LinkML loading"` |
| File not found | propagated | from `yaml_loader` |
| Invalid YAML | propagated | from `yaml_loader` |
