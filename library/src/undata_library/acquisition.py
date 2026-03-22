"""Source acquisition: download, cache, isolate, and extract schema sources."""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .models import SourceDefinition, SourceRef
from .utils import safe_load_yaml

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "undata" / "sources"
_DEFAULT_ENVS_DIR = Path.home() / ".cache" / "undata" / "envs"
_BUNDLED_DEFS_DIR = Path(__file__).parent / "source_defs"


# ---------------------------------------------------------------------------
# Source Definition Loader
# ---------------------------------------------------------------------------


def load_source_def(name_or_path: str) -> SourceDefinition:
    """Load a source definition by name (bundled) or file path (custom)."""
    # Try as file path first
    p = Path(name_or_path)
    if p.exists() and p.suffix in (".yaml", ".yml"):
        data = safe_load_yaml(p)
        if data is None:
            raise ValueError(f"Invalid or empty source definition: {p}")
        return SourceDefinition.model_validate(data)

    # Try bundled definitions
    bundled = _BUNDLED_DEFS_DIR / f"{name_or_path}.yaml"
    if bundled.exists():
        data = safe_load_yaml(bundled)
        if data is None:
            raise ValueError(f"Invalid or empty bundled source definition: {bundled}")
        return SourceDefinition.model_validate(data)

    available = [f.stem for f in _BUNDLED_DEFS_DIR.glob("*.yaml")]
    raise ValueError(
        f"Unknown source: '{name_or_path}'. "
        f"Available: {', '.join(sorted(available))}. "
        f"Or provide a path to a custom source definition YAML."
    )


def list_bundled_sources() -> list[str]:
    """List names of all bundled source definitions (excludes ontologies.yaml)."""
    return sorted(f.stem for f in _BUNDLED_DEFS_DIR.glob("*.yaml") if f.stem != "ontologies")


# ---------------------------------------------------------------------------
# Source Cache Manager
# ---------------------------------------------------------------------------


class SourceCache:
    """Download, cache, and retrieve schema sources with version metadata."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or _DEFAULT_CACHE_DIR

    def acquire(
        self,
        source_def: SourceDefinition,
        version: str | None = None,
        refresh: bool = False,
        offline: bool = False,
    ) -> Path:
        """Acquire a source, returning the path to cached files."""
        ver = version or source_def.default_version
        dest = self.cache_dir / source_def.name / ver

        # Check cache
        if dest.exists() and not refresh:
            logger.info("Using cached %s/%s", source_def.name, ver)
            return dest

        if offline:
            raise RuntimeError(
                f"Source {source_def.name}/{ver} not cached and --offline specified. "
                f"Run without --offline first to download."
            )

        dest.mkdir(parents=True, exist_ok=True)

        if source_def.acquisition == "git_clone":
            self._git_clone(source_def.repo, ver, dest)
        elif source_def.acquisition == "pip_install":
            # For pip_install, we just record the metadata here;
            # actual installation happens in IsolatedEnv
            pass
        elif source_def.acquisition == "download_file":
            self._download_file(source_def.repo, dest)
        else:
            raise ValueError(f"Unknown acquisition method: {source_def.acquisition}")

        self._write_source_meta(dest, source_def, ver)
        return dest

    def _git_clone(self, repo: str, version: str, dest: Path) -> None:
        """Clone a git repo at a specific version. Resolves HEAD SHA for provenance."""
        logger.info("Cloning %s at %s", repo, version)

        repo_dir = dest / "_repo"
        args = ["git", "clone", "--depth", "1"]
        if version != "latest":
            args += ["--branch", version]
        args += [repo, str(repo_dir)]

        result = subprocess.run(args, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.warning("Shallow clone failed, trying full clone: %s", result.stderr[:200])
            full_args = ["git", "clone", repo, str(repo_dir)]
            result = subprocess.run(full_args, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed: {result.stderr[:500]}")
            if version != "latest":
                subprocess.run(
                    ["git", "-C", str(repo_dir), "checkout", version],
                    capture_output=True,
                    text=True,
                    check=True,
                )

        # Resolve actual committish (HEAD SHA) for precise provenance
        sha_result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        if sha_result.returncode == 0:
            resolved_sha = sha_result.stdout.strip()
            # Write resolved committish to meta
            (dest / "_resolved_committish").write_text(resolved_sha)

    def _download_file(self, url: str, dest: Path) -> None:
        """Download a file from URL."""
        import httpx

        logger.info("Downloading %s", url)
        resp = httpx.get(url, follow_redirects=True, timeout=60)
        resp.raise_for_status()

        filename = url.rsplit("/", 1)[-1] or "schema"
        (dest / filename).write_bytes(resp.content)

    def _write_source_meta(
        self, cache_path: Path, source_def: SourceDefinition, version: str
    ) -> None:
        """Write source-meta.yaml with checksums."""
        checksums = {}
        for f in sorted(cache_path.rglob("*")):
            if f.is_file() and f.name != "source-meta.yaml":
                rel = str(f.relative_to(cache_path))
                checksums[rel] = hashlib.sha256(f.read_bytes()).hexdigest()

        meta = {
            "repo": source_def.repo,
            "version": version,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "acquisition": source_def.acquisition,
            "checksums": checksums,
        }
        (cache_path / "source-meta.yaml").write_text(
            yaml.dump(meta, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def list_cached(self) -> list[dict[str, Any]]:
        """List all cached sources with metadata."""
        results = []
        if not self.cache_dir.exists():
            return results
        for source_dir in sorted(self.cache_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            for ver_dir in sorted(source_dir.iterdir()):
                if not ver_dir.is_dir():
                    continue
                meta_file = ver_dir / "source-meta.yaml"
                meta = {}
                if meta_file.exists():
                    meta = safe_load_yaml(meta_file) or {}
                # Calculate size
                size = sum(f.stat().st_size for f in ver_dir.rglob("*") if f.is_file())
                results.append(
                    {
                        "source": source_dir.name,
                        "version": ver_dir.name,
                        "path": str(ver_dir),
                        "size_mb": round(size / 1024 / 1024, 1),
                        "downloaded_at": meta.get("downloaded_at", "unknown"),
                    }
                )
        return results

    def clean(self, older_than_days: int | None = None) -> int:
        """Remove cached sources. Returns count of removed directories."""
        removed = 0
        if not self.cache_dir.exists():
            return 0
        now = datetime.now(timezone.utc)
        for source_dir in sorted(self.cache_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            for ver_dir in sorted(source_dir.iterdir()):
                if not ver_dir.is_dir():
                    continue
                if older_than_days is not None:
                    meta_file = ver_dir / "source-meta.yaml"
                    if meta_file.exists():
                        meta = safe_load_yaml(meta_file) or {}
                        dl_at = meta.get("downloaded_at")
                        if dl_at:
                            from datetime import datetime as dt_cls

                            dl_time = dt_cls.fromisoformat(dl_at)
                            age = (now - dl_time).days
                            if age < older_than_days:
                                continue
                shutil.rmtree(ver_dir)
                removed += 1
        return removed


# ---------------------------------------------------------------------------
# Isolated Environment Manager
# ---------------------------------------------------------------------------


class IsolatedEnv:
    """Manage temporary venvs for code introspection."""

    def __init__(self, envs_dir: Path | None = None):
        self.envs_dir = envs_dir or _DEFAULT_ENVS_DIR

    def create_venv(self, source_def: SourceDefinition, version: str = "latest") -> Path:
        """Create an isolated venv for a source."""
        env_hash = hashlib.sha256(f"{source_def.name}_{version}".encode()).hexdigest()[:8]
        env_name = f"{source_def.name}_{version}_{env_hash}"
        env_path = self.envs_dir / env_name

        if env_path.exists():
            return env_path

        env_path.mkdir(parents=True, exist_ok=True)
        venv_path = env_path / ".venv"

        # Create venv with specified Python version
        cmd = ["uv", "venv"]
        if source_def.python_version:
            cmd += ["--python", source_def.python_version]
        cmd.append(str(venv_path))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to create venv for {source_def.name}: {result.stderr[:500]}"
            )

        return env_path

    def install_and_introspect(self, env_path: Path, package: str, adapter_name: str) -> list[dict]:
        """Install package in venv and run introspection script."""
        venv_path = env_path / ".venv"
        python = venv_path / "bin" / "python"

        # Install package
        install_cmd = ["uv", "pip", "install", "--python", str(python), package]
        result = subprocess.run(install_cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install {package}: {result.stderr[:500]}")

        # Run introspection script
        script = Path(__file__).parent / "adapters" / "docker_scripts" / "python_inspect.py"
        if not script.exists():
            raise FileNotFoundError(f"Introspection script not found: {script}")

        inspect_cmd = [str(python), str(script), package.replace("-", "_")]
        result = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Introspection failed for {package}: {result.stderr[:500]}")

        import json

        return json.loads(result.stdout)

    def install_and_run_adapter(
        self,
        env_path: Path,
        package: str,
        adapter_name: str,
        extra_deps: list[str] | None = None,
    ) -> list[dict] | str:
        """Install source package in venv, run standalone extraction script.

        Uses adapter-specific standalone scripts (bids_extract.py, dandi_extract.py).
        Extra dependencies (e.g., linkml-runtime) can be installed alongside the
        source package for scripts that need them.

        Returns JSON-parsed list of dicts, or raw string output if the script
        produces non-JSON (e.g., LinkML YAML).
        """
        import json

        venv_path = env_path / ".venv"
        python = venv_path / "bin" / "python"

        # Install source package + extra dependencies
        packages = [package]
        if extra_deps:
            packages.extend(extra_deps)
        install_cmd = ["uv", "pip", "install", "--python", str(python)] + packages
        result = subprocess.run(install_cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install {packages}: {result.stderr[:500]}")

        # Find standalone extraction script for this adapter
        scripts_dir = Path(__file__).parent / "adapters" / "docker_scripts"
        script = scripts_dir / f"{adapter_name}_extract.py"
        if not script.exists():
            # Fall back to generic introspection
            script = scripts_dir / "python_inspect.py"
            args = [str(python), str(script), package.replace("-", "_")]
        else:
            args = [str(python), str(script)]

        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Extraction failed for {adapter_name}: {result.stderr[:500]}")

        # Try JSON first; if it fails, return raw output (e.g., LinkML YAML)
        stdout = result.stdout.strip()
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return stdout

    def cleanup(self, env_path: Path) -> None:
        """Remove an isolated environment."""
        if env_path.exists():
            shutil.rmtree(env_path)


# ---------------------------------------------------------------------------
# Pipeline Helpers
# ---------------------------------------------------------------------------


def acquire_source(
    source_name: str,
    version: str | None = None,
    source_def_path: str | None = None,
    refresh: bool = False,
    offline: bool = False,
    keep_envs: bool = False,
    cache_dir: Path | None = None,
    envs_dir: Path | None = None,
) -> tuple[Path | None, list[dict] | None, SourceRef]:
    """Acquire a source and return (schema_path, entities_if_pip, source_ref).

    For git_clone/download_file: returns (path_to_files, None, source_ref)
    For pip_install: returns (None, classified_entities, source_ref)
    """
    # Load source definition
    def_name = source_def_path or source_name
    source_def = load_source_def(def_name)

    # Acquire/cache source
    cache = SourceCache(cache_dir)
    ver = version or source_def.default_version
    cache_path = cache.acquire(source_def, ver, refresh=refresh, offline=offline)

    # Build source_ref from cache metadata
    source_ref = build_source_ref_from_cache(source_def, cache_path)

    if source_def.acquisition == "pip_install":
        # Create isolated env, install, introspect
        iso = IsolatedEnv(envs_dir)
        env_path = iso.create_venv(source_def, ver)
        try:
            entities = iso.install_and_introspect(
                env_path, source_def.package or source_def.name, source_def.adapter
            )
            return None, entities, source_ref
        finally:
            if not keep_envs:
                iso.cleanup(env_path)
    else:
        # Return path to cloned/downloaded files
        schema_path = cache_path
        if source_def.acquisition == "git_clone" and (cache_path / "_repo").exists():
            schema_path = cache_path / "_repo"
        return schema_path, None, source_ref


def build_source_ref_from_cache(source_def: SourceDefinition, cache_path: Path) -> SourceRef:
    """Build SourceRef from cache metadata. Uses resolved git SHA, not 'latest'."""
    # Prefer resolved committish (actual SHA) over version label
    resolved_file = cache_path / "_resolved_committish"
    if resolved_file.exists():
        committish = resolved_file.read_text().strip()
    else:
        meta_file = cache_path / "source-meta.yaml"
        if meta_file.exists():
            meta = safe_load_yaml(meta_file) or {}
            committish = meta.get("version")
        else:
            committish = None

    return SourceRef(
        repo=source_def.repo,
        committish=committish,
        file=str(cache_path),
        checksum="",
    )
