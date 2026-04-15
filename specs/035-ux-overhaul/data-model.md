# Data Model: UX & UI Overhaul

## New Entities

### LinkHealthCheck

Tracks reachability of external URI domains and ontology base-URI prefixes.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| check_type | string | "domain" or "ontology_prefix" |
| target | string | Domain (e.g., "purl.obolibrary.org") or ontology prefix (e.g., "http://purl.obolibrary.org/obo/NCIT_") |
| http_status | integer | Last HTTP status code (200, 301, 404, 0=unreachable) |
| redirect_target | string (nullable) | Final URL after redirect chain |
| is_healthy | boolean | True if status 2xx/3xx |
| affected_entity_count | integer | Number of entities referencing URIs under this domain/prefix |
| checked_at | timestamp | When this check was performed |
| created_at | timestamp | First check timestamp |

**Uniqueness**: (check_type, target) — one record per domain or prefix, updated each run.

### SearchResult (virtual — not persisted)

Returned by the global search endpoint, not stored.

| Field | Type | Description |
|-------|------|-------------|
| entity_type | string | "element", "schema", "value", "valueset", "transform" |
| sha256 | string | Entity identifier |
| name | string | Display name (provenance name or label) |
| match_type | string | "lexical" or "semantic" |
| score | float | Relevance score (1.0 for exact lexical, 0.0–1.0 for semantic) |
| snippet | string | Matching text excerpt |

## Modified Entities

### Element (add columns)

| New Field | Type | Description |
|-----------|------|-------------|
| embedding | vector(384) | all-MiniLM-L6-v2 embedding of name+description |
| search_tsv | tsvector | Full-text search vector from provenance name + description |

### Schema (add columns)

| New Field | Type | Description |
|-----------|------|-------------|
| embedding | vector(384) | Embedding of name+description |
| search_tsv | tsvector | Full-text search vector |

### Value (add columns)

| New Field | Type | Description |
|-----------|------|-------------|
| embedding | vector(384) | Embedding of label+description |
| search_tsv | tsvector | Full-text search vector |

### ValueSet (add columns)

| New Field | Type | Description |
|-----------|------|-------------|
| embedding | vector(384) | Embedding of name+description |
| search_tsv | tsvector | Full-text search vector |

### SemanticIdentity (library model — add optional field)

| New Field | Type | Description |
|-----------|------|-------------|
| structural_type | string (nullable) | For array elements: mathematical structure type (e.g., "affine_matrix"). NOT included in identity hash. Used by transform validation. |

## Relationships

- LinkHealthCheck → entities: One check covers many entities (via domain/prefix matching at query time, not FK)
- Element.embedding → used by global search for semantic similarity
- SemanticIdentity.structural_type → used by transform pipeline validation

## Indexes

- GIN index on `search_tsv` for each entity table (full-text search)
- IVFFlat or HNSW index on `embedding` for each entity table (vector similarity)
- Index on `link_health_checks(check_type, target)` for status page queries
