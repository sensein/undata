# Research: 011-metamodel-provenance

**Date**: 2026-03-12
**Branch**: `011-metamodel-provenance`

---

## PROV-O OWL → LinkML → Pydantic

### Decision
Convert the W3C PROV-O OWL ontology (`https://www.w3.org/ns/prov-o`) to a LinkML YAML
subset (`backend/data/prov-o.linkml.yaml`), then run `gen-pydantic` to produce
`backend/src/models/prov_o.py` with Pydantic v2 models. Serialize instances to
JSON-LD by embedding the standard PROV-O `@context` from
`https://www.w3.org/ns/prov.jsonld`.

### Rationale
- The `prov` Python library is **not used** (user constraint).
- `rdflib` is already a dependency (`rdflib>=7.x`) and can load the OWL file for
  inspection, but the definitive representation lives in the hand-curated LinkML YAML.
- `gen-pydantic` (part of `linkml[generators]`) generates Pydantic v2 dataclass-style
  models; these models are used for structured construction and dict serialization.
- JSON-LD output = `model.model_dump(exclude_none=True)` + injected `@context` +
  `@type`/`@id` annotations; no third-party PROV library needed.

### PROV-O Subset Needed

Only the **Expanded Term Level** (OWL Primer) subset is required:

| LinkML class | PROV-O term         | JSON-LD @type          |
|--------------|---------------------|------------------------|
| `Entity`     | `prov:Entity`       | `prov:Entity`          |
| `Activity`   | `prov:Activity`     | `prov:Activity`        |
| `Agent`      | `prov:Agent`        | `prov:Agent`           |
| `Usage`      | `prov:Usage`        | `prov:Usage`           |
| `Generation` | `prov:Generation`   | `prov:Generation`      |
| `Derivation` | `prov:Derivation`   | `prov:Derivation`      |

Key properties: `wasGeneratedBy`, `wasAssociatedWith`, `used`, `wasDerivedFrom`,
`atTime`, `hadRole`, `wasAttributedTo`, `startedAtTime`, `endedAtTime`.

### OWL → LinkML Conversion Tool

`linkml-owl` (`pip install linkml-owl`) provides `linkml-owl-to-linkml` CLI that
reads any OWL ontology and emits a draft LinkML YAML. The output is then manually
pruned to the subset above.

Steps:
```bash
cd backend
uv add --group dev linkml-owl
uv run linkml-owl-to-linkml \
    --input https://www.w3.org/ns/prov-o \
    --output data/prov-o-raw.linkml.yaml
# Manually prune to the 6 classes + key properties → data/prov-o.linkml.yaml
uv run gen-pydantic data/prov-o.linkml.yaml \
    --output src/models/prov_o.py
```

**Alternatives considered**: Hand-writing the LinkML YAML from scratch (straightforward
but error-prone for URI anchoring); using `rdflib` to walk the OWL graph directly
(requires bespoke transformation code, no reuse).

---

## LinkML Import/Export

### Decision
Add `GET /schemas/{id}/linkml` (export) and `POST /schemas/import/linkml` (import)
to the backend. Both return/accept a `RoundtripResult` that quantifies fidelity loss.
The backend data model remains PostgreSQL-native; LinkML is a serialization surface only.

### Fidelity Loss Points (Known)

| Loss Point                        | Direction     | Notes                                 |
|-----------------------------------|---------------|---------------------------------------|
| slot versioning                   | export        | LinkML slots have no version; emitted as comment |
| `schema_ref` → inline class def   | export        | Must emit referenced schema inline or as import |
| PROV-O metadata                   | export        | No standard LinkML slot; emitted as `annotations` |
| URI stability                     | import        | Imported URIs must be validated against existing registry |
| Alias groups                      | export        | No LinkML concept; emitted as `aliases:` list on slot |
| `confidence_threshold`            | roundtrip     | Custom extension slot; preserved in `extensions` block |

### Rationale
`linkml_runtime` (`yaml_loader`/`yaml_dumper`) already used in `ingestion/`. The
`gen-python` dataclasses are for ingestion adapters; `gen-pydantic` is preferred for
backend models because FastAPI integrates natively with Pydantic v2.

---

## Meta-model YAML (`docs/undata-metamodel.yaml`)

### Decision
Write a self-describing LinkML YAML at `docs/undata-metamodel.yaml` that models the
undata domain concepts (DataElement, DynamicSchema, SemanticGraph, MappingFunction,
ProvenanceRecord). Generate HTML documentation via `gen-doc` + MkDocs. A GitHub
Actions workflow publishes the rendered site to GitHub Pages alongside JupyterBook.

### Rationale
The meta-model YAML is the canonical "what undata is" document. LinkML's `gen-doc`
produces Markdown that MkDocs turns into a searchable, navigable static site.
`class_uri` / `slot_uri` in the YAML anchor concepts to real ontology terms (OBO,
schema.org, PROV-O), making the meta-model machine-readable.

### Key Meta-model Classes

| LinkML class          | `class_uri`              | Notes                               |
|-----------------------|--------------------------|-------------------------------------|
| `DataElement`         | `schema:Property`        | leaf node, typed value              |
| `DynamicSchema`       | `owl:Class`              | dict of DataElements                |
| `SemanticGraph`       | `skos:ConceptScheme`     | ontological anchoring               |
| `MappingFunction`     | `sssom:Mapping`          | pair of elements + transform        |
| `ProvenanceRecord`    | `prov:Bundle`            | PROV-O activity bundle              |
| `DataElementVersion`  | `prov:Entity`            | snapshot of a DataElement at time T |

### gen-doc + GitHub Actions

```yaml
# .github/workflows/metamodel-docs.yml
- run: |
    uv run gen-doc docs/undata-metamodel.yaml -d docs/site/metamodel/
    uv run mkdocs build -f docs/mkdocs.yml
```

Published to `gh-pages` branch alongside the JupyterBook HTML output.

---

## schema_ref FK

### Decision
Add `schema_ref UUID FK → dynamic_schema(id)` on `data_element`. When
`value_type = "object"`, `schema_ref` MUST be set. When `value_type = "array"`,
`items_type` carries the scalar or `schema_ref` resolves the element type.
`DataElementChild` is retained **only** for anonymous inline structures with no
reusable identity.

### Migration
Alembic migration `0010_schema_ref.py`:
```sql
ALTER TABLE data_element
  ADD COLUMN schema_ref UUID REFERENCES dynamic_schema(id) ON DELETE SET NULL;
```
No backfill needed (existing elements are not object-typed).

---

## Alias Semantics

### Decision
Aliases represent `skos:exactMatch` only: same semantic graph, different
label/name. The `AliasGroup` table remains unchanged.

Inferred non-identity mappings (unit-conversion, scaling, structural) are:
- Attributed to a system `prov:Agent` (id = `urn:undata:system`)
- Created with `status = "pending_curation"`
- Auto-accepted when `PUT /mappings/{id}/accept?confidence_threshold=<float>` called
  and the mapping's `confidence_score >= threshold`

### No schema change needed for alias table; `MappingFunction.status` column added.

---

## Alternatives Rejected

| Alternative                            | Rejected Because                                              |
|----------------------------------------|---------------------------------------------------------------|
| Use `prov` Python library              | User explicitly excluded; adds heavyweight dependency         |
| Store PROV-O as RDF triples in Postgres| Adds `pg_rdflib` dependency; JSONB sufficient for query needs |
| Adopt PROV-O as primary data model     | Over-engineering; PostgreSQL relational model is simpler      |
| Separate `provenance` microservice     | Premature; backend owns all provenance for now                |
