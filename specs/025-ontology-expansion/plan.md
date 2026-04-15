# Implementation Plan: Ontology Expansion, Deduplication, and Precision Matching

**Branch**: `025-ontology-expansion` | **Date**: 2026-03-21 | **Spec**: spec.md

## Summary

Extend the ontology set to 12+ ontologies (adding UBERON, CL, EDAM, ATOM, TMN, BGO,
HOMBA), deduplicate across shared bases in the vector index, replace single
ontology_term assignment with multi-term OntologyAnnotation model (qualitative SKOS +
quantitative score + match_level), and enrich values/valuesets alongside elements.

## Technical Context

**Language/Version**: Python 3.14
**Dependencies**: pyoxigraph, pronto, pyarrow, sentence-transformers (existing)
**Storage**: oxigraph store + ontology-vectors.parquet at `{output_dir}/`
**Scale**: ~3.5M terms across 12+ ontologies; 10K+ entities to annotate
**No new dependencies** — uses existing stack

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | OntologyAnnotation is a list of dicts — simple extension |
| II. TDD | PASS | Test-alongside |
| III. API-First Design | PASS | OntologyAnnotation model defined before implementation |
| IV. Observability | PASS | Each annotation includes score + model for reproducibility |
| V. Versioning & Stability | PASS | Breaking: ontology_term field → ontology_annotations list |
| VI. Environment Isolation | PASS | No new system deps |

## Phase 1: OntologyAnnotation Data Model

**Goal**: Replace single `ontology_term` field with `ontology_annotations` list.

| File | Change |
|------|--------|
| `models.py` | ADD `OntologyAnnotation` Pydantic model (term_uri, term_label, ontology, mapping_relation, match_level, score, model); ADD `ontology_annotations: list[OntologyAnnotation]` to SemanticIdentity (NOT in hash — provenance metadata); ADD to ValueSemanticIdentity |

**OntologyAnnotation model**:
```python
class MatchLevel(str, Enum):
    concept_match = "concept_match"
    element_match = "element_match"

class OntologyAnnotation(BaseModel):
    term_uri: str
    term_label: str
    ontology: str                    # e.g., "ncit", "pato", "uberon"
    mapping_relation: str            # skos:exactMatch, closeMatch, etc.
    match_level: MatchLevel          # concept_match or element_match
    score: float                     # cosine similarity 0.0-1.0
    model: str                       # embedding model name
    primary: bool = False            # True for best match
```

**Key decision**: `ontology_annotations` is NOT part of the identity hash. It's enrichment metadata — same element, different annotations depending on which ontologies are loaded.

## Phase 2: Extended Ontology Configuration

**Goal**: Add 7 new ontologies to ontologies.yaml with download URLs.

| File | Change |
|------|--------|
| `source_defs/ontologies.yaml` | ADD entries for UBERON, CL, EDAM, ATOM, TMN, BGO, HOMBA |
| `ontology_fetch.py` | Ensure download handles non-OBO formats (JSON-LD for TMN, custom for HOMBA) |

**New ontology URLs**:
```yaml
- name: uberon
  url: http://purl.obolibrary.org/obo/uberon.obo
  format: obo
- name: cl
  url: http://purl.obolibrary.org/obo/cl.obo
  format: obo
- name: edam
  url: http://edamontology.org/EDAM.obo
  format: obo
- name: atom
  url: http://purl.bioontology.org/ontology/ATOM
  format: owl
  notes: "May need BioPortal API key or alternative URL"
- name: tmn
  url: https://raw.githubusercontent.com/BICCN/TMN/main/tmn.yaml
  format: custom
  notes: "YAML format — needs custom parser"
- name: bgo
  url: https://cellular-semantics.sanger.ac.uk/ols4/ontologies/bgo
  format: obo
  notes: "May need OLS download endpoint"
- name: homba
  url: https://alleninstitute.github.io/CCF-MAP/docs/HOMBA_ontology_v1.json
  format: json-ld
  notes: "Allen Institute brain atlas — JSON-LD"
```

## Phase 3: Cross-Ontology Deduplication in Vector Index

**Goal**: When building ontology-vectors.parquet, deduplicate by URI, merge labels.

| File | Change |
|------|--------|
| `ontology_store.py` | MODIFY `build_vector_index()`: deduplicate by term URI; merge labels+synonyms from all ontologies into single embedding text per URI |
| `ontology_store.py` | MODIFY `all_terms()`: GROUP BY URI, aggregate labels and synonyms |

**Dedup logic**: When UBERON:0000955 (Brain) appears in both UBERON and CL:
- Merge: text = "Brain: cerebrum, encephalon" (all synonyms from all ontologies)
- Single entry in vector index
- `lookup_term()` returns merged view

## Phase 4: Multi-Term Enrichment with Heuristic Selection

**Goal**: Enrich each entity with multiple ontology annotations, not just one.

| File | Change |
|------|--------|
| `enrich.py` | MAJOR REWRITE of `_assign_ontology_term()` → `_assign_ontology_annotations()`: query top-K nearest terms; apply heuristic (threshold + gap cutoff + max 10); assign SKOS relation + match_level per annotation; mark primary |

**Heuristic**:
1. Get top-20 nearest terms from vector index
2. Filter: keep terms with score ≥ threshold (elements: 0.5, values: 0.8)
3. Gap cutoff: if score[i] - score[i+1] > 0.15, stop at i
4. Cap at 10 annotations maximum
5. For each annotation:
   - SKOS relation from score: ≥0.95=exactMatch, 0.8-0.95=closeMatch, 0.5-0.8=relatedMatch
   - Check ontology hierarchy for broadMatch/narrowMatch
   - match_level: element_match if ValueConcept AND score ≥ 0.9, else concept_match
6. Mark highest-scoring as `primary: true`

## Phase 5: Value and Valueset Enrichment

**Goal**: Enrich values and valuesets (not just elements).

| File | Change |
|------|--------|
| `enrich.py` | ADD value enrichment loop: scan values/ directory, embed labels, find nearest ontology terms with high threshold (0.8) |
| `enrich.py` | ADD valueset enrichment: after member values are annotated, set `ontology_namespace` on valueset based on most common ontology prefix |

## Phase 6: Wire Annotations Into Output

**Goal**: Write ontology_annotations to YAML files; update ontology-index.

| File | Change |
|------|--------|
| `ingest.py` | Write `ontology_annotations` to element/value YAML alongside `semantic` |
| `index.py` | Update `build_ontology_index()`: index by all annotations (not just primary); include match_level in each entry |
| `transform.py` | Use primary annotation's term_uri for transform matching (concept_match elements still need transforms) |

## Phase 7: Polish + Full Re-enrichment

- Load all 12+ ontologies
- Build deduplicated vector index
- Re-enrich all entities (elements + values + valuesets)
- Verify multi-term annotations in output
- Lint + test + commit

## Dependency Graph

```
Phase 1 (model)       → foundational
Phase 2 (config)      → independent
Phase 3 (dedup)       → depends on Phase 2 (new ontologies loaded)
Phase 4 (enrichment)  → depends on Phase 1 + Phase 3
Phase 5 (values)      → depends on Phase 4
Phase 6 (wiring)      → depends on Phase 4 + Phase 5
Phase 7 (polish)      → depends on all

Parallelizable: Phase 1 ‖ Phase 2 ‖ Phase 3 (until Phase 4)
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| OntologyAnnotation model | Low | Simple Pydantic model + list field |
| New ontology configs | Low | YAML entries + URL verification |
| Non-OBO format parsers | Medium | TMN (YAML), HOMBA (JSON-LD) need custom parsers |
| Dedup in vector index | Medium | GROUP BY URI + merge labels/synonyms across ontologies |
| Multi-term heuristic | Medium | Score threshold + gap cutoff + max cap + SKOS assignment |
| Value enrichment | Low | Same pattern as element enrichment, different threshold |
| Hierarchy-based SKOS | High | Need to query rdfs:subClassOf chain to detect broad/narrow |
