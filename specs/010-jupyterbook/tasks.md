# Tasks: JupyterBook Documentation Site

**Feature**: `010-jupyterbook` | **Branch**: `010-jupyterbook`
**Input**: Design documents from `/specs/010-jupyterbook/`
**Prerequisites**: plan.md, spec.md, research.md

**User Stories**:
- US1 P1 — Build the documentation site
- US2 P1 — Pre-computed outputs preserved

---

## Phase 1: Setup

- [X] T001 Add `jupyter-book>=1.0,<2` to `tutorials/pyproject.toml` `[dependency-groups] dev`; run `uv sync` in `tutorials/`
- [X] T002 [P] Create `tutorials/_config.yml` per plan.md (execute_notebooks: off, title, exclude_patterns)
- [X] T003 [P] Create `tutorials/_toc.yml` per plan.md (jb-book format, README root, 7 chapter notebooks)
- [X] T004 [P] Create `tutorials/.gitignore` with `_build/` and `.jupyter_cache/`

## Phase 2: Build & Verify

- [X] T005 Run `uv run jupyter-book build .` from `tutorials/`; fix any errors (SC-001)
- [X] T006 Verify `tutorials/_build/html/index.html` exists (SC-002)
- [X] T007 Verify HTML pages for all 7 notebooks exist under `_build/html/` (SC-003)
- [X] T008 Verify build completes in < 60 seconds (SC-004)

## Phase 3: Documentation & Commit

- [X] T009 Update `tutorials/README.md` with JupyterBook build instructions (FR-006)
- [X] T010 Commit and push: `tutorials/pyproject.toml`, `tutorials/_config.yml`, `tutorials/_toc.yml`, `tutorials/.gitignore`, `tutorials/README.md`

---

## Dependencies

T001 → T002, T003, T004 (parallel) → T005 → T006, T007, T008 (parallel) → T009 → T010
