# Feature Specification: Repository Restructure & Ontology Bulk Download

**Feature Branch**: `023-repo-restructure`
**Created**: 2026-03-21
**Status**: Draft
**Input**: Move library output to a separate directory outside the git repo, delete the old ingestion/ folder (subsumed by library), switch ontology fetching from paginated OLS API to bulk OWL/TTL download, and fix the GitHub default branch.

## User Scenarios & Testing

### User Story 1 — Library Output Separated from Source Code (Priority: P1)

The library's extracted output (elements, schemas, values, valuesets, transforms, ontology cache, embeddings) is stored in a configurable output directory outside the library Python package and outside the git repository. The output directory is specified via CLI flag or environment variable and defaults to `~/.local/share/undata/registry/`. The library source code (`library/src/`) contains only Python modules and bundled source definitions — no YAML data files.

**Why this priority**: Currently, thousands of YAML files are mixed with source code in the git repo, making commits enormous (10K+ file changes on re-extraction), cluttering the repo history, and conflating code changes with data changes. Library output is generated data — it should not be version-controlled.

**Independent Test**: Run the pipeline with `--output-dir /tmp/test-registry`, verify all output goes there and nothing is written to `library/`.

**Acceptance Scenarios**:

1. **Given** `--output-dir /tmp/registry` is specified, **When** the pipeline runs, **Then** all output (elements/, schemas/, values/, valuesets/, transforms/, ontology-cache/, embeddings.parquet, hash-registry.yaml, ontology-index.yaml, ingestion-report.yaml) is written to `/tmp/registry/`.
2. **Given** no `--output-dir` is specified, **When** the pipeline runs, **Then** output goes to the default location (`~/.local/share/undata/registry/` or `$UNDATA_REGISTRY_DIR`).
3. **Given** the library git repo, **When** inspected, **Then** no generated YAML data files exist in the tracked tree. The `.gitignore` excludes output directories.
4. **Given** the library package is installed via pip, **When** a user runs `undata-library pipeline`, **Then** the output directory is created automatically at the default location.

---

### User Story 2 — Delete Old Ingestion Folder (Priority: P1)

The `ingestion/` directory at the repository root is deleted entirely. All its functionality (5 source adapters, CLI, LinkML generation) has been replaced by the library's adapter framework (019), which is more capable (8 adapters, 4-way classification, source acquisition, transforms).

**Why this priority**: The ingestion folder is dead code — it duplicates functionality now in `library/src/undata_library/adapters/`. Keeping it confuses contributors and wastes CI time.

**Independent Test**: After deletion, verify all tests pass and the library pipeline can extract all 5 sources without referencing anything in `ingestion/`.

**Acceptance Scenarios**:

1. **Given** the `ingestion/` directory is deleted, **When** `undata-library pipeline --source bids` runs, **Then** it succeeds using the library's adapter framework.
2. **Given** the `ingestion/` directory is deleted, **When** all library tests run, **Then** 0 failures (no test depends on ingestion/).
3. **Given** the deletion, **When** CLAUDE.md and README.md are updated, **Then** all references to `ingestion/` are removed or updated to point to `library/src/undata_library/adapters/`.

---

### User Story 3 — Bulk Ontology Download (Priority: P1)

The ontology cache is populated by downloading full ontology files (OWL, TTL, or JSON-LD) from their canonical distribution points (OBO Foundry, BioPortal) and parsing them locally, instead of making thousands of paginated OLS API calls. This is faster, gives complete coverage, and works offline after the initial download.

**Why this priority**: The current OLS API approach fetches 500 terms per page, requiring hundreds of HTTP requests for large ontologies like NCIT (~170K terms). It's slow (minutes per ontology), rate-limited, and gives incomplete results (the `--max-terms` parameter artificially truncates). Bulk download gives the full ontology in one HTTP request.

**Independent Test**: Run `undata-library ontology refresh` and verify NCIT has >100,000 terms cached (not the truncated 1,000–5,000 from OLS pagination).

**Acceptance Scenarios**:

1. **Given** `undata-library ontology refresh` runs, **When** NCIT is fetched, **Then** the system downloads `ncit.owl` (or `.obo`/`.json`) from purl.obolibrary.org in a single HTTP request and parses it locally.
2. **Given** all 5 ontologies are fetched via bulk download, **When** term counts are checked, **Then** NCIT has >100K terms, PATO has >2K terms, HP has >15K terms (full coverage, not truncated).
3. **Given** a bulk ontology file is downloaded, **When** parsed, **Then** each term includes: URI, label, synonyms, parent URIs, and deprecated status — same fields as the current cache format.
4. **Given** the OBO format is available, **When** downloading, **Then** prefer OBO format (smallest file size, easiest to parse) over OWL/TTL.

---

### User Story 4 — Library Output Not in Git (Priority: P2)

The `.gitignore` is updated to exclude all generated library output. The existing tracked output files are removed from git history. Documentation is updated to explain that the registry is generated data, not source code.

**Why this priority**: Generated data in git inflates the repo, creates merge conflicts, and makes the history unreadable.

**Independent Test**: After cleanup, `git status` shows a clean tree with no elements/schemas/values YAML files tracked.

**Acceptance Scenarios**:

1. **Given** the `.gitignore` is updated, **When** `git status` is checked after re-extraction, **Then** no output YAML files appear as untracked or modified.
2. **Given** the README is updated, **When** a new contributor reads it, **Then** they understand that `undata-library pipeline` generates the registry to a local directory, and the registry is not committed to the repo.

---

### Edge Cases

- What if a user has uncommitted changes in elements/? Warn before deleting; suggest `git stash` first.
- What if the bulk ontology file is very large (NCIT OWL is ~500MB)? Use the OBO format (~80MB) where available; stream parsing to limit memory.
- What if OBO Foundry is unreachable? Fall back to OLS API (existing behavior) with a warning.
- What if the default output directory doesn't exist? Create it automatically with appropriate permissions.

## Requirements

### Functional Requirements

**Output Directory Separation**

- **FR-001**: All pipeline output MUST be written to a configurable output directory, NOT to the library source tree. Default: `~/.local/share/undata/registry/` (XDG-compliant) or `$UNDATA_REGISTRY_DIR` environment variable.
- **FR-002**: `--output-dir PATH` CLI flag MUST be accepted by `ingest`, `pipeline`, `enrich`, `align`, `transform`, `embed`, `validate-ingestion`, `ontology-index`, and `ontology refresh` commands.
- **FR-003**: The output directory MUST contain: `elements/`, `schemas/`, `values/`, `valuesets/`, `transforms/`, `ontology-cache/`, `embeddings.parquet`, `hash-registry.yaml`, `ontology-index.yaml`, `alignment-report.yaml`, `ingestion-report.yaml`.
- **FR-004**: The library Python package (`library/src/undata_library/`) MUST NOT contain any generated YAML data files. Only source code, source definitions, and adapter scripts.

**Delete Ingestion Folder**

- **FR-005**: The `ingestion/` directory MUST be deleted from the repository.
- **FR-006**: All references to `ingestion/` in README.md, CLAUDE.md, docker-compose.yml, and CI workflows MUST be updated or removed.
- **FR-007**: The library MUST be fully self-contained for all 5 source extractions — no dependency on `ingestion/`.

**Bulk Ontology Download**

- **FR-008**: `ontology refresh` MUST download full ontology files from canonical URLs (OBO Foundry) instead of paginated OLS API calls.
- **FR-009**: Supported formats MUST include OBO (preferred for size), OWL/RDF-XML, and TTL. The system MUST auto-detect format from file extension or content type.
- **FR-010**: Canonical download URLs for the 5 bundled ontologies:
  - NCIT: `http://purl.obolibrary.org/obo/ncit.obo`
  - PATO: `http://purl.obolibrary.org/obo/pato.obo`
  - HP: `http://purl.obolibrary.org/obo/hp.obo`
  - OBI: `http://purl.obolibrary.org/obo/obi.obo`
  - NCBITaxon: `http://purl.obolibrary.org/obo/ncbitaxon.obo`
- **FR-011**: Parsing MUST extract from each term: URI, label (rdfs:label), synonyms (oboInOwl:hasExactSynonym), parent URIs (rdfs:subClassOf), and deprecated status (owl:deprecated).
- **FR-012**: The `--max-terms` CLI flag MUST be removed (no longer needed — bulk download gets everything).
- **FR-013**: OLS API MUST be retained as a fallback when bulk download fails, with a warning logged.

**Git Hygiene**

- **FR-014**: `.gitignore` MUST exclude: `elements/`, `schemas/`, `values/`, `valuesets/`, `transforms/`, `ontology-cache/*.yaml`, `ontology-cache/*.obo`, `embeddings.parquet`, `hash-registry.yaml`, `ontology-index.yaml`, `alignment-report.yaml`, `ingestion-report.yaml`.
- **FR-015**: Existing tracked library output files MUST be removed from git tracking (`git rm -r --cached`).

### Key Entities

- **RegistryConfig**: Output directory configuration — path, environment variable override, XDG default.
- **OntologySource**: Bulk download spec per ontology — name, canonical URL, preferred format, fallback URL.

## Success Criteria

### Measurable Outcomes

- **SC-001**: `git ls-files library/elements/` returns 0 files (no output tracked in git).
- **SC-002**: Pipeline output written to `~/.local/share/undata/registry/` by default (or `$UNDATA_REGISTRY_DIR`).
- **SC-003**: `ingestion/` directory does not exist in the repository.
- **SC-004**: NCIT ontology cache has >100,000 terms (not truncated by --max-terms).
- **SC-005**: Full ontology refresh for all 5 ontologies completes in under 5 minutes (bulk download, not API pagination).
- **SC-006**: All library tests pass after restructuring (0 failures).
- **SC-007**: GitHub default branch is `main` (not `009-tutorials`).

### Assumptions

- `rdflib` (already a dependency) is used to parse OWL/TTL ontology files.
- For OBO format parsing, a lightweight OBO parser is used (or `pronto` library).
- The XDG base directory spec (`~/.local/share/`) is the standard for Linux/macOS user data.
- The ingestion/ folder has no unique functionality not already in library/src/undata_library/adapters/.
