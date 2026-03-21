# Data Model: Extract & Transform Pipeline

## New Entities

### FunctionSpec

Typed function specification within a transform.

| Field | Type | Description |
|-------|------|-------------|
| function_type | string | identity, unit_conversion, type_conversion, scaling, structural, value_mapping, unknown |
| input_type | string | data_type of source element (string, integer, float, boolean, array, object) |
| output_type | string | data_type of target element |
| expression | string or null | formula, named function reference, or template |
| expression_type | string | arithmetic, named_function, template, lookup_table, none |
| parameters | dict or null | function parameters (e.g., {factor: 12, unit_from: "year", unit_to: "month"}) |

### TransformRecord

Content-addressed bidirectional transform between two elements.

```yaml
sha256: string                    # SHA-256 of canonical({source_element, target_element, function})
source_element: string            # element URI
target_element: string            # element URI
function:
  function_type: unit_conversion
  input_type: float
  output_type: float
  expression: "value * 12"
  expression_type: arithmetic
  parameters:
    factor: 12
    unit_from: year
    unit_to: month
confidence: float | null          # auto-detection confidence
sssom_predicate: string | null    # SSSOM mapping predicate
provenance:
  - source: string
    generated_at: datetime
    attributed_to: urn:undata:transform-pipeline
    activity: transform
    source_ref: SourceRef | null
```

URI pattern: `https://schema.undata.live/transforms/{source_name}_to_{target_name}_{12-hex-key}`

File pattern: `transforms/{source_name}_to_{target_name}_{12-hex-key}.yaml`

### Extended OntologyIndexEntry

```yaml
ontology-index.yaml:
  generated_at: datetime
  ontology_term_count: integer
  entity_count: integer
  terms:
    http://purl.obolibrary.org/obo/NCIT_C25150:
      - uri: https://schema.undata.live/elements/age_abc123
        entity_type: element      # NEW — element, schema, or valueset
        file: age_abc123.yaml
        data_type: float
        unit: year
        sources: [bids, nwb]
      - uri: https://schema.undata.live/schemas/participant_def456
        entity_type: schema       # NEW
        file: participant_def456.yaml
        sources: [bids]
```

## Modified Entities

### MappingFunctionType (extended)

| Value | Status | Description |
|-------|--------|-------------|
| identity | existing | Same representation, different source name |
| unit_conversion | existing | Same type, different unit (e.g., years → months) |
| type_conversion | **NEW** | Different type (e.g., float → string ISO8601) |
| scaling | existing | Numeric scaling factor |
| structural | existing | Structural transformation (flat → nested) |
| value_mapping | **NEW** | Enum/valueset value lookup table |
| unknown | existing | Unresolved — flagged for manual curation |

## Auto-Detection Pattern Registry

| Pattern | Detection Rule | function_type | expression |
|---------|---------------|---------------|------------|
| Same type + same unit | data_type match, unit match | identity | (none) |
| Same type + different unit (both numeric) | data_type match, unit differs | unit_conversion | `value * {factor}` |
| float ↔ string + unit=iso8601 | float vs string, ISO8601 context | type_conversion | `iso8601_duration_from_years` / `years_from_iso8601_duration` |
| Enum overlap > 50% | shared response_options values | value_mapping | lookup table of value mappings |
| object ↔ flat field | data_type: object vs primitive | structural | template |
| No pattern match | default | unknown | (none) |

## Directory Layout

```
library/
├── elements/            # ElementRecord YAML
├── schemas/             # SchemaRecord YAML
├── values/              # ValueConcept YAML
├── valuesets/           # ValueSetRecord YAML
├── transforms/          # NEW — TransformRecord YAML (replaces mappings/)
├── ontology-index.yaml  # MODIFIED — includes entity_type
├── hash-registry.yaml
├── embeddings.parquet
├── alignment-report.yaml
├── ingestion-report.yaml
└── ontology-cache/
```
