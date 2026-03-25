"""AIND schema adapter — converts JSON Schema to LinkML, then extracts.

Parses JSON Schema files (from aind-data-schema) and builds a LinkML
SchemaDefinition with classes from $defs, slots from properties,
and enums from enum fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import SourceRef
from .base import BaseAdapter, ClassifiedEntity

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
    "array": "string",
    "object": "string",
}


class AINDAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "aind"

    @property
    def supported_formats(self) -> list[str]:
        return [".json"]

    def to_linkml(self, source_path: Path, **options: Any) -> Any:
        """Convert AIND JSON Schema files to LinkML SchemaDefinition."""
        return self._build_linkml_schema(source_path)

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        schema = self.to_linkml(source_path, **options)
        if schema is None:
            return []

        repo = options.get("repo", "https://github.com/AllenNeuralDynamics/aind-data-schema")
        committish = options.get("committish")
        base_ref = SourceRef(repo=repo, committish=committish, file="schemas", checksum="")

        from .extractor import extract_from_schema_definition

        return extract_from_schema_definition(schema, source_name="aind", source_ref=base_ref)

    def _build_linkml_schema(self, source_path: Path) -> Any:
        """Convert AIND JSON Schema files to a LinkML SchemaDefinition."""
        from . import linkml_builder as lb

        ld = lb.build_schema(
            name="aind",
            schema_id="https://aind-data-schema.readthedocs.io/schema",
            title="AIND Data Schema",
            prefix="aind",
            prefix_uri="https://aind-data-schema.readthedocs.io/schema/",
        )

        for f in sorted(source_path.glob("*.json")):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue

            model_name = f.stem.replace("_schema", "")
            defs = data.get("$defs", {})

            # Top-level schema → class
            self._add_schema_class(ld, data, model_name, defs, lb)

            # $defs → classes or enums
            for def_name, def_schema in defs.items():
                if not isinstance(def_schema, dict):
                    continue
                self._add_def(ld, def_name, def_schema, model_name, defs, lb)

        return ld

    def _add_schema_class(
        self, ld: Any, schema: dict, model_name: str, defs: dict, lb: Any
    ) -> None:
        """Add top-level JSON Schema as a LinkML class."""
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        slot_names = []
        slot_usage = {}

        for prop_name, prop_def in props.items():
            if not isinstance(prop_def, dict):
                continue
            rng = self._json_schema_range(prop_def, defs)
            desc = prop_def.get("description", "")
            multivalued = prop_def.get("type") == "array"
            lb.add_slot(
                ld, prop_name, range=rng, description=desc[:500] or None, multivalued=multivalued
            )
            slot_names.append(prop_name)
            if prop_name in required:
                slot_usage[prop_name] = {"required": True}

        desc = schema.get("description", schema.get("title", ""))
        lb.add_class(
            ld, model_name, slots=slot_names, description=desc[:500] or None, slot_usage=slot_usage
        )

    def _add_def(
        self, ld: Any, def_name: str, def_schema: dict, parent: str, defs: dict, lb: Any
    ) -> None:
        """Add a $defs entry as a class or enum."""
        # Enum
        enum_vals = def_schema.get("enum")
        if enum_vals and isinstance(enum_vals, list):
            vals = [str(v) for v in enum_vals if v is not None]
            if vals:
                lb.add_enum(ld, def_name, vals, description=def_schema.get("description"))
            return

        # Check for const-only (discriminator member) — skip
        if "const" in def_schema and not def_schema.get("properties"):
            return

        # Class with properties
        props = def_schema.get("properties", {})
        if props:
            required = set(def_schema.get("required", []))
            slot_names = []
            slot_usage = {}
            for prop_name, prop_def in props.items():
                if not isinstance(prop_def, dict):
                    continue
                rng = self._json_schema_range(prop_def, defs)
                desc = prop_def.get("description", "")
                multivalued = prop_def.get("type") == "array"
                lb.add_slot(
                    ld,
                    prop_name,
                    range=rng,
                    description=desc[:500] or None,
                    multivalued=multivalued,
                )
                slot_names.append(prop_name)
                if prop_name in required:
                    slot_usage[prop_name] = {"required": True}

            desc = def_schema.get("description", def_schema.get("title", ""))
            lb.add_class(
                ld,
                def_name,
                slots=slot_names,
                description=desc[:500] or None,
                slot_usage=slot_usage,
            )

    def _json_schema_range(self, prop_def: dict, defs: dict) -> str:
        """Map a JSON Schema property to a LinkML range."""
        # Direct $ref
        ref = prop_def.get("$ref", "")
        if ref:
            return ref.split("/")[-1]

        # anyOf/oneOf — take first non-null $ref
        for combiner in ("anyOf", "oneOf"):
            options = prop_def.get(combiner, [])
            for opt in options:
                if isinstance(opt, dict):
                    ref = opt.get("$ref", "")
                    if ref:
                        return ref.split("/")[-1]
                    t = opt.get("type", "")
                    if t and t != "null":
                        return _TYPE_MAP.get(t, "string")

        # Array items
        if prop_def.get("type") == "array":
            items = prop_def.get("items", {})
            if isinstance(items, dict):
                ref = items.get("$ref", "")
                if ref:
                    return ref.split("/")[-1]
                # anyOf in items
                for combiner in ("anyOf", "oneOf"):
                    for opt in items.get(combiner, []):
                        if isinstance(opt, dict) and opt.get("$ref"):
                            return opt["$ref"].split("/")[-1]

        # Simple type
        t = prop_def.get("type", "string")
        if isinstance(t, list):
            t = next((x for x in t if x != "null"), "string")
        return _TYPE_MAP.get(str(t), "string")
