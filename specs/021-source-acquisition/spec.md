# Feature Specification: Automated Source Acquisition & Processing

**Feature Branch**: `021-source-acquisition`
**Created**: 2026-03-20
**Status**: Draft
**Input**: The ingestion pipeline should automatically download and cache schema sources from their upstream repositories, create isolated environments (separate venv or Docker containers) as needed to introspect code-based schemas, and process everything end-to-end without manual setup.

## User Scenarios & Testing

### User Story 1 — One-Command Full Extraction (Priority: P1)

A data curator runs a single command (`undata-library pipeline --source bids`) and the system automatically downloads the BIDS schema source (from its GitHub repository at a specific version), caches it locally, creates any required isolated environment, extracts all entities, generates transforms, and produces a validated library output — all without the curator having installed bidsschematools or any source-specific package.

**Why this priority**: Currently, each source requires manual pre-installation of source-specific packages (bidsschematools, dandischema) or manual download of schema files. This makes the pipeline fragile, non-reproducible, and impossible to run on a clean machine.

**Independent Test**: On a clean machine with only undata-library installed, run `undata-library pipeline --source bids` and verify complete library output is produced.

**Acceptance Scenarios**:

1. **Given** a clean environment with no source packages installed, **When** `undata-library pipeline --source bids` runs, **Then** the system downloads the BIDS schema source, caches it, extracts entities, and produces elements/schemas/transforms.
2. **Given** a source was previously downloaded and cached, **When** the same pipeline runs again, **Then** the cached version is used (no re-download) unless `--refresh` is specified.
3. **Given** `--version v1.9.0` is specified, **When** the pipeline runs, **Then** exactly that version is downloaded and the `source_ref.committish` in all provenance entries reflects `v1.9.0`.

---

### User Story 2 — Source Registry with Download Specs (Priority: P1)

Each known source (BIDS, NWB, DANDI, openMINDS, AIND) has a declarative source definition specifying: where to download it (repo URL, default version/tag), what files to extract, whether it requires code introspection (and what runtime), and any pre-processing steps. New sources can be added by providing a source definition file.

**Why this priority**: Source definitions make the system extensible and self-documenting. A curator can add a new schema source by writing a YAML definition file rather than Python adapter code.

**Independent Test**: Add a new source definition YAML for a previously unknown schema, run the pipeline, and verify extraction succeeds.

**Acceptance Scenarios**:

1. **Given** a source definition for BIDS specifying `repo: https://github.com/bids-standard/bids-specification`, `default_version: latest`, `acquisition: pip_install`, **When** the pipeline runs, **Then** the system installs bidsschematools in an isolated environment and extracts via the BIDS adapter.
2. **Given** a source definition for NWB specifying `acquisition: git_clone`, `schema_path: core/*.yaml`, **When** the pipeline runs, **Then** the system clones the NWB schema repo and passes the YAML files to the NWB adapter.
3. **Given** a source definition for a new schema with `acquisition: download_file`, `url: https://example.com/schema.json`, **When** the pipeline runs, **Then** the system downloads the file, auto-detects the adapter (JSON Schema), and extracts entities.

---

### User Story 3 — Isolated Environment Management (Priority: P1)

For sources that require code introspection (BIDS via bidsschematools, DANDI via dandischema), the system automatically creates and manages isolated environments — either a temporary venv (using uv) or a Docker container — installs the source package, runs introspection, and cleans up. The main undata-library environment is never polluted with source-specific dependencies.

**Why this priority**: Source packages have conflicting dependency requirements (some need Python 3.12, some need 3.14). Isolation prevents dependency hell and ensures reproducibility.

**Independent Test**: Run BIDS extraction in an isolated venv, verify bidsschematools is NOT installed in the main environment afterward.

**Acceptance Scenarios**:

1. **Given** a source requiring pip installation, **When** the pipeline runs, **Then** a temporary venv is created (via uv), the package is installed, introspection runs, results are serialized to JSON, and the venv is optionally cleaned up.
2. **Given** a source requiring Docker, **When** `--docker` is specified or the source definition says `isolation: docker`, **Then** a container is launched with the appropriate image, the package is installed, and results are extracted via the docker inspection scripts.
3. **Given** extraction completes, **When** the isolated environment is no longer needed, **Then** temporary venvs are deleted (unless `--keep-envs` is specified for debugging).
4. **Given** a source definition specifies `python_version: "3.12"` (bridge venv pattern), **When** the venv is created, **Then** uv creates the venv with the specified Python version, not the system default.

---

### User Story 4 — Source Caching with Version Pinning (Priority: P2)

Downloaded sources are cached locally with version metadata. The cache enables offline re-extraction and version pinning for reproducible builds. Each cached source records: repo URL, version/committish, download timestamp, and file checksums.

**Why this priority**: Caching avoids redundant downloads and enables reproducible extraction (same version → same output). Essential for CI/CD pipelines running offline.

**Independent Test**: Download a source, disconnect from network, run pipeline again, verify it succeeds from cache.

**Acceptance Scenarios**:

1. **Given** a source is downloaded for the first time, **When** cached, **Then** the cache directory contains the source files plus a `source-meta.yaml` with repo, version, downloaded_at, and per-file checksums.
2. **Given** a cached source exists at version v1.9.0, **When** `--version v1.10.0` is specified, **Then** the new version is downloaded and cached alongside the old one (both retained).
3. **Given** `--refresh` is specified, **When** the pipeline runs, **Then** the cache is bypassed and the source is re-downloaded even if a cached version exists.
4. **Given** `--offline` is specified and the source is cached, **When** the pipeline runs, **Then** it uses the cached version without any network access.

---

### Edge Cases

- What happens when a GitHub repo is unreachable? The system checks the cache first; if no cached version exists, it fails with a clear error message including the URL and suggested fix.
- What happens when a pip install in an isolated venv fails? The system logs the failure, includes the pip error output, and falls back to file-based extraction if schema files are available in the cache.
- What happens when the specified version/tag doesn't exist? Fail with a clear error listing available tags (if reachable) or suggesting `latest`.
- What happens when two sources need conflicting Python versions? Each source gets its own isolated venv with the specified Python version — no conflicts possible.
- What happens when disk space is low? Cache cleanup command (`undata-library cache clean`) removes old versions, keeping only the most recent per source.

## Requirements

### Functional Requirements

**Source Acquisition**

- **FR-001**: Each known source MUST have a declarative source definition (YAML) specifying: name, repo URL, default version, acquisition method (git_clone, pip_install, download_file), adapter name, schema file patterns, isolation requirements, and Python version if applicable.
- **FR-002**: Source definitions MUST be bundled with the library (in a `source-defs/` directory) for the 5 known sources, and MUST be overridable via `--source-def PATH` CLI flag for custom sources.
- **FR-003**: The system MUST support three acquisition methods:
  - `git_clone`: Clone a git repository at a specific committish (tag, branch, or SHA), extract files matching schema_path glob patterns.
  - `pip_install`: Install a Python package in an isolated venv, introspect code (Pydantic models, dataclasses).
  - `download_file`: Download a single file or archive from a URL, extract and pass to the appropriate adapter.
- **FR-004**: For `git_clone` acquisition, the system MUST use `git clone --depth 1 --branch {version}` for efficiency, with fallback to full clone if the tag is not found.
- **FR-005**: For `pip_install` acquisition, the system MUST create a temporary venv using `uv venv`, install the package via `uv pip install`, and run an introspection script that outputs ClassifiedEntity JSON.
- **FR-006**: The introspection script MUST run in the isolated venv (subprocess), not in the main process. Results are serialized to JSON and read back by the main process.

**Isolated Environment Management**

- **FR-007**: Isolated venvs MUST be created in a configurable directory (default: `~/.cache/undata/envs/`), named `{source}_{version}_{hash}` for uniqueness.
- **FR-008**: The system MUST support specifying a Python version per source (e.g., `python_version: "3.12"` for sources incompatible with 3.14), using `uv venv --python {version}`.
- **FR-009**: Docker isolation MUST be available as an alternative to venv isolation, triggered by `--docker` flag or `isolation: docker` in the source definition.
- **FR-010**: Temporary venvs MUST be cleaned up after extraction unless `--keep-envs` is specified.

**Source Caching**

- **FR-011**: Downloaded sources MUST be cached in a configurable directory (default: `~/.cache/undata/sources/`), organized as `{source}/{version}/`.
- **FR-012**: Each cached source MUST include a `source-meta.yaml` file recording: repo URL, version, downloaded_at (ISO 8601), acquisition method, and per-file SHA-256 checksums.
- **FR-013**: The cache MUST support version coexistence: multiple versions of the same source can be cached simultaneously.
- **FR-014**: `--refresh` flag MUST force re-download even if a cached version exists.
- **FR-015**: `--offline` flag MUST prevent all network access, using only cached sources.
- **FR-016**: `undata-library cache list` CLI MUST show all cached sources with version, size, and age.
- **FR-017**: `undata-library cache clean [--older-than DAYS]` CLI MUST remove old cached sources.

**Pipeline Integration**

- **FR-018**: The `pipeline` command MUST accept `--version VERSION` to pin the source version (tag, branch, or commit SHA).
- **FR-019**: When no `--path` is specified, the pipeline MUST automatically acquire the source using the source definition, download/cache it, and pass the path to the adapter.
- **FR-020**: The `source_ref` in all provenance entries MUST be populated from the actual acquisition metadata (repo URL, resolved committish, file paths, checksums from cache).
- **FR-021**: The pipeline MUST work end-to-end on a clean machine: `undata-library pipeline --source bids` with no prior setup.

### Key Entities

- **SourceDefinition**: Declarative YAML spec for a schema source — name, repo, default_version, acquisition method, adapter, schema_path patterns, isolation requirements, python_version.
- **SourceCache**: Local cache of downloaded sources with version metadata and checksums.
- **SourceMeta**: Per-cached-version metadata file — repo, version, downloaded_at, checksums.
- **IsolatedEnv**: Managed temporary venv or Docker container for code introspection.

## Success Criteria

### Measurable Outcomes

- **SC-001**: `undata-library pipeline --source bids` succeeds on a clean machine (no bidsschematools pre-installed) and produces a valid library output.
- **SC-002**: All 5 known sources can be extracted end-to-end without any manual pre-installation steps.
- **SC-003**: Second run of the same source uses the cache — no network access required (verifiable with `--offline`).
- **SC-004**: Each provenance entry contains a complete `source_ref` with actual repo URL, resolved committish, and file checksums from the cache.
- **SC-005**: Full pipeline for all 5 sources completes in under 10 minutes on a machine with cached sources (under 30 minutes on first run including downloads).
- **SC-006**: A new source can be added by writing a single YAML definition file — no code changes required for sources using generic adapters (JSON Schema, LinkML, CSV).

### Assumptions

- `uv` is available on the host system for venv creation (already a project requirement).
- `git` is available for `git_clone` acquisition.
- Docker is optional — only required for `isolation: docker` sources. Venv isolation is the default.
- Network access is available for first-run downloads (subsequent runs can be offline with cache).
- Source definitions for the 5 known sources encode the current best-known extraction paths (these were hardcoded in the old extractors).
