# Implementation Plan: Rich Data Element Model

**Branch**: `018-rich-data-model` | **Date**: 2026-03-17 | **Spec**: spec.md

## Summary

Enrich the library's data element model with reproschema-aligned fields, W3C PROV-O
provenance, ontology verification, semantic similarity scoring, and valueset-based
alias detection. Reclassify underscore-prefixed AIND entries as ValueConcepts.

## Technical Context

**Extends**: undata-library (015v2), backend (017)
**New dependencies**: sentence-transformers (for embedding similarity), requests (for OLS API)
**New CLI commands**: verify, similarity, detect-aliases, ontology refresh

## Phases

### Phase 1: Enriched SemanticIdentity + PROV-O Provenance
- Add response_options, question_text, value_domain, min_value, max_value to models
- Add generated_at, attributed_to, activity, derived_from to ProvenanceEntry
- Update LinkML schema
- Update extractors to populate new fields where available
- Update hash function: min_value/max_value in hash, question_text/value_domain excluded

### Phase 2: Underscore Reclassification
- Update AIND extractor to filter `_` prefixed $defs as ValueConcepts
- Apply source-qualified tags (aind.instrument.manufacturer.Abcam)
- Re-ingest, verify element count drops

### Phase 3: Ontology Cache + Verification
- Create ontology-cache/ directory with NCIT, PATO, HP, OBI, NCBITaxon YAML files
- Build initial cache from OLS API bulk download
- Implement `verify` CLI: existence check + label similarity
- Implement `ontology refresh` CLI: incremental update from OLS

### Phase 4: Semantic Similarity + Alias Detection
- Implement embedding similarity using sentence-transformers (all-MiniLM-L6-v2)
- Implement range overlap scoring (numeric intersection/union)
- Implement valueset Jaccard scoring (shared choices / total)
- Map scores to SKOS relations (exactMatch, broadMatch, narrowMatch, closeMatch, relatedMatch)
- Implement `detect-aliases` CLI: scan all elements, output candidate pairs
- Implement `similarity` CLI: pairwise element comparison

### Phase 5: Re-ingest + Backend Alignment + Polish
- Re-ingest all 5 sources with enriched model
- Update backend ORM + API for new fields
- Update frontend to display response_options, ranges, PROV-O provenance
- Update tests
