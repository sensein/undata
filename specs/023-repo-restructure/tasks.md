# Tasks: Repository Restructure & Ontology Bulk Download

**Feature**: `023-repo-restructure` | **Branch**: `023-repo-restructure`

**User Stories** (mapped from spec):
- US1 — Library Output Separated from Source Code (P1, FR-001 to FR-004)
- US2 — Delete Old Ingestion Folder (P1, FR-005 to FR-007)
- US3 — Bulk Ontology Download (P1, FR-008 to FR-013)
- US4 — Library Output Not in Git (P2, FR-014 to FR-015)

---

## Phase 1: Setup

- [ ] T001 Add `pronto>=2.5` to dependencies in `library/pyproject.toml`

---

## Phase 2: Foundational — Output Directory Configuration

**Goal**: RegistryConfig + --output-dir on all commands.

- [ ] T002 Add `RegistryConfig` to `library/src/undata_library/models.py`: `output_dir` property that resolves CLI flag > `$UNDATA_REGISTRY_DIR` env var > `~/.local/share/undata/registry/` (XDG default); `resolve(cli_output_dir) -> Path` classmethod
- [ ] T003 Add `get_output_dir(cli_value: str | None) -> Path` helper function to `library/src/undata_library/cli.py` using RegistryConfig resolution; create dir if not exists
- [ ] T004 [US1] Update `ingest` command in `library/src/undata_library/cli.py`: replace `--library-path` with `--output-dir` (keep `--library-path` as deprecated alias); pass resolved output dir to `ingest_source()`
- [ ] T005 [P] [US1] Update `pipeline` command in `library/src/undata_library/cli.py`: add `--output-dir`; pass to all sub-steps (ingest, enrich, align, transform)
- [ ] T006 [P] [US1] Update `enrich`, `align`, `transform`, `embed`, `validate-ingestion`, `ontology-index`, `ontology refresh` commands in `library/src/undata_library/cli.py`: add `--output-dir` flag; resolve via `get_output_dir()`
- [ ] T007 [US1] Update `library/src/undata_library/ingest.py`: accept `output_dir` parameter (default from RegistryConfig); write elements/schemas/values/valuesets to `output_dir` instead of `library_path`
- [ ] T008 [P] [US1] Update `library/src/undata_library/enrich.py`: accept `output_dir`; read/write elements from output dir
- [ ] T009 [P] [US1] Update `library/src/undata_library/align.py`: accept `output_dir`; write alignment-report.yaml to output dir
- [ ] T010 [P] [US1] Update `library/src/undata_library/transform.py`: accept `output_dir`; write transforms/ to output dir
- [ ] T011 [US1] Write tests in `library/tests/test_output_dir.py`: (a) RegistryConfig resolves CLI > env var > default; (b) output written to specified dir, not library source; (c) env var override works; (d) default dir created if missing
- [ ] T012 Lint + run all tests; commit Phase 2

---

## Phase 3: US3 — Bulk Ontology Download

**Goal**: Replace OLS API pagination with OBO Foundry bulk download + pronto parsing.

- [ ] T013 [US3] Rewrite `fetch_ontology()` in `library/src/undata_library/ontology_fetch.py`: download OBO file from canonical URL via httpx; parse with `pronto.Ontology(path)`; extract term URI, label, synonyms, parents, deprecated; return cache-format dict
- [ ] T014 [US3] Update `SUPPORTED_ONTOLOGIES` in `ontology_fetch.py`: change from OLS API config to OBO Foundry URLs — NCIT (`ncit.obo`), PATO (`pato.obo`), HP (`hp.obo`), OBI (`obi.obo`), NCBITaxon (`ncbitaxon.obo`)
- [ ] T015 [US3] Add OLS API fallback: if OBO download fails, fall back to existing OLS pagination with warning logged
- [ ] T016 [US3] Remove `--max-terms` flag from `ontology refresh` CLI in `library/src/undata_library/cli.py` (no longer needed with bulk download)
- [ ] T017 [US3] Update `ontology_cache.py`: write cache to `output_dir/ontology-cache/` (not library source tree)
- [ ] T018 [US3] Write tests in `library/tests/test_bulk_ontology.py`: (a) mock OBO download returns valid OBO content → terms parsed correctly; (b) term has label, synonyms, parents, deprecated; (c) fallback to OLS API on download failure; (d) cache written to output dir
- [ ] T019 Lint + run all tests; commit Phase 3

---

## Phase 4: US2 — Delete Ingestion Folder

**Goal**: Remove ingestion/ and update all references.

- [ ] T020 [US2] Delete `ingestion/` directory entirely: `git rm -r ingestion/`
- [ ] T021 [P] [US2] Update `README.md`: remove ingestion/ from project structure; remove ingestion CLI examples; update "Ingestion" section to point to `undata-library ingest`
- [ ] T022 [P] [US2] Update `CLAUDE.md`: remove ingestion section; remove ingestion commands; update project structure
- [ ] T023 [P] [US2] Update `docker-compose.yml`: remove ingestion service references if present
- [ ] T024 [P] [US2] Update `.github/workflows/`: remove or update CI workflows that reference ingestion/
- [ ] T025 [US2] Verify: `uv run pytest library/tests/ -q` passes with 0 failures after ingestion/ deletion
- [ ] T026 Lint + commit Phase 4

---

## Phase 5: US4 — Git Cleanup

**Goal**: Remove tracked output from git; update .gitignore.

- [ ] T027 [US4] Update `library/.gitignore`: add elements/, schemas/, values/, valuesets/, transforms/, ontology-cache/*.yaml, ontology-cache/*.obo, embeddings.parquet, hash-registry.yaml, ontology-index.yaml, alignment-report.yaml, ingestion-report.yaml
- [ ] T028 [US4] Remove tracked library output from git: `git rm -r --cached library/elements/ library/schemas/ library/values/ library/valuesets/ library/transforms/ library/hash-registry.yaml library/ontology-index.yaml library/ontology-cache/` (keeps files on disk but untracked)
- [ ] T029 [US4] Update `README.md`: add section explaining registry output location (`~/.local/share/undata/registry/` or `$UNDATA_REGISTRY_DIR`); explain registry is generated data, not committed
- [ ] T030 Lint + commit Phase 5

---

## Phase 6: Polish + Verify

- [ ] T031 Run full pipeline to default output dir: `undata-library pipeline --source bids --output-dir /tmp/test-registry` (repeat for all 5 sources)
- [ ] T032 [P] Run `undata-library ontology refresh --output-dir /tmp/test-registry` — verify bulk download produces >2000 terms for PATO
- [ ] T033 [P] Verify `git status` shows clean tree (no output files tracked)
- [ ] T034 [P] Verify `ls library/elements/` returns empty or doesn't exist (output is in output-dir)
- [ ] T035 Run all library tests: `uv run pytest tests/ -v`
- [ ] T036 Lint all code: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- [ ] T037 Final commit and push

---

## Dependencies

```
Phase 1 (T001): Setup — no deps
Phase 2 (T002-T012): Output dir config — depends on Phase 1
Phase 3 (T013-T019): Bulk ontology — depends on Phase 1 (can parallel with Phase 2)
Phase 4 (T020-T026): Delete ingestion — depends on Phase 2
Phase 5 (T027-T030): Git cleanup — depends on Phase 2
Phase 6 (T031-T037): Polish — depends on all

Parallelizable: Phase 2 ‖ Phase 3; T021-T024 parallel within Phase 4
```

## Implementation Strategy

1. **Phase 1-2** (T001-T012): Output dir config. **Suggested MVP** — decouples data from source.
2. **Phase 3** (T013-T019): Bulk ontology — can parallel with Phase 2.
3. **Phase 4** (T020-T026): Delete ingestion/ — straightforward cleanup.
4. **Phase 5** (T027-T030): Git hygiene.
5. **Phase 6** (T031-T037): Full verification.

**Suggested MVP**: Phases 1-2 (T001-T012) — output dir separation.
