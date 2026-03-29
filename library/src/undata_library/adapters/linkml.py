"""LinkML YAML schema adapter.

Can extract entities from:
1. LinkML YAML files on disk (extract method)
2. In-memory SchemaDefinition objects (extract_from_schema_definition method)

The second path enables other adapters to convert their native format to
LinkML programmatically and then use this adapter for entity extraction.
"""

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
        """Extract entities from LinkML YAML files on disk."""
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
            source_name = options.get("source_name", "linkml")
            self._extract_from_dict(data, schema_name, source_name, file_ref, results)

        return results

    def extract_from_schema_definition(
        self,
        schema_def: Any,
        source_name: str = "linkml",
        source_ref: SourceRef | None = None,
    ) -> list[ClassifiedEntity]:
        """Extract entities from an in-memory LinkML SchemaDefinition object.

        This is the entry point for adapters that build LinkML programmatically.
        """
        from linkml_runtime.dumpers import yaml_dumper

        # Serialize to dict via YAML round-trip (simplest, handles all LinkML types)
        yaml_str = yaml_dumper.dumps(schema_def)
        data = yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            return []

        schema_name = data.get("name", "schema")
        ref = source_ref or SourceRef(repo="", committish="", file="", checksum="")

        results: list[ClassifiedEntity] = []
        self._extract_from_dict(data, schema_name, source_name, ref, results)
        return results

    def _extract_from_dict(
        self,
        data: dict,
        schema_name: str,
        source_name: str,
        source_ref: SourceRef,
        results: list[ClassifiedEntity],
    ) -> None:
        """Core extraction logic from a LinkML schema dict."""
        # Classes → CLASS entities
        for cls_name, cls_def in data.get("classes", {}).items():
            if not isinstance(cls_def, dict):
                continue
            slots = list(cls_def.get("slots", []))
            attrs = list(cls_def.get("attributes", {}).keys())
            all_slots = slots + attrs

            semantic: dict[str, Any] = {"properties": all_slots}
            is_a = cls_def.get("is_a")
            if is_a:
                semantic["subclass_of"] = is_a
            mixins = cls_def.get("mixins", [])
            if mixins:
                semantic["mixins"] = mixins
            is_mixin = cls_def.get("mixin", False)
            if is_mixin:
                semantic["is_mixin"] = True

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic=semantic,
                    provenance={
                        "source": source_name,
                        "class": cls_name,
                        "name": cls_name,
                        "description": cls_def.get("description"),
                    },
                    confidence=0.95,
                    source_ref=source_ref,
                    source_context={
                        "is_a": is_a,
                        "mixins": mixins,
                        "mixin": is_mixin,
                    },
                )
            )

            # Inline attributes → ATTRIBUTE
            for attr_name, attr_def in cls_def.get("attributes", {}).items():
                if not isinstance(attr_def, dict):
                    continue
                dt = _linkml_type(attr_def)
                sem: dict[str, Any] = {"data_type": dt}
                rng = attr_def.get("range")
                if rng and rng not in _LINKML_TYPE_MAP:
                    sem["type_ref"] = rng
                if attr_def.get("required"):
                    sem["required"] = True
                if attr_def.get("multivalued"):
                    sem["multivalued"] = True
                # Annotations (e.g., unit)
                for ann_key, ann_val in attr_def.get("annotations", {}).items():
                    if isinstance(ann_val, dict):
                        ann_val = ann_val.get("value", str(ann_val))
                    if ann_key == "unit":
                        sem["unit"] = str(ann_val)

                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ATTRIBUTE,
                        semantic=sem,
                        provenance={
                            "source": source_name,
                            "class": cls_name,
                            "name": attr_name,
                            "description": attr_def.get("description"),
                        },
                        confidence=0.9,
                        source_ref=source_ref,
                    )
                )

            # Slot usage with required/recommended
            for su_name, su_def in cls_def.get("slot_usage", {}).items():
                if not isinstance(su_def, dict):
                    continue
                # These don't create new entities — they modify existing slots
                # in the context of this class. The slot itself is extracted below.

        # Slots → ATTRIBUTE entities
        for slot_name, slot_def in data.get("slots", {}).items():
            if not isinstance(slot_def, dict):
                continue
            dt = _linkml_type(slot_def)
            sem = {"data_type": dt}
            rng = slot_def.get("range")
            if rng and rng not in _LINKML_TYPE_MAP:
                sem["type_ref"] = rng
            if slot_def.get("pattern"):
                sem["pattern"] = slot_def["pattern"]
            if slot_def.get("multivalued"):
                sem["multivalued"] = True
            if slot_def.get("minimum_value") is not None:
                sem["min_value"] = float(slot_def["minimum_value"])
            if slot_def.get("maximum_value") is not None:
                sem["max_value"] = float(slot_def["maximum_value"])
            # Annotations (e.g., unit, bids_category)
            for ann_key, ann_val in slot_def.get("annotations", {}).items():
                if isinstance(ann_val, dict):
                    ann_val = ann_val.get("value", str(ann_val))
                if ann_key == "unit":
                    sem["unit"] = str(ann_val)

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=sem,
                    provenance={
                        "source": source_name,
                        "class": schema_name,
                        "name": slot_name,
                        "description": slot_def.get("description"),
                    },
                    confidence=0.9,
                    source_ref=source_ref,
                )
            )

        # Enums → VALUESET + ENUM_VALUE entities
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
                        "source": source_name,
                        "class": schema_name,
                        "name": enum_name,
                        "description": enum_def.get("description"),
                    },
                    confidence=0.95,
                    source_ref=source_ref,
                )
            )

            for val_name in members:
                val_def = pvs[val_name] if isinstance(pvs, dict) else {}
                val_desc = val_def.get("description") if isinstance(val_def, dict) else None
                val_meaning = val_def.get("meaning") if isinstance(val_def, dict) else None
                val_sem: dict[str, Any] = {
                    "label": val_name,
                    "value_type": "categorical",
                }
                if val_meaning:
                    val_sem["ontology_id"] = val_meaning
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ENUM_VALUE,
                        semantic=val_sem,
                        provenance={
                            "source": source_name,
                            "class": enum_name,
                            "name": val_name,
                            "description": val_desc,
                        },
                        confidence=0.95,
                        source_ref=source_ref,
                    )
                )


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
