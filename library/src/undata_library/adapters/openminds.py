"""openMINDS schema adapter — converts JSON-LD schemas to LinkML, then extracts.

Parses .schema.omi.json files and builds a LinkML SchemaDefinition with:
- Classes for schema types (with module/category metadata)
- Slots with short property names and type_ref from _linkedTypes/_embeddedTypes
- Enums for controlledTerms module types
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import SourceRef
from .base import BaseAdapter, ClassifiedEntity


def _short_name(prop_key: str, prop_def: Any) -> str:
    """Extract short property name from key or definition."""
    if isinstance(prop_def, dict) and prop_def.get("name"):
        return prop_def["name"]
    if "/" in prop_key:
        return prop_key.rsplit("/", 1)[-1]
    return prop_key


def _om_range(prop_def: dict) -> tuple[str, str | None]:
    """Determine (linkml_range, type_ref) for an openMINDS property."""
    linked = prop_def.get("_linkedTypes", [])
    embedded = prop_def.get("_embeddedTypes", [])
    if linked or embedded:
        refs = linked + embedded
        ref_name = refs[0].rsplit("/", 1)[-1] if refs else None
        return ref_name or "string", ref_name
    t = prop_def.get("type", "")
    if t == "array" or "items" in prop_def:
        return "string", None  # Array of primitives
    if t in ("integer", "number", "boolean"):
        return {"number": "float"}.get(t, t), None
    return "string", None


class OpenMINDSAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "openminds"

    @property
    def supported_formats(self) -> list[str]:
        return [".json", ".jsonld"]

    def to_linkml(self, source_path: Path, **options: Any) -> Any:
        """Convert openMINDS schemas to LinkML SchemaDefinition."""
        return self._build_linkml_schema(source_path)

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        schema = self.to_linkml(source_path, **options)
        if schema is None:
            return []

        repo = options.get("repo", "https://github.com/openMetadataInitiative/openMINDS")
        committish = options.get("committish")
        base_ref = SourceRef(repo=repo, committish=committish, file="schemas", checksum="")

        from .extractor import extract_from_schema_definition

        return extract_from_schema_definition(schema, source_name="openminds", source_ref=base_ref)

    def _build_linkml_schema(self, source_path: Path) -> Any:
        """Convert openMINDS JSON-LD schemas to a LinkML SchemaDefinition."""
        from . import linkml_builder as lb

        ld = lb.build_schema(
            name="openminds",
            schema_id="https://openminds.om-i.org/schema",
            title="openMINDS Schema",
            prefix="openminds",
            prefix_uri="https://openminds.om-i.org/schema/",
        )

        seen: set[str] = set()
        for f in sorted(source_path.rglob("*.schema.omi.json")):
            if str(f) in seen:
                continue
            seen.add(str(f))
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            self._add_schema_to_linkml(ld, data, lb)

        # Load controlled term instances from instances repo (if available)
        # Instances are in instances/latest/terminologies/<term>/<value>.jsonld
        self._load_instances(ld, source_path, lb)

        return ld

    def _load_instances(self, ld: Any, source_path: Path, lb: Any) -> None:
        """Load controlled term instances to populate enum values."""
        from linkml_runtime.linkml_model import PermissibleValue

        # Instance .jsonld files are in a separate repo cached at a known location
        cache_dir = Path.home() / ".cache" / "undata" / "sources"
        instance_dir = cache_dir / "openminds_instances" / "instances" / "latest" / "terminologies"
        instance_dirs = [instance_dir] if instance_dir.exists() else []

        for inst_dir in instance_dirs:
            for jsonld_file in sorted(inst_dir.rglob("*.jsonld")):
                try:
                    data = json.loads(jsonld_file.read_text())
                except (json.JSONDecodeError, OSError):
                    continue
                if not isinstance(data, dict):
                    continue

                # Get the type this instance belongs to
                inst_type = data.get("@type", "")
                if isinstance(inst_type, list):
                    inst_type = inst_type[0] if inst_type else ""
                type_name = inst_type.rsplit("/", 1)[-1] if "/" in inst_type else inst_type

                inst_name = data.get("name", jsonld_file.stem)
                if not type_name or not inst_name:
                    continue

                # Add to the enum if it exists
                if type_name in ld.enums:
                    enum_def = ld.enums[type_name]
                    if inst_name not in enum_def.permissible_values:
                        pv = PermissibleValue(text=inst_name)
                        desc = data.get("definition", data.get("description", ""))
                        if desc:
                            pv.description = str(desc)[:200]
                        # Attach ontology identifier if available
                        onto_id = data.get("preferredOntologyIdentifier")
                        if onto_id:
                            pv.meaning = onto_id
                        enum_def.permissible_values[inst_name] = pv

    def _add_schema_to_linkml(self, ld: Any, data: dict, lb: Any) -> None:
        """Add a single openMINDS schema to the LinkML schema."""
        class_name = data.get("name", "")
        if not class_name:
            type_uri = data.get("_type", "")
            class_name = type_uri.rsplit("/", 1)[-1] if "/" in type_uri else type_uri
        if not class_name:
            return

        module = data.get("_module", "")
        description = data.get("description", "")
        properties = data.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        required_fields = set(data.get("required", []))

        # Collect slots
        slot_names = []
        slot_usage = {}
        for prop_key, prop_def in properties.items():
            if prop_key.startswith("@") or not isinstance(prop_def, dict):
                continue
            name = _short_name(prop_key, prop_def)
            rng, ref = _om_range(prop_def)

            multivalued = prop_def.get("type") == "array" or bool(
                prop_def.get("_linkedTypes") and len(prop_def.get("_linkedTypes", [])) > 1
            )

            lb.add_slot(
                ld,
                name,
                range=rng,
                description=(prop_def.get("description") or "")[:500] or None,
                multivalued=multivalued,
            )
            slot_names.append(name)
            if prop_key in required_fields:
                slot_usage[name] = {"required": True}

        # Controlled vocabulary → enum
        if module == "controlledTerms":
            lb.add_enum(ld, class_name, values=[], description=description)
        else:
            lb.add_class(
                ld,
                class_name,
                slots=slot_names,
                description=description,
                slot_usage=slot_usage,
            )
