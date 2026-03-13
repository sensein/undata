# Research: System Tutorials

**Branch**: `009-tutorials` | **Date**: 2026-03-11

---

## Decision 1: Tutorial Format

**Decision**: Jupyter notebooks (`.ipynb`)

**Rationale**: Jupyter notebooks are the established standard for interactive, narrative
tutorials in scientific computing and API-first tools. They combine markdown prose with
executable code and rendered output — ideal for demonstrating REST APIs and CLI workflows.
The neuroscience community (the primary audience of undata) is highly familiar with notebooks.

**Alternatives considered**:
- Plain Python scripts with comments: readable but not interactive; no rendered output
- Sphinx/ReadTheDocs with code blocks: requires separate build pipeline; not directly executable
- pytest integration tests: machine-readable but not human-friendly as documentation

---

## Decision 2: Notebook Execution in pytest

**Decision**: `nbmake` (treebeardtech/nbmake v1.5+)

**Rationale**: nbmake is the most actively maintained pytest plugin for notebook testing.
Its "runs without error" semantics are ideal for tutorials where output varies (HTTP responses,
UUIDs). Unlike `nbval`, it does not validate output cell contents — correct behavior for
live-service tutorials.

**Configuration**: `pytest --nbmake tutorials/` discovers and runs all `.ipynb` files.
Notebooks are run in-process with a Jupyter kernel; each cell failure fails the test.

**Alternatives considered**:
- `pytest-notebook`: stalled maintenance; complex configuration
- `nbval`: validates output content, causing false failures on dynamic HTTP responses
- `nbconvert --execute`: not integrated with pytest; no skip/mark support

---

## Decision 3: Service Skip Logic

**Decision**: `conftest.py` session-scoped fixture with `httpx` health check + `pytest.skip()`

**Rationale**: nbmake does not have built-in HTTP service detection. A session-scoped
conftest fixture that calls `GET /health` before any notebook runs provides clean skip
semantics. Using `pytest.importorskip`-style logic at collection time is too early; a
session fixture (with `autouse=False` — triggered per-notebook via marker) is cleaner.

**Implementation**:
```python
# tutorials/conftest.py
@pytest.fixture(scope="session")
def backend_available() -> bool:
    try:
        httpx.get(BACKEND_URL + "/health", timeout=2.0)
        return True
    except Exception:
        return False

# notebooks: first cell calls pytest.skip if service down (via env var check)
```

**Per-notebook skip pattern** (first cell of each notebook):
```python
import os, httpx, sys
backend_url = os.getenv("BACKEND_URL", "http://localhost:8002")
try:
    r = httpx.get(f"{backend_url}/health", timeout=2.0)
    r.raise_for_status()
except Exception as e:
    import pytest; pytest.skip(f"Backend unavailable: {e}")
```
nbmake treats a `pytest.skip()` in a cell as a skip, not a failure.

---

## Decision 4: Auth Token Strategy

**Decision**: Environment variable `API_KEY` with hardcoded dev-only default

**Rationale**: The backend has a well-known dev API key seeded by the quickstart fixture
(`a1b2c3d4...` 64-char hex). Using this as the default for local development means tutorials
work out-of-the-box with no setup. Production/CI uses `API_KEY` env var to override.

**Default value** (from MEMORY.md — dev token):
`a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2`

This token corresponds to the curator-role test user seeded in the backend database.

**Alternatives considered**:
- OIDC login flow in notebook: too complex, requires browser interaction
- Hardcoded token in notebook: secrets in git, violation of NFR-003
- conftest injection into kernel globals: nbmake does not support kernel pre-injection

---

## Decision 5: Tutorial Organization

**Decision**: Standalone `tutorials/` directory at repo root with `tutorials/pyproject.toml`

**Rationale**: The undata repo has no root-level `pyproject.toml` — each service (backend,
ingestion, migration-api) is independently versioned. Tutorials span all services, so a
standalone `tutorials/pyproject.toml` is the cleanest approach. It declares only the
tutorial-specific dev deps (`nbmake`, `ipykernel`), and imports `httpx` which is already
installed in the active environment.

**The tutorials venv** uses Python 3.14 and `uv` per constitution §VI.

**Alternatives considered**:
- Add nbmake to ingestion's pyproject.toml: conflates tutorial runner with schema ingestion dep
- Root pyproject.toml: doesn't exist; creating it would require major restructuring

---

## Decision 6: Tutorial Scope and Ordering

**Decision**: 7 tutorials covering the full system workflow in dependency order

| # | File | Services Required | Priority |
|---|------|-------------------|----------|
| 01 | `01_getting_started.ipynb` | backend | P1 |
| 02 | `02_ingest_schemas.ipynb` | backend + ingestion | P1 |
| 03 | `03_browse_elements.ipynb` | backend | P1 |
| 04 | `04_mappings_aliases.ipynb` | backend | P2 |
| 05 | `05_linkml_export.ipynb` | backend + ingestion | P2 |
| 06 | `06_schema_roundtrip.ipynb` | none (offline) | P2 |
| 07 | `07_data_migration.ipynb` | backend + migration-api | P3 |

**Rationale**: Ordered by dependency — each tutorial builds on the previous. T06 is placed
before T07 to allow offline validation without needing the full stack. T01 doubles as
the "infrastructure smoke test".

---

## Decision 7: Notebook Structure Template

Each notebook follows this standard structure:

```
Cell 1 (markdown): Title + one-paragraph goal + services required + estimated run time
Cell 2 (code):    Imports + environment variable reads + service availability check/skip
Cell 3 (markdown): Section heading "Setup"
Cell 4+ (code):   Tutorial steps with inline comments
Last cell (markdown): "Next Steps" pointing to the following tutorial
```

**Rationale**: Consistent structure makes tutorials predictable and easy to extend.
The service-check cell (cell 2) ensures pytest skip happens before any API calls.

---

## Open Questions: All Resolved

- **Q: Should tutorials create their own test data or depend on prior tutorials?**
  A: Each tutorial is self-contained — it creates any data it needs and cleans up via API
  (soft-delete) at the end. This ensures tutorials can run independently in any order.

- **Q: How to handle the Keycloak OIDC flow for API key creation?**
  A: Use the pre-seeded dev API key (from MEMORY.md). The getting-started tutorial documents
  the manual key creation flow in a markdown cell but uses the pre-seeded key for automation.

- **Q: Should tutorials test the frontend (003)?**
  A: No — the frontend is TypeScript/Next.js. Frontend tutorials would require Playwright,
  which is out of scope for this feature. Deferred to 010-frontend-tutorials.
