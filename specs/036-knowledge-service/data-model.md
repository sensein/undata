# Data Model: Knowledge Service

## New Entities

### OntologySource

Tracks registered ontologies in the ontology store.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | string | Short name (e.g., "homba", "nidm", "dicom", "radlex") |
| display_name | string | Human-readable name |
| url | string | Download URL or source path |
| format | string | "owl", "obo", "ttl", "json-ld", "pydicom" |
| term_count | integer | Number of terms loaded |
| active | boolean | Whether this ontology is used for enrichment |
| last_refreshed_at | timestamp | When the terms were last loaded |
| checksum | string (nullable) | Hash of the downloaded file for change detection |
| created_at | timestamp | When first registered |

### IngestionJob

Tracks queued and completed ingestion runs.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| repository_url | string | Source URL or identifier (e.g., "openneuro/ds000228") |
| adapter_type | string | Adapter used (e.g., "bids", "dandi", "reproschema", "csv") |
| status | string | "pending", "approved", "running", "completed", "failed" |
| auto_approved | boolean | True if from pre-approved source |
| entity_counts | JSONB | {elements, schemas, values, valuesets} created/merged |
| error_message | string (nullable) | Error details if failed |
| approved_by | string (nullable) | Curator email/name who approved |
| started_at | timestamp (nullable) | When ingestion started |
| completed_at | timestamp (nullable) | When ingestion finished |
| created_at | timestamp | When queued |

**State transitions**: pending → approved → running → completed/failed

### LLMEnrichmentProposal

Tracks LLM-generated enrichment proposals for curator review.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| entity_type | string | "element", "schema", "value", "valueset" |
| entity_ref | string | sha256 of the target entity |
| proposal_type | string | "ontology_annotation", "unit_correction", "description", "alignment" |
| proposed_value | JSONB | The proposed change (annotation dict, unit string, etc.) |
| reasoning | text | LLM's explanation for the proposal |
| confidence | float | LLM self-assessed confidence 0.0-1.0 |
| status | string | "pending", "approved", "rejected" |
| reviewed_by | string (nullable) | Curator who reviewed |
| reviewed_at | timestamp (nullable) | When reviewed |
| created_at | timestamp | When proposed |

## Modified Entities

### Element (add optional field)

| Field | Type | Description |
|-------|------|-------------|
| superseded_by | string (nullable) | sha256 of the new version if this element was updated via curation |
| curated_annotations | JSONB (nullable) | Annotations approved by curators (protected from re-enrichment overwrite) |

### SemanticIdentity (library model)

No changes — curated annotations are stored separately from ontology_annotations to avoid hash changes for metadata-only updates.

## Relationships

- OntologySource → ontology_annotations: Terms from this source appear in entity annotations
- IngestionJob → entities: Job produces elements, schemas, values, valuesets
- LLMEnrichmentProposal → entity: Proposal targets a specific entity by sha256
- Element.superseded_by → Element: Version chain linking old→new
- Transform (function_type="curation_update") → Element pair: Links old element to new version

## Indexes

- `ontology_sources(name)` — unique by short name
- `ingestion_jobs(status)` — for queue queries
- `ingestion_jobs(repository_url)` — for dedup checks
- `llm_enrichment_proposals(entity_type, entity_ref, status)` — for pending proposals per entity
