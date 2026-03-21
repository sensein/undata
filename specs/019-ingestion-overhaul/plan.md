# Implementation Plan: Ingestion Overhaul

**Branch**: `019-ingestion-overhaul` | **Date**: 2026-03-20 | **Spec**: spec.md

## Summary

Overhaul the ingestion pipeline with rigorous 4-way entity classification
(class/attribute/enum/valueset), a pluggable BaseAdapter interface, LLM-assisted
disambiguation via litellm, docker-based code inspection, parameterizable YAML
workflows, output validation, and schema provenance alignment with PROV-O.

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14"`)
**Primary Dependencies**: pyyaml, pydantic 2.x, click, pyarrow (existing); litellm (new, optional for LLM); docker SDK (new, optional for code inspection)
**Storage**: File-based (YAML elements/values/schemas/valuesets + parquet embeddings)
**Testing**: pytest
**Target Platform**: CLI tool (library package)
**Project Type**: Library/CLI
**Performance Goals**: Full BIDS ingest + validate < 60s; CSV 500 rows < 10s
**Constraints**: LLM and Docker are optional — system fully functional without either
**Scale/Scope**: ~5000 elements across 5+ sources, extensible to arbitrary JSON Schema/LinkML/CSV sources

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | BaseAdapter is minimal ABC; classification is rule-based with optional LLM overlay |
| II. TDD | PASS | Test-alongside pattern (established in 018); classification test fixtures first |
| III. API-First Design | PASS | BaseAdapter contract defined before implementations; CLI contracts in spec |
| IV. Observability | PASS | classification_confidence in provenance; ingestion-report.yaml; workflow step logging |
| V. Versioning & Stability | PASS | Existing adapters refactored with backward-compatible output |
| VI. Environment Isolation | PASS | `uv run`; litellm + docker as optional deps; Docker inspection runs in isolated containers |
| Git Commit Discipline | PASS | Commit per phase |

## Current State (what exists)

- **5 extractors**: `bids.py`, `nwb.py`, `dandi.py`, `openminds.py`, `aind.py` — standalone functions, no base class
- **Dispatcher**: `_extract(source_name, schema_path)` in `ingest.py` switches on source_name string
- **No ValueSet**: Individual ValueConcepts exist but no collection entity
- **Schema provenance gap**: `SchemaProvenance` has only `source/name/description` — no PROV-O fields
- **No classification confidence**: Entities emitted without confidence scores
- **No output validation**: No post-ingestion self-check
- **No workflow spec**: Ingestion is imperative CLI calls, not declarative

## Phase 1: Schema Provenance Alignment + ValueSet Model

**Goal**: Align SchemaProvenance with ProvenanceEntry (PROV-O fields), add ValueSet entity, add sha256 to schemas.

**File Changes**:

| File | Change |
|------|--------|
| `models.py` | Extend `SchemaProvenance` with `generated_at`, `attributed_to`, `activity`, `derived_from`; add `ValueSetIdentity` + `ValueSetRecord` models |
| `hashing.py` | Add `build_valueset_uri(name, key)` |
| `ingest.py` | Update schema writing to include sha256; update schema provenance population |
| `tests/test_models.py` or fixture | Tests for new model fields |

**ValueSet model**:
```
ValueSetIdentity:
  name: str                    # e.g., "units", "modalities"
  members: list[str]           # sorted ValueConcept URIs — IN hash

ValueSetRecord:
  semantic: ValueSetIdentity
  provenance: list[ProvenanceEntry]   # same PROV-O model as elements
  sha256: str                         # stored in YAML
```

## Phase 2: BaseAdapter Interface + ClassifiedEntity

**Goal**: Define the adapter contract; refactor existing extractors to conform.

**Design**:

```python
class EntityType(str, Enum):
    CLASS = "class"           # → SchemaRecord
    ATTRIBUTE = "attribute"   # → ElementRecord
    ENUM_VALUE = "enum_value" # → ValueConcept
    VALUESET = "valueset"     # → ValueSetRecord

@dataclass
class ClassifiedEntity:
    entity_type: EntityType
    semantic: dict              # raw semantic identity dict
    provenance: dict            # raw provenance dict
    confidence: float           # 0.0–1.0 classification confidence
    source_context: dict | None # adapter-specific metadata

class BaseAdapter(ABC):
    @abstractmethod
    def extract(self, source_path: Path, **options) -> list[ClassifiedEntity]:
        """Extract and classify all entities from a source."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter name for provenance tracking."""

    @property
    def supported_formats(self) -> list[str]:
        """File extensions this adapter handles."""
        return []
```

**File Changes**:

| File | Change |
|------|--------|
| `adapters/__init__.py` | NEW — `BaseAdapter`, `ClassifiedEntity`, `EntityType`, adapter registry |
| `adapters/base.py` | NEW — ABC + dataclasses |
| `adapters/classifier.py` | NEW — Rule-based `classify_entity()` with structural signal detection |
| `extractors/bids.py` | REFACTOR → `adapters/bids.py` extending BaseAdapter |
| `extractors/nwb.py` | REFACTOR → `adapters/nwb.py` extending BaseAdapter |
| `extractors/dandi.py` | REFACTOR → `adapters/dandi.py` extending BaseAdapter |
| `extractors/openminds.py` | REFACTOR → `adapters/openminds.py` extending BaseAdapter |
| `extractors/aind.py` | REFACTOR → `adapters/aind.py` extending BaseAdapter |
| `ingest.py` | Refactor to consume `list[ClassifiedEntity]` from adapters; route by EntityType |

## Phase 3: Generic Source Adapters

**Goal**: JSONSchemaAdapter, LinkMLAdapter, CSVDictionaryAdapter — handle any schema source, not just the 5 known ones.

| File | Change |
|------|--------|
| `adapters/json_schema.py` | NEW — Generic JSON Schema (draft-07/2019/2020-12) → ClassifiedEntity |
| `adapters/linkml.py` | NEW — LinkML YAML → ClassifiedEntity (classes → CLASS, slots → ATTRIBUTE, enums → VALUESET) |
| `adapters/csv_dictionary.py` | NEW — CSV data dictionary → ClassifiedEntity (one row per element) |
| `adapters/registry.py` | NEW — Adapter registry with auto-detection by file extension + entry point loading |

**Adapter auto-detection**:
- `.json` → JSONSchemaAdapter
- `.yaml`/`.yml` with LinkML markers (`classes:`, `slots:`, `prefixes:`) → LinkMLAdapter
- `.csv`/`.tsv` → CSVDictionaryAdapter
- Directory with `pyproject.toml`/`package.json` → CodeRepoAdapter (Phase 5)

## Phase 4: LLM-Assisted Classification

**Goal**: Optional LLM fallback when rule-based confidence < threshold.

| File | Change |
|------|--------|
| `adapters/llm_classifier.py` | NEW — `LLMClassifier` using litellm; structured prompt → classification decision |
| `adapters/classifier.py` | MODIFY — integrate LLM fallback when confidence < threshold |
| `pyproject.toml` | Add `litellm` to `[llm]` optional extra |

**LLM prompt structure**:
```
Classify this schema entity as one of: class, attribute, enum_value, valueset.

Entity: {name}
Type signature: {type}
Description: {description}
Parent class: {parent_name} ({parent_type})
Sibling entities: {sibling_names}

Respond with JSON: {"classification": "...", "confidence": 0.0-1.0, "reasoning": "..."}
```

## Phase 5: Docker-Based Code Inspection

**Goal**: Launch containers to install and introspect code-defined schemas.

| File | Change |
|------|--------|
| `adapters/code_repo.py` | NEW — `CodeRepoAdapter`: detect language, build Docker command, run container, parse JSON output |
| `adapters/docker_scripts/python_inspect.py` | NEW — Script injected into Python containers: introspect Pydantic/dataclass models, emit JSON |
| `adapters/docker_scripts/ts_inspect.js` | NEW — Script for Node containers: parse TypeScript AST, emit JSON |
| `pyproject.toml` | Add `docker` to `[docker]` optional extra |

**Docker execution flow**:
1. Detect language from `pyproject.toml` (Python) or `package.json` (TypeScript)
2. Select base image (`python:3.12` / `node:20`) or use `--docker-image`
3. Mount repo read-only at `/source`
4. Copy inspection script into container
5. Run: `pip install /source && python /inspect.py > /output/result.json`
6. Read `/output/result.json` → parse into `list[ClassifiedEntity]`
7. Timeout after `--docker-timeout` seconds (default 300)

## Phase 6: Parameterizable Workflow + Output Validation

**Goal**: YAML workflow spec + ingestion-report.yaml validation.

| File | Change |
|------|--------|
| `workflow.py` | NEW — `WorkflowSpec` model (Pydantic); `run_workflow(spec, library_path)` orchestrator |
| `validation.py` | MODIFY — add `validate_ingestion_output()`: data_type validity, sha256 integrity, URI uniqueness, orphan check |
| `cli.py` | MODIFY — add `--workflow`, `--strict`, `--llm-model`, `--docker`, `--docker-image`, `--docker-timeout` to `ingest`/`pipeline` commands |
| `models.py` | ADD `IngestionReport` model |

**Workflow YAML format**:
```yaml
sources:
  - path: schemas/bids/
    adapter: bids
    options: {}
  - path: external/redcap-dd.csv
    adapter: csv_dictionary
    options:
      name_column: variable_name
      type_column: field_type
      description_column: field_label
      values_column: select_choices

classification:
  overrides:
    units: valueset      # force "units" to be classified as valueset
  confidence_threshold: 0.7
  llm_model: null        # or "ollama/llama3"

validation:
  strict: true
  checks:
    - data_type_valid
    - sha256_integrity
    - no_duplicate_uris
    - no_orphan_values
    - schema_has_properties
```

## Phase 7: Polish + Re-ingest

- Re-ingest all 5 sources with new adapter framework
- Verify 0 misclassification violations (units/modalities as ValueSets)
- Verify backward compatibility: diff output against pre-refactor baseline
- Run full test suite
- Commit and push

## Project Structure

### Source Code (library)

```text
library/src/undata_library/
├── models.py              # MODIFY — ValueSetRecord, SchemaProvenance alignment, IngestionReport
├── hashing.py             # MODIFY — build_valueset_uri
├── ingest.py              # MAJOR REFACTOR — consume ClassifiedEntity from adapters
├── adapters/              # NEW directory (replaces extractors/)
│   ├── __init__.py        # BaseAdapter, ClassifiedEntity, EntityType exports
│   ├── base.py            # ABC + dataclasses
│   ├── classifier.py      # Rule-based classification + LLM fallback
│   ├── registry.py        # Adapter auto-detection + entry point loading
│   ├── json_schema.py     # Generic JSON Schema adapter
│   ├── linkml.py          # Generic LinkML adapter
│   ├── csv_dictionary.py  # CSV data dictionary adapter
│   ├── code_repo.py       # Docker-based code inspection adapter
│   ├── llm_classifier.py  # LLM classification via litellm
│   ├── bids.py            # BIDS (refactored from extractors/)
│   ├── nwb.py             # NWB (refactored)
│   ├── dandi.py           # DANDI (refactored)
│   ├── openminds.py       # openMINDS (refactored)
│   ├── aind.py            # AIND (refactored)
│   └── docker_scripts/    # Inspection scripts injected into containers
│       ├── python_inspect.py
│       └── ts_inspect.js
├── workflow.py            # NEW — WorkflowSpec + orchestrator
├── validation.py          # MODIFY — add ingestion output validation
├── cli.py                 # MODIFY — new flags
├── embeddings.py          # EXISTING
├── enrich.py              # EXISTING
├── align.py               # EXISTING
├── similarity.py          # EXISTING
└── ...                    # other existing modules unchanged
```

## Dependency Graph

```
Phase 1 (models)     depends on: nothing (foundational)
Phase 2 (BaseAdapter) depends on: Phase 1 (ClassifiedEntity uses new EntityType)
Phase 3 (generic)    depends on: Phase 2 (extends BaseAdapter)
Phase 4 (LLM)        depends on: Phase 2 (integrates with classifier)
Phase 5 (Docker)     depends on: Phase 2 (extends BaseAdapter)
Phase 6 (workflow)   depends on: Phase 2 + Phase 3 (orchestrates adapters)
Phase 7 (polish)     depends on: all phases
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| BaseAdapter refactoring | High | 5 existing extractors must produce identical output post-refactor; backward compat is critical |
| Rule-based classifier | Medium | Structural signal detection for 4 entity types; edge cases in nested/polymorphic schemas |
| ValueSet model | Low | Simple collection entity with content-addressed identity |
| LLM classification | Medium | Prompt engineering + litellm integration + response validation |
| Docker code inspection | High | Container lifecycle management, timeout handling, fallback, two language runtimes |
| CSV adapter | Low | Row-per-element mapping with configurable column names |
| Workflow engine | Medium | YAML parsing + step orchestration + provenance recording |
| Output validation | Low | Hash check + type check + uniqueness check — straightforward |

## Risks

| Risk | Mitigation |
|------|-----------|
| Adapter refactoring breaks existing output | Golden-file tests: snapshot current output, diff after refactor |
| LLM prompt returns inconsistent results | Validate against EntityType enum; retry once; fall back to rule-based |
| Docker SDK not available | Optional dependency; clear error message; `--docker` flag required |
| Classification confidence threshold too strict/loose | Configurable (default 0.7); tuned against curated test set |
| CSV data dictionaries vary widely in format | Configurable column mapping via adapter options |
| Circular $ref in JSON Schema | Cycle detection with visited set; emit warning and extract acyclic subgraph |
