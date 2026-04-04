# Contract: Alignment Pipeline

## Library API

### `align_entities()`

```
align_entities(
    registry_path: Path,
    entity_types: list[str] = ["elements", "schemas", "values", "valuesets"],
    threshold: float = 0.7,
    weights: dict = {"name": 0.3, "embedding": 0.3, "ontology": 0.25, "alias": 0.15},
    dry_run: bool = False,
    backend: StorageBackend | None = None,
) -> AlignmentReport
```

**Returns**: `AlignmentReport` dict with:
- `total_entities_processed: int`
- `alignment_groups: int` — number of groups formed
- `canonical_entities: int` — designated canonicals
- `member_entities: int` — entities merged into groups
- `unaligned_entities: int` — entities with no matches
- `conflicts: int` — flagged metadata conflicts
- `candidates_from_search: int` — search-suggested candidates evaluated
- `entity_type_breakdown: dict[str, dict]` — per-type stats

### `build_schemaview(schema_def: SchemaDefinition) -> SchemaView`

Constructs a SchemaView from a SchemaDefinition for slot dedup analysis.

### `compute_alignment_score(entity_a: dict, entity_b: dict, weights: dict) -> AlignmentScore`

```
AlignmentScore = {
    "composite": float,  # weighted sum
    "name": float,       # normalized name similarity (0-1)
    "embedding": float,  # cosine similarity (0-1)
    "ontology": float,   # annotation overlap ratio (0-1)
    "alias": float,      # alias hint match (0 or 0.95)
}
```

## Adapter Contract

All adapters MUST implement `to_linkml() -> SchemaDefinition`:

```
class BaseAdapter:
    def to_linkml(self) -> SchemaDefinition:
        """Return a LinkML SchemaDefinition representing the source schema.

        The SchemaDefinition MUST:
        - Have all slots that represent entity fields
        - Use slot aliases for known alternative names
        - Use enums for categorical value domains
        - Use classes for logical groupings (schemas, structures, activities)
        """
        ...
```

## GraphQL Contract

### Query: Entity Alignment

```graphql
type Element {
  # ... existing fields ...
  alignedTo: Element          # canonical entity (null if this IS canonical or unaligned)
  alignedMembers: [Element!]  # member entities (empty if not canonical)
  alignmentScore: Float       # score that led to alignment (null if canonical/unaligned)
}

# Same pattern for Schema, Value, ValueSet types
```

### Query: Alignment Candidates

```graphql
type AlignmentCandidate {
  entityA: Entity!
  entityB: Entity!
  similarity: Float!
  source: String!  # "search" or "pipeline"
  createdAt: String!
}

type Query {
  alignmentCandidates(resolved: Boolean, first: Int): [AlignmentCandidate!]!
}
```

### Mutation: Record Search-Based Candidates

```graphql
type Mutation {
  recordAlignmentCandidates(
    pairs: [AlignmentCandidateInput!]!
  ): Int!  # number of candidates recorded
}
```

This mutation is called automatically by the search resolver when semantic/both mode returns multiple unaligned entities with similarity > 0.8.
