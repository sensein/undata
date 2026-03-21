# Data Model: Ingestion Overhaul

## New Entities

### ValueSetIdentity

Content-addressed identity for a named collection of enum values.

| Field | Type | In Hash | Description |
|-------|------|---------|-------------|
| name | string | yes | Collection name (e.g., "units", "modalities") |
| members | list[string] | yes | Sorted ValueConcept URIs |

### ValueSetRecord

```yaml
sha256: string               # full SHA-256 of canonical(semantic)
semantic:
  name: string               # e.g., "units"
  members:                   # sorted ValueConcept URIs
    - https://schema.undata.live/values/meter_abc123
    - https://schema.undata.live/values/second_def456
provenance:
  - source: bids
    name: units
    description: "Measurement units used in BIDS"
    generated_at: datetime
    attributed_to: uriorcurie
    activity: ingestion
    derived_from: uriorcurie | null
```

URI pattern: `https://schema.undata.live/valuesets/{name}_{12-hex-key}`

### EntityType (enum)

| Value | Maps To | File Directory |
|-------|---------|---------------|
| `class` | SchemaRecord (sh:NodeShape) | `schemas/` |
| `attribute` | ElementRecord (rdf:Property) | `elements/` |
| `enum_value` | ValueConcept | `values/` |
| `valueset` | ValueSetRecord | `valuesets/` |

### ClassifiedEntity (adapter output)

| Field | Type | Description |
|-------|------|-------------|
| entity_type | EntityType | class / attribute / enum_value / valueset |
| semantic | dict | Raw semantic identity for the entity |
| provenance | dict | Raw provenance data (source, name, description, etc.) |
| confidence | float | Classification confidence 0.0–1.0 |
| source_context | dict or null | Adapter-specific metadata (parent class, siblings, etc.) |

### WorkflowSpec

```yaml
sources:
  - path: string             # file or directory path
    adapter: string | null   # adapter name or null for auto-detect
    options: dict            # adapter-specific options

classification:
  overrides:                 # entity_name → forced EntityType
    units: valueset
  confidence_threshold: float  # default 0.7
  llm_model: string | null   # litellm model spec

docker:
  enabled: boolean           # default false
  image: string | null       # custom Docker image
  timeout: integer           # seconds, default 300

validation:
  strict: boolean            # default false
  checks: list[string]       # validation check names
```

### IngestionReport

```yaml
generated_at: datetime
workflow: string | null       # path to workflow YAML (if used)
sources_processed: integer
stats:
  elements_created: integer
  elements_merged: integer
  schemas_created: integer
  valuesets_created: integer
  values_created: integer
  llm_invocations: integer
  classification_overrides: integer
validation:
  passed: boolean
  violations:
    - file: string
      entity_type: string
      check: string
      message: string
      severity: ERROR | WARNING
```

## Modified Entities

### SchemaProvenance (extended)

Add PROV-O fields to match ProvenanceEntry:

| Field | Status | Type |
|-------|--------|------|
| source | existing | string |
| name | existing | string |
| description | existing | string or null |
| **generated_at** | **NEW** | string (ISO 8601) |
| **attributed_to** | **NEW** | string (agent URI) |
| **activity** | **NEW** | string (ingestion/curation/enrichment/migration) |
| **derived_from** | **NEW** | string (schema URI) or null |

### SemanticIdentity (extended)

| Field | Status | Type | In Hash |
|-------|--------|------|---------|
| type_ref | **NEW** | string or null | yes | URI of referenced SchemaRecord when data_type=object |

### ElementRecord / SchemaRecord / ValueSetRecord YAML

All record types now include top-level `sha256` field for hash verification.

## Relationships

```
SchemaRecord ──has_property──▶ ElementRecord (via properties[] URIs)
ElementRecord ──type_ref──▶ SchemaRecord (when data_type=object)
ValueSetRecord ──has_member──▶ ValueConcept (via members[] URIs)
ElementRecord ──response_options──▶ ValueConcept (via ontology_term URIs)
All records ──derived_from──▶ Any record (via provenance.derived_from)
```

## Directory Layout

```
library/
├── elements/        # ElementRecord YAML files
├── schemas/         # SchemaRecord YAML files
├── values/          # ValueConcept YAML files
├── valuesets/       # NEW — ValueSetRecord YAML files
├── hash-registry.yaml
├── embeddings.parquet
├── alignment-report.yaml
├── ingestion-report.yaml   # NEW — per-run validation report
└── ontology-cache/
```
