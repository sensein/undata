# Implementation Plan: Unit Standardization with QUDT

**Branch**: `033-unit-standardization` | **Date**: 2026-03-28 | **Spec**: [spec.md](spec.md)

## Summary

Resolve raw unit strings to canonical QUDT URIs using the bundled TTL vocabulary, normalize units before hashing for correct dedup, extract units from all adapters, and generate QUDT-based conversion transforms.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: pyoxigraph (RDF parsing, already in deps), cmixf 0.2.x (unit validation, to be re-added)
**Storage**: QUDT TTL bundled in library package
**Testing**: pytest, 400+ existing tests as regression baseline
**Project Type**: Library (pipeline enhancement)
**Constraints**: Must not break existing 400+ tests. Fallback to raw strings when QUDT unavailable.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | UnitResolver is a single module with dict-based lookup. No new abstractions. |
| II. TDD | PASS | Unit resolver tests before implementation. |
| III. API-First Design | PASS | UnitResolver has clear interface: resolve(string) → UnitResult. |
| IV. Observability | PASS | Unresolved units logged as warnings + curation flags. |
| V. No Deprecation | PASS | Adding unit_uri field, not changing unit field. |
| VI. Environment Isolation | PASS | QUDT TTL bundled, no external downloads. |
| VII. Developer Experience | PASS | Resolver works offline with bundled data. |
| CI Green Before Merge | PASS | All tests must pass. |

## Project Structure

```text
library/src/undata_library/
├── unit_resolver.py              # NEW: QUDT resolution + alias table
├── data/
│   └── qudt/
│       └── VOCAB_QUDT-UNITS-ALL.ttl  # COPY from backend/data/qudt/
├── models.py                     # UPDATE: add unit_uri to SemanticIdentity
├── hashing.py                    # UPDATE: use unit_uri in hash when available
├── enrich.py                     # UPDATE: call resolve_units() in enrich_all()
├── adapters/
│   ├── nwb.py                    # UPDATE: extract units from NWB schemas
│   ├── dandi.py                  # UPDATE: extract units from DANDI models
│   ├── openminds.py              # UPDATE: extract units from openMINDS
│   └── aind.py                   # UPDATE: extract units from AIND JSON Schema
└── transform.py                  # UPDATE: use QUDT conversion factors

library/tests/
├── test_unit_resolver.py         # NEW: resolver tests
└── [existing 400+ tests]         # UNCHANGED
```

## Implementation Approach

### Phase 1: QUDT in Ontology Store + UnitResolver (US1)
1. Copy QUDT TTL to library/src/undata_library/data/qudt/
2. Add QUDT to ontologies.yaml config so OntologyStore loads it alongside NCIT, PATO, etc.
3. Update ontology_store.py — add unit-specific methods: `lookup_unit(symbol)`, `search_units(query)`
4. Create unit_resolver.py — thin wrapper over OntologyStore with alias table for common neuroscience unit variants ("years"→YR, "kg"→KiloGM), `resolve(raw_string) → UnitResult`
5. Write resolver tests — common units, aliases, unresolved, conversion factors
6. Re-add cmixf to library deps

### Phase 2: Hash Normalization (US2)
1. Add unit_uri field to SemanticIdentity in models.py
2. Update hashing.py — use unit_uri in canonical_json when available
3. Write hash normalization tests — verify equivalent units produce same hash

### Phase 3: Enrichment Integration (US1 continued)
1. Add resolve_units() function to enrich.py (or unit_resolver.py)
2. Call from enrich_all() as first enrichment step
3. Generate unresolved_unit curation flags
4. Verify with pipeline run

### Phase 4: Adapter Unit Extraction (US3)
1. Update NWB adapter — extract units from dtype/quantity annotations
2. Update DANDI adapter — extract units from Pydantic model field metadata
3. Update openMINDS adapter — extract units from property definitions
4. Update AIND adapter — extract units from JSON Schema fields
5. Verify entity counts and unit coverage

### Phase 5: QUDT Transforms + cmixf + Polish (US4 + US5)
1. Update transform.py — use QUDT conversion factors instead of hardcoded table
2. Add cmixf validation as optional enrichment step
3. Run full test suite, verify CI green
