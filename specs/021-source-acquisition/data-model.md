# Data Model: Source Acquisition

## New Entities

### SourceDefinition

Declarative specification for a schema source.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | yes | Unique source identifier (e.g., "bids", "nwb") |
| repo | string | yes | Git repository URL |
| default_version | string | yes | Default version to acquire ("latest" or tag) |
| acquisition | string | yes | git_clone, pip_install, or download_file |
| package | string | no | Python package name (for pip_install) |
| adapter | string | yes | Adapter name from registry |
| schema_path | string | no | Glob pattern for schema files within cloned repo |
| isolation | string | yes | none, venv, or docker |
| python_version | string | no | Required Python version for venv (bridge venv pattern) |

### SourceMeta

Per-cached-version metadata.

| Field | Type | Description |
|-------|------|-------------|
| repo | string | Repository URL |
| version | string | Resolved version (tag, branch, or SHA) |
| downloaded_at | string | ISO 8601 timestamp |
| acquisition | string | Method used |
| checksums | dict[str, str] | file path → SHA-256 |

### IsolatedEnv (runtime only, not persisted)

| Field | Type | Description |
|-------|------|-------------|
| env_path | Path | Path to venv or container ID |
| source_name | string | Source this env was created for |
| python_version | string | Python version in the env |
| created_at | string | ISO 8601 |

## Cache Directory Layout

```
~/.cache/undata/
├── sources/
│   ├── bids/
│   │   ├── v1.9.0/
│   │   │   ├── source-meta.yaml
│   │   │   └── <schema files or package>
│   │   └── latest/
│   │       └── ...
│   ├── nwb/
│   │   └── latest/
│   │       ├── source-meta.yaml
│   │       └── core/
│   │           └── *.yaml
│   └── ...
└── envs/
    ├── bids_v1.9.0_abc123/
    │   └── .venv/
    └── dandi_latest_def456/
        └── .venv/
```

## Source Definition Bundled Files

```
library/src/undata_library/source_defs/
├── bids.yaml
├── nwb.yaml
├── dandi.yaml
├── openminds.yaml
└── aind.yaml
```
