# Implementation Plan: Extract & Transform Pipeline

**Branch**: `020-extract-transforms` | **Date**: 2026-03-20 | **Spec**: spec.md

## Summary

Re-extract all 5 sources with the 019 adapter framework, generate typed bidirectional
transforms between overlapping elements, extend the ontology inverse map to all entity
types, and integrate the `transform` step into the pipeline.

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14"`)
**Primary Dependencies**: pyyaml, pydantic 2.x, click (existing); no new dependencies
**Storage**: File-based (YAML in elements/, schemas/, values/, valuesets/, transforms/)
**Testing**: pytest
**Target Platform**: CLI tool (library package)
**Project Type**: Library/CLI
**Performance Goals**: Full 5-source pipeline < 5 minutes; standalone transform < 30s
**Constraints**: Transforms are specifications, not executable code
**Scale/Scope**: ~5000 elements across 5 sources → ~500-2000 transform pairs
**Depends on**: 019-ingestion-overhaul (adapter framework, BaseAdapter, ClassifiedEntity)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Transform generation reuses existing similarity/alignment; extends MappingRecord |
| II. TDD | PASS | Test-alongside pattern |
| III. API-First Design | PASS | CLI contracts defined; TransformRecord model before implementation |
| IV. Observability | PASS | Transform count in ingestion report; validation checks transforms |
| V. Versioning & Stability | PASS | New pipeline step; no breaking changes |
| VI. Environment Isolation | PASS | `uv run`; no new deps |
| Git Commit Discipline | PASS | Commit per phase |

## Current State

- **MappingRecord** exists in models.py with basic fields (source_element, target_element, function_type, expression)
- **MappingFunctionType** enum: identity, unit_conversion, scaling, structural, unknown
- **`_generate_transform_mappings()`** in ingest.py: generates bidirectional mappings for elements sharing ontology_term with different type/unit — writes to `mappings/` directory
- **`ontology-index` CLI**: builds reverse index from ontology_term → element URIs (elements only, not schemas/valuesets)
- **019 adapter framework**: BaseAdapter + 8 adapters + classifier + registry ready

## Phase 1: Transform Model Enhancement

**Goal**: Upgrade MappingRecord → TransformRecord with typed function specs.

| File | Change |
|------|--------|
| `models.py` | Add `type_conversion` and `value_mapping` to `MappingFunctionType`; add `TransformRecord` with `FunctionSpec` (input_type, output_type, expression, expression_type, parameters); extend provenance with PROV-O + source_ref |
| `hashing.py` | Add `build_transform_uri(source_name, target_name, key)` |

**TransformRecord model**:
```yaml
sha256: string
source_element: string          # element URI
target_element: string          # element URI
function:
  function_type: string         # identity|unit_conversion|type_conversion|scaling|structural|value_mapping
  input_type: string            # data_type of source element
  output_type: string           # data_type of target element
  expression: string | null     # formula, named function, or template
  expression_type: string       # arithmetic|named_function|template|lookup_table|none
  parameters: dict | null       # e.g., {factor: 12} for unit_conversion
confidence: float | null
sssom_predicate: string | null
provenance:
  - source: string
    generated_at: datetime
    attributed_to: uriorcurie
    activity: transform
    source_ref: SourceRef | null
```

## Phase 2: Transform Generation Engine

**Goal**: Auto-detect and generate typed transforms between overlapping elements.

| File | Change |
|------|--------|
| `transform.py` | NEW — `generate_transforms(elements_dir, library_path) -> dict`; pattern matchers for known conversions |
| `ingest.py` | Replace `_generate_transform_mappings()` with call to `transform.py` |

**Auto-detection patterns**:

| Pattern | function_type | expression_type | Example |
|---------|--------------|-----------------|---------|
| Same type, same unit | identity | none | BIDS age = NWB age (both float/years) |
| Same type, different unit | unit_conversion | arithmetic | years → months: `value * 12` |
| float → string (ISO8601) | type_conversion | named_function | `iso8601_duration_from_years` |
| string → float | type_conversion | named_function | `years_from_iso8601_duration` |
| Enum A → Enum B (shared values) | value_mapping | lookup_table | sex mapping across sources |
| flat → nested object | structural | template | field → PropertyValue wrapper |
| Different type, unknown relation | unknown | none | Flagged for manual curation |

## Phase 3: Ontology Inverse Map Extension

**Goal**: Extend `build_ontology_index()` to include schemas and valuesets.

| File | Change |
|------|--------|
| `index.py` | Modify `build_ontology_index()`: scan schemas/ and valuesets/ in addition to elements/; each entry includes entity_type |

## Phase 4: Pipeline Integration + CLI

**Goal**: Add `transform` step to pipeline, standalone `transform` CLI, validate transforms.

| File | Change |
|------|--------|
| `cli.py` | Add `transform` command; extend `pipeline` to include transform step after align; extend `validate-ingestion` to check transform integrity |
| `validation.py` | Add transform checks: source/target URIs resolve, function_type valid, expression present for non-identity |
| `workflow.py` | Add transform step to workflow engine |

**Pipeline order**: `ingest → enrich → align → transform → validate`

## Phase 5: Re-extraction + Polish

**Goal**: Run full pipeline on all 5 sources, verify output, commit.

- Delete old library output (elements/, schemas/, values/, mappings/)
- Run pipeline for each source
- Verify transforms/ populated with correct function specs
- Verify ontology-index.yaml includes schemas + valuesets
- Verify 0 validation violations
- Run all tests
- Commit and push

## Project Structure

### New/Modified Files

```text
library/src/undata_library/
├── models.py         # MODIFY — TransformRecord, FunctionSpec, MappingFunctionType extension
├── hashing.py        # MODIFY — build_transform_uri
├── transform.py      # NEW — transform generation engine + pattern matchers
├── index.py          # MODIFY — ontology index extended for schemas/valuesets
├── validation.py     # MODIFY — transform validation checks
├── workflow.py        # MODIFY — transform step in workflow
├── cli.py            # MODIFY — transform command, pipeline extension
└── ingest.py         # MODIFY — replace _generate_transform_mappings

library/
├── transforms/       # NEW — TransformRecord YAML files
└── ontology-index.yaml  # MODIFIED — includes schemas + valuesets
```

## Dependency Graph

```
Phase 1 (models)     → foundational
Phase 2 (engine)     → depends on Phase 1
Phase 3 (ontology)   → independent (can parallel with Phase 2)
Phase 4 (CLI)        → depends on Phase 2 + Phase 3
Phase 5 (re-extract) → depends on all
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| Transform model | Low | Extend existing MappingRecord; add FunctionSpec |
| Pattern detection | Medium | Rule-based matching for ~6 common patterns; edge cases in structural transforms |
| Bidirectional generation | Low | Generate forward + reverse for each match |
| Ontology index extension | Low | Add glob for schemas/ and valuesets/ |
| Pipeline integration | Low | Sequential step after align |

## Risks

| Risk | Mitigation |
|------|-----------|
| Too many transforms generated (combinatorial explosion) | Only generate between elements sharing ontology_term; skip same-hash pairs |
| Expression accuracy for complex conversions | Mark unknown patterns as `function_type: unknown`; manual curation downstream |
| Old mappings/ directory conflicts | Delete mappings/ during re-extraction; transforms/ replaces it |
