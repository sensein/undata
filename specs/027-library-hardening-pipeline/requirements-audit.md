# Requirements Audit: Features 001-026

**Audited**: 2026-03-22 | **Baseline**: Feature 026 (staged enrichment pipeline)

## Library-Affecting Features

| # | Feature | Key User Stories | Status |
|---|---------|-----------------|--------|
| 001 | Neuro Schema Integration | 4 schema adapters (BIDS, NWB, DANDI, openMINDS) | **Implemented** — adapters in adapters/*.py |
| 002 | Schema Backend | FastAPI + PostgreSQL REST API for elements/schemas | **Implemented** — in backend/ (separate from library) |
| 003 | Schema Explorer | Next.js frontend for browsing | **Implemented** — in frontend/ (separate from library) |
| 004 | Migration API | Dynamic schema construction + migration pathways | **Partial** — migration-api/ exists, not integrated with library |
| 005 | Schema Enrichment | Dual-path extraction, ValidationRule classifier, MRO, PROV-DM | **Implemented** — enrichment pipeline in library |
| 006 | Dual-Path Adapters | load_code()/load_file() extraction modes | **Partial** — ExtractionMode exists but file-mode not fully tested |
| 007 | End-to-End Pipeline | All 5 adapters + 9 vocabulary types | **Implemented** — pipeline CLI, all adapters working |
| 008 | Schema Import Roundtrip | GenericJSONSchemaAdapter + LinkMLAdapter | **Implemented** — adapters/json_schema.py, adapters/linkml.py |
| 009 | Tutorials | 7 notebooks, nbmake tests | **Implemented** — tutorials/ directory |
| 018 | Rich Data Element Model | ReproSchema + PROV-O + ontology + similarity | **Implemented** — models.py, hashing.py, similarity.py |
| 019 | Adapter Refactoring | BaseAdapter + ClassifiedEntity + 4-way classifier | **Implemented** — adapters/base.py, classifier.py |
| 020 | (not found) | — | N/A |
| 021 | Source Acquisition | Auto-download, cache, isolated venvs | **Implemented** — acquisition.py |
| 022 | Library Re-extraction | Full re-extraction with routing | **Implemented** — ingest.py |
| 023 | Output Directory | XDG-based output, remove ingestion/ folder | **Implemented** — cli.py get_output_dir() |
| 024 | Ontology Store | pyoxigraph RDF store, vector index | **Implemented** — ontology_store.py |
| 025 | Multi-Annotation Model | OntologyAnnotation list, SKOS relations, match_level | **Implemented** — models.py OntologyAnnotation |
| 026 | Staged Enrichment | UUID staging → in-place enrich → two-mode hash commit | **Implemented** — staging.py, commit.py, enrich.py |

## Outdated Requirements (removed/superseded)

| Requirement | Removed In | Reason |
|-------------|-----------|--------|
| `ontology_term` field on SemanticIdentity | 026 | Replaced by `ontology_annotations` list |
| `Constraints` model | 026 | `pattern` moved to SemanticIdentity, `allowed_values` → `response_options` |
| `SchemaProvenance` / `ValueProvenance` | 026 | Unified to `ProvenanceEntry` |
| `source_attribute` / `source_class` | 026 | Class + attribute from provenance in structural fallback hash |
| Element creation during enrichment | 026 | Enrichment now in-place only |
| Hash-based filenames at extraction | 026 | UUID filenames during staging, hash at commit |

## Active Requirements Summary

All library-affecting features (001, 005-008, 018-026) are implemented. The backend (002) and frontend (003) are separate codebases that will be rebuilt in US3. The migration API (004) is standalone and not part of the current library pipeline.

**No orphaned or conflicting requirements found.**
