# Implementation Plan: undata-library v2 — Content-Addressed RDF Property Model

**Branch**: `015-undata-library-v2` | **Date**: 2026-03-16 | **Spec**: spec.md (v2 with clarifications)

## Summary

Redesign the library around RDF property semantics with content-addressed identity.
Elements are `rdf:Property` instances identified by their semantic graph hash.
Schemas are `sh:NodeShape` instances identified by their property set hash.
Provenance (source name, class, description) is stored separately from identity.

This replaces the v1 model (9,629 flat elements with UUID filenames) with a
deduplicated, content-addressed registry using `{attribute}_{6-char-id}` naming.

## Technical Context

**Language**: Python 3.12+
**Dependencies**: pydantic >=2.0, pyyaml, click, httpx (existing from v1)
**New**: hashlib (stdlib — no new deps)
**Testing**: pytest with offline fixtures
**Reuses**: existing `library/` directory, pyproject.toml, CLI structure

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity | ✅ | Same deps; cleaner model (identity ≠ provenance) |
| II. TDD | ✅ | Tests for hashing, dedup, validation before implementation |
| III. API-First | ✅ | CLI contract + file format contract defined |
| V. Versioning | ✅ | Content-addressed = immutable identity; provenance versioned |
| VI. Env Isolation | ✅ | uv-managed, standalone |

## Project Structure (v2)

```text
library/
├── pyproject.toml                  # (modified: same package, updated version)
├── library-schema.linkml.yaml      # (rewritten: RDF property + SHACL shape model)
├── hash-registry.yaml              # NEW: 6-char key → SHA-256 → URI
│
├── src/undata_library/
│   ├── __init__.py
│   ├── models.py                   # REWRITTEN: SemanticIdentity, Provenance, etc.
│   ├── hashing.py                  # NEW: content hash + 6-char key generation
│   ├── validation.py               # MODIFIED: validate new format
│   ├── export.py                   # REWRITTEN: content-addressed export
│   ├── import_lib.py               # MODIFIED: import new format
│   ├── ingest.py                   # NEW: direct schema ingestion (no backend)
│   ├── diff.py                     # MODIFIED: diff provenance entries
│   ├── index.py                    # MODIFIED: index new format
│   └── cli.py                      # MODIFIED: add hash + ingest commands
│
├── elements/                       # REWRITTEN: {attr}_{6-char-id}.yaml
├── schemas/                        # NEW: populated with class shapes
├── mappings/                       # Future: non-identity mappings
│
├── tests/
│   ├── test_hashing.py             # NEW: hash determinism, collision, 6-char keys
│   ├── test_models.py              # REWRITTEN: new model validation
│   ├── test_validation.py          # MODIFIED: new format fixtures
│   ├── test_ingest.py              # NEW: ingestion from raw schemas
│   ├── test_diff.py                # MODIFIED
│   ├── test_index.py               # MODIFIED
│   └── fixtures/                   # REWRITTEN: new format examples
│
├── index.yaml
└── README.md                       # UPDATED
```

## Phases

### Phase 1: Core — Hashing + Models + LinkML Schema
- Rewrite `models.py` with `SemanticIdentity`, `ProvenanceEntry`, `ElementRecord`, `SchemaRecord`
- Create `hashing.py`: `compute_semantic_hash()`, `generate_short_key()`, `build_uri()`
- Rewrite `library-schema.linkml.yaml` for the new RDF property model
- Write test fixtures in new format
- Tests: hash determinism, collision detection, model validation

### Phase 2: Validation + CLI
- Rewrite `validation.py` for new format
- Update CLI `validate` command
- Add CLI `hash` command
- Tests: validate new fixtures

### Phase 3: Ingestion Pipeline
- Create `ingest.py`: read raw schemas (BIDS/NWB/AIND/DANDI/openMINDS) →
  extract semantic graphs → compute hashes → merge provenance → write files
- Add CLI `ingest` command
- Re-export all 5 sources through the new pipeline
- Tests: ingest from fixtures, verify dedup

### Phase 4: Schema Shapes
- Extract class shapes from ingested sources
- Write `schemas/` files with property URIs + inheritance
- Build `hash-registry.yaml` for schemas
- Tests: schema hash, inheritance tracking

### Phase 5: Export/Import + Index
- Rewrite `export.py` for content-addressed output
- Update `import_lib.py` for new format
- Update `index.py` for new directory structure
- Tests: export/import round-trip

### Phase 6: Polish
- Update README.md
- Run full validation on all files
- Update CLAUDE.md
- Commit and push

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Content-addressed identity | Same semantic graph = same element, automatic dedup |
| 6-char alphanumeric keys | Human-readable, URL-safe, collision-free at scale |
| Identity ≠ provenance | Follows reproschema pattern; enables multi-source convergence |
| RDF-native in LinkML | Standard vocabularies (rdf:Property, sh:NodeShape, owl:equivalentProperty) |
| Direct ingestion (no backend) | Library can be populated from raw schema files offline |
| Underspecification OK | Partial hashes for elements without ontology terms |
