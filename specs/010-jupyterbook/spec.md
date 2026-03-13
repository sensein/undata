# Feature Specification: JupyterBook Documentation Site

**Feature Branch**: `010-jupyterbook`
**Created**: 2026-03-12
**Status**: Draft
**Input**: "create a jupyterbook from the notebooks and create a rendered output"

## Overview

Build a rendered, static HTML documentation site from the 7 existing tutorial notebooks in
`tutorials/` using Jupyter Book 1.x. The site:

- Is built from the existing notebooks **without re-executing them** (services may not be
  available at build time)
- Produces a self-contained `_build/html/` directory deployable as a static site
- Integrates into the existing `tutorials/` uv-managed environment (single `pyproject.toml`)
- Can be built with a single `uv run jupyter-book build .` command from `tutorials/`

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Build the Documentation Site (Priority: P1)

A developer has the tutorial notebooks on disk (with pre-computed outputs) and wants to
generate a static HTML site they can browse locally or host.

**Independent Test**: `uv run jupyter-book build . && ls _build/html/index.html` — passes
when jupyter-book is installed and configuration files exist.

**Acceptance Scenarios**:

1. **Given** `tutorials/_config.yml` and `tutorials/_toc.yml` exist, **When** `uv run
   jupyter-book build .` is run from `tutorials/`, **Then** `_build/html/index.html` is
   created without errors.

2. **Given** the build output, **When** `_build/html/index.html` is opened in a browser,
   **Then** all 7 tutorials are listed with correct titles and navigable.

3. **Given** the build fails, **When** the error is inspected, **Then** it is due to a missing
   notebook or config file (not a Python version incompatibility).

---

### User Story 2 — Pre-computed Outputs Preserved (Priority: P1)

Notebooks must display their pre-computed cell outputs without re-execution.

**Independent Test**: Inspect `_build/html/01_getting_started.html` for rendered output.

**Acceptance Scenarios**:

1. **Given** notebooks have saved outputs (run against live services), **When** the book is
   built with `execute_notebooks: off`, **Then** cell outputs are rendered as-is.

2. **Given** a notebook with no saved outputs (e.g., 07_data_migration.ipynb on a fresh clone),
   **When** the book is built, **Then** the notebook renders without error, just with empty
   output cells.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `tutorials/_config.yml` MUST configure `execute_notebooks: off` to avoid
  requiring live services during build.
- **FR-002**: `tutorials/_toc.yml` MUST reference all 7 notebooks in execution order.
- **FR-003**: `jupyter-book` (>=1.0,<2) MUST be added to `tutorials/pyproject.toml`
  `[dependency-groups] dev`.
- **FR-004**: Build command `uv run jupyter-book build .` (from `tutorials/`) MUST produce
  `tutorials/_build/html/index.html`.
- **FR-005**: `tutorials/_build/` MUST be added to `.gitignore`.
- **FR-006**: `tutorials/README.md` MUST document the JupyterBook build step.

### Non-Functional Requirements

- **NFR-001**: Build MUST complete in under 60 seconds on a cold (no cached outputs).
- **NFR-002**: `_build/html/` MUST be a self-contained static site (no server required to view).
- **NFR-003**: No additional Python packages beyond `jupyter-book` MUST be required.

### Key Entities

- **`tutorials/_config.yml`**: JupyterBook metadata, execution settings, HTML theme.
- **`tutorials/_toc.yml`**: Table of contents listing all 7 tutorial notebooks.
- **`tutorials/_build/html/`**: Rendered output (gitignored).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run jupyter-book build .` exits with code 0 from `tutorials/`.
- **SC-002**: `tutorials/_build/html/index.html` exists after build.
- **SC-003**: HTML pages for all 7 notebooks exist under `_build/html/`.
- **SC-004**: Build completes in < 60 seconds.
- **SC-005**: `_build/` is listed in `.gitignore`.
