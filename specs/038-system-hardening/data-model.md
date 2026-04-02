# Data Model: System Hardening

## New Entities

### EvidenceChain (embedded in proposals and annotations)

Not a DB table — embedded as JSONB in annotations, proposals, and audit log entries.

| Field | Type | Description |
|-------|------|-------------|
| similarity_score | float | Cosine similarity (0.0-1.0) between element and matched term |
| similarity_method | string | "cosine_embedding", "exact_name", "llm_reasoning" |
| source_text | string | The element text that was matched (name + description) |
| target_term_uri | string | URI of the matched ontology term |
| target_term_label | string | Label of the matched term |
| target_term_definition | string | Definition from the ontology |
| uri_verified | boolean | Whether the URI was verified as reachable |
| reasoning | string | Step-by-step explanation of why the match was made |

### VersionTransition (embedded in provenance entries)

Recorded when an ontology or source is updated.

| Field | Type | Description |
|-------|------|-------------|
| dependency_type | string | "ontology" or "source" |
| dependency_name | string | e.g., "homba", "bids" |
| old_version | string | Previous checksum or version tag |
| new_version | string | New checksum or version tag |
| affected_entities | integer | Number of entities re-enriched |
| timestamp | string (ISO 8601) | When the transition occurred |

## Modified Entities

### OntologyAnnotation (add evidence field)

| New Field | Type | Description |
|-----------|------|-------------|
| evidence | EvidenceChain (nullable) | Evidence supporting this annotation |

### TransformRecord (extend for many-to-one)

| New Field | Type | Description |
|-----------|------|-------------|
| source_elements | list[string] (nullable) | For many-to-one: list of source element sha256/URIs |

### LLMEnrichmentProposal (add evidence field)

| New Field | Type | Description |
|-----------|------|-------------|
| evidence | EvidenceChain (nullable) | Evidence supporting this proposal |

## Relationships

- EvidenceChain → OntologyAnnotation: every annotation can carry its evidence
- EvidenceChain → LLMEnrichmentProposal: every proposal carries its evidence
- VersionTransition → provenance: recorded as a provenance entry on affected entities
- TransformRecord.source_elements → Element[]: many-to-one mapping
