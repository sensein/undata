"""Export manifest and validation utilities.

Generates manifest.json for registry exports and validates
export directory structure on import.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

FORMAT_VERSION = "1.0"
REQUIRED_DIRS = ["elements", "schemas", "values", "valuesets"]
OPTIONAL_DIRS = ["transforms", "curation-flags", "runs"]


def generate_manifest(
    output_dir: Path,
    version: str | None = None,
    entity_counts: dict | None = None,
) -> dict:
    """Generate manifest.json for an export directory.

    If entity_counts is not provided, counts files in each subdirectory.
    """
    if entity_counts is None:
        entity_counts = {}
        for subdir in REQUIRED_DIRS + OPTIONAL_DIRS:
            d = output_dir / subdir
            if d.exists():
                entity_counts[subdir.replace("-", "_")] = len(list(d.glob("*.yaml")))
            else:
                entity_counts[subdir.replace("-", "_")] = 0

    now = datetime.now(timezone.utc).isoformat()
    if version is None:
        version = f"export-{now[:10]}"

    manifest = {
        "version": version,
        "format_version": FORMAT_VERSION,
        "timestamp": now,
        "entity_counts": entity_counts,
        "has_embeddings": (output_dir / "embeddings.parquet").exists(),
        "source_system": "undata",
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Generated manifest: %s", manifest_path)
    return manifest


def validate_export(export_dir: Path) -> dict:
    """Validate an export directory structure and manifest.

    Returns dict with 'valid' bool, 'errors' list, and parsed manifest.
    Checks:
    - manifest.json exists and has correct format_version
    - Required subdirectories exist
    - Entity counts in manifest match actual file counts
    """
    errors: list[str] = []
    manifest = None

    # Check manifest
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.exists():
        errors.append("manifest.json not found")
        return {"valid": False, "errors": errors, "manifest": None}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"Invalid manifest.json: {exc}")
        return {"valid": False, "errors": errors, "manifest": None}

    # Check format version
    fmt_ver = manifest.get("format_version", "")
    if fmt_ver != FORMAT_VERSION:
        errors.append(f"Incompatible format version: {fmt_ver} (expected {FORMAT_VERSION})")

    # Check required directories
    for subdir in REQUIRED_DIRS:
        d = export_dir / subdir
        if not d.exists():
            errors.append(f"Required directory missing: {subdir}/")

    # Check entity counts match file counts
    counts = manifest.get("entity_counts", {})
    for subdir in REQUIRED_DIRS + OPTIONAL_DIRS:
        d = export_dir / subdir
        key = subdir.replace("-", "_")
        if d.exists():
            actual = len(list(d.glob("*.yaml")))
            expected = counts.get(key, 0)
            if actual != expected:
                errors.append(f"{subdir}: manifest says {expected} files but found {actual}")

    return {"valid": len(errors) == 0, "errors": errors, "manifest": manifest}


def compute_archive_checksum(archive_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(archive_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
