# Data Model: Neuroscience Schema Integration
**Feature**: 001-neuro-schema-integration | **Date**: 2026-03-07

This feature is a CLI library — it does not own a database. Its "data model" is the
set of intermediate Python data structures used during ingestion, normalization, and
LinkML schema generation, plus the LinkML schema structure it produces as output.

---

## Ingestion Pipeline Data Flow

```
SourceSchema (external)
    │
    ▼
IngestionAdapter (per-source)
    │  produces
    ▼
NormalizedElement (Python dataclass)
    │  bulk-sent to
    ▼
BackendAPI (002-schema-backend)  ← stores DataElement records
    │  retrieved from
    ▼
LinkMLGenerator
    │  produces
    ▼
UnifiedLinkMLSchema (YAML output artifact)
```

---

## Internal Data Structures

### NormalizedElement (Python dataclass)

Intermediate representation produced by each ingestion adapter.

```python
@dataclass
class NormalizedElement:
    name: str                          # snake_case normalized name
    data_type: str                     # "string"|"number"|"boolean"|"object"|"array"
    description: str
    required: bool
    multivalued: bool
    allowed_values: list[str] | None   # None for non-enum types
    constraints: dict                  # {"minimum": 0, "maximum": 150, ...}
    source_local_id: str               # original field path in source schema
    source_name: str                   # "BIDS"|"DANDI"|"openMINDS"|"NWB"
    raw_metadata: dict                 # full original field dict for debugging
```

### IngestionResult

Summary returned after a completed ingestion run.

```python
@dataclass
class IngestionResult:
    source_name: str
    elements_submitted: int
    elements_succeeded: int
    elements_failed: int
    failures: list[dict]              # [{index, error, element_name}]
    duration_seconds: float
```

### AliasCandidate

Output of the alias detection phase.

```python
@dataclass
class AliasCandidate:
    element_a_id: str                 # UUID from backend
    element_b_id: str
    similarity_score: float
    predicate: str                    # "skos:exactMatch" | "skos:closeMatch"
    detection_method: str             # "exact_name" | "embedding" | "token_synonym"
```

---

## LinkML Schema Structure (Output Artifact)

The generated unified LinkML schema has this logical structure:

```yaml
id: https://undata.org/schema/neuroscience
name: NeuroscienceUnified
version: 2026.03.0
description: Unified neuroscience metadata schema integrating BIDS, DANDI, openMINDS, NWB

prefixes:
  linkml: https://w3id.org/linkml/
  schema: http://schema.org/
  skos: http://www.w3.org/2004/02/skos/core#
  bids: https://bids-specification.readthedocs.io/
  dandi: https://schema.dandiarchive.org/
  nwb: https://nwb-schema.readthedocs.io/
  openminds: https://openminds.ebrains.eu/

default_range: string

# Top-level unified class
classes:
  NeuroscienceDataset:
    description: Unified metadata record for a neuroscience dataset
    slots: [subject_age, session_id, task_name, ...]

  BIDSDataset:
    is_a: NeuroscienceDataset
    description: BIDS-specific dataset metadata
    slots: [bids_version, dataset_type, ...]

  DANDIDataset:
    is_a: NeuroscienceDataset
    slots: [dandiset_id, contributor, ...]

  NWBFile:
    is_a: NeuroscienceDataset
    slots: [nwb_version, session_description, ...]

  openMINDSDataset:
    is_a: NeuroscienceDataset
    slots: [fullName, shortName, ...]

# Unified slots (one per deduplicated DataElement)
slots:
  subject_age:
    range: float
    description: Age of the research subject
    multivalued: false
    required: false
    annotations:
      sources: "BIDS,DANDI"
      bids_alias: "sub-age"
      dandi_alias: "participant/age"

  session_id:
    range: string
    description: Identifier for the recording session
    ...

# Enumerations for enumerated fields
enums:
  SexEnum:
    permissible_values:
      male: {}
      female: {}
      unknown: {}
      other: {}
```

---

## Source Adapter Interface

Each ingestion adapter implements a common protocol:

```python
class SchemaAdapter(Protocol):
    source_name: str
    source_format: str

    def load(self, path_or_url: str) -> None:
        """Load the raw schema from a local path or remote URL."""

    def extract_elements(self) -> list[NormalizedElement]:
        """Return all normalized data elements from the loaded schema."""

    def get_version_info(self) -> dict:
        """Return version_tag and content_hash for SchemaSource registration."""
```

Concrete implementations:
- `BIDSAdapter` — uses `bidsschematools.schema.load_schema()`
- `DANDIAdapter` — introspects `dandischema.models` Pydantic classes
- `OpenMINDSAdapter` — parses JSON-LD schema template files
- `NWBAdapter` — uses `hdmf` spec loader on YAML files
