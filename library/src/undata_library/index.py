"""Build index.yaml registry from v2 element and schema files."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def build_index(base_path: Path) -> dict[str, Any]:
    """Scan elements/ and schemas/ directories, build registry."""
    elements_dir = base_path / "elements"
    schemas_dir = base_path / "schemas"

    elements: list[dict[str, Any]] = []
    schemas: list[dict[str, Any]] = []
    multi_source = 0

    if elements_dir.exists():
        for f in sorted(elements_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "semantic" not in data:
                    continue
                prov = data.get("provenance", [])
                name = prov[0].get("name", "") if prov else ""
                sources = [p.get("source", "") for p in prov]
                if len(set(sources)) > 1:
                    multi_source += 1
                elements.append(
                    {
                        "file": str(f.relative_to(base_path)),
                        "name": name,
                        "data_type": data["semantic"].get("data_type", ""),
                        "sources": sorted(set(sources)),
                        "provenance_count": len(prov),
                    }
                )
            except (yaml.YAMLError, OSError):
                continue

    if schemas_dir.exists():
        for f in sorted(schemas_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "semantic" not in data:
                    continue
                prov = data.get("provenance", [])
                name = prov[0].get("name", "") if prov else ""
                schemas.append(
                    {
                        "file": str(f.relative_to(base_path)),
                        "name": name,
                        "property_count": len(data["semantic"].get("properties", [])),
                        "provenance_count": len(prov),
                    }
                )
            except (yaml.YAMLError, OSError):
                continue

    values: list[dict[str, Any]] = []
    values_dir = base_path / "values"
    if values_dir.exists():
        for f in sorted(values_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "semantic" not in data:
                    continue
                prov = data.get("provenance", [])
                values.append(
                    {
                        "file": str(f.relative_to(base_path)),
                        "label": data["semantic"].get("label", ""),
                        "ontology_term": data["semantic"].get("ontology_term"),
                        "provenance_count": len(prov),
                    }
                )
            except (yaml.YAMLError, OSError):
                continue

    return {
        "generated_at": None,
        "element_count": len(elements),
        "schema_count": len(schemas),
        "value_count": len(values),
        "multi_source_elements": multi_source,
        "elements": elements,
        "schemas": schemas,
        "values": values,
    }


def write_index(base_path: Path, output: Path) -> dict[str, Any]:
    """Build index and write to YAML file."""
    idx = build_index(base_path)
    idx["generated_at"] = datetime.now(timezone.utc).isoformat()
    output.write_text(yaml.dump(idx, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return idx
