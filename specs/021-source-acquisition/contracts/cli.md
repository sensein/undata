# CLI Contract: Source Acquisition

## Modified Commands

### `undata-library ingest` / `undata-library pipeline`

New flags (in addition to existing):

```
--version VERSION       Pin source version (git tag, branch, or commit SHA)
--refresh               Force re-download even if cached
--offline               Use only cached sources (no network)
--keep-envs             Don't clean up temporary venvs after extraction
--source-def PATH       Custom source definition YAML file
```

When `--path` is NOT specified, the system auto-acquires the source using its definition.

### `undata-library cache` (new subcommand group)

```
undata-library cache list                    # Show all cached sources
undata-library cache clean [--older-than N]  # Remove old cached sources (N days)
```

## Source Definition YAML Schema

```yaml
name: string              # unique source identifier
repo: string              # git repository URL
default_version: string   # "latest" or specific tag/branch
acquisition: string       # git_clone | pip_install | download_file
package: string | null    # Python package name (for pip_install)
adapter: string           # adapter name from registry
schema_path: string | null  # glob pattern for schema files (for git_clone)
isolation: string         # none | venv | docker
python_version: string | null  # e.g., "3.12" for bridge venvs
```

## source-meta.yaml (cache metadata)

```yaml
repo: https://github.com/bids-standard/bids-specification
version: v1.9.0
downloaded_at: "2026-03-20T12:00:00Z"
acquisition: pip_install
checksums:
  schema/objects/entities.yaml: "a1b2c3..."
  schema/objects/metadata.yaml: "d4e5f6..."
```
