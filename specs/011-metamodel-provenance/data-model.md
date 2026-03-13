# Data Model: 011-metamodel-provenance

**Date**: 2026-03-12

---

## Database Changes

### Migration 0010 — `schema_ref` on `data_element`

```sql
ALTER TABLE data_element
  ADD COLUMN schema_ref UUID
  REFERENCES dynamic_schema(id) ON DELETE SET NULL;
```

**Constraints**:
- Nullable; backfill not needed (existing elements are not object-typed).
- Application layer enforces: when `value_type = 'object'`, `schema_ref` MUST be non-null.

### Migration 0011 — `status` on `mapping_function`

```sql
ALTER TABLE mapping_function
  ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active';

ALTER TABLE mapping_function
  ADD COLUMN attributed_to TEXT;  -- e.g. 'urn:undata:system' or user id

ALTER TABLE mapping_function
  ADD COLUMN confidence_score FLOAT;
```

---

## SQLAlchemy ORM Changes

### `DataElement` model (`backend/src/models/db.py`)

New column:
```python
schema_ref: Mapped[Optional[UUID]] = mapped_column(
    ForeignKey("dynamic_schema.id", ondelete="SET NULL"), nullable=True
)
schema_ref_rel: Mapped[Optional["DynamicSchema"]] = relationship(
    "DynamicSchema", foreign_keys=[schema_ref], lazy="noload"
)
```

### `MappingFunction` model (`backend/src/models/db.py`)

New columns:
```python
status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
attributed_to: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
```

---

## New Files

### `backend/data/prov-o.linkml.yaml` (hand-curated, committed)

Minimal PROV-O subset in LinkML format. Key classes:

| Class            | `class_uri`               | Slots (key)                                     |
|------------------|---------------------------|-------------------------------------------------|
| `Entity`         | `prov:Entity`             | `id`, `wasGeneratedBy`, `wasAttributedTo`, `wasDerivedFrom` |
| `Activity`       | `prov:Activity`           | `id`, `startedAtTime`, `endedAtTime`, `wasAssociatedWith` |
| `Agent`          | `prov:Agent`              | `id`, `type`                                    |
| `Generation`     | `prov:Generation`         | `entity`, `activity`, `atTime`                  |
| `Usage`          | `prov:Usage`              | `entity`, `activity`, `atTime`                  |
| `Bundle`         | `prov:Bundle`             | `id`, `entity` (list), `activity` (list), `agent` (list) |

Generated from:
```bash
cd backend
uv run linkml-owl-to-linkml \
    --input https://www.w3.org/ns/prov-o \
    --output data/prov-o-raw.linkml.yaml
# Prune to subset → data/prov-o.linkml.yaml
```

### `backend/src/models/prov_o.py` (generated, committed)

Pydantic v2 models generated via:
```bash
cd backend
uv run gen-pydantic data/prov-o.linkml.yaml \
    --output src/models/prov_o.py
```

The generated models are committed to the repository. Regenerate by running the
command above. Key classes: `Entity`, `Activity`, `Agent`, `Bundle`.

### `backend/src/services/provenance.py`

Pure-Python service (no ORM writes). Reads `AuditLog` / `SchemaChangeLog` records,
constructs `Bundle` Pydantic objects, serializes via `model.model_dump(exclude_none=True)`
and injects the PROV-O `@context`.

```python
PROV_CONTEXT = "https://www.w3.org/ns/prov.jsonld"

def audit_log_to_bundle(records: list[AuditLog], resource_uri: str) -> dict:
    """Assembles a PROV-O JSON-LD Bundle from AuditLog rows."""
    ...
    return {
        "@context": PROV_CONTEXT,
        "@graph": [...],  # Bundle.model_dump() contents
    }
```

### `backend/src/api/v1/provenance.py`

FastAPI router with two routes:
- `GET /elements/{element_id}/provenance` → calls `provenance.audit_log_to_bundle()`
- `GET /schemas/{schema_id}/provenance` → calls `provenance.changelog_to_bundle()`

Response media type: `application/ld+json`.

### `backend/src/services/linkml_io.py`

```python
class RoundtripResult(BaseModel):
    fidelity_score: float      # 0.0 – 1.0
    loss_points: list[str]     # list of documented loss reasons
    schema_id: Optional[UUID]  # set on import, None on export

def export_schema(schema_id: UUID, session: AsyncSession) -> tuple[str, RoundtripResult]:
    """Returns (linkml_yaml_str, RoundtripResult)."""

async def import_schema(yaml_str: str, session: AsyncSession) -> RoundtripResult:
    """Creates DynamicSchema + DataElements; returns RoundtripResult."""
```

---

## `docs/undata-metamodel.yaml` (new file, repo root `docs/` dir)

Self-describing meta-model for the undata system. Structure:

```yaml
id: https://undata.org/meta/undata-metamodel
name: undata-metamodel
description: LinkML meta-model describing the undata schema system

prefixes:
  linkml: https://w3id.org/linkml/
  prov: http://www.w3.org/ns/prov#
  skos: http://www.w3.org/2004/02/skos/core#
  sssom: https://w3id.org/sssom/
  owl: http://www.w3.org/2002/07/owl#
  schema: https://schema.org/
  undata: https://undata.org/meta/

default_prefix: undata
default_range: string

imports:
  - linkml:types

classes:
  DataElement:
    class_uri: schema:Property
    description: >-
      A named, typed data element with an optional semantic graph anchor.
    attributes:
      id: { identifier: true, range: uriorcurie }
      name: { required: true }
      value_type: { range: ValueType, required: true }
      schema_ref: { range: DynamicSchema }
      semantic_graph: { range: SemanticGraph }
      version: { range: string }

  DynamicSchema:
    class_uri: owl:Class
    description: A named collection of DataElements.
    attributes:
      id: { identifier: true, range: uriorcurie }
      name: { required: true }
      elements:
        range: DataElement
        multivalued: true
        inlined_as_list: true

  SemanticGraph:
    class_uri: skos:ConceptScheme
    description: Ontological anchoring of a DataElement.
    attributes:
      ontology_term: { range: uriorcurie }
      unit: { range: string }
      external_uri: { range: uriorcurie }

  MappingFunction:
    class_uri: sssom:Mapping
    description: A directed transformation between two DataElements.
    attributes:
      source: { range: DataElement, required: true }
      target: { range: DataElement, required: true }
      function_type: { range: MappingFunctionType }
      status: { range: MappingStatus }
      confidence_score: { range: float }

  ProvenanceRecord:
    class_uri: prov:Bundle
    description: PROV-O bundle of activities for a resource.

enums:
  ValueType:
    permissible_values:
      string: {}
      integer: {}
      float: {}
      boolean: {}
      array: {}
      object: {}

  MappingFunctionType:
    permissible_values:
      identity: {}
      unit_conversion: {}
      scaling: {}
      structural: {}
      unknown: {}

  MappingStatus:
    permissible_values:
      active: {}
      pending_curation: {}
```

---

## Entity Relationships

```
DynamicSchema 1──* DataElement
DataElement 0..1──> DynamicSchema  (schema_ref, for object-typed)
DataElement 0..1──> SemanticGraph
DataElement *──* DataElement  (via MappingFunction)
AuditLog *──1 DataElement      (existing)
SchemaChangeLog *──1 DynamicSchema  (existing)
AuditLog ──> ProvenanceRecord  (assembled on-demand)
SchemaChangeLog ──> ProvenanceRecord  (assembled on-demand)
```
