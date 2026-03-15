# undata-library

Flat-file library of neuroscience data elements and mappings in LinkML YAML format with
version history, validation, and CLI tools.

**This directory can be used as a standalone git repository.** See [Standalone Setup](#standalone-setup) below.

## Contents

- **1032 data elements** from BIDS (981) and AIND (51) schemas
- **LinkML meta-schema** (`library-schema.linkml.yaml`) defining the data format
- **Python CLI** for validation, diff, export, import, and indexing

## Install

```bash
pip install -e .
# or
uv sync
```

## Usage

```bash
# Validate all YAML files
undata-library validate elements/

# Show version differences
undata-library diff elements/element-abc123.yaml
undata-library diff elements/element-abc123.yaml --format json

# Export from a running backend
undata-library export --backend-url http://localhost:8002 --output .

# Import YAML files to a backend
undata-library import --backend-url http://localhost:8002 --path elements/

# Build machine-readable index
undata-library index --output index.yaml
```

## Data Format

Each element is a single YAML file with embedded version history:

```yaml
element:
  id: https://schema.undata.live/elements/{uuid}
  source_local_id: BIDS.subject_age
  source_id: https://schema.undata.live/sources/bids
  created_at: "2026-03-09T15:30:00Z"

versions:
  - version_num: 1
    name: subject_age
    data_type: integer
    description: Age of the research subject in years
    created_at: "2026-03-09T15:30:00Z"
    created_by: urn:undata:system

current_version: 1
```

The schema is defined by `library-schema.linkml.yaml` with classes: `ElementRecord`,
`ElementVersion`, `MappingRecord`, `MappingVersion`, `SemanticGraph`, `ChangeEntry`.

## Standalone Setup

To use this as an independent repository:

```bash
# 1. Create the standalone repo
gh repo create sensein/undata-library --public
cd /path/to/undata/library
git init
git remote add origin https://github.com/sensein/undata-library.git
git add .
git commit -m "Initial commit: 1032 elements + LinkML schema + CLI"
git push -u origin main

# 2. Add as submodule to the main undata repo
cd /path/to/undata
rm -rf library
git submodule add https://github.com/sensein/undata-library.git library
git commit -m "feat: add undata-library as git submodule"
```

## License

MIT
