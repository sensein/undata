"""Build an index.yaml registry from element and mapping YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def build_index(base_path: Path) -> dict[str, Any]:
    """Scan elements/ and mappings/ directories, build registry."""
    elements_dir = base_path / "elements"
    mappings_dir = base_path / "mappings"

    elements: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []

    if elements_dir.exists():
        for f in sorted(elements_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "element" in data:
                    el = data["element"]
                    versions = data.get("versions", [])
                    current = data.get("current_version", 1)
                    name = ""
                    if versions:
                        current_ver = next(
                            (v for v in versions if v.get("version_num") == current),
                            versions[-1],
                        )
                        name = current_ver.get("name", "")
                    elements.append({
                        "id": el.get("id", ""),
                        "source_local_id": el.get("source_local_id", ""),
                        "name": name,
                        "current_version": current,
                        "version_count": len(versions),
                        "file": str(f.relative_to(base_path)),
                    })
            except (yaml.YAMLError, OSError):
                continue

    if mappings_dir.exists():
        for f in sorted(mappings_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "mapping" in data:
                    m = data["mapping"]
                    mappings.append({
                        "id": m.get("id", ""),
                        "status": m.get("status", ""),
                        "current_version": data.get("current_version", 1),
                        "version_count": len(data.get("versions", [])),
                        "file": str(f.relative_to(base_path)),
                    })
            except (yaml.YAMLError, OSError):
                continue

    return {
        "generated_at": None,  # Set by caller
        "element_count": len(elements),
        "mapping_count": len(mappings),
        "elements": elements,
        "mappings": mappings,
    }


def write_index(base_path: Path, output: Path) -> dict[str, Any]:
    """Build index and write to YAML file."""
    from datetime import datetime, timezone

    idx = build_index(base_path)
    idx["generated_at"] = datetime.now(timezone.utc).isoformat()

    output.write_text(yaml.dump(idx, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return idx
