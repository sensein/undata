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

### Session 2026-03-20

- Q: What operations should the enrich step perform? → A: Auto-assign ontology_term via name→cache matching + resolve response_options to ValueConcept URIs + auto-populate value_domain from data_type. min/max already handled at ingestion time.
- Q: What should the align step produce? → A: Re-run alias detection post-enrichment, update alias groups on elements, track all changes as provenance entries. Alignment modifies elements with full provenance traceability.
- Q: Should ingest/enrich/align be one command or separate? → A: Separate `ingest`, `enrich`, `align` CLI commands + a convenience `pipeline` command that chains all three.
- Q: How to handle enrichment changing semantic identity? → A: Content-addressed identity means changing ontology_term produces a new element (new hash/URI). Old element is never deleted (may be referenced by schemas). New element gets `derived_from` pointing to old element.
- Q: What happens to old elements after enrichment? → A: No elements are ever deleted. New enriched element has `derived_from` → old element URI. Old element retained because it may be used in schemas.
- Q: What text should the semantic embedding combine? → A: `"{class} {attribute_name}: {description}"` — class disambiguates, description provides domain context.
- Q: Should embeddings be precomputed or on-the-fly? → A: Precomputed in `embeddings.parquet` (URI + vector columns), regenerated on enrich or explicit rebuild. Optimized for storage/access.
- Q: How should semantic embedding integrate with similarity scoring? → A: Replace `name_sim` component (0.3 weight) with `semantic_embedding` — richer embedding subsumes bare name similarity. Same 4-component architecture.
- Q: Should ontology alignment use embeddings too? → A: Yes — ontology terms also get embeddings; enrich matches element embeddings against ontology term embeddings for assignment.
- Q: Which embedding model? → A: Configurable with `--model` flag, default `all-MiniLM-L6-v2` (384-dim). Allows upgrade to larger models when needed.

---

## Overview

Extend the undata-library data element model to be richer and more standards-aligned,
and define the **ingest → enrich → align** pipeline:

1. **reproschema-aligned SemanticIdentity** — add `response_options` (choices/valueset),
   `question_text`, `value_domain`, `min_value`/`max_value` to the identity block
2. **W3C PROV-O provenance** — enrich provenance entries with `generated_at`,
   `attributed_to`, `activity`, `derived_from`
3. **Underscore entry reclassification** — filter `_Abcam`, `_Nikon` etc. from elements
   into ValueConcepts with source-qualified tags
4. **Ontology alignment verification** — bundled ontology cache with term existence +
   label similarity checking; `undata-library ontology refresh` CLI
5. **Semantic embedding layer** — precomputed embeddings from `"{class} {name}: {description}"`
   stored in `embeddings.parquet`; configurable model (default `all-MiniLM-L6-v2`);
   used for similarity scoring, alias detection, and ontology alignment
6. **Semantic similarity scoring** — embedding-based element similarity; alias detection
   using range overlap + valueset Jaccard + SKOS mapping relations
7. **Valueset-as-mapping-table** — valuesets (response_options.choices) treated as mapping
   tables between sources; shared choices = evidence of alias relationship
8. **Enrichment pipeline** — `enrich` command auto-assigns `ontology_term` via embedding
   distance against ontology term embeddings, resolves `response_options` to ValueConcept
   URIs, auto-populates `value_domain`. Identity-changing enrichments produce new elements
   with `derived_from` provenance links.
9. **Alignment pipeline** — `align` command re-runs alias detection post-enrichment
   using precomputed embeddings, updates alias groups, tracks changes with provenance.
10. **Pipeline orchestration** — `pipeline` convenience command chains
    `ingest → enrich → align` as a single invocation

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
- **FR-007**: *(Deferred — manual curation workflow, not part of ingest→enrich→align pipeline.)*
  Curation events (manual ontology annotation, description edit) MUST create
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

**Semantic Embedding Layer**

- **FR-015**: Each element MUST have a semantic embedding computed from the text
  `"{class} {attribute_name}: {description}"`, where class and description come from
  provenance entries. Missing description is omitted (text degrades gracefully).
- **FR-016**: Embeddings MUST be precomputed and stored in `embeddings.parquet`
  (columns: `uri`, `text`, `vector`) in the library root. Parquet format for efficient
  columnar storage and access. Regenerated on `enrich` or via explicit
  `undata-library embed [PATH]` command.
- **FR-017**: Embedding model MUST be configurable via `--model` flag (default:
  `all-MiniLM-L6-v2`, 384-dim). Model name stored in parquet metadata for consistency
  checks on reload.
- **FR-018**: Ontology terms in the cache MUST also have precomputed embeddings
  (from `"{label}: {synonyms joined}"`) stored in `ontology-cache/embeddings.parquet`.
  Used by `enrich` for ontology_term assignment via embedding distance.

**Semantic Similarity and Alias Detection**

- **FR-019**: `undata-library similarity` CLI MUST compute pairwise similarity between
  elements using: (a) ontology_term match (weight 0.4), (b) semantic embedding cosine
  distance (weight 0.3), (c) range overlap (weight 0.15), (d) valueset Jaccard
  (weight 0.15). The semantic embedding replaces the former bare-name similarity.
- **FR-020**: Similarity output MUST include a SKOS mapping relation type:
  `skos:exactMatch` (score ≥ 0.95), `skos:closeMatch` (0.8-0.95),
  `skos:broadMatch`/`skos:narrowMatch` (one range subsumes another),
  `skos:relatedMatch` (0.5-0.8).
- **FR-021**: `undata-library detect-aliases` CLI MUST scan all elements, compute
  similarities using precomputed embeddings from `embeddings.parquet`, and output
  candidate alias pairs with relation type and confidence.
- **FR-022**: Valueset overlap MUST contribute to alias confidence — if two elements
  share >50% of their response_options choices, they are alias candidates.

**Enrichment Pipeline (post-ingestion)**

- **FR-023**: `undata-library enrich` CLI MUST auto-assign `ontology_term` to elements
  that lack one by computing cosine distance between element embeddings and ontology term
  embeddings (from `ontology-cache/embeddings.parquet`). Best match above a configurable
  threshold (default 0.7) is assigned.
- **FR-024**: `enrich` MUST resolve `response_options` values to ValueConcept URIs where
  matching ValueConcepts exist in the library. Unresolved values remain as raw strings.
- **FR-025**: `enrich` MUST auto-populate `value_domain` from `data_type`:
  string→text, integer/float→numeric, boolean→boolean, array/object→left null.
  Elements with `response_options` get `value_domain: categorical` regardless of data_type.
- **FR-026**: When enrichment changes an identity-hash field (e.g., assigns `ontology_term`),
  a **new element** MUST be created with a new content-addressed URI. The new element's
  provenance MUST include `derived_from` pointing to the old element's URI and
  `activity: enrichment`.
- **FR-027**: Old elements MUST NOT be deleted — they may be referenced by schemas. Only
  new elements are created; originals are retained as-is.
- **FR-028**: `enrich` MUST be idempotent — re-running on already-enriched elements with
  no changes MUST produce no new elements or provenance entries.
- **FR-029**: `enrich` MUST regenerate `embeddings.parquet` after creating any new elements
  (new enriched elements need embeddings for subsequent alignment).

**Alignment Pipeline (post-enrichment)**

- **FR-030**: `undata-library align` CLI MUST re-run alias detection across all elements
  using precomputed embeddings from `embeddings.parquet`.
- **FR-031**: `align` MUST update alias groups: elements with `skos:exactMatch` (≥ 0.95)
  share the same content-addressed URI (by design); elements with `skos:closeMatch`
  (0.8–0.95) are recorded as alias candidates with SKOS relation metadata.
- **FR-032**: All alias group changes MUST be tracked as provenance entries with
  `activity: enrichment` and `attributed_to: urn:undata:alignment-pipeline`.
- **FR-033**: `align` MUST produce an alignment report (YAML) summarizing: new alias
  groups formed, alias groups unchanged, total element pairs evaluated, and per-pair
  SKOS relation + confidence score.

**Pipeline Orchestration**

- **FR-034**: `undata-library pipeline` CLI MUST chain `ingest → enrich → align` in
  sequence, passing the library path through each step.
- **FR-035**: `pipeline` MUST accept `--source` (required), `--path` (schema files),
  `--library-path`, `--model` (embedding model), and `--skip-enrich` / `--skip-align`
  flags to allow partial runs.
- **FR-036**: `pipeline` MUST report aggregate stats: elements ingested, elements enriched
  (new + unchanged), alias pairs detected, and elapsed time per step.

### Non-Functional Requirements

- **NFR-001**: Ontology cache MUST be < 50MB total (compressed term labels, not full OWL).
- **NFR-002**: `verify` on 3,000 elements MUST complete in < 30 seconds (cache-based).
- **NFR-003**: `similarity` between two elements MUST complete in < 100ms.
- **NFR-004**: `detect-aliases` on 3,000 elements MUST complete in < 5 minutes.
- **NFR-005**: `enrich` on 3,000 elements MUST complete in < 60 seconds.
- **NFR-006**: Embedding generation (`embed`) for 3,000 elements MUST complete in < 30 seconds.

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

### Embedding Store

```
# embeddings.parquet — element embeddings
Columns:
  uri: string              # element URI (primary key)
  text: string             # input text "{class} {name}: {description}"
  vector: list[float32]    # embedding vector (384-dim for MiniLM)

# Parquet metadata:
  model: string            # e.g. "all-MiniLM-L6-v2"
  generated_at: string     # ISO 8601

# ontology-cache/embeddings.parquet — ontology term embeddings
Columns:
  term_uri: string         # ontology term URI (primary key)
  text: string             # input text "{label}: {synonyms joined}"
  vector: list[float32]    # embedding vector (same model as element embeddings)
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
- **SC-007**: `undata-library enrich` auto-assigns ontology_term, resolves response_options URIs, populates value_domain.
- **SC-008**: Identity-changing enrichment creates new element with `derived_from` link; old element retained.
- **SC-009**: `undata-library align` produces alias groups with SKOS relations and alignment report YAML.
- **SC-010**: `undata-library pipeline` chains ingest → enrich → align and reports aggregate stats.
- **SC-011**: `enrich` is idempotent — re-run on unchanged elements produces no new artifacts.
- **SC-012**: `embeddings.parquet` generated with URI + text + vector columns; loadable via pyarrow/pandas.
- **SC-013**: Ontology term embeddings in `ontology-cache/embeddings.parquet`; used by `enrich` for ontology_term assignment.
- **SC-014**: `similarity` and `detect-aliases` use semantic embeddings (class+name+description) instead of bare name similarity.
- **SC-015**: Embedding model configurable via `--model` flag; default `all-MiniLM-L6-v2`.
