# Implementation Plan: Neuroscience Schema Integration

**Branch**: `001-neuro-schema-integration` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-neuro-schema-integration/spec.md`

## Summary

A Python CLI library (`undata`) that ingests BIDS, DANDI, openMINDS, NWB, and AIND
schemas via five independent adapters, normalizes elements to a common format, pushes
them to the backend (002), runs semantic alias detection, and generates a unified
LinkML schema.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: bidsschematools, dandischema, openminds-python, hdmf,
linkml-runtime 1.8+, sentence-transformers 3.x, httpx 0.27+, typer 0.12+, pydantic v2
**Note — AIND compatibility**: `aind-data-schema` 2.x uses a native Rust extension
(`pyo3-ffi`) that does not compile on Python 3.14 yet. The `AINDAdapter` therefore
reads the pre-exported JSON Schema files bundled in `tests/fixtures/aind/` (generated
once from a Python 3.12 venv) rather than importing the package at runtime. When
`aind-data-schema` gains Python 3.14 support it can be added as an optional dependency.
**Storage**: N/A — uses 002-schema-backend API exclusively
**Testing**: pytest, pytest-asyncio, respx (httpx mock)
**Target Platform**: Developer workstation and CI (Linux, macOS)
**Project Type**: library/cli
**Performance Goals**: Full 5-schema ingestion in < 5 min on developer workstation;
alias detection over 1k elements in < 30s
**Constraints**: Must not store data locally; all persistence via backend API.
Adapters must be independently testable with mock backend responses.
**Scale/Scope**: ~500–1600 data elements across all five schemas initially

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | ✅ PASS | Five independent adapters; no shared parser abstraction forced |
| II. Test-Driven Development | ✅ PASS | CLI contract defined first; adapter tests use mock HTTP |
| III. API-First Design | ✅ PASS | CLI interface contract in contracts/cli-interface.md |
| IV. Observability | ✅ PASS | Structured log output per ingest run; progress reporting to stderr |
| V. CalVer | ✅ PASS | Generated LinkML schema version uses CalVer |
| VI. Environment Isolation | ✅ PASS | Python 3.14, `uv venv` + `uv pip install` (T002, T038); `requires-python = ">=3.14"` in pyproject.toml; no system-Python invocations |

**Dependency gate**: 002-schema-backend must be deployed and healthy before integration
tests for this feature can run. Unit tests (adapter parsing) have no such dependency.

## Project Structure

### Source Code (repository root)

```text
ingestion/
├── src/
│   └── undata/
│       ├── adapters/
│       │   ├── base.py           # SchemaAdapter Protocol
│       │   ├── aind.py           # AINDAdapter (JSON Schema file parsing)
│       │   ├── bids.py           # BIDSAdapter
│       │   ├── dandi.py          # DANDIAdapter
│       │   ├── openminds.py      # OpenMINDSAdapter
│       │   └── nwb.py            # NWBAdapter
│       ├── ingestion.py          # IngestionPipeline (httpx, bulk POST)
│       ├── alias_detection.py    # AliasDetector (embeddings + synonym table)
│       ├── linkml_gen.py         # LinkMLSchemaGenerator
│       ├── validation.py         # undata validate (linkml-runtime)
│       └── cli.py                # typer CLI entry point
├── tests/
│   ├── unit/
│   │   ├── test_bids_adapter.py
│   │   ├── test_dandi_adapter.py
│   │   ├── test_openminds_adapter.py
│   │   ├── test_nwb_adapter.py
│   │   └── test_alias_detection.py
│   ├── integration/
│   │   ├── test_ingest_pipeline.py   # uses respx mock
│   │   └── test_linkml_gen.py
│   └── fixtures/
│       ├── aind/                      # AIND JSON Schema files (generated via Python 3.12 venv)
│       │   ├── subject_schema.json
│       │   ├── acquisition_schema.json
│       │   ├── data_description_schema.json
│       │   ├── procedures_schema.json
│       │   └── instrument_schema.json
│       ├── bids_schema_sample.yaml
│       ├── dandi_schema_sample.json
│       ├── openminds_sample.json
│       └── nwb_schema_sample.yaml
└── pyproject.toml
```

## Phase 0 Research Summary

See [research.md](research.md).

| Question | Decision |
|----------|----------|
| BIDS parsing | bidsschematools + direct YAML |
| DANDI parsing | dandischema Pydantic introspection |
| openMINDS parsing | direct JSON-LD template file parsing |
| NWB parsing | hdmf spec loader |
| LinkML generation | linkml-runtime SchemaDefinition API |
| Alias detection | 3-phase: exact name → type gate → embedding cosine |
| Backend transport | httpx async, bulk POST |

## Phase 1 Design Artifacts

- [data-model.md](data-model.md) — internal data structures, adapter protocol, schema output structure
- [contracts/cli-interface.md](contracts/cli-interface.md) — CLI command contracts and Python library API
- [quickstart.md](quickstart.md) — developer validation checklist
