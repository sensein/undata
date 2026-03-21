# CLI Contract: Extract & Transform Pipeline

## New Commands

### `undata-library transform`

```
undata-library transform [PATH] [--threshold FLOAT] [--output-dir DIR]
```

Generate transforms between overlapping elements in the library. Scans elements with shared ontology_term, detects conversion patterns, and writes TransformRecord YAML files to `transforms/`.

**Output**: Stats (pairs evaluated, transforms created, patterns matched) + files in transforms/

## Modified Commands

### `undata-library pipeline`

Extended pipeline order: `ingest → enrich → align → transform → validate`

New step `transform` runs after `align` and before `validate`. Accepts existing `--skip-*` flags plus new `--skip-transform`.

### `undata-library validate-ingestion`

New transform validation checks:
- source_element URI resolves to existing element file
- target_element URI resolves to existing element file
- function_type is a valid enum value
- expression is present for non-identity transforms
- sha256 matches recomputed hash

## Transform YAML Format

```yaml
sha256: "a1b2c3d4e5f6..."
source_element: "https://schema.undata.live/elements/age_abc123456789"
target_element: "https://schema.undata.live/elements/age_def123456789"
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
confidence: 0.95
sssom_predicate: "skos:closeMatch"
provenance:
  - source: auto
    generated_at: "2026-03-20T..."
    attributed_to: "urn:undata:transform-pipeline"
    activity: transform
```
