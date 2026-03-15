# undata-library

Flat-file library of neuroscience data elements and mappings in LinkML YAML format.

## Install

```bash
pip install undata-library
# or
uv add undata-library
```

## Usage

```bash
# Validate YAML files
undata-library validate elements/

# Export from backend
undata-library export --backend-url http://localhost:8002 --output ./elements/

# Import to backend
undata-library import --backend-url http://localhost:8002 --path elements/

# Diff element versions
undata-library diff elements/element-e001.yaml

# Build index
undata-library index --output index.yaml
```

## Schema

The data format is defined by `library-schema.linkml.yaml`. Each element/mapping is stored
as a single YAML file with embedded version history.
