# Tasks: Automated Source Acquisition & Processing

**Feature**: `021-source-acquisition` | **Branch**: `021-source-acquisition`

**User Stories** (mapped from spec):
- US1 — One-Command Full Extraction (P1, FR-018 to FR-021)
- US2 — Source Registry with Download Specs (P1, FR-001 to FR-006)
- US3 — Isolated Environment Management (P1, FR-007 to FR-010)
- US4 — Source Caching with Version Pinning (P2, FR-011 to FR-017)

---

## Phase 1: Setup

- [X] T001 Create `library/src/undata_library/source_defs/` directory
- [X] T002 [P] Create `library/src/undata_library/acquisition.py` stub with module docstring

---

## Phase 2: Foundational — SourceDefinition Model + Bundled Defs

**Goal**: SourceDefinition model, YAML loader, 5 bundled source definitions.

- [X] T003 [US2] Add `SourceDefinition` Pydantic model to `library/src/undata_library/models.py`: name, repo, default_version, acquisition (git_clone|pip_install|download_file), package (optional), adapter, schema_path (optional glob), isolation (none|venv|docker), python_version (optional)
- [X] T004 [P] [US2] Create `library/src/undata_library/source_defs/bids.yaml`: name=bids, repo=github bids-specification, acquisition=pip_install, package=bidsschematools, adapter=bids, isolation=venv
- [X] T005 [P] [US2] Create `library/src/undata_library/source_defs/nwb.yaml`: name=nwb, repo=github nwb-schema, acquisition=git_clone, schema_path="core/*.yaml", adapter=nwb, isolation=none
- [X] T006 [P] [US2] Create `library/src/undata_library/source_defs/dandi.yaml`: name=dandi, repo=github dandischema, acquisition=pip_install, package=dandischema, adapter=dandi, isolation=venv
- [X] T007 [P] [US2] Create `library/src/undata_library/source_defs/openminds.yaml`: name=openminds, repo=github openMINDS, acquisition=git_clone, schema_path="**/*.jsonld", adapter=openminds, isolation=none
- [X] T008 [P] [US2] Create `library/src/undata_library/source_defs/aind.yaml`: name=aind, repo=github aind-data-schema, acquisition=git_clone, schema_path="src/**/*.json", adapter=aind, isolation=none
- [X] T009 [US2] Implement `load_source_def(name_or_path)` in `library/src/undata_library/acquisition.py`: look up bundled defs by name in source_defs/ directory; fall back to loading custom YAML path; return SourceDefinition
- [X] T010 [US2] Write tests in `library/tests/test_source_defs.py`: (a) all 5 bundled defs load successfully; (b) each has required fields (name, repo, adapter); (c) custom YAML file loads; (d) unknown name raises clear error
- [X] T011 Lint + run all tests; commit Phase 2

---

## Phase 3: US4 — Source Cache Manager

**Goal**: Download, cache, and retrieve source files with version metadata.

- [X] T012 [US4] Implement `SourceCache` class in `library/src/undata_library/acquisition.py`: `__init__(cache_dir)` with configurable base directory (default `~/.cache/undata/sources/`); `acquire(source_def, version, refresh, offline) -> Path`; dispatches to acquisition method
- [X] T013 [US4] Implement `_git_clone(repo, version, dest_dir)` in `acquisition.py`: `git clone --depth 1 --branch {version} {repo} {dest_dir}`; fallback to full clone + checkout if shallow fails; record source-meta.yaml
- [X] T014 [P] [US4] Implement `_download_file(url, dest_dir)` in `acquisition.py`: download via httpx; write to cache; compute checksums; record source-meta.yaml
- [X] T015 [US4] Implement `_write_source_meta(cache_path, source_def, version)` in `acquisition.py`: write source-meta.yaml with repo, version, downloaded_at, acquisition method, per-file SHA-256 checksums
- [X] T016 [US4] Implement cache lookup: if `{cache_dir}/{name}/{version}/` exists and `--refresh` not set, return cached path; if `--offline` and not cached, raise error
- [X] T017 [US4] Write tests in `library/tests/test_cache.py`: (a) cache miss triggers download (mock subprocess/httpx); (b) cache hit returns existing path without download; (c) --refresh forces re-download; (d) --offline with cache hit succeeds; (e) --offline without cache raises error; (f) source-meta.yaml written with correct fields
- [X] T018 Lint + run all tests; commit Phase 3

---

## Phase 4: US3 — Isolated Environment Manager

**Goal**: Create, run, and clean up temporary venvs for pip_install sources.

- [X] T019 [US3] Implement `IsolatedEnv` class in `library/src/undata_library/acquisition.py`: `create_venv(source_def, cache_path, envs_dir) -> Path`; uses `uv venv --python {python_version}` if specified; creates in `{envs_dir}/{name}_{version}_{hash}/`
- [X] T020 [US3] Implement `install_and_introspect(env_path, package, adapter_name) -> list[dict]` in `acquisition.py`: `uv pip install --python {env_path}/bin/python {package}`; copy introspection script (from adapters/docker_scripts/python_inspect.py); run `{env_path}/bin/python {script} {package}` as subprocess; parse JSON output; return ClassifiedEntity-compatible dicts
- [X] T021 [US3] Implement `cleanup_env(env_path)` in `acquisition.py`: `shutil.rmtree(env_path)` unless `--keep-envs`
- [X] T022 [US3] Implement `acquire_pip_install(source_def, version, cache, envs_dir) -> tuple[Path, list[dict]]` in `acquisition.py`: orchestrate cache lookup → venv creation → install → introspect → cleanup → return (cache_path, entities)
- [X] T023 [US3] Write tests in `library/tests/test_isolation.py`: (a) venv creation command includes correct python version; (b) install command uses correct package name; (c) introspection subprocess returns valid JSON; (d) cleanup removes venv directory; (e) --keep-envs skips cleanup (all with mocked subprocess)
- [X] T024 Lint + run all tests; commit Phase 4

---

## Phase 5: US1 — Pipeline Integration

**Goal**: Wire acquisition into pipeline; auto-acquire when no --path; new CLI flags.

- [X] T025 [US1] Modify `_extract()` in `library/src/undata_library/ingest.py`: if schema_path is None, call `load_source_def(source_name)` → `SourceCache.acquire()` → pass acquired path to adapter; for pip_install sources, use IsolatedEnv instead of adapter.extract()
- [X] T026 [US1] Add CLI flags to `ingest` and `pipeline` commands in `library/src/undata_library/cli.py`: `--version`, `--refresh`, `--offline`, `--keep-envs`, `--source-def`
- [X] T027 [US1] Add `cache` subcommand group to `library/src/undata_library/cli.py`: `cache list` (show cached sources with version/size/age) and `cache clean [--older-than N]` (remove old cached sources)
- [X] T028 [US1] Implement `build_source_ref_from_cache(source_def, cache_path) -> SourceRef` in `acquisition.py`: read source-meta.yaml, populate repo, committish (resolved version), file checksums; pass as `repo` and `committish` options to adapter.extract()
- [X] T029 [US1] Write tests in `library/tests/test_acquisition_pipeline.py`: (a) pipeline with no --path acquires source automatically (mock); (b) --version pins correct tag; (c) source_ref in provenance matches cache metadata; (d) cache list shows cached sources; (e) cache clean removes old entries
- [X] T030 Lint + run all tests; commit Phase 5

---

## Phase 6: End-to-End + Polish

- [X] T031 Run `undata-library pipeline --source bids` end-to-end (requires network for first download); verify library output produced
- [X] T032 [P] Run `undata-library pipeline --source nwb` with auto-acquisition; verify NWB elements extracted
- [X] T033 [P] Run `undata-library pipeline --source dandi` with auto-acquisition; verify DANDI elements extracted
- [X] T034 [P] Run remaining sources (openminds, aind) with auto-acquisition
- [X] T035 Verify all provenance entries have populated source_ref with repo URL and resolved committish
- [X] T036 Verify `undata-library cache list` shows all 5 cached sources
- [X] T037 Run all library tests: `uv run pytest tests/ -v`
- [X] T038 Lint all code: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- [X] T039 Final commit and push

---

## Dependencies

```
Phase 1 (T001-T002): Setup — no deps
Phase 2 (T003-T011): Source definitions — depends on Phase 1
Phase 3 (T012-T018): Cache manager — depends on Phase 2
Phase 4 (T019-T024): Isolated envs — depends on Phase 2 (can parallel with Phase 3)
Phase 5 (T025-T030): Pipeline integration — depends on Phase 3 + Phase 4
Phase 6 (T031-T039): End-to-end — depends on all

Parallelizable: Phase 3 ‖ Phase 4
```

## Implementation Strategy

1. **Phase 1-2** (T001-T011): Foundation — SourceDefinition model + 5 bundled YAML defs. **Suggested MVP.**
2. **Phase 3** (T012-T018): Cache manager — download + cache with version metadata.
3. **Phase 4** (T019-T024): Isolated envs — venv creation + introspection subprocess.
4. **Phase 5** (T025-T030): Pipeline wiring — auto-acquire, new CLI flags, source_ref from cache.
5. **Phase 6** (T031-T039): Full end-to-end extraction of all 5 sources.

**Suggested MVP**: Phases 1-3 (T001-T018) — source defs + cache manager. Enables `git_clone` sources (NWB, openMINDS, AIND) to auto-download.
