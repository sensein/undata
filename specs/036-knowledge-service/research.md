# Research: Knowledge Service

## R1: Ontology Source Formats & Integration

| Source | Format | Terms | Download | Parse Method |
|--------|--------|-------|----------|-------------|
| HoMBA | OWL | ~2,341 | `https://purl.brain-bican.org/ontology/homba.owl` | `ontology_store.load_rdf("homba", path, "owl")` |
| NIDM-Terms | JSON-LD/OWL | ~500-1000 | `https://github.com/incf-nidash/nidm-terms` | Convert JSON-LD→OWL via rdflib, then `load_rdf()` |
| DICOM | Python dict + OWL | ~3,000+ | pydicom embedded dict + INCF-NIDASH OWL wrapper | Hybrid: pydicom tags → custom OWL/TTL generation |
| RadLex | OWL | ~58,065 | `https://radlex.org/` (license required) or BioPortal | `ontology_store.load_rdf("radlex", path, "owl")` |
| ReproSchema | JSON-LD | ~200-500 activities | `https://github.com/ReproNim/reproschema-library` | Custom adapter: parse activity/item JSON-LD files |

**Decision**: Use the existing `ontology_store.load_rdf()` and `load_obo()` for OWL/OBO sources. For DICOM, generate a TTL file from pydicom's data dictionary. For NIDM-Terms and ReproSchema, write lightweight converters.

**Rationale**: The existing pyoxigraph-based ontology store already handles OWL, OBO, and TTL. Adding new ontologies is primarily a configuration task (URL + format), not an architecture change.

## R2: OpenNeuro Dataset Access via Datalad

**Decision**: Use datalad to clone OpenNeuro datasets (shallow, metadata-only where possible), then scan for all TSV/CSV files and their JSON sidecars.

**Rationale**: Datalad provides version-controlled access to OpenNeuro datasets without downloading full imaging data. The `datalad clone` + `datalad get` pattern allows selective file retrieval (only metadata files).

**Access pattern**:
1. `datalad clone https://github.com/OpenNeuroDatasets/{dataset_id}.git` (shallow clone)
2. Scan for `*.tsv`, `*.csv` files (participants.tsv, phenotype/*.tsv, etc.)
3. For each TSV, check for `{basename}.json` sidecar describing columns
4. Extract column headers as element names, infer data types from values
5. Source provenance: `openneuro/{dataset_id}`

**Dataset discovery**: OpenNeuro GraphQL API at `https://openneuro.org/crn/graphql` — query for new datasets since last check.

## R3: ReproSchema Library Integration

**Decision**: Write a ReproSchema adapter that parses the library's JSON-LD activity/item files into LinkML, then uses the standard extractor.

**Rationale**: ReproSchema uses JSON-LD with a well-defined schema. Activities map to schemas (CLASS entities), items map to elements (ATTRIBUTE entities). The JSON-LD structure includes response options, value constraints, and descriptions.

**Source**: `https://github.com/ReproNim/reproschema-library`
- Activities in `activities/` → SchemaRecord entities
- Items in `activities/{name}/items/` → ElementRecord entities
- Response options → ValueSet entities

## R4: Element Versioning

**Decision**: Use the existing Transform model with `function_type: "curation_update"` to link old→new element versions. Add a `superseded_by` field to elements (optional, points to new sha256).

**Rationale**: Element identity is content-addressed (sha256). When a semantic field changes, the hash changes automatically. A curation_update transform explicitly records the link. No new DB model needed.

## R5: LLM Enrichment Skills

**Decision**: Use litellm (already a backend dependency) for LLM calls. Define structured tool schemas for each enrichment skill. Use batch processing with configurable concurrency and token budget.

**Skills**:
1. `suggest_ontology_annotation` — given element context, search ontology store, propose best match with reasoning
2. `suggest_unit` — given element name+description, propose unit with justification
3. `assess_alignment` — given two elements, assess if they're the same concept or different variants
4. `generate_description` — given element name+type+source, generate descriptive text

**Rationale**: LLM tools are already defined in the curation chat system (feature 034). Extending with enrichment-specific tools is incremental.

## R6: Ingestion Queue & Discovery

**Decision**: Add `IngestionJob` DB model for the queue. Background task polls approved repository APIs on schedule (configurable, default daily). Pre-approved sources auto-ingest; others queue for review.

**Approved sources** (auto-ingest with known adapters):
- OpenNeuro → BIDS adapter (via datalad)
- DANDI Archive → DANDI adapter
- ReproSchema Library → ReproSchema adapter

**Discovery endpoints**:
- OpenNeuro: `https://openneuro.org/crn/graphql` → datasets query
- DANDI: `https://api.dandiarchive.org/api/dandisets/` → list endpoint
