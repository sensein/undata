# Evaluation Record

This file records extraction results, benchmarks, and quality metrics from pipeline runs.
Updated after each significant re-extraction or pipeline change.

---

## 2026-03-21 — Full Re-extraction (Features 019–025)

**Pipeline**: ingest → embed → enrich → align → transform
**Adapters**: 019 framework (BaseAdapter + ClassifiedEntity + 4-way classification)
**Ontologies**: 024 oxigraph store + 025 expansion (13 ontologies)
**Output dir**: `/tmp/undata-registry/` (not in git)

### Source Extraction

| Source | Elements | Merged | Adapter |
|--------|----------|--------|---------|
| BIDS | 1,036 | 0 | BIDSAdapter (isolated venv, bidsschematools) |
| DANDI | 398 | 0 | DANDIAdapter (isolated venv, dandischema) |
| NWB | 283 | 0 | NWBAdapter (git clone, YAML parse) |
| openMINDS | 4,753 | 0 | OpenMINDSAdapter (git clone, JSON-LD parse) |
| AIND | 1,286 | 23 | AINDAdapter (git clone, JSON Schema parse) |
| **Total pre-enrichment** | **7,756** | **23** | |

### Enrichment

| Metric | Count |
|--------|-------|
| Elements after enrichment | 14,114 |
| New elements (identity changed by ontology_term) | 5,834 |
| Ontology terms assigned | 5,834 (74% of original) |
| Values resolved (response_options → ValueConcept URIs) | 2,856 |
| Value domain set (data_type → categorical/numeric/text/boolean) | 4,796 |

### Entity Counts (Final)

| Entity Type | Count |
|-------------|-------|
| Elements | 14,114 |
| Schemas | 642 |
| Values | 987 |
| Valuesets | 86 |
| Transforms | 176,880 |

### Transforms Breakdown

| Function Type | Count |
|---------------|-------|
| identity | 72,574 |
| unknown | 15,417 |
| structural | 449 |
| **Total** | **176,880** |
| Alias groups (close-match) | 11 |

### Ontology Store

| Ontology | Terms in Store | In Vector Index | Format | Source |
|----------|---------------|-----------------|--------|--------|
| NCIT | 209,910 | 209,910 | OBO | purl.obolibrary.org |
| NCBITaxon | 2,708,857 | 130 (neuro subset) | OBO | purl.obolibrary.org |
| UBERON | 28,342 | 28,342 | OWL | purl.obolibrary.org |
| CL | 21,463 | 21,463 | OWL | purl.obolibrary.org |
| HP | 19,944 | 19,944 | OBO | purl.obolibrary.org |
| TMN | 53 | 53 | OWL (base) | github.com/BICCN/TMN |
| BGO | 336 | 336 | OWL (base) | github.com/Cellular-Semantics |
| OBI | 5,546 | 5,546 | OWL | purl.obolibrary.org |
| HBAO | 4,939 | 4,939 | OWL | github.com/brain-bican |
| PATO | 2,785 | 2,785 | OBO | purl.obolibrary.org |
| EDAM | 2,745 | 2,745 | OBO | edamontology.org |
| ATOM | 101 | 101 | TTL | github.com/SciCrunch |
| PROV-O | 81 | 81 | TTL | w3.org |
| SKOS | 32 | 32 | OWL/RDF | w3.org |
| **Total** | **2,992,292** | **268,581** | | |

### Known Issues

- OBI/UBERON/CL: OBO format has IRI issues → loaded as OWL instead
- TMN full OWL imports 9K+ terms from OBI/BFO → use tmn-base.owl (53 native)
- BGO full OWL imports 10K+ from CL/UBERON → use bgo-base.owl (336 native)
- PROV-O: needs Accept header for content negotiation (TTL format)
- NCBITaxon: 2.7M terms too large for full embedding → 130 neuro-relevant taxa via 3-level parent-child traversal from 14 seed model organisms
- 15,417 "unknown" transforms: different types with no detected conversion pattern → flagged for manual curation

### Performance

- Ontology refresh (excl NCBITaxon): ~5 minutes
- NCBITaxon load: ~15 minutes (624MB OBO download + 2.7M term insert)
- Vector index build (268K terms): ~3 minutes
- Full 5-source extraction: ~5 minutes
- Enrichment (7,756 elements): ~2 minutes
- Align + transform: ~5 minutes
- **Total pipeline (excl NCBITaxon)**: ~20 minutes
