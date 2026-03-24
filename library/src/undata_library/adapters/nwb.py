"""NWB schema adapter — converts NWB YAML to LinkML, then extracts entities.

Parses neurodata_type_def YAML files and builds a LinkML SchemaDefinition
with classes (is_a for inheritance), slots (attributes, datasets, links, groups),
and proper type references.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import SourceRef
from ..utils import safe_load_yaml
from .base import BaseAdapter, ClassifiedEntity

_NWB_TYPE_MAP = {
    "text": "string",
    "utf": "string",
    "utf8": "string",
    "ascii": "string",
    "isodatetime": "string",
    "int8": "integer",
    "int16": "integer",
    "int32": "integer",
    "int64": "integer",
    "uint8": "integer",
    "uint16": "integer",
    "uint32": "integer",
    "uint64": "integer",
    "float16": "float",
    "float32": "float",
    "float64": "float",
    "double": "float",
    "bool": "boolean",
}


def _nwb_range(dtype_val: Any) -> tuple[str, str | None]:
    """Resolve NWB dtype to (linkml_range, type_ref)."""
    if dtype_val is None:
        return "string", None
    if isinstance(dtype_val, list):
        return "string", None  # Compound dtype
    if isinstance(dtype_val, dict):
        target = dtype_val.get("target_type")
        if target:
            return target, target
        return "string", None
    return _NWB_TYPE_MAP.get(str(dtype_val), "string"), None


class NWBAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "nwb"

    @property
    def supported_formats(self) -> list[str]:
        return [".yaml", ".yml"]

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        repo = options.get("repo", "https://github.com/NeurodataWithoutBorders/nwb-schema")
        committish = options.get("committish")
        base_ref = SourceRef(repo=repo, committish=committish, file="core", checksum="")

        schema = self._build_linkml_schema(source_path)

        from .linkml import LinkMLAdapter

        return LinkMLAdapter().extract_from_schema_definition(
            schema, source_name="nwb", source_ref=base_ref
        )

    def _build_linkml_schema(self, source_path: Path) -> Any:
        """Convert NWB YAML files to a LinkML SchemaDefinition."""
        from . import linkml_builder as lb

        ld = lb.build_schema(
            name="nwb",
            schema_id="https://nwb-schema.readthedocs.io/schema",
            title="NWB Schema",
            prefix="nwb",
            prefix_uri="https://nwb-schema.readthedocs.io/schema/",
        )

        for f in sorted(source_path.glob("*.yaml")):
            data = safe_load_yaml(f)
            if data is None or "namespaces" in data:
                continue

            for section in ("datasets", "groups"):
                for item in data.get(section, []):
                    self._add_type_to_schema(ld, item, section, lb)

        return ld

    def _add_type_to_schema(self, ld: Any, item: dict, section: str, lb: Any) -> None:
        """Add an NWB type definition to the LinkML schema."""
        type_def = item.get("neurodata_type_def")
        type_name = type_def or item.get("default_name") or item.get("name", "")
        if not type_name:
            return

        if type_def:
            # This is a named type → class
            parent = item.get("neurodata_type_inc")
            slot_names = []

            # Attributes → slots
            for attr in item.get("attributes", []):
                aname = attr.get("name", "")
                if not aname:
                    continue
                rng, _ = _nwb_range(attr.get("dtype"))
                lb.add_slot(ld, aname, range=rng, description=attr.get("doc"))
                slot_names.append(aname)

            # Nested datasets → slots
            for ds in item.get("datasets", []):
                dname = ds.get("name") or ds.get("neurodata_type_def", "")
                if not dname:
                    continue
                rng, ref = _nwb_range(ds.get("dtype"))
                if ds.get("dims") or ds.get("shape"):
                    rng = "string"  # Array — LinkML doesn't have native array range
                lb.add_slot(
                    ld,
                    dname,
                    range=rng,
                    description=ds.get("doc"),
                    multivalued=ds.get("quantity") in ("*", "+"),
                )
                slot_names.append(dname)

            # Links → slots with range = target_type
            for lnk in item.get("links", []):
                lname = lnk.get("name") or lnk.get("target_type", "")
                target = lnk.get("target_type", "")
                if not lname:
                    continue
                lb.add_slot(
                    ld,
                    lname,
                    range=target or "string",
                    description=lnk.get("doc"),
                    multivalued=lnk.get("quantity") in ("*", "+"),
                )
                slot_names.append(lname)

            # Nested groups → slots with range = neurodata_type_inc
            for grp in item.get("groups", []):
                gname = (
                    grp.get("name")
                    or grp.get("neurodata_type_def")
                    or grp.get("neurodata_type_inc", "")
                )
                ginc = grp.get("neurodata_type_inc", "")
                if not gname:
                    continue
                lb.add_slot(
                    ld,
                    gname,
                    range=ginc or "string",
                    description=grp.get("doc"),
                    multivalued=grp.get("quantity") in ("*", "+"),
                )
                slot_names.append(gname)

                # Recurse if nested type def
                if grp.get("neurodata_type_def"):
                    self._add_type_to_schema(ld, grp, "groups", lb)

            # Build slot_usage for required fields
            slot_usage = {}
            for attr in item.get("attributes", []):
                if attr.get("required") is not False and attr.get("name"):
                    slot_usage[attr["name"]] = {"required": True}

            lb.add_class(
                ld,
                type_name,
                slots=slot_names,
                is_a=parent,
                description=item.get("doc"),
                slot_usage=slot_usage,
            )
        else:
            # Not a type def — just a slot
            rng, _ = _nwb_range(item.get("dtype"))
            if section == "groups":
                rng = item.get("neurodata_type_inc") or "string"
            if item.get("dims") or item.get("shape"):
                rng = "string"
            lb.add_slot(
                ld,
                type_name,
                range=rng,
                description=item.get("doc"),
                multivalued=item.get("quantity") in ("*", "+"),
            )
