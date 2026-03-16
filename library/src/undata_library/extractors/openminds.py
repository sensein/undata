"""openMINDS schema extractor — JSON-LD file parse."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import ProvenanceEntry, SemanticIdentity


def extract_openminds(schema_path: Path) -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Extract elements from openMINDS JSON-LD schema files."""
    results: list[tuple[SemanticIdentity, ProvenanceEntry]] = []

    # openMINDS uses .schema.omi.json files or JSON-LD
    for pattern in ("**/*.schema.omi.json", "**/*.jsonld"):
        for f in (
            sorted(schema_path.rglob("*.jsonld"))
            if pattern.endswith(".jsonld")
            else sorted(schema_path.rglob(pattern))
        ):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            if not isinstance(data, dict):
                continue

            # Try JSON-LD format
            class_name = data.get("@type", f.stem)
            if isinstance(class_name, list):
                class_name = class_name[0] if class_name else f.stem

            properties = data.get("properties", data.get("@context", {}))
            if not isinstance(properties, dict):
                continue

            for prop_name, prop_def in properties.items():
                if prop_name.startswith("@"):
                    continue

                if isinstance(prop_def, str):
                    # Simple string value in @context — it's a URI mapping
                    sem = SemanticIdentity(data_type="string")
                    prov = ProvenanceEntry(
                        source="openminds",
                        **{"class": class_name},
                        name=prop_name,
                        description=None,
                    )
                    results.append((sem, prov))
                elif isinstance(prop_def, dict):
                    dt = _om_type(prop_def)
                    desc = prop_def.get("description", "")
                    sem = SemanticIdentity(data_type=dt)
                    prov = ProvenanceEntry(
                        source="openminds",
                        **{"class": class_name},
                        name=prop_name,
                        description=desc or None,
                    )
                    results.append((sem, prov))

    return results


def _om_type(prop_def: dict) -> str:
    t = prop_def.get("type", "")
    if t == "array" or "items" in prop_def:
        return "array"
    if t in ("string", "integer", "number", "boolean"):
        return {"number": "float"}.get(t, t)
    return "string"
