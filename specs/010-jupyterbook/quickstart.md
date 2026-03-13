# Quickstart: JupyterBook Documentation Site

**Feature**: 010-jupyterbook

## Build the Documentation

```bash
# From tutorials/ directory
cd tutorials

# Install dependencies (including jupyter-book)
uv sync

# Build the HTML site
uv run jupyter-book build .

# Open in browser (macOS)
open _build/html/index.html

# Open in browser (Linux)
xdg-open _build/html/index.html
```

## Expected Output

```
Running Jupyter-Book...
...
===============================================================================

Finished generating HTML for book.
Your book's HTML pages are here:
    tutorials/_build/html/
You can look at your book by opening this file in a browser:
    tutorials/_build/html/index.html
```

## Rebuild After Changes

```bash
# Clean rebuild
uv run jupyter-book clean .
uv run jupyter-book build .
```

## Verification

After build, verify:

```bash
ls _build/html/index.html                  # landing page
ls _build/html/01_getting_started.html     # T01
ls _build/html/07_data_migration.html      # T07 (last)
```
