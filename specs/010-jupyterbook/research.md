# Research: JupyterBook Documentation Site

**Phase 0 Output** | **Feature**: 010-jupyterbook | **Date**: 2026-03-12

---

## Decision 1: Jupyter Book Version

**Decision**: Use `jupyter-book>=1.0,<2` (Sphinx-based, 1.x series)

**Rationale**: Jupyter Book 2.0 (Nov 2024) is built on the MyST Document Engine
(JavaScript/TypeScript runtime), introducing a Node.js dependency and build complexity that
violates Principle I (Simplicity First). Jupyter Book 1.x is pure Python, well-tested, and
handles `.ipynb` files natively via Sphinx. The 1.x series is in maintenance mode but fully
supported and appropriate for this use case.

**Alternatives considered**:
- `jupyter-book>=2`: Requires Node.js runtime, adds operational complexity, in early release.
  Rejected: violates Simplicity First.
- `mkdocs` + `mkdocs-jupyter`: Additional plugin ecosystem, not designed for notebooks.
  Rejected: adds unnecessary complexity for a notebooks-first project.
- `nbconvert` direct: Produces individual HTML files without navigation, search, or theming.
  Rejected: does not meet "rendered documentation site" requirement.

---

## Decision 2: Execution Mode

**Decision**: `execute_notebooks: off`

**Rationale**: The tutorial notebooks (T01–T05, T07) require live Docker services (PostgreSQL,
Keycloak, backend at :8002, migration-api at :8004). Building documentation should not require
services to be running. Notebooks ship with pre-computed outputs from the last successful
test run against live services; JupyterBook renders those outputs as-is.

**Alternatives considered**:
- `execute_notebooks: cache`: Would attempt execution on first build; fails without services.
  Rejected: build is unreliable in offline/CI environments without full service stack.
- `execute_notebooks: auto`: Re-runs all notebooks every build. Rejected: same issue.
- Per-notebook `skip_execution` tags: Possible but requires per-cell tagging. Rejected:
  `off` is simpler and applies globally.

---

## Decision 3: Python 3.14 Compatibility

**Decision**: `jupyter-book<2` is compatible with Python 3.14 via the standard Sphinx/docutils
stack. No bridge venv required.

**Rationale**: Jupyter Book 1.x's dependencies (Sphinx 5/6/7, docutils, myst-parser,
myst-nb) support Python 3.11+. Python 3.14 may require the latest patch releases but no
structural changes. The build runs in the existing `tutorials/` venv managed by `uv`.

**Risk mitigation**: If any transitive Sphinx dependency fails on 3.14, pin to the working
version in `pyproject.toml`. The `uv.lock` file ensures reproducibility.

---

## Decision 4: Build Location

**Decision**: `tutorials/_build/html/` — build inside the `tutorials/` directory.

**Rationale**: Keeps the build output co-located with sources (standard JupyterBook convention).
The `_build/` directory is gitignored. Build command is `uv run jupyter-book build .` run
from `tutorials/`, producing `tutorials/_build/html/index.html`.

**Alternatives considered**:
- `docs/_build/html/`: Separate top-level docs dir. Rejected: adds complexity, breaks the
  current `tutorials/` self-contained structure.
- `tutorials/html/`: Non-standard location. Rejected: JupyterBook defaults and tooling expect
  `_build/`.

---

## Decision 5: Book Root / Landing Page

**Decision**: Use `tutorials/README.md` as the book root (`root: README` in `_toc.yml`).

**Rationale**: `tutorials/README.md` already exists and contains a good introduction to the
tutorial suite. Using it as the JupyterBook landing page avoids creating a redundant `intro.md`
file, keeping file count minimal (Principle I).

**Format**: `jb-book` (the standard JupyterBook format with root + chapters).

---

## Decision 6: Integration with Existing pyproject.toml

**Decision**: Add `jupyter-book>=1.0,<2` to `[dependency-groups] dev` in
`tutorials/pyproject.toml`. Run `uv sync` to regenerate `uv.lock`.

**Rationale**: The `tutorials/` directory is already a self-contained uv project with its own
`pyproject.toml` and `uv.lock`. Adding `jupyter-book` to the dev group keeps it alongside
`nbmake`, `ipykernel`, and `jupyter` — all documentation/testing tools. No separate
requirements file needed.

---

## Resolved Questions

| Question | Answer |
|----------|--------|
| Does jupyter-book work with Python 3.14? | Yes, 1.x series; may need latest patches |
| Do we need to re-execute notebooks? | No — `execute_notebooks: off` |
| Where does build output go? | `tutorials/_build/html/` |
| What is the landing page? | `tutorials/README.md` |
| Do we need a separate venv? | No — add to existing tutorials venv |
| Does this require Node.js? | No — jupyter-book 1.x is pure Python |
