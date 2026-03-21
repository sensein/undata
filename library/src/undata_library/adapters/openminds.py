"""openMINDS schema adapter — JSON-LD file parse."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity


class OpenMINDSAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "openminds"

    @property
    def supported_formats(self) -> list[str]:
        return [".json", ".jsonld"]

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        repo = options.get("repo", "https://github.com/openMetadataInitiative/openMINDS")
        committish = options.get("committish")
        results: list[ClassifiedEntity] = []

        for pattern in ("**/*.schema.omi.json", "**/*.jsonld"):
            files = (
                sorted(source_path.rglob("*.jsonld"))
                if pattern.endswith(".jsonld")
                else sorted(source_path.rglob(pattern))
            )
            for f in files:
                try:
                    data = json.loads(f.read_text())
                except (json.JSONDecodeError, OSError):
                    continue
                if not isinstance(data, dict):
                    continue

                file_ref = SourceRef(
                    repo=repo,
                    committish=committish,
                    file=str(f.relative_to(source_path))
                    if f.is_relative_to(source_path)
                    else str(f),
                    checksum=hashlib.sha256(f.read_bytes()).hexdigest(),
                )

                class_name = data.get("@type", f.stem)
                if isinstance(class_name, list):
                    class_name = class_name[0] if class_name else f.stem

                # Emit class
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.CLASS,
                        semantic={"properties": []},
                        provenance={"source": "openminds", "class": class_name, "name": class_name},
                        confidence=0.85,
                        source_ref=file_ref,
                    )
                )

                properties = data.get("properties", data.get("@context", {}))
                if not isinstance(properties, dict):
                    continue

                for prop_name, prop_def in properties.items():
                    if prop_name.startswith("@"):
                        continue

                    if isinstance(prop_def, str):
                        dt = "string"
                        desc = None
                    elif isinstance(prop_def, dict):
                        dt = _om_type(prop_def)
                        desc = prop_def.get("description", "") or None
                    else:
                        continue

                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.ATTRIBUTE,
                            semantic={"data_type": dt},
                            provenance={
                                "source": "openminds",
                                "class": class_name,
                                "name": prop_name,
                                "description": desc,
                            },
                            confidence=0.85,
                            source_ref=file_ref,
                        )
                    )

        return results


def _om_type(prop_def: dict) -> str:
    t = prop_def.get("type", "")
    if t == "array" or "items" in prop_def:
        return "array"
    if t in ("string", "integer", "number", "boolean"):
        return {"number": "float"}.get(t, t)
    return "string"
