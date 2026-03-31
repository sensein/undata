# Quickstart: Knowledge Service

## 1. Add Domain-Specific Ontologies

```bash
cd library

# Add HoMBA (brain anatomy)
uv run undata-library ontology add --name homba --url https://purl.brain-bican.org/ontology/homba.owl --format owl

# Add NIDM-Terms (neuroimaging data model)
uv run undata-library ontology add --name nidm --url https://github.com/incf-nidash/nidm-terms --format json-ld

# Add DICOM (data element dictionary — generated from pydicom)
uv run undata-library ontology add --name dicom --format pydicom

# Add RadLex (radiology lexicon)
uv run undata-library ontology add --name radlex --url /path/to/radlex.owl --format owl

# Verify
uv run undata-library ontology list
# Expected: homba (2341 terms), nidm (~500), dicom (~3000), radlex (~58000)
```

## 2. Re-Enrich with New Ontologies

```bash
# Re-run enrichment on existing elements with expanded ontology store
uv run undata-library enrich /path/to/registry

# Check coverage improvement
uv run undata-library ontology info
# Expected: enrichment coverage >40% (up from ~10%)
```

## 3. Ingest OpenNeuro Dataset via Datalad

```bash
# Single dataset
uv run undata-library ingest --source openneuro --path ds000228

# Verify: check for elements from participants.tsv and phenotype TSVs
ls /path/to/registry/elements/ | grep ds000228
```

## 4. Ingest ReproSchema Library

```bash
uv run undata-library ingest --source reproschema --path /path/to/reproschema-library
```

## 5. Verify via GraphQL

```bash
# Check ontology sources
curl -s http://localhost:8002/graphql -H "Content-Type: application/json" \
  -d '{"query":"{ ontologySources { name termCount active lastRefreshedAt } }"}' | python3 -m json.tool

# Check ingestion queue
curl -s http://localhost:8002/graphql -H "Content-Type: application/json" \
  -d '{"query":"{ ingestionQueue { repositoryUrl status adapterType entityCounts } }"}' | python3 -m json.tool

# Check enrichment improvement
curl -s http://localhost:8002/graphql -H "Content-Type: application/json" \
  -d '{"query":"{ browseElements(hasAnnotations: true, first: 1) { totalCount } }"}' | python3 -m json.tool
```

## 6. LLM Enrichment (via Chat)

Open http://localhost:3000/curation/chat and type:
- "suggest better annotations for EchoTime"
- "re-enrich all unannotated BIDS elements"
- "ingest this OpenNeuro dataset: ds000228"
