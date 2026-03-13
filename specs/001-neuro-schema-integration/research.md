# Research: Neuroscience Schema Integration
**Feature**: 001-neuro-schema-integration | **Date**: 2026-03-07

---

## Decision 1: Schema Ingestion Strategy per Source

### BIDS
- **Package**: `bidsschematools` (Python, part of bids-validator project) provides a
  `schema` object that loads the full BIDS schema from its YAML directory structure.
  Key entry point: `bidsschematools.schema.load_schema()`.
- **Structure**: BIDS schema lives in subdirectories — `objects/metadata.yaml`,
  `objects/files.yaml`, `rules/` directory with per-datatype rules. Each metadata field
  is defined with `type`, `description`, `levels` (allowed values).
- **Extraction approach**: Load schema with `bidsschematools`; iterate `schema.objects.metadata`
  dict to enumerate all metadata fields. Each entry has `type`, `description`,
  optional `enum` (allowed values list).

### DANDI
- **Package**: `dandischema` (PyPI) — pure Pydantic v2 models.
- **Extraction approach**: Use Python introspection on `dandischema.models` module.
  For each Pydantic `BaseModel` subclass, iterate `model.model_fields` to get
  `FieldInfo` objects (name, annotation, description, default). JSON Schema export
  via `model.model_json_schema()` provides full type + constraint information.

### openMINDS
- **Package**: `openminds` Python client (PyPI, `openminds-python`).
- **Structure**: Schema types are JSON-LD documents in the repo under
  `schemas/<module>/latest/*.schema.tpl.json`. Each file defines a type with a
  `properties` object listing all fields with `"@type"`, `"label"`, `"description"`.
- **Extraction approach**: Parse JSON files directly from the repo (local clone or
  remote fetch). Each property entry maps cleanly to a DataElement.

### NWB
- **Package**: `hdmf` (Python) — provides `hdmf.spec.SpecCatalog` and related classes
  for loading YAML spec files.
- **Structure**: `nwb-schema/core/*.yaml` files contain `NWBGroupSpec`/`NWBDatasetSpec`
  definitions with `attributes` (metadata fields) and `datasets`.
- **Extraction approach**: Use `hdmf.spec.NWBGroupSpec` / `NWBDatasetSpec` to load
  YAML files; iterate `spec.attributes` and `spec.datasets` to extract fields.

**Decision**: Write four independent ingestion adapters, one per schema source. Each
adapter returns a normalized list of `DataElementCreate` objects matching the backend
API's POST /elements schema. No shared parser — the formats are too different.

---

## Decision 2: Normalization to Common DataElement Format

**Decision**: Map each source field to these normalized fields:
- `name`: snake_case normalized field name
- `data_type`: mapped to one of {string, number, boolean, object, array}
- `description`: original description string (no truncation)
- `required`: from field constraints; default False if not specified
- `multivalued`: True if list/array type
- `allowed_values`: list of strings for enum types; null otherwise
- `constraints`: JSON object with min/max/pattern where available
- `source_local_id`: original field path within the source schema

Type mapping table:
| Source type | Normalized |
|-------------|-----------|
| string, text, str | string |
| number, float, integer, int | number |
| boolean, bool | boolean |
| object, dict, mapping | object |
| array, list, List[*] | array |
| Literal["a","b"] | string + allowed_values |

---

## Decision 3: LinkML Schema Generation

**Decision**: Use `linkml-runtime` Python library to programmatically construct
a `SchemaDefinition` object and serialize it to YAML via `YAMLDumper`.

Key classes used:
- `linkml_runtime.linkml_model.meta.SchemaDefinition`
- `linkml_runtime.linkml_model.meta.SlotDefinition`
- `linkml_runtime.linkml_model.meta.ClassDefinition`
- `linkml_runtime.linkml_model.meta.EnumDefinition` + `PermissibleValue`
- `linkml_runtime.utils.yamlutils.YAMLDumper`

One top-level class `NeuroscienceDataset` with all slots. Per-source subclasses
(`BIDSDataset`, `DANDIDataset`, etc.) that inherit from it and include only their
own slots — enabling source-specific validation while sharing the unified schema.

JSON-LD export: `linkml_runtime.utils.metamodelcore` context generation, or via
`gen-jsonld-context` CLI.

**No existing BIDS→LinkML or NWB→LinkML converter found** — this is novel work.
DANDI has a Pydantic→JSON Schema path but not LinkML. openMINDS has JSON-LD but
no LinkML representation found.

---

## Decision 4: Alias Detection Algorithm

**Decision**: Three-phase pipeline:
1. **Exact name match** (after normalization): `subject_age` == `participant_age`?
   Normalized names compared after stripping prefixes (sub_, participant_, etc.) and
   synonymous tokens (age/years, session/visit, subject/participant).
2. **Type + cardinality gate**: only consider elements with compatible data types and
   the same multivalued flag.
3. **Description cosine similarity** via sentence-transformers `all-MiniLM-L6-v2`:
   threshold 0.92 for `skos:exactMatch`, 0.80–0.92 for `skos:closeMatch`.

Token synonym table (hardcoded, expandable): `{subject: participant, session: visit,
acquisition: acq, run: run_index, task: task_id, age: years, ...}`.

---

## Decision 5: Backend Communication

**Decision**: `httpx` async client calling the 002-schema-backend REST API.
The ingestion pipeline is a standalone Python CLI tool / library that:
1. Accepts schema source URLs or local paths as arguments.
2. Ingests each schema, normalizes elements, bulk-POSTs to `/api/v1/elements/bulk`.
3. Runs alias detection, registers identity mappings via `/api/v1/mappings`.
4. Generates the unified LinkML schema from the stored elements (fetched from backend).
5. Outputs the LinkML YAML to a file or stdout.

---

## Technology Summary

**Note on linkml-map**: The `linkml-map` (`linkml-transformer`) library provides
declarative schema-to-schema transformation using YAML `TransformationSpecification`
with `slot_derivations` and `expr:` fields (simpleeval-compatible expressions). It is
used for structural projections where both source and target are already LinkML schemas.
For BIDS, DANDI, openMINDS, and NWB ingestion (which are not natively LinkML), the
custom adapters handle the initial extraction; linkml-map applies post-generation for
cross-schema slot derivations.

---

## Technology Summary

| Concern | Choice | Version |
|---------|--------|---------|
| Language | Python | 3.14 |
| BIDS parsing | bidsschematools | latest |
| DANDI parsing | dandischema | latest |
| openMINDS parsing | openminds-python + direct JSON parsing | latest |
| NWB parsing | hdmf + nwb-schema YAML | latest |
| LinkML generation | linkml-runtime | 1.8+ |
| Backend client | httpx async | 0.27+ |
| Alias similarity | sentence-transformers (all-MiniLM-L6-v2) | 3.x |
| CLI | typer | 0.12+ |
| Testing | pytest | latest |
