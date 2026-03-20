# undata-library

Content-addressed registry of neuroscience data elements and class schemas in LinkML YAML format.

**Design**: Elements are `rdf:Property` instances identified by their semantic graph hash.
Schemas are `sh:NodeShape` instances identified by their property set hash.
Identity ≠ provenance — two sources defining the same concept produce one element with multiple provenance entries.

## Contents

- **2,697 data elements** (content-addressed, reproschema-aligned)
- **482 class schemas** with property membership from BIDS, DANDI, NWB, AIND, openMINDS
- **1,207 value concepts** — categorical/enum values as semantic entities
- **Enriched model**: response_options, min/max ranges, question_text, W3C PROV-O provenance
- **Ontology verification**: offline cache + OLS refresh for NCIT, PATO, HP, OBI, NCBITaxon
- **Alias detection**: semantic similarity with SKOS mapping relations
- **Content-addressed filenames**: `{attribute}_{6-char-hash}.yaml`

## Install

```bash
pip install -e .
# or with source extractors
pip install -e ".[bids,dandi]"
```

## Element Format

Each element's identity is its semantic graph (ontology_term, data_type, unit, constraints).
Everything else is provenance:

```yaml
# elements/age_3c1gtm.yaml
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
```

Same semantic graph → same file → automatic cross-source deduplication.

## CLI Commands

```bash
# Validate all YAML files
undata-library validate elements/ schemas/

# Compute content hash for a file
undata-library hash elements/age_3c1gtm.yaml

# Ingest from raw schema files (offline, no backend)
undata-library ingest --source bids --library-path .
undata-library ingest --source nwb --path /path/to/nwb/schemas/ --library-path .
undata-library ingest --source aind --path /path/to/aind/schemas/ --library-path .

# Build machine-readable index
undata-library index

# Show provenance differences within an element
undata-library diff elements/age_3c1gtm.yaml
undata-library diff elements/age_3c1gtm.yaml --format json
```

## Standalone Repository Setup

```bash
# Create the standalone repo
gh repo create sensein/undata-library --public
git init && git remote add origin https://github.com/sensein/undata-library.git
git add . && git commit -m "Initial commit" && git push -u origin main

# Add as submodule to the main undata repo
cd /path/to/undata
rm -rf library
git submodule add https://github.com/sensein/undata-library.git library
```

## Architecture

```
Identity (hashed)           Provenance (NOT hashed)
─────────────────           ──────────────────────
ontology_term               source
data_type                   class
unit                        name
constraints                 description
                            required, multivalued
```

Two elements with identical semantic graphs ARE the same element.
Cross-source equivalence is automatic via content-addressing.

## License

MIT
