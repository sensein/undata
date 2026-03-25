# Contract: StorageBackend Protocol

## EntityStore

```python
class EntityStore(Protocol):
    def read(self, entity_type: str, identifier: str) -> dict | None: ...
    def write(self, entity_type: str, data: dict, identifier: str | None = None) -> str: ...
    def list(self, entity_type: str, **filters) -> Iterator[dict]: ...
    def exists(self, entity_type: str, identifier: str) -> bool: ...
    def delete(self, entity_type: str, identifier: str) -> bool: ...
    def merge_provenance(self, entity_type: str, identifier: str, provenance: list[dict]) -> dict: ...
    def count(self, entity_type: str, **filters) -> int: ...
    def find_by_hash(self, entity_type: str, short_key: str) -> dict | None: ...
```

**entity_type**: One of `"elements"`, `"schemas"`, `"values"`, `"valuesets"`

**identifier**: Backend-specific. FileBackend uses filename stem (e.g., `"age_a1b2c3"`). DatabaseBackend would use sha256 or UUID.

**filters**: Optional keyword args:
- `source: str` — filter by provenance source name
- `has_annotations: bool` — filter by presence of ontology_annotations
- `data_type: str` — filter by semantic.data_type (elements only)

## FlagStore

```python
class FlagStore(Protocol):
    def write_flag(self, flag: CurationFlag) -> str: ...
    def read_flags(self, status: str | None = None, flag_type: str | None = None) -> list[CurationFlag]: ...
    def resolve_flag(self, flag_id: str, action: str, resolved_by: str, note: str | None = None) -> CurationFlag | None: ...
```

## RunStore

```python
class RunStore(Protocol):
    def save_summary(self, summary: RunSummary) -> str: ...
    def load_previous(self, source: str) -> RunSummary | None: ...
    def list_runs(self, source: str | None = None, limit: int | None = None) -> list[RunSummary]: ...
```

## StorageBackend (Composite)

```python
class StorageBackend(Protocol):
    entities: EntityStore
    flags: FlagStore
    runs: RunStore
```

## Pipeline Function Signatures

```python
def ingest_source(source_name: str, schema_path: Path | None, staging: StorageBackend) -> dict[str, int]: ...
def enrich_elements(staging: StorageBackend, cache_dir: Path | None = None, ...) -> dict[str, int]: ...
def enrich_all(staging: StorageBackend, cache_dir: Path | None = None, ...) -> dict[str, dict]: ...
def align_elements(backend: StorageBackend, threshold: float = 0.5, ...) -> dict: ...
def cross_source_align(backend: StorageBackend) -> dict[str, int]: ...
def commit_staged(staging: StorageBackend, output: StorageBackend, ...) -> dict[str, int]: ...
def generate_transforms(backend: StorageBackend, threshold: float = 0.5) -> dict[str, int]: ...
```

## FileBackend Constructor

```python
class FileBackend:
    def __init__(self, base_dir: Path) -> None: ...
    # Implements StorageBackend via EntityStore + FlagStore + RunStore
    # backed by YAML files in base_dir/{entity_type}/*.yaml
```

## Test Contract

A conforming StorageBackend implementation must pass:

1. **Round-trip**: `write(type, data)` → `read(type, id)` returns equivalent data
2. **List**: After N writes, `list(type)` yields N entities
3. **Exists**: `exists(type, id)` returns True after write, False after delete
4. **Merge provenance**: `merge_provenance` appends without duplicating (same source+name)
5. **Find by hash**: `find_by_hash(type, key)` returns entity with matching short_key
6. **Filters**: `list(type, source="bids")` returns only bids-sourced entities
7. **Flag lifecycle**: write_flag → read_flags(status=pending) → resolve_flag → read_flags(status=approved)
8. **Run lifecycle**: save_summary → load_previous returns same summary
