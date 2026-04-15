# CLI Contract: undata-library

## Commands

### `undata-library validate [PATH]`
Validate YAML files against the library schema.
- **Input**: file or directory path (default: `.`)
- **Output**: per-file OK/FAIL with violation details
- **Exit 0**: all valid | **Exit 1**: any violations

### `undata-library export --backend-url URL [--output DIR] [--token TOKEN]`
Export backend elements/schemas/mappings to content-addressed YAML.
- Fetches from backend API (paginated)
- Computes semantic hash for each element
- Merges provenance into existing files if element hash matches
- Writes `hash-registry.yaml`
- **Exit 0**: success | **Exit 1**: backend unreachable

### `undata-library import --backend-url URL [--path DIR] [--token TOKEN]`
Import library YAML files to backend.
- Reads element/schema files
- POSTs to backend API
- Skips on 409 (duplicate)
- **Exit 0**: success | **Exit 1**: errors

### `undata-library diff FILE [--from N --to M] [--format text|json]`
Show differences between element versions (provenance changes).
- Default: compare last two provenance entries
- **Exit 0**: always

### `undata-library hash FILE`
Compute and display the content hash for a YAML file.
- Shows: attribute name, 6-char key, full SHA-256, URI
- **Exit 0**: always

### `undata-library index [--output FILE]`
Build machine-readable registry.
- Scans elements/, schemas/, mappings/
- Writes `index.yaml` with counts and summaries
- **Exit 0**: success

### `undata-library ingest --source NAME --path DIR`
Ingest from raw schema files (BIDS YAML, NWB YAML, AIND JSON Schema, etc.)
directly into the library format — no backend required.
- Reads source schemas
- Extracts elements with semantic graphs
- Computes content hashes
- Writes element + schema + hash-registry files
- Merges provenance for elements that already exist
- **Exit 0**: success | **Exit 1**: parse errors

## File Format Contract

### Element file: `elements/{attribute}_{6-char-key}.yaml`
```yaml
semantic:
  ontology_term: <uriorcurie | null>
  data_type: <DataType>
  unit: <string | null>
  constraints: <object | null>

provenance:
  - source: <string>
    class: <string>
    name: <string>
    description: <string | null>
    required: <boolean | null>
    multivalued: <boolean | null>
```

### Schema file: `schemas/{name}_{6-char-key}.yaml`
```yaml
semantic:
  properties: [<element URIs>]
  subclass_of: <schema URI | null>
  mixins: [<schema URIs>]

provenance:
  - source: <string>
    name: <string>
    description: <string | null>
```

### Hash registry: `hash-registry.yaml`
```yaml
elements:
  <6-char-key>:
    sha256: <64-hex-chars>
    attribute: <string>
    uri: <full URI>
schemas:
  <6-char-key>:
    sha256: <64-hex-chars>
    name: <string>
    uri: <full URI>
```
