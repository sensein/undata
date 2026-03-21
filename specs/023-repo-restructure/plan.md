# Implementation Plan: Repository Restructure & Ontology Bulk Download

**Branch**: `023-repo-restructure` | **Date**: 2026-03-21 | **Spec**: spec.md

## Summary

Move generated library output to a configurable directory outside git, delete the
old `ingestion/` folder, replace OLS API pagination with bulk OWL/OBO ontology downloads,
and clean tracked output from git history.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: pyyaml, rdflib 7.x (existing, for OWL/TTL parsing), httpx (existing, for downloads)
**New dependency**: `pronto>=2.5` (OBO format parser — much faster than rdflib for OBO files)
**Storage**: XDG-compliant output directory (`~/.local/share/undata/registry/`)
**Testing**: pytest
**Project Type**: Library/CLI restructure

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Removes dead code (ingestion/); simplifies output management |
| II. TDD | PASS | Test-alongside |
| III. API-First Design | PASS | CLI contracts unchanged, just `--output-dir` added |
| IV. Observability | PASS | Output location logged on every command |
| V. Versioning & Stability | PASS | Breaking change: output location moves. Migration documented. |
| VI. Environment Isolation | PASS | No changes to venv setup |
| Git Commit Discipline | PASS | Commit per phase |

## Phase 1: Output Directory Configuration

**Goal**: All commands write to configurable output dir, default `~/.local/share/undata/registry/`.

| File | Change |
|------|--------|
| `models.py` | ADD `RegistryConfig` with `output_dir` resolution (CLI > env var > XDG default) |
| `cli.py` | ADD `--output-dir` flag to all pipeline commands; resolve via RegistryConfig |
| `ingest.py` | Replace hardcoded `library_path` with resolved output dir |
| `enrich.py` | Use output dir |
| `align.py` | Use output dir |
| `transform.py` | Use output dir |
| `index.py` | Use output dir |
| `validation.py` | Use output dir |

**Resolution order**: `--output-dir` CLI flag > `$UNDATA_REGISTRY_DIR` env var > `~/.local/share/undata/registry/`

## Phase 2: Bulk Ontology Download

**Goal**: Replace OLS API pagination with single-file OBO/OWL download from OBO Foundry.

| File | Change |
|------|--------|
| `ontology_fetch.py` | REWRITE — `fetch_ontology(name)` downloads OBO file from canonical URL, parses with pronto, extracts terms to cache format |
| `ontology_cache.py` | Minor — ensure cache dir is under output dir |
| `cli.py` | Remove `--max-terms` flag from `ontology refresh` |
| `pyproject.toml` | ADD `pronto>=2.5` to dependencies |

**Canonical OBO URLs**:
```
NCIT:      http://purl.obolibrary.org/obo/ncit.obo
PATO:      http://purl.obolibrary.org/obo/pato.obo
HP:        http://purl.obolibrary.org/obo/hp.obo
OBI:       http://purl.obolibrary.org/obo/obi.obo
NCBITaxon: http://purl.obolibrary.org/obo/ncbitaxon.obo
```

**Parsing with pronto** (OBO format):
```python
import pronto
ont = pronto.Ontology(path_or_url)
for term in ont.terms():
    uri = term.id        # e.g., "NCIT:C25150"
    label = term.name    # e.g., "Age"
    synonyms = [s.description for s in term.synonyms]
    parents = [r.id for r in term.superclasses(distance=1) if r.id != term.id]
    deprecated = term.obsolete
```

**Why pronto over rdflib**: pronto is purpose-built for OBO/OWL ontologies — 10x faster parsing, native synonym/parent extraction, handles OBO format natively. rdflib would require SPARQL queries for the same information.

## Phase 3: Delete ingestion/ + Git Cleanup

**Goal**: Remove dead code and tracked output.

| Action | Details |
|--------|---------|
| Delete `ingestion/` | `git rm -r ingestion/` — adapters, CLI, scripts, tests all replaced by library |
| Update `.gitignore` | Add: elements/, schemas/, values/, valuesets/, transforms/, ontology-cache/*.yaml, ontology-cache/*.obo, embeddings.parquet, hash-registry.yaml, ontology-index.yaml, alignment-report.yaml, ingestion-report.yaml |
| Remove tracked output | `git rm -r --cached library/elements/ library/schemas/ library/values/ library/valuesets/ library/transforms/ library/hash-registry.yaml library/ontology-cache/*.yaml library/ontology-index.yaml` |
| Update README.md | Remove ingestion/ references; document output directory; explain registry is generated |
| Update CLAUDE.md | Remove ingestion section; update project structure |
| Update docker-compose.yml | Remove ingestion service if present |

## Phase 4: Polish + Verify

- Run full pipeline to new output directory
- Verify all tests pass
- Verify `git status` shows clean tree after re-extraction
- Verify ontology cache has full term counts
- Lint + commit + push

## Project Structure (after restructure)

```text
undata/
├── backend/              # Schema backend REST API
├── frontend/             # Schema Explorer UI
├── migration-api/        # Migration execution API
├── library/              # Python package ONLY (no data files)
│   ├── src/undata_library/
│   │   ├── adapters/     # 8 adapter classes
│   │   ├── source_defs/  # 5 bundled YAML source definitions
│   │   ├── models.py
│   │   ├── ingest.py
│   │   ├── enrich.py
│   │   ├── align.py
│   │   ├── transform.py
│   │   ├── acquisition.py
│   │   ├── ontology_fetch.py  # REWRITTEN for bulk download
│   │   └── ...
│   ├── tests/
│   └── pyproject.toml
├── tutorials/
├── specs/
├── docker-compose.yml
└── README.md
```

**Generated output** (NOT in git):
```text
~/.local/share/undata/registry/   # or $UNDATA_REGISTRY_DIR
├── elements/           # 5000+ element YAML files
├── schemas/            # 600+ schema YAML files
├── values/             # 700+ value YAML files
├── valuesets/          # 80+ valueset YAML files
├── transforms/         # bidirectional transform YAML files
├── ontology-cache/     # 5 ontology OBO/YAML files + embeddings
├── embeddings.parquet
├── hash-registry.yaml
├── ontology-index.yaml
├── alignment-report.yaml
└── ingestion-report.yaml
```

## Dependency Graph

```
Phase 1 (output dir)     → foundational
Phase 2 (bulk ontology)  → independent (can parallel with Phase 1)
Phase 3 (git cleanup)    → depends on Phase 1 (output must move before removing tracked files)
Phase 4 (polish)         → depends on all
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| Output dir config | Medium | Touch every command; env var + CLI flag resolution |
| Bulk ontology download | Medium | pronto parsing; handle download failures; large file streaming |
| Delete ingestion/ | Low | Just deletion + reference updates |
| Git cleanup | Low | git rm --cached; .gitignore update |
| README/CLAUDE.md updates | Low | Text editing |

## Risks

| Risk | Mitigation |
|------|-----------|
| pronto fails on large ontology (NCIT) | Stream parse; fall back to OLS API |
| OBO Foundry URL changes | Store URLs in config; easy to update |
| Users expect output in library/ | Clear error message: "Output moved to {dir}. See README." |
| Existing CI depends on library/elements/ | Update CI to generate output before testing |
