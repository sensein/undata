"""openMINDS schema adapter — JSON-LD (.schema.omi.json) file parse.

Extracts:
- Classes with module/category metadata
- Attributes with short property names (not full URIs)
- References (_linkedTypes/_embeddedTypes) → type_ref
- Controlled vocabulary types (controlledTerms module) → VALUESET
- Required fields from schema required array
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity


def _short_name(prop_key: str, prop_def: Any) -> str:
    """Extract short property name from key or definition."""
    # prop_def may have a "name" field with the short name
    if isinstance(prop_def, dict) and prop_def.get("name"):
        return prop_def["name"]
    # Fallback: extract from URI
    if "/" in prop_key:
        return prop_key.rsplit("/", 1)[-1]
    return prop_key


def _om_type(prop_def: dict) -> tuple[str, str | None]:
    """Determine (data_type, type_ref) for an openMINDS property.

    Checks _linkedTypes and _embeddedTypes for reference types.
    """
    # Reference types
    linked = prop_def.get("_linkedTypes", [])
    embedded = prop_def.get("_embeddedTypes", [])
    if linked or embedded:
        refs = linked + embedded
        # Get the first referenced type's short name
        type_ref = refs[0].rsplit("/", 1)[-1] if refs else None
        if prop_def.get("type") == "array" or len(refs) > 1:
            return "array", type_ref
        return "object", type_ref

    t = prop_def.get("type", "")
    if t == "array" or "items" in prop_def:
        return "array", None
    if t in ("string", "integer", "number", "boolean"):
        return {"number": "float"}.get(t, t), None
    return "string", None


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
        seen_files: set[str] = set()

        for pattern in ("**/*.schema.omi.json",):
            for f in sorted(source_path.rglob(pattern)):
                if str(f) in seen_files:
                    continue
                seen_files.add(str(f))

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

                self._extract_schema(data, file_ref, results)

        return results

    def _extract_schema(
        self,
        data: dict,
        file_ref: SourceRef,
        results: list[ClassifiedEntity],
    ) -> None:
        """Extract entities from a single openMINDS schema file."""
        # Get class name — use "name" field, fall back to "_type" URI
        class_name = data.get("name", "")
        if not class_name:
            type_uri = data.get("_type", "")
            class_name = type_uri.rsplit("/", 1)[-1] if "/" in type_uri else type_uri

        if not class_name:
            return

        module = data.get("_module", "")
        categories = data.get("_categories", [])
        description = data.get("description", "")
        required_fields = set(data.get("required", []))

        properties = data.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}

        # Determine if this is a controlled vocabulary type
        is_vocabulary = module == "controlledTerms"

        # Collect property short names
        prop_names = []
        for prop_key in properties:
            if prop_key.startswith("@"):
                continue
            prop_def = properties[prop_key]
            name = _short_name(prop_key, prop_def)
            prop_names.append(name)

        # Emit CLASS or VALUESET
        if is_vocabulary:
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.VALUESET,
                    semantic={
                        "name": class_name,
                        "members": [],  # Instances are not in schema files
                    },
                    provenance={
                        "source": "openminds",
                        "class": class_name,
                        "name": class_name,
                        "description": description,
                    },
                    confidence=0.9,
                    source_ref=file_ref,
                    source_context={"module": module, "categories": categories},
                )
            )
        else:
            semantic: dict[str, Any] = {"properties": prop_names}
            if categories:
                semantic["categories"] = categories
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic=semantic,
                    provenance={
                        "source": "openminds",
                        "class": class_name,
                        "name": class_name,
                        "description": description,
                    },
                    confidence=0.85,
                    source_ref=file_ref,
                    source_context={"module": module, "categories": categories},
                )
            )

        # Emit properties as ATTRIBUTEs
        for prop_key, prop_def in properties.items():
            if prop_key.startswith("@"):
                continue
            if isinstance(prop_def, str):
                # Simple string value — likely a context entry, skip
                continue
            if not isinstance(prop_def, dict):
                continue

            name = _short_name(prop_key, prop_def)
            dt, type_ref = _om_type(prop_def)
            desc = prop_def.get("description", "") or None

            sem: dict[str, Any] = {"data_type": dt}
            if type_ref:
                sem["type_ref"] = type_ref
            if prop_key in required_fields:
                sem["required"] = True

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=sem,
                    provenance={
                        "source": "openminds",
                        "class": class_name,
                        "name": name,
                        "description": desc,
                    },
                    confidence=0.85,
                    source_ref=file_ref,
                )
            )
