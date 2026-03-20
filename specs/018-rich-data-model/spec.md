# Feature Specification: Rich Data Element Model

**Feature Branch**: `018-rich-data-model`
**Created**: 2026-03-17
**Status**: Draft
**Input**: Enrich the data element and schema models using reproschema Item semantics,
W3C PROV-O provenance, ontology alignment verification, semantic similarity scoring,
valueset-based alias detection, and underscore-prefixed entry reclassification.

---

## Clarifications

### Session 2026-03-17

- Q: What should the canonical data element model include? → A: reproschema Item model minus UI fields (data_type, response_options/choices, value constraints/range, question_text, unit, minValue/maxValue). NDA/CDE fields map as provenance metadata, not identity.
- Q: How should underscore-prefixed elements be handled? → A: Reclassify as ValueConcepts with source-qualified tags (e.g., aind.instrument.manufacturer.Abcam). Filter from element extraction.
- Q: How should alias detection use value ranges and valuesets? → A: Similarity scoring with SKOS/LinkML mapping relations (exactMatch, broadMatch, narrowMatch, closeMatch, relatedMatch). Range overlap + valueset Jaccard as confidence score. Threshold-based detection.
- Q: Should W3C PROV-O provenance replace the current flat model? → A: PROV-O enriched flat — current fields + generated_at, attributed_to, activity, derived_from. Flat YAML with PROV-O semantics.
- Q: How should ontology alignment verification work? → A: Bundled offline ontology cache (NCIT, PATO, HP, OBI, NCBITaxon) with refresh/extend CLI command. Check URI existence + label similarity. No live API calls during validation.

---

## Overview

Extend the undata-library data element model to be richer and more standards-aligned:

1. **reproschema-aligned SemanticIdentity** — add `response_options` (choices/valueset),
   `question_text`, `value_domain`, `min_value`/`max_value` to the identity block
2. **W3C PROV-O provenance** — enrich provenance entries with `generated_at`,
   `attributed_to`, `activity`, `derived_from`
3. **Underscore entry reclassification** — filter `_Abcam`, `_Nikon` etc. from elements
   into ValueConcepts with source-qualified tags
4. **Ontology alignment verification** — bundled ontology cache with term existence +
   label similarity checking; `undata-library ontology refresh` CLI
5. **Semantic similarity scoring** — embedding-based element similarity; alias detection
   using range overlap + valueset Jaccard + SKOS mapping relations
6. **Valueset-as-mapping-table** — valuesets (response_options.choices) treated as mapping
   tables between sources; shared choices = evidence of alias relationship

---

## Requirements

### Functional Requirements

**Enriched SemanticIdentity (reproschema-aligned)**

- **FR-001**: `SemanticIdentity` MUST add optional fields: `response_options` (list of
  choice objects with `value`, `label`, `ontology_term`), `question_text` (preferred
  question/label), `value_domain` (categorical/numeric/text/date/boolean), `min_value`,
  `max_value`.
- **FR-002**: `response_options` MUST reference ValueConcept URIs when values have been
  ingested. Raw string choices are acceptable when value concepts don't exist yet.
- **FR-003**: `min_value`/`max_value` MUST be part of the identity hash when present —
  elements with different ranges are different elements (linked by mapping).
- **FR-004**: `question_text` and `value_domain` MUST NOT be part of the identity hash —
  they are descriptive metadata that varies by source.

**W3C PROV-O Provenance**

- **FR-005**: `ProvenanceEntry` MUST add fields: `generated_at` (ISO 8601 datetime),
  `attributed_to` (agent URI: system URN, ORCID, or user ID), `activity` (enum:
  ingestion/curation/enrichment/migration), `derived_from` (element URI or null).
- **FR-006**: All ingestion operations MUST populate `generated_at` and `attributed_to`
  automatically. `activity` defaults to `ingestion`.
- **FR-007**: Curation events (manual ontology annotation, description edit) MUST create
  a new provenance entry with `activity: curation` and the curator's identity.

**Underscore Entry Reclassification**

- **FR-008**: AIND extractor MUST filter entries where the `$defs` model name starts with
  `_` and reclassify them as ValueConcepts.
- **FR-009**: Reclassified values MUST use source-qualified tags:
  `{source}.{schema}.{class}.{value}` (e.g., `aind.instrument.manufacturer.Abcam`).
- **FR-010**: Element count MUST decrease after reclassification (fewer elements, more values).

**Ontology Alignment Verification**

- **FR-011**: `undata-library ontology cache` directory MUST bundle pre-downloaded term
  data for: NCIT, PATO, HP, OBI, NCBITaxon (at minimum).
- **FR-012**: Cache format: one YAML file per ontology with `{term_uri: {label, synonyms,
  parents, deprecated}}` entries.
- **FR-013**: `undata-library verify` CLI MUST check each element's `ontology_term`:
  (a) exists in cache, (b) label similarity to element name > 0.5, (c) term not deprecated.
  Report misalignments as warnings.
- **FR-014**: `undata-library ontology refresh [--ontology NAME]` CLI MUST fetch latest
  terms from OLS API and update the cache. Support incremental refresh.

**Semantic Similarity and Alias Detection**

- **FR-015**: `undata-library similarity` CLI MUST compute pairwise similarity between
  elements using: (a) ontology_term match, (b) name embedding similarity
  (sentence-transformers), (c) range overlap (numeric intersection / union),
  (d) valueset Jaccard (shared choices / total choices).
- **FR-016**: Similarity output MUST include a SKOS mapping relation type:
  `skos:exactMatch` (score ≥ 0.95), `skos:closeMatch` (0.8-0.95),
  `skos:broadMatch`/`skos:narrowMatch` (one range subsumes another),
  `skos:relatedMatch` (0.5-0.8).
- **FR-017**: `undata-library detect-aliases` CLI MUST scan all elements, compute
  similarities, and output candidate alias pairs with relation type and confidence.
- **FR-018**: Valueset overlap MUST contribute to alias confidence — if two elements
  share >50% of their response_options choices, they are alias candidates.

### Non-Functional Requirements

- **NFR-001**: Ontology cache MUST be < 50MB total (compressed term labels, not full OWL).
- **NFR-002**: `verify` on 3,000 elements MUST complete in < 30 seconds (cache-based).
- **NFR-003**: `similarity` between two elements MUST complete in < 100ms.
- **NFR-004**: `detect-aliases` on 3,000 elements MUST complete in < 5 minutes.

---

## Key Entities (Changes)

### SemanticIdentity (enriched)

```yaml
semantic:
  ontology_term: uriorcurie | null
  data_type: DataType
  unit: string | null
  constraints:
    minimum: number | null      # renamed from min for clarity
    maximum: number | null
    pattern: string | null
    allowed_values: list[str] | null
  # NEW fields (reproschema-aligned):
  response_options:             # structured choices with ontology links
    - value: string
      label: string
      ontology_term: uriorcurie | null
  question_text: string | null  # preferred question/label (NOT in hash)
  value_domain: string | null   # categorical | numeric | text | date | boolean (NOT in hash)
  min_value: number | null      # explicit range bound (IN hash)
  max_value: number | null      # explicit range bound (IN hash)
```

### ProvenanceEntry (PROV-O enriched)

```yaml
provenance:
  - source: string
    class: string
    name: string
    description: string | null
    required: boolean | null
    multivalued: boolean | null
    # NEW PROV-O fields:
    generated_at: datetime       # prov:generatedAtTime
    attributed_to: uriorcurie    # prov:wasAttributedTo
    activity: string             # ingestion | curation | enrichment | migration
    derived_from: uriorcurie | null  # prov:wasDerivedFrom
```

### Ontology Cache

```yaml
# ontology-cache/ncit.yaml
ontology: NCIT
version: "24.10e"
fetched_at: "2026-03-17T12:00:00Z"
terms:
  http://purl.obolibrary.org/obo/NCIT_C25150:
    label: Age
    synonyms: ["age", "patient age"]
    parents: ["http://purl.obolibrary.org/obo/NCIT_C25347"]
    deprecated: false
  http://purl.obolibrary.org/obo/NCIT_C45293:
    label: Species
    synonyms: ["organism species"]
    parents: ["http://purl.obolibrary.org/obo/NCIT_C14250"]
    deprecated: false
```

---

## Success Criteria

- **SC-001**: `SemanticIdentity` includes response_options, min_value, max_value fields.
- **SC-002**: Provenance entries include generated_at, attributed_to, activity.
- **SC-003**: Underscore elements reclassified — element count drops, value count increases.
- **SC-004**: `undata-library verify` reports misaligned ontology terms.
- **SC-005**: `undata-library detect-aliases` finds cross-source alias candidates with SKOS relations.
- **SC-006**: Ontology cache bundled and refreshable.
