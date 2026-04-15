# Data Model: Cross-Source Alignment

**Date**: 2026-04-03 | **Feature**: 041-cross-source-alignment

## Entity Changes

### Extended Entity Fields (in `semantic` JSON)

All entity types (elements, schemas, values, valuesets) gain these optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `aligned_to` | `string` (sha256) | Points to the canonical entity this entity was merged into. Null for canonical entities and unaligned entities. |
| `aligned_members` | `list[string]` (sha256 list) | List of member entity sha256 hashes. Only set on canonical entities. Empty for non-canonical entities. |
| `alignment_score` | `float` (0.0–1.0) | Composite similarity score that led to this entity being aligned. Null for canonical entities. |
| `alignment_signals` | `dict` | Breakdown of alignment signals: `{"name": float, "embedding": float, "ontology": float, "alias": float}`. Null for unaligned. |

### Alignment Candidate (new entity in `alignment_candidates.parquet`)

| Field | Type | Description |
|-------|------|-------------|
| `entity_a` | `string` (sha256) | First entity in candidate pair |
| `entity_b` | `string` (sha256) | Second entity in candidate pair |
| `similarity` | `float` | Similarity score from search |
| `source` | `string` | How the candidate was discovered: `"search"`, `"pipeline"` |
| `created_at` | `string` | ISO timestamp |
| `resolved` | `bool` | Whether this candidate has been evaluated |

## Relationships

```
Canonical Entity (1) ←── aligned_members ──→ (N) Member Entities
Member Entity (N) ←── aligned_to ──→ (1) Canonical Entity

Search Results ──→ Alignment Candidates ──→ Pipeline Alignment
```

### Graph Traversal

- **Find all members of a group**: Read canonical entity's `aligned_members` list
- **Find canonical for a member**: Read member entity's `aligned_to` field
- **Find related groups**: Member entities that share ontology annotations but have different ranges — cross-referenced but NOT merged

## Entity Lifecycle with Alignment

```
Source Data
    ↓
Adapter.to_linkml() → SchemaDefinition
    ↓
SchemaView(schema_def) → Unified slots/aliases
    ↓
extract_from_schema_definition() → ClassifiedEntity[]
    ↓
Staging (ParquetStore)
    ↓
Enrich (ontology annotations)
    ↓
Commit (embeddings computed, sha256 assigned)
    ↓
Align:
  1. Intra-source verification (lightweight)
  2. Cross-source candidate generation (name blocking + embedding k-NN)
  3. Multi-signal scoring
  4. Group formation (union-find)
  5. Canonical designation
  6. Write aligned_to/aligned_members fields
    ↓
Transform
    ↓
Backend Import → PostgreSQL (alignment fields indexed for UI queries)
```

## Validation Rules

- An entity MUST NOT have both `aligned_to` and `aligned_members` set (it's either canonical or member, not both)
- An entity with `aligned_to` set MUST appear in the referenced canonical's `aligned_members` list (bidirectional consistency)
- Entities in the same alignment group MUST have compatible identity properties (same name+type+range, or high multi-signal score)
- Entities with different ranges MUST NOT be in the same alignment group
- `alignment_score` MUST be >= configured threshold (default 0.7) for alignment to occur
