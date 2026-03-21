# Implementation Plan: Staged Enrichment Pipeline

**Branch**: `026-staged-enrichment` | **Date**: 2026-03-21 | **Spec**: spec.md

## Summary

Refactor the pipeline from identity-changing enrichment (creates duplicate elements)
to a staged model: extract → stage → enrich in-place → commit (rehash → registry).
Remove `ontology_term` from identity hash. Enrich all 4 registry entity types
(elements, schemas, valuesets, values) in dependency order. Re-extract and evaluate.

## Technical Context

**Language/Version**: Python 3.14
**Dependencies**: No new deps — refactoring existing code
**Breaking change**: `ontology_term` removed from identity hash → all elements rehashed
**Scale**: 7,756 elements → should stay ~7,756 after enrichment (not 14,114)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Simpler model: one entity = one file, no derived copies |
| II. TDD | PASS | Test-alongside |
| III. API-First Design | PASS | Same CLI interface, behavior change documented |
| IV. Observability | PASS | Enrichment provenance on each entity |
| V. Versioning & Stability | PASS | Breaking hash change; not released |
| VI. Environment Isolation | PASS | No changes |
| Evaluation Record | PASS | Re-extraction results recorded in eval-record.md |

## Phase 1: Identity Hash Change

**Goal**: Remove `ontology_term` from hash; add to `_EXCLUDED_FROM_HASH`.

| File | Change |
|------|--------|
| `hashing.py` | ADD `"ontology_term"` to `_EXCLUDED_FROM_HASH` |
| `models.py` | Document that `ontology_term` is enrichment metadata, not identity |

**Impact**: Two elements differing only in `ontology_term` now produce the same hash.
This is the desired behavior — ontology alignment is metadata, not identity.

## Phase 2: Staging Directory + Pipeline Refactor

**Goal**: Extract writes to `.staging/{run_id}/`, not directly to registry.

| File | Change |
|------|--------|
| `ingest.py` | MODIFY — write extracted entities to staging dir, not output dir |
| `cli.py` | MODIFY — pipeline generates run_id (UUID), creates staging dir, passes to ingest/enrich/commit |

**Staging layout**:
```
{output_dir}/.staging/{run_id}/
├── elements/      # staged element YAMLs (temporary names)
├── schemas/
├── values/
└── valuesets/
```

## Phase 3: In-Place Enrichment (No New Entities)

**Goal**: Enrich modifies staged files in-place. No `_create_enriched_element()`.

| File | Change |
|------|--------|
| `enrich.py` | MAJOR REFACTOR — remove `_create_enriched_element()`; replace with `_update_entity_in_place()`; enrichment adds `ontology_annotations` + `value_domain` to existing YAML files; append enrichment provenance entry |

**Enrichment order** (dependency-driven):
1. Elements + Values (parallel)
2. Valuesets (needs enriched member values)
3. Schemas (needs enriched element context)

## Phase 4: Commit Stage (Rehash → Registry)

**Goal**: Rehash each staged entity, write to registry under content-addressed name, delete staging.

| File | Change |
|------|--------|
| `ingest.py` or new `commit.py` | ADD `commit_staged(staging_dir, output_dir)` — for each staged entity: compute sha256 from semantic (excl annotations), generate filename `{name}_{hash}.yaml`, write to registry dir, merge provenance if duplicate hash, delete staging dir |

**Commit logic**:
```
for each entity in staging_dir:
    semantic = entity['semantic']
    sha256 = compute_sha256(canonical_json(semantic))  # excludes ontology_annotations etc.
    key = sha256[:12]
    filename = f"{name}_{key}.yaml"
    if registry/filename exists:
        merge provenance
    else:
        write new file with sha256 field
delete staging_dir
```

## Phase 5: All Entity Types Enrichment

**Goal**: Enrich schemas, values, valuesets (not just elements).

| File | Change |
|------|--------|
| `enrich.py` | ADD `enrich_values()` — embed value labels, assign ontology_annotations with threshold 0.8 |
| `enrich.py` | ADD `enrich_valuesets()` — derive ontology_namespace from enriched member values |
| `enrich.py` | ADD `enrich_schemas()` — assign ontology_annotations for class concepts |

## Phase 6: Re-extraction + Evaluation

**Goal**: Full pipeline run with new staged model. Verify no element proliferation. Record in eval-record.md.

| Step | Verification |
|------|-------------|
| Extract all 5 sources | Element count matches pre-enrichment baseline (~7,756) |
| Enrich all entity types | ontology_annotations present, sha256 unchanged |
| Commit to registry | Final element count = pre-enrichment count (no proliferation) |
| Transforms | Generated from committed elements (correct hashes) |
| eval-record.md | Updated with new extraction results + comparison to 2026-03-21 baseline |

**Expected eval metrics**:
- Element count: ~7,756 (not 14,114)
- Schemas: ~642
- Values: ~987
- Valuesets: ~86
- Ontology assignment rate: ≥ 70% (annotations on entities, not new entities)
- Transforms: should decrease (fewer duplicate elements = fewer pairings)

## Dependency Graph

```
Phase 1 (hash change)    → foundational
Phase 2 (staging)        → depends on Phase 1
Phase 3 (in-place enrich)→ depends on Phase 2
Phase 4 (commit)         → depends on Phase 3
Phase 5 (all types)      → depends on Phase 3
Phase 6 (re-extract+eval)→ depends on all
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| Hash exclusion | Low | Add one string to set |
| Staging directory | Medium | Pipeline needs run_id, staging path plumbing |
| In-place enrichment | Medium | Remove _create_enriched_element, replace with update pattern |
| Commit rehash | Medium | Rehash + merge logic + cleanup |
| Schema/value enrichment | Medium | New enrichment passes for 3 entity types |
| Re-extraction eval | Low | Run pipeline, check counts, update eval-record.md |

## Risks

| Risk | Mitigation |
|------|-----------|
| Existing tests expect ontology_term in hash | Update tests; ontology_term now excluded |
| Existing tests expect enrichment to create new elements | Remove/update those tests |
| Pipeline interruption leaves stale staging dir | Cleanup on next run; staging dir has run_id + timestamp |
| Schema enrichment quality (class concept matching) | Start with basic label matching; improve later |
