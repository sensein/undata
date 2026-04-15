# Implementation Plan: Automated Source Acquisition & Processing

**Branch**: `021-source-acquisition` | **Date**: 2026-03-20 | **Spec**: spec.md

## Summary

Make the ingestion pipeline self-contained: auto-download and cache schema sources,
create isolated venvs or Docker containers for code introspection, and run end-to-end
on a clean machine with zero manual setup. Declarative YAML source definitions for
all 5 known sources plus extensible custom source support.

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14"`)
**Primary Dependencies**: pyyaml, pydantic 2.x, click (existing); no new prod deps (uv + git assumed on host)
**Storage**: File-based (source cache at `~/.cache/undata/sources/`, envs at `~/.cache/undata/envs/`)
**Testing**: pytest
**Target Platform**: CLI tool (library package)
**Project Type**: Library/CLI
**Performance Goals**: Cached pipeline < 10 min for all 5 sources; first-run < 30 min
**Constraints**: uv and git required on host; Docker optional; network required for first download
**Depends on**: 019 (adapter framework), 020 (transforms)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Declarative YAML definitions; three acquisition methods cover all cases |
| II. TDD | PASS | Test-alongside pattern |
| III. API-First Design | PASS | SourceDefinition YAML schema + CLI contracts defined before implementation |
| IV. Observability | PASS | source-meta.yaml with checksums; provenance source_ref from cache metadata |
| V. Versioning & Stability | PASS | Version pinning for reproducible builds |
| VI. Environment Isolation | PASS | Isolated venvs per source via uv; bridge venv pattern for Python <3.14 |
| Git Commit Discipline | PASS | Commit per phase |

## Phase 1: Source Definition Model + Registry

**Goal**: SourceDefinition Pydantic model, YAML loader, 5 bundled definitions.

| File | Change |
|------|--------|
| `models.py` | ADD `SourceDefinition` model (name, repo, default_version, acquisition, package, adapter, schema_path, isolation, python_version) |
| `source_defs/bids.yaml` | NEW — BIDS source definition |
| `source_defs/nwb.yaml` | NEW — NWB source definition |
| `source_defs/dandi.yaml` | NEW — DANDI source definition |
| `source_defs/openminds.yaml` | NEW — openMINDS source definition |
| `source_defs/aind.yaml` | NEW — AIND source definition |
| `acquisition.py` | NEW — `load_source_def(name_or_path)` loader; bundled defs lookup |

**Source definitions**:

```yaml
# bids.yaml
name: bids
repo: https://github.com/bids-standard/bids-specification
default_version: latest
acquisition: pip_install
package: bidsschematools
adapter: bids
isolation: venv

# nwb.yaml
name: nwb
repo: https://github.com/NeurodataWithoutBorders/nwb-schema
default_version: latest
acquisition: git_clone
schema_path: "core/*.yaml"
adapter: nwb
isolation: none

# dandi.yaml
name: dandi
repo: https://github.com/dandi/dandischema
default_version: latest
acquisition: pip_install
package: dandischema
adapter: dandi
isolation: venv

# openminds.yaml
name: openminds
repo: https://github.com/openMetadataInitiative/openMINDS
default_version: latest
acquisition: git_clone
schema_path: "**/*.jsonld"
adapter: openminds
isolation: none

# aind.yaml
name: aind
repo: https://github.com/AllenNeuralDynamics/aind-data-schema
default_version: latest
acquisition: git_clone
schema_path: "src/**/*.json"
adapter: aind
isolation: none
```

## Phase 2: Source Cache Manager

**Goal**: Download, cache, and retrieve source files with version metadata.

| File | Change |
|------|--------|
| `acquisition.py` | ADD `SourceCache` class: `acquire(source_def, version, refresh) -> Path`; `git_clone()`, `pip_download()`, `download_file()` methods; cache directory management; source-meta.yaml writing |

**Cache structure**:
```
~/.cache/undata/sources/
├── bids/
│   └── v1.9.0/
│       ├── source-meta.yaml      # repo, version, downloaded_at, checksums
│       └── <cloned/downloaded files>
├── nwb/
│   └── latest/
│       └── ...
```

**Acquisition flows**:
- `git_clone`: `git clone --depth 1 --branch {version} {repo} {cache_dir}`
- `pip_install`: Download package to cache (for version tracking), install happens in Phase 3
- `download_file`: `httpx.get(url)` → write to cache dir

## Phase 3: Isolated Environment Manager

**Goal**: Create, run, and clean up temporary venvs for code introspection.

| File | Change |
|------|--------|
| `acquisition.py` | ADD `IsolatedEnv` class: `create_venv(source_def, cache_path) -> Path`; `run_in_venv(venv_path, script, args) -> str`; `cleanup()`; bridge venv support for python_version |

**Venv flow**:
1. `uv venv --python {python_version} {env_dir}` (or system default if not specified)
2. `uv pip install --python {env_dir}/bin/python {package}` (from cached source or PyPI)
3. `{env_dir}/bin/python {introspection_script} {package_name}` → JSON to stdout
4. Parse JSON → `list[ClassifiedEntity]`
5. Clean up venv (unless `--keep-envs`)

## Phase 4: Pipeline Integration

**Goal**: Wire acquisition into the existing pipeline so `--path` is optional.

| File | Change |
|------|--------|
| `ingest.py` | MODIFY — if `schema_path` is None, acquire source via `SourceCache.acquire()` |
| `cli.py` | ADD `--version`, `--refresh`, `--offline`, `--keep-envs`, `--source-def` flags to `ingest`/`pipeline`; ADD `cache list` and `cache clean` subcommands |

**Decision logic in pipeline**:
```
if --path provided:
    use --path directly (existing behavior)
elif source has source definition:
    acquire(source_def, version=--version, refresh=--refresh, offline=--offline)
    if acquisition == pip_install:
        create isolated venv → run introspection → get ClassifiedEntity JSON
    elif acquisition == git_clone:
        pass cloned path to adapter.extract()
    elif acquisition == download_file:
        pass downloaded file to adapter.extract()
else:
    error: "No --path and no source definition for {source}"
```

## Phase 5: Populate source_ref from Cache Metadata

**Goal**: All provenance entries get accurate source_ref from cache.

| File | Change |
|------|--------|
| `acquisition.py` | ADD `build_source_ref_from_cache(source_def, cache_path) -> SourceRef` — reads source-meta.yaml, resolves committish, computes file checksums |
| `ingest.py` | Pass `repo` and `committish` options to adapter.extract() from cache metadata |

## Phase 6: Polish + End-to-End Test

- Write integration tests: clean-machine simulation (mock downloads)
- Write cache list/clean tests
- Run full pipeline for all 5 sources (requires network)
- Verify all provenance has accurate source_ref
- Lint + test + commit

## Project Structure

```text
library/src/undata_library/
├── acquisition.py          # NEW — SourceCache, IsolatedEnv, load_source_def
├── source_defs/            # NEW — bundled YAML source definitions
│   ├── bids.yaml
│   ├── nwb.yaml
│   ├── dandi.yaml
│   ├── openminds.yaml
│   └── aind.yaml
├── models.py               # MODIFY — add SourceDefinition
├── ingest.py               # MODIFY — auto-acquire when no --path
├── cli.py                  # MODIFY — new flags + cache commands
└── adapters/               # EXISTING — unchanged
```

## Dependency Graph

```
Phase 1 (definitions)  → foundational
Phase 2 (cache)        → depends on Phase 1
Phase 3 (isolation)    → depends on Phase 1
Phase 4 (pipeline)     → depends on Phase 2 + Phase 3
Phase 5 (source_ref)   → depends on Phase 2
Phase 6 (polish)       → depends on all

Parallelizable: Phase 2 ‖ Phase 3
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| Source definitions | Low | 5 YAML files + Pydantic loader |
| Git clone acquisition | Low | subprocess git clone with depth 1 |
| Pip install in venv | Medium | uv venv creation + subprocess install + introspection script + JSON parsing |
| Cache management | Low | Directory structure + source-meta.yaml |
| Bridge venv (Python version) | Medium | uv --python flag; must handle version not available |
| Pipeline integration | Medium | Decision logic for acquisition vs --path; pass metadata to adapters |

## Risks

| Risk | Mitigation |
|------|-----------|
| uv not installed | Clear error: "uv required for source acquisition" with install link |
| git not installed | Clear error for git_clone sources; pip_install/download_file don't need git |
| Python version not available for bridge venv | Error: "Python {version} not available; install via uv python install {version}" |
| Large repo clone takes too long | `--depth 1` shallow clone; cache avoids repeat downloads |
| PyPI package version differs from repo tag | source-meta records both; package_version from pip, committish from tag |
