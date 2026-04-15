"""Generic JSON Schema adapter — draft-07/2019/2020-12."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity
from .classifier import classify_entity

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
    "null": "string",
}


class JSONSchemaAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "json-schema"

    @property
    def supported_formats(self) -> list[str]:
        return [".json"]

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        repo = options.get("repo")
        committish = options.get("committish")
        results: list[ClassifiedEntity] = []

        files = [source_path] if source_path.is_file() else sorted(source_path.glob("**/*.json"))
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
                if not source_path.is_file() and f.is_relative_to(source_path)
                else str(f),
                checksum=hashlib.sha256(f.read_bytes()).hexdigest(),
            )

            defs = data.get("$defs", data.get("definitions", {}))
            visited: set[str] = set()

            # Top-level schema
            schema_name = data.get("title", f.stem)
            self._extract_schema(data, schema_name, defs, file_ref, visited, results)

            # $defs / definitions
            for def_name, def_schema in defs.items():
                if not isinstance(def_schema, dict):
                    continue
                self._extract_schema(def_schema, def_name, defs, file_ref, visited, results)

        return results

    def _extract_schema(
        self,
        schema: dict,
        name: str,
        defs: dict,
        file_ref: SourceRef,
        visited: set[str],
        results: list[ClassifiedEntity],
    ) -> None:
        if name in visited:
            return  # Circular reference protection
        visited.add(name)

        etype, conf = classify_entity(name, schema)

        if etype == EntityType.CLASS:
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic={"properties": []},
                    provenance={
                        "source": "json-schema",
                        "class": name,
                        "name": name,
                        "description": schema.get("description"),
                    },
                    confidence=conf,
                    source_ref=file_ref,
                )
            )
            # Extract properties as attributes
            for prop_name, prop_def in schema.get("properties", {}).items():
                self._extract_property(prop_name, prop_def, name, defs, file_ref, visited, results)

        elif etype == EntityType.VALUESET:
            enum_vals = schema.get("enum", [])
            for key in ("oneOf", "anyOf"):
                if not enum_vals:
                    items = schema.get(key, [])
                    enum_vals = [
                        v.get("const", v.get("enum", [None])[0] if v.get("enum") else None)
                        for v in items
                        if isinstance(v, dict)
                    ]
                    enum_vals = [v for v in enum_vals if v is not None]
            members = sorted(str(v) for v in enum_vals)
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.VALUESET,
                    semantic={"name": name, "members": members},
                    provenance={"source": "json-schema", "class": "", "name": name},
                    confidence=conf,
                    source_ref=file_ref,
                )
            )
            for val in members:
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ENUM_VALUE,
                        semantic={"label": val, "value_type": "categorical"},
                        provenance={"source": "json-schema", "raw_value": val},
                        confidence=0.95,
                        source_ref=file_ref,
                    )
                )

        elif etype == EntityType.ENUM_VALUE:
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ENUM_VALUE,
                    semantic={"label": str(schema.get("const", name)), "value_type": "categorical"},
                    provenance={
                        "source": "json-schema",
                        "raw_value": str(schema.get("const", name)),
                    },
                    confidence=conf,
                    source_ref=file_ref,
                )
            )

    def _extract_property(
        self,
        prop_name: str,
        prop_def: dict,
        class_name: str,
        defs: dict,
        file_ref: SourceRef,
        visited: set[str],
        results: list[ClassifiedEntity],
    ) -> None:
        resolved = prop_def
        ref = prop_def.get("$ref", "")
        type_ref = None
        if ref:
            ref_name = ref.split("/")[-1]
            resolved = defs.get(ref_name, prop_def)
            if ref_name in visited:
                return  # Circular $ref
            # Check if referenced def is a class
            if isinstance(resolved, dict) and resolved.get("properties"):
                type_ref = ref_name

        dt = _get_type(resolved, defs)
        desc = prop_def.get("description") or resolved.get("description") or ""

        semantic: dict[str, Any] = {"data_type": dt}
        if type_ref:
            semantic["type_ref"] = type_ref

        # Enum
        enum_vals = resolved.get("enum") or prop_def.get("enum")
        if enum_vals:
            allowed = [str(v) for v in enum_vals if v is not None]
            semantic["response_options"] = [{"value": v, "label": v} for v in allowed]

        # Min/max
        for src in (prop_def, resolved):
            for attr, key in [
                ("minimum", "min_value"),
                ("exclusiveMinimum", "min_value"),
                ("maximum", "max_value"),
                ("exclusiveMaximum", "max_value"),
            ]:
                if key not in semantic and src.get(attr) is not None:
                    semantic[key] = float(src[attr])

        # Pattern
        for src in (prop_def, resolved):
            if "pattern" not in semantic and src.get("pattern"):
                semantic["pattern"] = src["pattern"]

        # Format → pattern mapping
        for src in (prop_def, resolved):
            fmt = src.get("format")
            if fmt and "pattern" not in semantic:
                fmt_patterns = {
                    "date-time": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                    "date": r"^\d{4}-\d{2}-\d{2}$",
                    "time": r"^\d{2}:\d{2}:\d{2}",
                    "email": r"^[^@]+@[^@]+\.[^@]+$",
                    "uri": r"^https?://",
                    "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                }
                if fmt in fmt_patterns:
                    semantic["pattern"] = fmt_patterns[fmt]

        results.append(
            ClassifiedEntity(
                entity_type=EntityType.ATTRIBUTE,
                semantic=semantic,
                provenance={
                    "source": "json-schema",
                    "class": class_name,
                    "name": prop_name,
                    "description": desc or None,
                },
                confidence=0.85,
                source_ref=file_ref,
            )
        )


def _get_type(prop: dict, defs: dict) -> str:
    if "$ref" in prop:
        ref_name = prop["$ref"].split("/")[-1]
        resolved = defs.get(ref_name, {})
        if isinstance(resolved, dict) and resolved.get("properties"):
            return "object"
        return _get_type(resolved, defs)
    raw = prop.get("type")
    if isinstance(raw, list):
        non_null = [t for t in raw if t != "null"]
        raw = non_null[0] if non_null else "string"
    if raw:
        return _TYPE_MAP.get(raw, "string")
    for combiner in ("anyOf", "oneOf", "allOf"):
        for opt in prop.get(combiner, []):
            if isinstance(opt, dict) and "type" in opt:
                return _TYPE_MAP.get(opt["type"], "string")
    return "string"
