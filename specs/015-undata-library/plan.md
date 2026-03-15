# Implementation Plan: undata-library

**Branch**: `015-undata-library` | **Date**: 2026-03-15 | **Spec**: spec.md

## Summary

Standalone Python package defining a LinkML schema for flat-file storage of data elements,
mappings, and schemas with embedded version history. Provides CLI for validate, export,
import, diff, and index operations. Lives in its own git repo, added as a submodule to
the main undata repo.

## Technical Context

**Language/Version**: Python 3.12+ (broader compatibility than backend's 3.14)
**Primary Dependencies**: linkml-runtime >=1.8, pydantic >=2.0, pyyaml, httpx, click
**Storage**: Flat YAML files in `elements/`, `mappings/`, `schemas/` directories
**Testing**: pytest with offline fixtures (no backend required for unit tests)
**Package**: `undata-library` on PyPI (or internal registry)
**Submodule**: `library/` in main undata repo

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity | ✅ | Flat YAML files; no database; minimal deps |
| II. TDD | ✅ | Tests first for validation, diff; fixtures for export/import |
| III. API-First | ✅ | CLI contract defined; LinkML schema is the interface contract |
| V. Versioning | ✅ | CalVer for package; element versions embedded in YAML |
| VI. Env Isolation | ✅ | uv-managed; standalone from main repo |

## Project Structure

```text
undata-library/                     # Standalone git repo
├── pyproject.toml                  # Package config (undata-library)
├── library-schema.linkml.yaml      # LinkML meta-schema (THE contract)
│
├── src/undata_library/
│   ├── __init__.py                 # Package version, public API
│   ├── models.py                   # Pydantic: ElementRecord, MappingRecord, etc.
│   ├── validation.py               # LinkML validation + cross-ref checks
│   ├── export.py                   # Backend API → YAML files
│   ├── import_lib.py               # YAML files → Backend API
│   ├── diff.py                     # Version diff engine
│   ├── index.py                    # Build index.yaml registry
│   └── cli.py                      # Click CLI: validate, export, import, diff, index
│
├── elements/                       # Element YAML files (one per element)
│   └── .gitkeep
├── mappings/                       # Mapping YAML files
│   └── .gitkeep
├── schemas/                        # Schema definition YAML files
│   └── .gitkeep
│
├── index.yaml                      # Auto-generated registry
│
├── tests/
│   ├── conftest.py
│   ├── test_validation.py          # Validates fixtures against schema
│   ├── test_models.py              # Pydantic model tests
│   ├── test_diff.py                # Version diff tests
│   ├── test_export.py              # Export with mocked backend
│   ├── test_import.py              # Import with mocked backend
│   └── fixtures/
│       ├── valid-element.yaml
│       ├── invalid-element-missing-field.yaml
│       ├── invalid-element-bad-enum.yaml
│       ├── valid-mapping.yaml
│       └── multi-version-element.yaml
│
└── README.md
```

## Data Format Design

### Element Record (one YAML file per element)

```yaml
element:
  id: https://schema.undata.live/elements/{uuid}
  source_local_id: BIDS.subject_age
  source_id: https://schema.undata.live/sources/{uuid}
  created_at: 2026-03-09T15:30:00Z

versions:
  - version_num: 1
    name: subject_age
    data_type: integer
    description: Age of the research subject in years
    required: true
    multivalued: false
    constraints:
      minimum: 0
      maximum: 150
    semantic_graph:
      ontology_term: http://purl.obolibrary.org/obo/NCIT_C124353
      unit: year
      external_uri: https://qudt.org/vocab/UNIT/YR
    created_at: 2026-03-09T15:30:00Z
    created_by: urn:undata:system

  - version_num: 2
    name: subject_age
    data_type: integer
    description: Age of the research subject in years (clarified)
    required: true
    multivalued: false
    constraints:
      minimum: 0
      maximum: 150
    semantic_graph:
      ontology_term: http://purl.obolibrary.org/obo/NCIT_C124353
      unit: year
      external_uri: https://qudt.org/vocab/UNIT/YR
    created_at: 2026-03-10T08:00:00Z
    created_by: urn:undata:curator-001
    changelog:
      - change_type: description_update
        reason: Clarified definition for domain experts
        breaking: false

current_version: 2
```

### Mapping Record (one YAML file per mapping)

```yaml
mapping:
  id: https://schema.undata.live/mappings/{uuid}
  output_element_id: https://schema.undata.live/elements/{uuid}
  status: active
  attributed_to: urn:undata:system
  confidence_score: 0.95
  created_at: 2026-03-09T16:00:00Z

versions:
  - version_num: 1
    function_type: identity
    input_element_ids:
      - https://schema.undata.live/elements/{uuid-a}
    expression_type: identity
    sssom_predicate: skos:exactMatch
    created_at: 2026-03-09T16:00:00Z
    created_by: urn:undata:system

current_version: 1
```

## LinkML Schema Design (library-schema.linkml.yaml)

Key classes:
- `ElementRecord` (root): `element` (ElementMetadata) + `versions` (ElementVersion[]) + `current_version`
- `ElementMetadata`: `id`, `source_local_id`, `source_id`, `created_at`
- `ElementVersion`: all versioned fields + `changelog` (ChangeEntry[])
- `MappingRecord` (root): `mapping` (MappingMetadata) + `versions` (MappingVersion[]) + `current_version`
- `MappingMetadata`: `id`, `output_element_id`, `status`, `attributed_to`, `confidence_score`
- `MappingVersion`: `function_type`, `expression`, `input_element_ids`, etc.
- Enums: `DataType`, `MappingFunctionType`, `MappingStatus`

Prefixes: `linkml:`, `schema:`, `prov:`, `sssom:`, `undata:`

## CLI Design

```bash
undata-library validate [PATH]           # Validate YAML against schema
undata-library export --backend-url URL  # Export backend → YAML
undata-library import --backend-url URL  # Import YAML → backend
undata-library diff FILE [--from N --to M] [--format text|json]
undata-library index [--output index.yaml]
```

Entry point via `[project.scripts]` in pyproject.toml:
```toml
[project.scripts]
undata-library = "undata_library.cli:main"
```

## Phases

1. **Phase 1**: Scaffold repo, pyproject.toml, LinkML schema, Pydantic models
2. **Phase 2**: Validation engine + CLI `validate` command + test fixtures
3. **Phase 3**: Export from backend + CLI `export` command
4. **Phase 4**: Import to backend + CLI `import` command
5. **Phase 5**: Diff engine + CLI `diff` command
6. **Phase 6**: Index builder + CLI `index` command
7. **Phase 7**: Add as git submodule to main repo, update CLAUDE.md

## Integration with Main Repo

```bash
# In main undata repo
git submodule add https://github.com/sensein/undata-library.git library
echo "library/" >> .gitmodules
```

The backend can optionally depend on `undata-library` for export/import operations,
or the CLI can be used standalone.
