"""Code repository adapter — Docker-based schema introspection."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity

logger = logging.getLogger(__name__)

_DEFAULT_IMAGES = {
    "python": "python:3.12-slim",
    "typescript": "node:20-slim",
}


class CodeRepoAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "code-repo"

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        repo = options.get("repo")
        committish = options.get("committish")
        docker_image = options.get("docker_image")
        timeout = int(options.get("docker_timeout", 300))

        language = self._detect_language(source_path)
        if not language:
            logger.warning("Cannot detect language for %s", source_path)
            return []

        image = docker_image or _DEFAULT_IMAGES.get(language, "python:3.12-slim")
        scripts_dir = Path(__file__).parent / "docker_scripts"

        try:
            result_json = self._run_container(source_path, language, image, scripts_dir, timeout)
        except Exception as exc:
            logger.warning("Docker extraction failed for %s: %s. Falling back.", source_path, exc)
            return self._fallback_file_extraction(source_path, repo, committish)

        # Parse JSON output into ClassifiedEntity
        results: list[ClassifiedEntity] = []
        for item in result_json:
            try:
                etype = EntityType(item["entity_type"])
                # Determine package version from container output
                pkg_version = item.get("source_context", {}).get("package_version")
                ref = SourceRef(
                    repo=repo,
                    committish=committish,
                    file=item.get("source_context", {}).get("module", str(source_path)),
                    checksum="",
                    package_version=pkg_version,
                )
                results.append(
                    ClassifiedEntity(
                        entity_type=etype,
                        semantic=item["semantic"],
                        provenance=item["provenance"],
                        confidence=float(item.get("confidence", 0.8)),
                        source_ref=ref,
                        source_context=item.get("source_context"),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping invalid entity from container: %s", exc)

        return results

    def _detect_language(self, source_path: Path) -> str | None:
        if (source_path / "pyproject.toml").exists() or (source_path / "setup.py").exists():
            return "python"
        if (source_path / "package.json").exists() or (source_path / "tsconfig.json").exists():
            return "typescript"
        return None

    def _run_container(
        self,
        source_path: Path,
        language: str,
        image: str,
        scripts_dir: Path,
        timeout: int,
    ) -> list[dict]:
        """Run Docker container and return parsed JSON output."""
        if language == "python":
            script = scripts_dir / "python_inspect.py"
            # Determine package name from pyproject.toml or directory name
            pkg_name = source_path.name.replace("-", "_")
            cmd = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{source_path}:/source:ro",
                "-v",
                f"{script}:/inspect.py:ro",
                image,
                "bash",
                "-c",
                f"pip install -q /source && python /inspect.py {pkg_name}",
            ]
        elif language == "typescript":
            script = scripts_dir / "ts_inspect.js"
            cmd = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{source_path}:/source:ro",
                "-v",
                f"{script}:/inspect.js:ro",
                image,
                "node",
                "/inspect.js",
                "/source",
            ]
        else:
            raise ValueError(f"Unsupported language: {language}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Container failed: {result.stderr[:500]}")

        return json.loads(result.stdout)

    def _fallback_file_extraction(
        self,
        source_path: Path,
        repo: str | None,
        committish: str | None,
    ) -> list[ClassifiedEntity]:
        """Fall back to file-based extraction when Docker fails."""
        # Try JSON Schema adapter on any .json files
        json_files = list(source_path.glob("**/*.json"))
        if json_files:
            from .json_schema import JSONSchemaAdapter

            adapter = JSONSchemaAdapter()
            return adapter.extract(source_path, repo=repo, committish=committish)
        return []
