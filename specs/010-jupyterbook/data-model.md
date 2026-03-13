# Data Model: JupyterBook Documentation Site

**Phase 1 Output** | **Feature**: 010-jupyterbook | **Date**: 2026-03-12

This feature introduces no database entities, API endpoints, or Python data models.
The "data model" for this feature is the set of configuration files and their schema.

---

## Configuration Files

### `tutorials/_config.yml`

JupyterBook book-level configuration (YAML).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | yes | Book title shown in HTML nav |
| `author` | string | yes | Author attribution |
| `copyright` | string | yes | Copyright year |
| `logo` | string | no | Path to logo image (relative to book root) |
| `execute.execute_notebooks` | enum | yes | `"off"` — never re-run notebooks |
| `execute.timeout` | int | yes | Per-cell timeout in seconds |
| `exclude_patterns` | list[str] | yes | Glob patterns to exclude from build |
| `only_build_toc_files` | bool | yes | `true` — only build files listed in `_toc.yml` |
| `html.use_repository_button` | bool | no | Link to source repository |
| `html.use_issues_button` | bool | no | Link to issue tracker |

### `tutorials/_toc.yml`

Table of contents defining the navigation tree (YAML).

| Field | Type | Description |
|-------|------|-------------|
| `format` | string | Always `"jb-book"` |
| `root` | string | Filename (no extension) of the root/landing page |
| `chapters` | list | Ordered list of chapter entries |
| `chapters[].file` | string | Notebook filename relative to book root (no extension) |
| `chapters[].title` | string | Override display title (optional) |

### Build Output

| Path | Description |
|------|-------------|
| `tutorials/_build/html/index.html` | Landing page (from `README.md`) |
| `tutorials/_build/html/01_getting_started.html` | T01 rendered page |
| `tutorials/_build/html/02_ingest_schemas.html` | T02 rendered page |
| `tutorials/_build/html/03_browse_elements.html` | T03 rendered page |
| `tutorials/_build/html/04_mappings_aliases.html` | T04 rendered page |
| `tutorials/_build/html/05_linkml_export.html` | T05 rendered page |
| `tutorials/_build/html/06_schema_roundtrip.html` | T06 rendered page |
| `tutorials/_build/html/07_data_migration.html` | T07 rendered page |
| `tutorials/_build/html/_static/` | CSS, JS, fonts |

---

## File Dependency Diagram

```
tutorials/
├── _config.yml          ← new: JupyterBook config
├── _toc.yml             ← new: Table of contents
├── README.md            ← existing: becomes landing page
├── 01_getting_started.ipynb  ← existing: chapter 1
├── 02_ingest_schemas.ipynb   ← existing: chapter 2
├── 03_browse_elements.ipynb  ← existing: chapter 3
├── 04_mappings_aliases.ipynb ← existing: chapter 4
├── 05_linkml_export.ipynb    ← existing: chapter 5
├── 06_schema_roundtrip.ipynb ← existing: chapter 6
├── 07_data_migration.ipynb   ← existing: chapter 7
├── pyproject.toml       ← modified: add jupyter-book dep
├── .gitignore           ← new or modified: add _build/
└── _build/              ← gitignored: build output
    └── html/
        └── index.html
```
