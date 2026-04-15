# Feature Specification: Ontology Expansion, Deduplication, and Precision Matching

**Feature Branch**: `025-ontology-expansion`
**Created**: 2026-03-21
**Status**: Draft
**Input**: Extend the ontology set beyond the 5 initial ontologies to cover broader neuroscience and neuroinformatics domains. Deduplicate across shared ontology bases. Use SKOS/LinkML mapping properties for precise match types. Enrich values and valuesets with ontology alignment.

## Clarifications

### Session 2026-03-21

- Q: How should ontology-to-element matching distinguish concepts from data elements? → A: Ontology terms are concepts (e.g., NCIT:C25150 = "Age" as a concept, without type/unit). Data elements are concrete (type=float, unit=years). Every alignment must record a `match_level`: `concept_match` or `element_match`.
- Q: Can entities match multiple ontology terms? → A: Yes. Each entity (element, schema, valueset, value) can have multiple ontology annotations from different ontologies. Each annotation records both qualitative (SKOS relation + match_level) and quantitative (embedding distance + model name) metadata. The number of annotations is determined by a heuristic: include all terms above a score threshold (e.g., 0.5 for elements, 0.8 for values), with a gap-based cutoff (if there's a significant drop in similarity between top-N and N+1, stop at N).

---

## User Scenarios & Testing

### User Story 1 — Extended Neuroscience Ontology Coverage (Priority: P1)

The ontology store covers the full breadth of neuroscience and neuroinformatics by including additional domain ontologies beyond the initial 5. This enables ontology_term assignment for anatomy (UBERON), cell types (CL), brain regions (HOMBA), experimental methods (TMN), bioinformatics operations (EDAM), and more.

**Why this priority**: The initial 5 ontologies (NCIT, PATO, HP, OBI, NCBITaxon) miss key neuroscience domains — anatomy, cell types, brain atlases, and experimental methods. Without these, many elements can't be aligned to ontology terms.

**Independent Test**: After loading all ontologies, search for "hippocampus" and verify UBERON results appear. Search for "patch clamp" and verify TMN/OBI results.

**Acceptance Scenarios**:

1. **Given** `ontology refresh` runs, **When** all ontologies are loaded, **Then** the store contains terms from at least 12 ontologies: NCIT, PATO, HP, OBI, NCBITaxon, UBERON, CL, EDAM, ATOM, TMN, BGO, HOMBA.
2. **Given** UBERON is loaded, **When** searching for "brain", **Then** results include anatomical structures (UBERON:0000955 Brain, etc.).
3. **Given** CL (Cell Ontology) is loaded, **When** searching for "neuron", **Then** results include cell types (CL:0000540 Neuron, etc.).

---

### User Story 2 — Cross-Ontology Deduplication (Priority: P1)

Many ontologies import common bases — UBERON terms appear in CL, HP, and others. The system deduplicates terms across ontologies so each unique term URI appears once in the vector index, even if it's referenced by multiple ontologies. This prevents duplicate matches and reduces index size.

**Why this priority**: Without deduplication, the same UBERON term embedded 5 times wastes space and returns duplicate results from different ontology contexts.

**Independent Test**: Load UBERON and CL (which imports UBERON). Verify "UBERON:0000955" appears once in the vector index, not twice.

**Acceptance Scenarios**:

1. **Given** UBERON and CL are both loaded into the oxigraph store, **When** the vector index is built, **Then** each term URI appears exactly once (deduplicated by URI).
2. **Given** duplicate terms exist across ontologies, **When** `ontology info` shows term counts, **Then** the vector index count ≤ sum of individual ontology counts (deduplicated).
3. **Given** a term imported from UBERON into CL, **When** `lookup_term(uri)` is called, **Then** it returns labels and synonyms from all ontologies that define it (merged view).

---

### User Story 3 — SKOS/LinkML Precision Matching (Priority: P1)

When assigning ontology_terms to elements via embedding similarity, the system classifies each match with a SKOS mapping relation (exactMatch, closeMatch, broadMatch, narrowMatch, relatedMatch) based on the cosine distance and ontology hierarchy. This replaces the simple threshold-based assignment with precision-aware matching.

**Why this priority**: A cosine distance of 0.7 doesn't distinguish between "this is exactly the same concept" and "this is a related but broader concept." SKOS relations enable downstream consumers to understand the precision of each alignment.

**Independent Test**: Enrich an element named "age" and verify the assigned ontology_term includes a SKOS relation type (e.g., `skos:exactMatch` for NCIT:C25150 Age).

**Acceptance Scenarios**:

1. **Given** enrichment assigns ontology_term to an element, **When** the match score ≥ 0.95, **Then** the provenance records `mapping_relation: skos:exactMatch`.
2. **Given** a match score between 0.8–0.95, **Then** `mapping_relation: skos:closeMatch`.
3. **Given** the matched term is a parent of a more specific term that also matches, **Then** `mapping_relation: skos:broadMatch` (the parent) and `skos:narrowMatch` (the child) are both recorded.
4. **Given** enrichment results, **When** reviewed, **Then** each ontology_term assignment includes: term URI, label, score, and SKOS mapping relation.

---

### User Story 4 — Value and Valueset Ontology Enrichment (Priority: P1)

Individual values (ValueConcepts like "male", "female", "EEG") and valuesets (collections like "SexEnum", "ModalityEnum") are enriched with ontology_term alignment. Values require high-confidence matching (≥ 0.8) since they are specific terms. Valuesets are annotated with the most common ontology namespace of their members.

**Why this priority**: Currently only elements are enriched. Values like "male" should map to PATO:0000384, "Homo sapiens" to NCBITaxon:9606, etc. This enables cross-source value standardization.

**Independent Test**: After enrichment, verify that the value "male" has `ontology_term: http://purl.obolibrary.org/obo/PATO_0000384`.

**Acceptance Scenarios**:

1. **Given** a value "male" exists, **When** enrichment runs with threshold 0.8, **Then** it is assigned `ontology_term: PATO:0000384` with `mapping_relation: skos:exactMatch`.
2. **Given** a value "Homo sapiens" exists, **When** enriched, **Then** it is assigned `ontology_term: NCBITaxon:9606`.
3. **Given** a valueset "SexEnum" with members mapped to PATO terms, **When** enriched, **Then** the valueset gets an `ontology_namespace: PATO` annotation.
4. **Given** a value with no close ontology match (score < 0.8), **When** enrichment runs, **Then** no ontology_term is assigned (avoids false matches for specific terms).

---

### Edge Cases

- What if two ontologies define the same term URI with different labels? Use the label from the ontology that defines it as a primary term (not just imports it).
- What if an ontology download URL changes? Log error, skip that ontology, continue with others.
- What if the TMN methods ontology is not in OBO format? Support loading from GitHub raw YAML/JSON-LD.
- What if HOMBA is not available as OBO? Parse from the Allen Institute CCF-MAP docs or custom format.
- What if value embedding matches multiple ontology terms equally well? Record the top match and include alternatives in a `candidates` list in provenance.

## Requirements

### Functional Requirements

**Extended Ontology Set**

- **FR-001**: The bundled ontology configuration MUST include at least 12 ontologies:
  - Existing: NCIT, PATO, HP, OBI, NCBITaxon
  - New: UBERON (anatomy), CL (cell types), EDAM (bioinformatics operations), ATOM (neuroscience atlas), TMN (experimental methods), BGO (brain gene ontology), HOMBA (human brain atlas)
- **FR-002**: Each ontology MUST specify: name, canonical download URL, format (obo/owl/ttl/json-ld), and an enabled/disabled flag.
- **FR-003**: `ontology refresh` MUST handle mixed formats — OBO (via line parser), OWL/TTL (via pyoxigraph load_rdf), and custom formats (via format-specific parsers).

**Cross-Ontology Deduplication**

- **FR-004**: The vector index MUST deduplicate by term URI — each URI appears at most once, regardless of how many ontologies reference it.
- **FR-005**: When building the vector index, if a term URI has labels/synonyms from multiple ontologies, the system MUST merge them into a single embedding text (richer context = better embedding).
- **FR-006**: `lookup_term(uri)` MUST return merged results: labels from all ontologies, all synonyms, all parent URIs.

**Multi-Term Ontology Annotation**

- **FR-007**: Each entity (element, schema, valueset, value) MUST support multiple ontology annotations — not just a single `ontology_term`. The annotations are stored as a list: `ontology_annotations: list[OntologyAnnotation]`.
- **FR-008**: Each `OntologyAnnotation` MUST include both qualitative and quantitative metadata:
  - `term_uri`: the ontology term URI
  - `term_label`: human-readable label from the ontology
  - `ontology`: which ontology the term comes from (e.g., "ncit", "pato", "uberon")
  - `mapping_relation`: SKOS value — `skos:exactMatch`, `skos:closeMatch`, `skos:broadMatch`, `skos:narrowMatch`, or `skos:relatedMatch`
  - `match_level`: `concept_match` or `element_match`
  - `score`: cosine similarity (0.0–1.0)
  - `model`: embedding model used (e.g., "all-MiniLM-L6-v2")
- **FR-009**: The number of annotations per entity MUST be determined by a heuristic:
  - Include all terms with score above a threshold (elements: 0.5, values: 0.8)
  - Apply a gap-based cutoff: if the score drops by > 0.15 between rank N and N+1, stop at N
  - Cap at a maximum of 10 annotations per entity to prevent noise
  - The best match (highest score) is designated as the `primary` annotation

**SKOS Relation Assignment**

- **FR-010**: Mapping relation MUST be determined by cosine distance AND ontology hierarchy:
  - ≥ 0.95 → `skos:exactMatch`
  - 0.8–0.95 → `skos:closeMatch`
  - If assigned term is a parent of a better-matching child → `skos:broadMatch`
  - If assigned term is a child of a matching parent → `skos:narrowMatch`
  - 0.5–0.8 → `skos:relatedMatch`

**Concept vs Data-Element Match Level**

- **FR-014**: Every ontology annotation MUST include `match_level`:
  - `concept_match`: Ontology term represents the same concept but does not specify data type, unit, or constraints. Example: NCIT:C25150 (Age) ≈ element "age" (float/years).
  - `element_match`: Ontology term exactly describes the data value. Example: PATO:0000384 (male) = value "male".
- **FR-015**: `match_level` MUST be: `element_match` if the entity is a ValueConcept/enum AND score ≥ 0.9; otherwise `concept_match`.
- **FR-016**: Two elements sharing a `concept_match` ontology annotation may still need transforms (they share the concept but differ in data representation). Two values sharing an `element_match` are equivalent.

**Value and Valueset Enrichment**

- **FR-010**: The `enrich` command MUST process values (ValueConcepts) in addition to elements. Values use a higher confidence threshold (default 0.8) than elements (default 0.5).
- **FR-011**: Value embedding text MUST be: `"{label}"` (just the label, no class/description context — values are specific terms).
- **FR-012**: Valuesets MUST be annotated with `ontology_namespace` based on the most common ontology prefix of their enriched member values.
- **FR-013**: Each enriched value MUST have `ontology_annotations` (same structure as elements) with `mapping_relation`, `match_level`, `score`, and `model` per annotation.

### Key Entities

- **OntologyConfig** (extended): Add 7 new ontologies to `ontologies.yaml` with URLs and formats.
- **OntologyAnnotation**: Per-entity annotation with: term_uri, term_label, ontology, mapping_relation (SKOS), match_level (concept/element), score (cosine), model (embedding model name). Multiple annotations per entity.
- **MatchLevel**: `concept_match` or `element_match`. Recorded on every annotation.
- **ValueEnrichment**: Multiple ontology annotations on ValueConcept entities with high threshold (0.8).

## Success Criteria

### Measurable Outcomes

- **SC-001**: Ontology store contains terms from ≥ 12 ontologies after `ontology refresh`.
- **SC-002**: Vector index has no duplicate URIs (deduplication verified by count comparison).
- **SC-003**: ≥ 80% of enriched elements have a `mapping_relation` field in provenance.
- **SC-004**: Values like "male", "female", "Homo sapiens" are correctly mapped to their canonical ontology terms with ≥ 0.8 confidence.
- **SC-005**: UBERON anatomical terms are found when searching for neuroscience anatomy concepts.
- **SC-007**: Value "male" enriched with match_level=element_match; element "age" enriched with match_level=concept_match.
- **SC-006**: Full ontology refresh for all 12+ ontologies completes in under 30 minutes.

### Assumptions

- ATOM, TMN, and HOMBA may not be available in standard OBO format. Custom parsers or alternative download formats (JSON-LD, YAML) may be needed.
- EDAM is available at `http://edamontology.org/EDAM.obo`.
- UBERON is available at `http://purl.obolibrary.org/obo/uberon.obo`.
- CL (Cell Ontology) is available at `http://purl.obolibrary.org/obo/cl.obo`.
- BGO may require fetching from the Sanger OLS instance or a direct download.
- The SKOS mapping relation is stored in provenance, not in the semantic identity block (it's metadata about the alignment, not part of the element's identity).
