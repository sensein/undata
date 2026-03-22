# Data Model: 027 Library Hardening, Pipeline Optimization, UI/DB Rebuild

## Core Entities (existing — from library registry)

### Element
Content-addressed data element (rdf:Property). Identity = two-mode hash.
- `sha256`: string (content hash)
- `semantic`: SemanticIdentity (data_type, unit, pattern, response_options, min/max, description, ontology_annotations)
- `provenance`: list[ProvenanceEntry] (source, class, name, description, PROV-O fields)

### Schema
Class shape (sh:NodeShape). Lists property references.
- `sha256`: string
- `semantic`: SchemaIdentity (properties, subclass_of, mixins, description, ontology_annotations)
- `provenance`: list[ProvenanceEntry]

### Value
Categorical value concept.
- `sha256`: string
- `semantic`: ValueSemanticIdentity (label, value_type, description, ontology_annotations)
- `provenance`: list[ProvenanceEntry]

### ValueSet
Named collection of value references.
- `sha256`: string
- `semantic`: ValueSetIdentity (name, members, description, ontology_annotations)
- `provenance`: list[ProvenanceEntry]

### Transform
Bidirectional mapping between elements.
- `source_element`: string (element URI)
- `target_element`: string (element URI)
- `function`: FunctionSpec (type, expression, parameters)
- `confidence`: float
- `provenance`: list[ProvenanceEntry]

## New Entities (027)

### CurationFlag
Machine-generated flag requiring human review.
- `id`: UUID
- `entity_type`: enum (element, schema, value, valueset, transform)
- `entity_ref`: string (file path or content hash)
- `flag_type`: enum (low_confidence, ambiguous_match, multiple_candidates, unknown_transform, needs_review, suspicious_source, provenance_bloat)
- `context`: dict (candidate_matches: list[{uri, score, label}], reason: string)
- `llm_verification`: dict | None (model, response, confidence, justification)
- `status`: enum (pending, approved, rejected, deferred)
- `created_at`: ISO 8601 timestamp
- `resolved_at`: ISO 8601 timestamp | None
- `resolved_by`: string | None (user identity)
- `resolution_note`: string | None

### RunSummary
Per-pipeline-run report.
- `run_id`: string
- `source`: string
- `started_at`: ISO 8601
- `completed_at`: ISO 8601
- `entity_counts`: dict (elements, schemas, values, valuesets per stage)
- `enrichment_rate`: dict (ontology_assigned, value_domain_set per type)
- `curation_flags`: dict (by flag_type: count)
- `delta`: dict | None (comparison to previous run: added, removed, modified per type)
- `timing`: dict (extract_s, enrich_s, commit_s, align_s, transform_s)

### Contribution (UI/DB layer)
User-submitted suggestion on an entity.
- `id`: UUID
- `entity_type`: enum
- `entity_id`: UUID (database ID)
- `contributor_id`: UUID (user)
- `contribution_type`: enum (suggest_annotation, comment, flag_issue, suggest_edit)
- `content`: dict (proposed annotation, comment text, etc.)
- `status`: enum (pending, approved, rejected)
- `reviewed_by`: UUID | None
- `reviewed_at`: ISO 8601 | None
- `review_note`: string | None
- `created_at`: ISO 8601

### User (UI/DB layer)
- `id`: UUID
- `external_sub`: string (OIDC subject)
- `email`: string
- `display_name`: string
- `role`: enum (contributor, curator, admin)
- `created_at`: ISO 8601

## Relationships

```
Element ─── ontology_annotations ──→ OntologyAnnotation (embedded list)
Element ←── properties ──── Schema
Element ←── response_options ──→ Value (via label match)
Element ←── source/target ──── Transform
Value ←── members ──── ValueSet
Any entity ←── entity_ref ──── CurationFlag
Any entity ←── entity_id ──── Contribution
Contribution ←── contributor_id ──── User
CurationFlag ←── resolved_by ──── User
```

## State Transitions

### CurationFlag lifecycle
```
pending → approved (curator approves machine annotation)
pending → rejected (curator rejects annotation)
pending → deferred (curator defers decision)
```

### Contribution lifecycle
```
pending → approved (curator accepts suggestion)
pending → rejected (curator rejects suggestion)
```

### Pipeline entity lifecycle
```
extracted (UUID file in staging) → enriched (in-place annotations) → committed (content-addressed in registry)
```
