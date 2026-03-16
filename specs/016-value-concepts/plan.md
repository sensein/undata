# Implementation Plan: Value Concepts

**Branch**: `016-value-concepts` | **Date**: 2026-03-16 | **Spec**: spec.md

## Summary

Add content-addressed `ValueConcept` entities to the library. Enum values
(sex, species, modality, etc.) become first-class semantic objects with
ontology mappings and cross-source provenance. Extends the identity-vs-provenance
pattern from elements and schemas to the value level.

## Technical Context

**Extends**: undata-library v2 (015)
**New files**: `values/` directory, `value-mappings.yaml`, `ValueConcept` model
**Dependencies**: None new (pydantic, pyyaml, click already present)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity | ✅ | Same pattern as elements; one new model + one directory |
| II. TDD | ✅ | Tests for value model, ingestion, validation |
| III. API-First | ✅ | File format contract matches element/schema pattern |

## Project Structure (additions)

```text
library/
├── values/                        # NEW: value concept YAML files
├── value-mappings.yaml            # NEW: curated raw-string → ontology mapping
├── src/undata_library/
│   ├── models.py                  # MODIFIED: add ValueConcept
│   ├── extractors/*.py            # MODIFIED: extract enum values
│   ├── validation.py              # MODIFIED: validate value files
│   ├── ingest.py                  # MODIFIED: create value concepts during ingestion
│   └── index.py                   # MODIFIED: count values in index
└── tests/
    ├── test_values.py             # NEW
    └── fixtures/valid-value.yaml  # NEW
```

## Phases

### Phase 1: Model + Fixtures
- Add `ValueConcept`, `ValueSemanticIdentity`, `ValueProvenance` to models.py
- Create test fixtures (valid value, multi-provenance value)
- Update LinkML schema with ValueConcept class
- Tests: model validation

### Phase 2: Value Mappings + Ingestion
- Create `value-mappings.yaml` with sex, species, handedness, modality
- Update extractors to detect enum fields and create value concepts
- Update `ingest.py` to write `values/` files and update hash-registry
- Tests: ingestion creates value files, cross-source merge

### Phase 3: Validation + Index
- Update `validation.py` to validate value files
- Update `Constraints.allowed_values` to accept URIs
- Update `index.py` to include value counts
- Tests: validate value files, URI-based allowed_values

### Phase 4: Re-ingest + Polish
- Re-ingest all 5 sources with value extraction
- Verify cross-source value dedup (BIDS male = AIND Male = NWB M)
- Update README
- Commit and push
