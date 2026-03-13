# Implementation Plan: End-to-End Schema Ingestion and LinkML Export

**Branch**: `007-end-to-end-pipeline` | **Date**: 2026-03-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-end-to-end-pipeline/spec.md`

---

## Summary

Extend the ingestion package to ingest the full real-world schemas from all five
neuroscience data standards (BIDS: 500+ fields, DANDI: 200+ fields, NWB: 80 types,
openMINDS: 292 schemas, AIND: 9 core modules) into a clean database. Enhance
`NWBAdapter.load_file()` to traverse the NWB multi-file namespace structure.
Extend `LinkMLSchemaGenerator` to emit schema-level `is_a`, `mixin: true`, and
`mixins: [...]` from DynamicSchema inheritance data in the backend. Provide a
reproducible `Makefile` pipeline.

---

## Technical Context

**Language/Version**: Python 3.14 (ingestion); Python 3.12 bridge venv for AIND only
**Primary Dependencies**:
- `bidsschematools` — BIDS code-path (already in pyproject.toml)
- `dandischema` — DANDI code-path (already in pyproject.toml)
- `pynwb` — NWB code-path (ADD to pyproject.toml)
- `openMINDS` — openMINDS code-path (ADD to pyproject.toml; PyPI name `openMINDS`)
- `hdmf` — NWB namespace parsing (already in pyproject.toml)
- `linkml-runtime>=1.8` — LinkML YAML generation (already in pyproject.toml)
- `linkml` — `linkml-validate` CLI for output validation (dev dependency, not runtime)
**Storage**: N/A (pipeline writes to backend PostgreSQL 16 via REST API)
**Testing**: pytest + pytest-asyncio; `uv run pytest tests/` in `ingestion/`
**Target Platform**: Python 3.14 venv (uv-managed); AIND file-path uses downloaded
JSON Schema files (no bridge venv for this feature)
**Performance Goals**: Full pipeline completes in < 10 minutes; each adapter ingests
in < 60s; generate-schema completes in < 60s
**Constraints**: All 132 existing ingestion tests MUST remain green; NWBAdapter
backward-compatible with existing single-file YAML tests

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | ✅ PASS | NWBAdapter extension is a backward-compatible addition; LinkML generator uses existing API endpoints |
| II. TDD | ✅ PASS | Tests for NWBAdapter namespace traversal and LinkML inheritance output written before implementation |
| III. API-First | ✅ PASS | All backend access via documented REST endpoints; no direct DB access |
| IV. Observability | ✅ PASS | WARN on 409 duplicate source; INFO per adapter; schema-level log counts |
| V. Versioning | ✅ PASS | linkml_gen.py version bump after generator changes; pyproject.toml version bump |
| VI. Environment Isolation | ✅ PASS | All work in Python 3.14 uv venv; AIND file-only (no bridge venv needed for this feature) |

---

## Project Structure

### Source Code (affected paths)

```text
ingestion/
├── pyproject.toml                      # Add pynwb, openMINDS deps
├── Makefile                            # New: pipeline targets
├── scripts/
│   └── fetch-schemas.sh               # New: download full fixtures
├── schemas/                           # New: downloaded full schema files
│   ├── openminds/                     # 292 .schema.omi.json files (cloned)
│   ├── nwb/                           # 13 core YAML files
│   └── aind/                          # Extended AIND JSON Schema files
├── src/undata/
│   ├── adapters/
│   │   ├── bids.py                    # Extend: full vocabulary + sidecar class grouping
│   │   ├── dandi.py                   # Fix: $defs extraction + self-ref model fallback
│   │   └── nwb.py                     # Enhance load_file(): multi-file namespace traversal
│   └── linkml_gen.py                  # Extend: inheritance + mixin emission
└── tests/
    ├── fixtures/
    │   └── nwb_namespace_sample/       # New: multi-file NWB namespace fixture for tests
    │       ├── test.namespace.yaml
    │       └── test.types.yaml
    └── unit/
        ├── test_bids_adapter.py        # Add tests for full vocabulary + sidecar classes
        ├── test_dandi_adapter.py       # Add tests for $defs extraction + self-ref fix
        ├── test_nwb_adapter.py         # Add tests for namespace traversal
        └── test_linkml_gen.py          # Add tests for inheritance/mixin emission
```

---

## Architecture Decisions

### AD-001: NWBAdapter namespace traversal

`NWBAdapter.load_file()` detects three input formats:
1. **Single YAML with `groups:` key** (current behavior, backward-compatible): load as-is.
2. **Single YAML with `namespaces:` key** (NWB namespace manifest): parse the
   `namespaces[].doc` list (each entry has a `source:` key), load each referenced
   YAML file relative to the manifest's parent directory. Each file is assumed to
   have `groups:`. (Note: the YAML key is `doc`, not `catalog`.)
3. **Directory**: glob `*.namespace.yaml` first; if found, treat as case 2.
   Fallback: glob all `*.yaml` and load each individually.

The existing test fixture `nwb_schema_sample.yaml` uses a `groups:` key — backward-
compatible. New test fixture `tests/fixtures/nwb_namespace_sample/` tests case 2/3.

### AD-002: LinkML generator two-pass architecture

**Pass 1** (existing): Fetch `GET /elements`, build per-source subclasses and slots.
**Pass 2** (new): Fetch `GET /schemas?limit=500`, then for each schema fetch
`GET /schemas/{id}/inheritance-tree`. Build `ClassDefinition` objects with `is_a`,
`mixin=True`, and `mixins=[...]`. Emit them into `schema.classes`. Do NOT re-emit
slots already covered by mixin classes (dedup by slot name set).

Pass 2 is additive — it adds new classes to `schema.classes` alongside the existing
source-level subclasses. No existing classes are replaced.

### AD-003: Makefile targets

```makefile
backend-up:    docker compose -f backend/docker-compose.yml up -d db backend
backend-wait:  wait for GET /health to return 200 (poll loop with timeout)
fetch-schemas: run scripts/fetch-schemas.sh (idempotent)
ingest-code:   undata ingest bids dandi nwb openminds --extraction-mode code
ingest-aind:   undata ingest aind --extraction-mode file
ingest:        ingest-code ingest-aind
generate:      undata generate-schema --output unified.yaml
validate:      linkml-validate --schema unified.yaml
pipeline:      backend-up backend-wait fetch-schemas ingest generate validate
```

### AD-004: openMINDS schema acquisition strategy

Primary: install `openMINDS` package (`pip install openMINDS`), use
`load_code()` with `openminds.registry["types"]["latest"]`.

Secondary (fetch-schemas.sh): sparse-checkout `schemas/latest/` from the
`openMetadataInitiative/openMINDS` GitHub repository. This provides all 292
`.schema.omi.json` files for `load_file(path)` as the file-path fallback.

The fetch-schemas.sh script handles both NWB and openMINDS:
```bash
# NWB: download 13 core YAML files
NWB_BASE="https://raw.githubusercontent.com/NeurodataWithoutBorders/nwb-schema/dev/core"
# openMINDS: sparse-checkout from GitHub
git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/openMetadataInitiative/openMINDS.git schemas/openminds-repo
# AIND: download additional JSON Schema files
AIND_BASE="https://raw.githubusercontent.com/AllenNeuralDynamics/aind-data-schema/main/..."
```

---

## Phase Plan

### Phase 0: BIDSAdapter and DANDIAdapter Enhancements (TDD)

**BIDSAdapter — full vocabulary + sidecar class grouping**

The current adapter loads only `schema.objects.metadata` (449/1,012 vocab entries).
The real BIDS vocabulary has 9 object types totaling 1,012 entries. Additionally,
the class grouping produces 440 meaningless singleton classes instead of the 22
modality-based sidecar groups from `schema.rules.sidecars`.

Changes to `ingestion/src/undata/adapters/bids.py`:
1. Extend `load_code()` to iterate ALL `schema.objects.*` attributes:
   `metadata`, `columns`, `entities`, `suffixes`, `enums`, `formats`, `datatypes`,
   `extensions`, `files`. Each entry becomes a `NormalizedElement` with
   `raw_metadata["vocabulary_type"]` set to its object type.
2. Extend `extract_classes()` to read `schema.rules.sidecars` from bidsschematools.
   Each sidecar YAML file contains named field groups; map each group to one
   `SchemaClassPayload`. Replace the `_` name-split heuristic.

**DANDIAdapter — `$defs` extraction + self-ref fix**

The current file-path mode ignores `$defs` (loses 83% of schema data). The code-path
silently drops `BioSample` (10 fields) and `PropertyValue` (8 fields).

Changes to `ingestion/src/undata/adapters/dandi.py`:
1. In `_elements_from_json_schema()`, after processing `schema["properties"]`, also
   iterate `schema.get("$defs", {})`. Each `$defs` entry with its own `properties`
   dict produces: (a) a `SchemaClassPayload` named after the `$defs` key, and
   (b) `NormalizedElement` instances for its properties.
2. In `load_code()`, after `model_json_schema()` returns 0 properties, fall back to
   `{name: field_info.annotation.__name__ for name, field_info in model.model_fields.items()}`
   to extract field names and types for self-referencing models.

### Phase 1: Dependencies + pyproject.toml

- Add `pynwb` and `openMINDS` to `ingestion/pyproject.toml` dependencies
- Bump version to `2026.03.2`
- Run `uv lock` to update lock file
- Verify existing 132 tests still pass

### Phase 2: NWBAdapter Multi-File Namespace (TDD)

- Write failing tests for namespace YAML traversal (multi-file fixture in
  `tests/fixtures/nwb_namespace_sample/`)
- Enhance `NWBAdapter.load_file()` with namespace manifest detection and traversal
- Write failing test for `extract_classes()` returning `parent_class_name` from
  `neurodata_type_inc`
- Implement class hierarchy preservation in `_elements_from_nwb_yaml()`

### Phase 3: openMINDS Full Load Verification

- Confirm `OpenMINDSAdapter.load_code()` works with installed `openMINDS` package
- Write test with real openMINDS registry mock (all 292 types → verify ≥ 200 elements)
- If openMINDS doesn't install on Python 3.14: update fetch-schemas.sh and use
  `load_file(path)` in ingest command

### Phase 4: AIND Extended Fixtures

- Write fetch-schemas.sh script downloading extended AIND JSON Schema files
- Verify `AINDAdapter.load_file(path)` works with the 4 additional modules
- Add test for extended AIND fixture loading (files in `schemas/aind/`, not
  bundled in `tests/fixtures/`)

### Phase 5: LinkML Generator Inheritance (TDD)

- Write failing tests in `test_linkml_gen.py`:
  - Mock `GET /schemas` returning a DynamicSchema with `is_mixin=True`
  - Assert output YAML has `mixin: true`
  - Mock schema with `parent_id` → assert `is_a: ParentName`
  - Mock schema with mixin edges → assert `mixins: [MixinName]`
  - Assert no slot duplication for mixin-contributed slots
- Implement `_fetch_dynamic_schemas()` in `LinkMLSchemaGenerator`
- Integrate Pass 2 into `generate()` method

### Phase 6: Makefile + fetch-schemas.sh

- Write `ingestion/scripts/fetch-schemas.sh`:
  - Download NWB core YAML files
  - Sparse-checkout openMINDS schemas/latest/
  - Download extended AIND JSON Schema files
- Write `ingestion/Makefile` with all targets
- Test idempotency (second run skips already-downloaded files)

### Phase 7: Integration + Quickstart

- Run full pipeline against live backend (requires Docker)
- Verify SC-001 through SC-007 pass
- Document any adapter-specific flags in Makefile

---

## Complexity Tracking

| Risk | Mitigation |
|------|------------|
| pynwb or openMINDS don't install on Python 3.14 | Makefile falls back to file-path; fetch-schemas.sh provides fixtures |
| NWB namespace YAML references remote schemas | load_file() fetches via httpx; tests use local multi-file fixture |
| Backend 409 on re-ingest | Ingestion pipeline already handles DuplicateSourceError via FR-006 |
| LinkML slot dedup misses cross-schema duplicates | Use `GET /schemas/{id}/resolved` to get MRO-deduped element list |
| openMINDS registry structure changes between versions | Pin `openMINDS` version in pyproject.toml; test with mock registry |
| BIDS `schema.rules.sidecars` API shape changes in bidsschematools | Pin bidsschematools version; test with mock schema object |
| DANDI `$defs` recursive $ref loops in nested types | Detect `$ref`-only entries and skip (same as existing self-ref handling) |
| DANDI Pydantic v2 self-referencing models return 0 props | Fall back to `model.model_fields` for models with empty `model_json_schema().properties` |
