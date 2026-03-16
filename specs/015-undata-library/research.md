# Research: undata-library v2 — Content-Addressed RDF Property Model

**Date**: 2026-03-16

## R1: Content-Addressed Hashing for Semantic Identity

**Decision**: SHA-256 of canonicalized semantic graph → 6-char alphanumeric short key.

**Rationale**: The semantic graph fields (`ontology_term`, `data_type`, `unit`,
`constraints`) are serialized as sorted JSON, hashed with SHA-256, then the first N
bytes are base36-encoded to produce a 6-char key. Base36 (a-z0-9) gives 2.18 billion
keys — collision-free at our scale with a collision check at generation time.

**Canonical form** (hash input):
```json
{"constraints":{"maximum":150,"minimum":0},"data_type":"integer","ontology_term":"http://purl.obolibrary.org/obo/NCIT_C124353","unit":"year"}
```
- Keys sorted alphabetically
- Null/missing fields omitted (not set to null)
- Compact JSON (no whitespace)

**Alternatives considered**:
- UUID v5 (SHA-1): weaker hash, but standard UUID format. Rejected: SHA-256 is stronger.
- Multihash (IPFS): self-describing, future-proof. Rejected: unnecessary complexity.
- Full 64-char hex: too long for filenames/URIs. Truncation via mapping table is cleaner.

## R2: RDF Property Model in LinkML

**Decision**: Use LinkML's native RDF support. Elements map to `rdf:Property`.
Schemas map to `sh:NodeShape`. Relationships are standard RDF predicates.

**Rationale**: LinkML already generates RDF from YAML schemas. By using standard
`class_uri` and `slot_uri` annotations, the library YAML can be consumed directly
by RDF tooling (SPARQL, SHACL validators) without conversion.

**Mapping**:
| undata concept | RDF/SHACL | LinkML annotation |
|---|---|---|
| Element (property) | `rdf:Property` | `class_uri: rdf:Property` |
| Schema (class shape) | `sh:NodeShape` | `class_uri: sh:NodeShape` |
| Property membership | `sh:property` | slot with range = element URI |
| Inheritance | `rdfs:subClassOf` | `is_a:` in LinkML class |
| Mixin composition | `sh:property` on multiple shapes | `mixins:` in LinkML class |
| Alias/equivalence | `owl:equivalentProperty` | Automatic via same content hash |

## R3: Identity vs Provenance Separation (reproschema pattern)

**Decision**: Element files have two top-level sections: `semantic` (identity) and
`provenance` (list of source attestations).

**Rationale**: Follows the reproschema model where an item's identity is its semantic
content (question, response options, ontology mappings), and which protocol/activity
uses it is metadata. This enables automatic deduplication: two elements from different
sources with the same semantic graph are the SAME element.

**Element file structure**:
```yaml
# elements/age_x7k2m9.yaml
semantic:
  ontology_term: http://purl.obolibrary.org/obo/NCIT_C124353
  data_type: integer
  unit: year
  constraints:
    minimum: 0
    maximum: 150

provenance:
  - source: bids
    class: Participant
    name: age
    description: "Age of the participant in years"
    required: true
  - source: nwb
    class: Subject
    name: age
    description: "Age of subject"
  - source: dandi
    class: DandiModel
    name: age
    description: "Age of the subject"
```

## R4: Schema Shape Structure

**Decision**: Schema files list property URIs + inheritance + provenance.

**Schema file structure**:
```yaml
# schemas/participant_a1b2c3.yaml
semantic:
  properties:
    - https://schema.undata.live/elements/age_x7k2m9
    - https://schema.undata.live/elements/sex_y8l3n0
    - https://schema.undata.live/elements/species_z9m4o1
  subclass_of: null
  mixins: []

provenance:
  - source: bids
    name: Participant
    description: "A participant in a study"
  - source: dandi
    name: DandiModel
    description: "Subject metadata"
```

## R5: Handling Underspecified Elements

**Decision**: Elements with missing `ontology_term` use remaining fields for identity.
An element with `{data_type: string}` and no ontology term has a valid but partial
hash. When later enriched with an ontology term, it gets a NEW hash and the old
element file is superseded (with a `superseded_by` link).

**Alternatives considered**:
- Block creation until annotated: Too restrictive for bulk ingestion.
- NLP-based matching: Non-deterministic, fragile.
- Source-scoped fallback: Creates two identity systems. Rejected for simplicity.

## R6: Deduplication Strategy for Current 9,629 Elements

**Decision**: Re-export all elements through the new content-addressed pipeline.
Elements with identical semantic graphs merge automatically. Elements with only
`data_type` (no ontology term) remain separate until enriched.

**Expected outcome**:
- Cross-source duplicates (age, sex, species across 4 sources) → merge to ~60 elements
- Within-source class duplicates (AIND name × 996) → remain separate (different class
  context = different provenance, but may share identity if semantic graph is identical)
- Underspecified elements (data_type only) → remain as-is with partial hashes
- Estimated final count: ~2,000-4,000 unique elements (down from 9,629)
