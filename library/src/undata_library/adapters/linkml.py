"""LinkML YAML schema adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity


class LinkMLAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "linkml"

    @property
    def supported_formats(self) -> list[str]:
        return [".yaml", ".yml"]

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        repo = options.get("repo")
        committish = options.get("committish")
        results: list[ClassifiedEntity] = []

        files = [source_path] if source_path.is_file() else sorted(source_path.glob("**/*.yaml"))
        for f in files:
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
            except (yaml.YAMLError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            # Skip non-LinkML YAML (must have classes, slots, or enums)
            if not any(k in data for k in ("classes", "slots", "enums", "prefixes")):
                continue

            file_ref = SourceRef(
                repo=repo,
                committish=committish,
                file=str(f.relative_to(source_path))
                if not source_path.is_file() and f.is_relative_to(source_path)
                else str(f),
                checksum=hashlib.sha256(f.read_bytes()).hexdigest(),
            )

            schema_name = data.get("name", f.stem)

            # Classes → CLASS
            for cls_name, cls_def in data.get("classes", {}).items():
                if not isinstance(cls_def, dict):
                    continue
                slots = list(cls_def.get("slots", []))
                attrs = list(cls_def.get("attributes", {}).keys())
                all_slots = slots + attrs

                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.CLASS,
                        semantic={"properties": all_slots},
                        provenance={
                            "source": "linkml",
                            "class": cls_name,
                            "name": cls_name,
                            "description": cls_def.get("description"),
                        },
                        confidence=0.95,
                        source_ref=file_ref,
                        source_context={
                            "is_a": cls_def.get("is_a"),
                            "mixins": cls_def.get("mixins", []),
                        },
                    )
                )

                # Inline attributes → ATTRIBUTE
                for attr_name, attr_def in cls_def.get("attributes", {}).items():
                    if not isinstance(attr_def, dict):
                        continue
                    dt = _linkml_type(attr_def)
                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.ATTRIBUTE,
                            semantic={"data_type": dt},
                            provenance={
                                "source": "linkml",
                                "class": cls_name,
                                "name": attr_name,
                                "description": attr_def.get("description"),
                            },
                            confidence=0.9,
                            source_ref=file_ref,
                        )
                    )

            # Slots → ATTRIBUTE
            for slot_name, slot_def in data.get("slots", {}).items():
                if not isinstance(slot_def, dict):
                    continue
                dt = _linkml_type(slot_def)
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ATTRIBUTE,
                        semantic={"data_type": dt},
                        provenance={
                            "source": "linkml",
                            "class": schema_name,
                            "name": slot_name,
                            "description": slot_def.get("description"),
                        },
                        confidence=0.9,
                        source_ref=file_ref,
                    )
                )

            # Enums → VALUESET + ENUM_VALUE
            for enum_name, enum_def in data.get("enums", {}).items():
                if not isinstance(enum_def, dict):
                    continue
                pvs = enum_def.get("permissible_values", {})
                members = sorted(pvs.keys()) if isinstance(pvs, dict) else []

                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.VALUESET,
                        semantic={"name": enum_name, "members": members},
                        provenance={
                            "source": "linkml",
                            "class": schema_name,
                            "name": enum_name,
                            "description": enum_def.get("description"),
                        },
                        confidence=0.95,
                        source_ref=file_ref,
                    )
                )

                for val_name in members:
                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.ENUM_VALUE,
                            semantic={
                                "label": val_name,
                                "value_type": "categorical",
                            },
                            provenance={"source": "linkml", "raw_value": val_name},
                            confidence=0.95,
                            source_ref=file_ref,
                        )
                    )

        return results


_LINKML_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "float": "float",
    "double": "float",
    "boolean": "boolean",
    "date": "string",
    "datetime": "string",
    "uri": "string",
    "uriorcurie": "string",
    "ncname": "string",
}


def _linkml_type(slot_def: dict) -> str:
    r = slot_def.get("range", "string")
    if slot_def.get("multivalued"):
        return "array"
    return _LINKML_TYPE_MAP.get(r, "string")
