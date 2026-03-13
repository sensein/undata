# Research: End-to-End Schema Ingestion and LinkML Export

**Feature**: `007-end-to-end-pipeline` | **Date**: 2026-03-11

---

## Decision Log

### D-001: pynwb and openMINDS Python 3.14 Compatibility

**Decision**: Add `pynwb` and `openMINDS` to `ingestion/pyproject.toml` dependencies
and attempt `--extraction-mode code` first. Fall back to `--extraction-mode file`
with downloaded fixtures if installation fails on Python 3.14.

**Rationale**: Both packages declare `requires-python = ">=3.9"` (pure Python or
with optional C extensions via h5py/numpy). Python 3.14 is generally compatible
with packages that follow the `>=3.9` convention. If pynwb's optional h5py
dependency does not compile, `load_code()` will raise `ImportError` as designed
and the runbook will use the file-path.

**Real schema sizes driving this decision**:
- NWB: 80 `neurodata_type_def` entries across 13 YAML files (nwb-schema repo).
  The test fixture covers 1 type with 4 attributes — far below the real ~400+
  attributes/datasets across all types.
- openMINDS: 292 `.schema.omi.json` files (v4/latest) across 10 modules
  (controlledTerms 112, core 84, SANDS 41, computation 18, publications 11,
  ephys 9, neuroimaging 6, specimenPrep 5, chemicals 4, stimulation 2).
  The test fixture covers 1 type with 3 fields.

**Alternatives considered**:
- Bridge venv for pynwb/openMINDS: over-engineering since both packages are
  pure Python or have optional C extensions that can be omitted.
- Always use file-path: would require maintaining downloaded fixture copies;
  code-path is cleaner and captures the living schema directly.

### D-002: NWBAdapter Multi-File Namespace Enhancement

**Decision**: Enhance `NWBAdapter.load_file()` to detect and traverse the NWB
multi-file namespace structure (`nwb.namespace.yaml` → 12 domain YAML files).

**Rationale**: The real NWB core schema is not a single YAML file; it is a namespace
manifest that references 12 domain files (base, icephys, ecephys, ophys, behavior,
image, misc, file, epoch, device, ogen, retinotopy). Loading only one file captures
~4 types; loading the full namespace captures 80 types.

**Current behavior**: `load_file(path)` reads a single YAML file with a `groups:` key.
Existing tests use `nwb_schema_sample.yaml` which has 1 NWBFile group with 4 fields.

**New behavior**:
- If `path` is a directory: look for `*.namespace.yaml`, parse the `namespaces:`
  list, and load all referenced `*.yaml` files in the same directory.
- If `path` is a single YAML file with a `namespaces:` key (namespace manifest):
  load the referenced files relative to the manifest's directory.
- If `path` is a single YAML file with a `groups:` key (existing behavior): load
  it as before (backward-compatible with current tests).
- URL support: if `path` is an HTTP URL to `nwb.namespace.yaml`, fetch and traverse.
  Referenced files are fetched from the same base URL.

**NWB core namespace YAML source**:
`https://raw.githubusercontent.com/NeurodataWithoutBorders/nwb-schema/dev/core/`
Files: `nwb.namespace.yaml` + 12 domain files.

**Alternatives considered**:
- Fetch all files individually via explicit URL list: brittle, breaks on schema
  version updates.
- Only support code-path (pynwb): leaves file-path broken for Python environments
  where pynwb doesn't install.

### D-003: AIND Extended Fixtures

**Decision**: Download the 4 additional AIND core schema modules
(metadata.py, model.py, processing.py, quality_control.py)
via `aind-data-schema` GitHub raw file URLs and add them to `ingestion/schemas/aind/`
(not bundled into `tests/fixtures/aind/` to avoid bloating test fixtures).

**Rationale**: The bundled `tests/fixtures/aind/` covers only 5 of 9 `core/`
modules (acquisition, data_description, instrument, procedures, subject). The
4 missing modules include `quality_control.py` (QC metrics) and `processing.py`
(processing pipeline metadata). Downloading their exported JSON Schema files from
GitHub releases gives the full picture. (Verified: 9 modules total in
`src/aind_data_schema/core/`, not 10 as previously estimated.)

**Source**: `https://github.com/AllenNeuralDynamics/aind-data-schema/releases/`
(pre-exported JSON Schema files from each release).

**Alternatives considered**:
- Bridge venv for aind-data-schema on Python 3.12: generates the most current
  schemas but adds complexity. Deferred to a future feature.
- Use only bundled fixtures: captures only 50% of AIND schema; accepted as minimum
  viable for this feature since AIND's Python 3.14 incompatibility is a known blocker.

### D-004: LinkML Generator Architecture for Inheritance

**Decision**: Add a new `_fetch_dynamic_schemas()` private method to
`LinkMLSchemaGenerator` that fetches the DynamicSchema inheritance graph from
`GET /schemas` + `GET /schemas/{id}/inheritance-tree`, then emits one LinkML
`ClassDefinition` per schema with `is_a`, `mixin`, and `mixins` populated.

**Rationale**: The existing generator already produces per-source subclasses with
`is_a: NeuroscienceDataset` using a hard-coded `_SOURCE_CLASSES` dict. The new
method adds a second pass that emits DynamicSchema-level classes on top. These
two passes are complementary: the first captures real ingested element metadata,
the second captures schema-level structural relationships.

**Backend APIs used**:
- `GET /schemas?limit=500` → list of `DynamicSchemaSummary` (id, name, is_mixin)
- `GET /schemas/{id}/inheritance-tree` → nodes (id, name, is_mixin) + edges
  (type: "inherits"|"mixin", child_id, parent_id, position)
- `GET /schemas/{id}/resolved` → MRO-ordered element list (for dedup)
- `GET /schemas?q=ProvenanceMixin` → find the system mixin schema

**LinkML ClassDefinition fields populated**:
- `is_mixin=True` → `mixin: true` in YAML
- Parent edge (type="inherits") → `is_a: <ParentName>`
- Mixin edges (type="mixin", ordered by position) → `mixins: [M1, M2, ...]`

**Slot deduplication**:
- Slots already in a mixin class are NOT repeated in classes that list that mixin
- Implemented by building a `Set[str]` of mixin-contributed slot names and
  excluding them from the child class's slot list

**Alternatives considered**:
- Single API call using `/schemas/{id}/resolved` for everything: would require N+1
  calls per schema; the inheritance-tree endpoint gives the graph in one call per
  schema, acceptable for the ~20 DynamicSchemas expected.
- Separate generator subclass for inheritance: unnecessary complexity per Principle I.

### D-005: Makefile vs shell script for runbook

**Decision**: Use a `Makefile` at `ingestion/Makefile` with targets: `setup`,
`fetch-schemas`, `ingest-code`, `ingest-file`, `ingest`, `generate`, `validate`,
`pipeline`.

**Rationale**: Makefile targets are self-documenting, support dependency ordering
(`pipeline: setup fetch-schemas ingest generate validate`), and are universally
available on macOS/Linux without additional tooling. The `make` tool is already
a prerequisite for Docker/uv usage.

**Alternatives considered**:
- `scripts/run-pipeline.sh`: less self-documenting, no dependency ordering.
- `Taskfile.yml` (go-task): adds external dependency, not universally available.

### D-006: openMINDS Schema Acquisition

**Decision**: Use `--extraction-mode code` with the installed `openMINDS` PyPI
package. The package provides `openminds.registry` which contains all 292+ schema
types in the latest version. For file-path fallback, clone the
`openMetadataInitiative/openMINDS` GitHub repo (sparse checkout of `schemas/latest/`).

**Source**: https://github.com/openMetadataInitiative/openMINDS
**PyPI package**: `openMINDS` (`pip install openMINDS`)

**Schema structure** (latest version, 292 files):
- `controlledTerms/`: 112 schemas (species, disease, strain, technique, etc.)
- `core/`: 84 schemas (actors, data, digitalIdentifier, miscellaneous, products, research)
- `SANDS/`: 41 schemas (atlas, mathematicalShape, miscellaneous, non-atlas)
- `computation/`: 18 schemas
- `publications/`: 11 schemas
- `ephys/`: 9 schemas
- `neuroimaging/`: 6 schemas
- `specimenPrep/`: 5 schemas
- `chemicals/`: 4 schemas
- `stimulation/`: 2 schemas

### D-007: BIDS Adapter — Full Vocabulary Loading

**Decision**: Extend `BIDSAdapter.load_code()` to load ALL vocabulary objects from
`bidsschematools` (not just `schema.objects.metadata`), and fix class grouping to
use `rules/sidecars/` modality groups instead of a `_` name-split heuristic.

**Rationale**: The current adapter loads only `schema.objects.metadata` (449 of 1,012
vocabulary entries = 44%). The real BIDS vocabulary includes:

| Object type | Count | Description |
|-------------|-------|-------------|
| metadata | 449 | Sidecar JSON fields (currently loaded) |
| columns | 101 | TSV column definitions (events, channels, etc.) |
| suffixes | 118 | File type suffixes (BOLD, T1w, dwi, events, …) |
| enums | 218 | Shared enumerated value sets |
| entities | 35 | File-name entities (sub, ses, task, run, acq, …) |
| datatypes | 16 | Top-level modality directories (anat, func, eeg, …) |
| extensions | 44 | File extension definitions |
| files | 13 | Special dataset-level file definitions |
| formats | 18 | Data format/regex constraint definitions |
| **Total** | **1,012** | **all vocabulary objects** |

**Class grouping bug**: The current `_classes_from_fields()` splits on `_` and creates
440 singleton classes (one field per class). Real BIDS classes are the 22
modality-specific sidecar groups defined in `schema.rules.sidecars` (MRI hardware,
MRI sequence, EEG hardware, PET, ASL, etc.). Fixing this requires reading
`schema.rules.sidecars` from bidsschematools.

**New element count target**: ≥ 900 elements from BIDS (up from 449).

**Alternatives considered**:
- Only fix class grouping, keep metadata-only elements: half-measure; misses 563
  vocabulary entries.
- Parse raw BIDS schema YAML from GitHub: redundant since bidsschematools already
  wraps this; use the library.

### D-008: DANDI Adapter — `$defs` Extraction and Self-Ref Fix

**Decision**: Fix two bugs in `DANDIAdapter`:
1. **File-path**: Parse `$defs` from each JSON Schema release file to extract nested
   entity definitions (additional ~606 property instances across 4 schema files).
2. **Code-path**: Handle self-referencing Pydantic models (`BioSample`, `PropertyValue`)
   that return 0 properties from `model_json_schema()` due to `$ref` recursion — fall
   back to `model.model_fields` for these.

**Rationale**: The DANDI JSON Schema files for v0.7.0 have:
- 4 schema files × top-level properties = **122 direct properties**
- 4 schema files × `$defs` = **~606 nested property instances** across ~125 unique
  entity types (`Participant`, `BioSample`, `Organization`, `Person`, `Resource`, etc.)

Without `$defs` extraction, file-path mode captures only 122 of 728 fields (17%).
The code-path misses `BioSample` (10 fields) and `PropertyValue` (8 fields) due to
a Pydantic v2 `$ref` recursion bug.

**DANDI release files (v0.7.0)**:
- `asset.json` (33 top-level + 182 in `$defs`)
- `dandiset.json` (25 top-level + 112 in `$defs`)
- `published-asset.json` (35 top-level + 191 in `$defs`)
- `published-dandiset.json` (29 top-level + 121 in `$defs`)
- `context.json` (JSON-LD context — URIs for semantic enrichment; read for
  `raw_metadata` annotation, not as elements)

**New element count target**: ≥ 350 unique elements from DANDI code-path (up from
current ~361 which drops BioSample/PropertyValue), plus ≥ 100 unique `$defs`
entities from file-path mode (deduplicated across the 4 release files).

**Alternatives considered**:
- Skip `$defs`: leaves 83% of file-path schema data on the floor.
- Treat every `$defs` entry as a top-level element: would bloat the flat element
  list; better to treat each `$defs` entry as its own `SchemaClassPayload` (nested
  entity type) and link its properties as elements.

---

## Technical Findings

### NWB Schema Files

The NWB core schema (v2.10.0-alpha) lives at:
```
https://raw.githubusercontent.com/NeurodataWithoutBorders/nwb-schema/dev/core/
  nwb.namespace.yaml       # namespace manifest, references all below
  nwb.base.yaml            # 11 types (TimeSeries, NWBDataInterface, etc.)
  nwb.icephys.yaml         # 16 types
  nwb.ecephys.yaml         # 11 types
  nwb.ophys.yaml           # 11 types
  nwb.behavior.yaml        # 8 types
  nwb.image.yaml           # 7 types
  nwb.misc.yaml            # 6 types
  nwb.file.yaml            # 4 types (NWBFile)
  nwb.epoch.yaml           # 1 type
  nwb.device.yaml          # 2 types
  nwb.ogen.yaml            # 2 types
  nwb.retinotopy.yaml      # 1 type
Total: 80 neurodata_type_def entries
```

### DANDI Schema Models

`dandischema.models` contains these Pydantic v2 classes (introspectable via
`inspect.getmembers(dandischema.models, inspect.isclass)`):
- Asset, BareAsset, PublishedAsset, AccessRequirements
- Dandiset, PublishedDandiset
- AssetsSummary, CommonModel, DigestStatus
- Organization, Person, Participant
- Software, Activity, Relation, License
- Resource, RoleType, EthicsApproval
- Approx 20+ total models with combined 200–300 fields

### BIDS Schema Metadata Fields

`bidsschematools.schema.load_schema().objects.metadata` returns a dict of 500+
fields. Key categories: `sub-*` (subject metadata), `ses-*` (session), `task-*`,
`acq-*`, global fields (RepetitionTime, FlipAngle, etc.).

### AIND Core Modules

| Module | Description | Status |
|--------|-------------|--------|
| acquisition.py | Acquisition metadata | ✅ bundled fixture |
| data_description.py | Dataset description | ✅ bundled fixture |
| instrument.py | Instrument configuration | ✅ bundled fixture |
| procedures.py | Subject procedures | ✅ bundled fixture |
| subject.py | Subject metadata | ✅ bundled fixture |
| metadata.py | Top-level container | ❌ not in fixtures |
| model.py | Model metadata | ❌ not in fixtures |
| processing.py | Processing pipeline | ❌ not in fixtures |
| quality_control.py | QC metrics | ❌ not in fixtures |

The 4 missing modules are exported to `ingestion/schemas/aind/` by the fetch script.

### LinkML ClassDefinition API

```python
from linkml_runtime.linkml_model.meta import ClassDefinition

# Mixin class
ClassDefinition(
    name="ProvenanceMixin",
    mixin=True,
    description="...",
    slots=["was_derived_from", "was_generated_by"],
)

# Schema with parent and mixin
ClassDefinition(
    name="NWBTimeSeries",
    is_a="NWBDataInterface",
    mixins=["ProvenanceMixin"],
    description="...",
    slots=["data", "timestamps", "unit"],
)
```

### Backend Inheritance-Tree API Response

```json
{
  "schema_id": "uuid",
  "nodes": [
    {"id": "uuid1", "name": "ChildSchema", "is_mixin": false},
    {"id": "uuid2", "name": "ParentSchema", "is_mixin": false},
    {"id": "uuid3", "name": "ProvenanceMixin", "is_mixin": true}
  ],
  "edges": [
    {"child_id": "uuid1", "parent_id": "uuid2", "type": "inherits", "position": 0},
    {"child_id": "uuid1", "parent_id": "uuid3", "type": "mixin", "position": 0}
  ]
}
```
