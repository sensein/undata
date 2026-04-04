# Evaluation Record

This file records extraction results, benchmarks, and quality metrics from pipeline runs.
Updated after each significant re-extraction or pipeline change.

---

## 2026-04-04 — Feature 041: Cross-Source Alignment (SchemaView + multi-signal scoring)

**Pipeline**: LinkML-first adapters → SchemaView extraction → enrich → commit → align → transform

### Entity Counts (7 sources — NDA pending)

| Source | Elements | Schemas | Values | Valuesets | Total |
|--------|----------|---------|--------|-----------|-------|
| BIDS | ~500 | ~200 | ~400 | ~7 | 1,477 |
| NWB | ~600 | ~300 | ~100 | ~5 | ~1,000 |
| DANDI | ~200 | ~100 | ~200 | ~5 | 600 |
| openMINDS | ~500 | ~300 | ~800 | ~50 | ~1,600 |
| AIND | ~400 | ~200 | ~300 | ~20 | ~900 |
| ReproSchema | ~9,500 | ~90 | ~9,900 | ~4,300 | ~24,000 |
| **Total (7 sources)** | **13,742** | **1,679** | **15,598** | **4,638** | **35,657** |

### Alignment Results (5 sources, pre-ReproSchema)

| Metric | Value |
|--------|-------|
| Entities processed | 11,678 |
| Alignment groups | 521 |
| Canonical entities | 521 |
| Member entities (merged) | 925 |
| Unaligned (unique) | 10,232 |
| Conflicts (range mismatch) | 0 |
| Processing time | 2 min 27 sec |

### Key Changes from Previous Run

- **SchemaView dedup**: All 8 adapters now produce LinkML SchemaDefinitions. Slots shared across classes within a source are deduplicated before entity extraction. ReproSchema items shared across activities produce 1 element each (not per-activity).
- **Multi-signal alignment scoring**: 4-signal weighted composite (name 0.3, embedding 0.3, ontology 0.25, alias 0.15) replaces the old single-signal alias detection.
- **Graph-based persistence**: Alignment groups stored as aligned_to/aligned_members sha256 references on entities (no separate table).
- **Pipeline reordering**: Alignment now runs post-commit (after embeddings computed), enabling embedding k-NN candidate generation.

### Known Issues

- NDA pipeline pending (API-based, takes ~60 min for all structures)
- OpenNeuro batch ingestion not run yet (requires datalad + network)
- Full alignment with 35K+ entities takes >5 minutes due to k-NN computation on large embedding matrix — may need chunking or HNSW index for 100K+ scale
- ReproSchema extraction takes ~64 minutes (SchemaView construction for 4,759 slots is slow)

---

## 2026-03-22 — Feature 027: Library Hardening (post-adapter review)

**Pipeline**: LinkML-first adapters → extract → enrich → commit
**Changes**: All 5 adapters converted to LinkML-first. Entity classification fixed. Schemas, values, valuesets now routed directly from extraction.

### Source Extraction (post-reclassification)

| Source | Elements | Schemas | Values | Valuesets |
|--------|----------|---------|--------|-----------|
| BIDS | 585 | 214 | 628 | 7 |
| DANDI | 398 | 44 | 152 | 5 |
| NWB | 179 | 80 | 0 | 0 |
| openMINDS | 473 | 202 | 4,378 | 123 |
| AIND | 556 | 375 | 401 | 79 |
| **Total** | **2,191** | **915** | **5,559** | **214** |

### Comparison to 026 Baseline

| Metric | 026 | 027 | Notes |
|--------|-----|-----|-------|
| Elements | 7,745 | 2,191 | Vocabulary terms reclassified as values (correct) |
| Schemas | 642 | 915 | Now includes sidecar field groups + tabular classes |
| Values | 1,000 | 5,559 | Includes enum_values from all sources + openMINDS instances |
| Valuesets | 86 | 214 | controlledTerms, BIDS valuesets, AIND enums |

### Key Changes

- **LinkML-first architecture**: All adapters build LinkML SchemaDefinition, extract via standard LinkML adapter
- **BIDS**: Sidecar rules → 165 mixin classes + 32 modality classes. Units on 70 fields. ~494 vocabulary terms correctly as values.
- **DANDI**: Inheritance tracked (42/44 classes). 76 enum_values from enum classes.
- **NWB**: Full inheritance (80/80 classes). Links, groups, reference dtypes extracted.
- **openMINDS**: 4,390 instances from separate repo. 123 controlled vocabulary types as valuesets. Short property names.
- **AIND**: JSON Schema $defs → classes/enums via LinkML builder.

### Enrichment (027 pipeline with source metadata + LLM + cross-source)

| Source | Source Metadata | Embedding | Schemas | Total Enriched | Flags |
|--------|----------------|-----------|---------|----------------|-------|
| BIDS | 0 | 15 elem + 356 val | 2 | 374 | 1,466 |
| DANDI | 0 | 103 elem + 8 val | 22 | 134 | 2,085 |
| NWB | 0 | 2 elem | 5 | 7 | 2,344 |
| openMINDS | 3,084 | 1 elem + 859 val + 85 vs | 70 | 4,099 | 4,213 |
| AIND | 0 | 191 elem + 264 val + 19 vs | 78 | 552 | 5,591 |

Cross-source alignment: 73 label matches, 43 annotations transferred (openMINDS → BIDS/AIND)

### Pipeline Performance

| Step | Time |
|------|------|
| BIDS pipeline | 277s |
| DANDI pipeline | 220s |
| NWB pipeline | 197s |
| openMINDS pipeline | 340s |
| AIND pipeline | 274s |
| **Total** | **~22 min** |

### Enrichment Notes

- Element enrichment rates low (2-35%) — ontology coverage is the bottleneck, not matching quality
- LLM verification (gpt-5.4-nano) works correctly but most candidates are rejected (bad ontology coverage)
- Source metadata pre-enrichment effective for openMINDS (70% of instances have curated ontology IDs)
- Cross-source alignment transfers annotations between matching entities (73 label matches found)
- Further improvement needs: ontology expansion, fine-tuned embeddings, quantified validation

---

## 2026-03-21 — Feature 026: Staged Enrichment Pipeline

**Pipeline**: extract (UUID staging) → enrich (in-place) → commit (two-mode hash) → align
**Changes**: Staged pipeline, two-mode identity hash, in-place enrichment, no new elements from enrichment
**Output dir**: `/tmp/undata-registry/` (not in git)

### Source Extraction

| Source | Elements | Schemas | Values | Valuesets |
|--------|----------|---------|--------|-----------|
| BIDS | 1,036 | 12 | 289 | 7 |
| DANDI | 398 | 43 | 76 | 5 |
| NWB | 283 | 80 | 0 | 0 |
| openMINDS | 4,736 | 322 | 0 | 0 |
| AIND | 1,292 | 185 | 641 | 74 |
| **Total** | **7,745** | **642** | **1,006** | **86** |

### Comparison to Baseline (019–025)

| Metric | Baseline | 026 | Delta | Notes |
|--------|----------|-----|-------|-------|
| Elements | 7,756 | 7,745 | -11 | openMINDS dedup by (source,class,name) |
| Schemas | 642 | 642 | 0 | |
| Values | 987 | 1,000 | +13 | AIND description differentiation |
| Valuesets | 86 | 86 | 0 | |

### Enrichment

| Source | Elements | Values | Schemas | Valuesets |
|--------|----------|--------|---------|-----------|
| BIDS | 58/1,036 (5.6%) | 90/295 (31%) | 8/12 (67%) | 0/7 |
| DANDI | 103/398 (26%) | 0/76 | 29/43 (67%) | 0/5 |
| NWB | 21/283 (7.4%) | 0/0 | 25/80 (31%) | 0/0 |
| openMINDS | 124/4,736 (2.6%) | 0/0 | 20/322 (6.2%) | 0/0 |
| AIND | 225/1,292 (17%) | 321/836 (38%) | 84/185 (45%) | 16/74 (22%) |
| **Total** | **531** | **411** | **166** | **16** |

### Key Changes from 026

- **UUID staging**: Extraction writes UUID-named files (no hash at extraction time)
- **Two-mode hash**: Computed at commit time (ontology-anchored or structural fallback)
- **In-place enrichment**: No new elements created from enrichment
- **Enrichment working**: 531 elements + 411 values + 166 schemas + 16 valuesets annotated
- **Cross-source merge**: 118 AIND elements merged at commit time (same hash from different sources)
- **Ontology store**: 268K embedded terms from 13 ontologies (reused from 025)

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
