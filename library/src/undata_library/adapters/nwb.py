"""NWB schema adapter — YAML parse of neurodata_type_def format.

Extracts:
- Classes with inheritance (neurodata_type_inc → subclass_of)
- Attributes from datasets, attributes, and nested datasets
- Links as object references (type_ref to target_type)
- Nested groups as composition references
- Fixed values as response_options
- quantity → required/multivalued flags
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
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


def _nwb_dtype(dtype_val: Any) -> tuple[str, str | None]:
    """Resolve NWB dtype to (data_type, type_ref).

    Returns (data_type, type_ref) where type_ref is set for object references.
    """
    if dtype_val is None:
        return "string", None
    if isinstance(dtype_val, list):
        # Compound dtype — treat as object
        return "object", None
    if isinstance(dtype_val, dict):
        # Reference dtype: {target_type: X, reftype: object}
        target = dtype_val.get("target_type")
        if target:
            return "object", target
        return "object", None
    return _NWB_TYPE_MAP.get(str(dtype_val), "string"), None


def _quantity_to_flags(quantity: Any) -> tuple[bool, bool]:
    """Map NWB quantity to (required, multivalued)."""
    if quantity is None or quantity == 1:
        return True, False
    if quantity == "?":
        return False, False
    if quantity == "+":
        return True, True
    if quantity == "*":
        return False, True
    return True, False


class NWBAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "nwb"

    @property
    def supported_formats(self) -> list[str]:
        return [".yaml", ".yml"]

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        self._repo = options.get("repo", "https://github.com/NeurodataWithoutBorders/nwb-schema")
        self._committish = options.get("committish")
        self._base_path = source_path
        results: list[ClassifiedEntity] = []

        for f in sorted(source_path.glob("*.yaml")):
            data = safe_load_yaml(f)
            if data is None:
                continue
            # Skip namespace files (they list source files, not schema)
            if "namespaces" in data:
                continue

            file_ref = self._file_ref(f)

            for section in ("datasets", "groups"):
                for item in data.get(section, []):
                    self._extract_type(item, section, file_ref, results)

        return results

    def _extract_type(
        self,
        item: dict,
        section: str,
        file_ref: SourceRef,
        results: list[ClassifiedEntity],
    ) -> None:
        """Extract a single NWB type definition (dataset or group)."""
        type_def = item.get("neurodata_type_def")
        type_name = type_def or item.get("default_name") or item.get("name", "")
        if not type_name:
            return

        # If this is a type definition, emit CLASS
        if type_def:
            parent = item.get("neurodata_type_inc")
            semantic: dict[str, Any] = {"properties": []}
            if parent:
                semantic["subclass_of"] = parent

            # Collect property names
            props = []
            for attr in item.get("attributes", []):
                if attr.get("name"):
                    props.append(attr["name"])
            for ds in item.get("datasets", []):
                n = ds.get("name") or ds.get("neurodata_type_def", "")
                if n:
                    props.append(n)
            for grp in item.get("groups", []):
                n = (
                    grp.get("name")
                    or grp.get("neurodata_type_def")
                    or grp.get("neurodata_type_inc", "")
                )
                if n:
                    props.append(n)
            for lnk in item.get("links", []):
                if lnk.get("name"):
                    props.append(lnk["name"])
            semantic["properties"] = props

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic=semantic,
                    provenance={
                        "source": "nwb",
                        "class": type_name,
                        "name": type_name,
                        "description": item.get("doc", ""),
                    },
                    confidence=0.9,
                    source_ref=file_ref,
                )
            )
        else:
            # Not a type def — emit as attribute only
            dt, type_ref = _nwb_dtype(item.get("dtype"))
            if section == "groups":
                dt = "object"
                type_ref = item.get("neurodata_type_inc")
            sem: dict[str, Any] = {"data_type": dt}
            if type_ref:
                sem["type_ref"] = type_ref
            # Fixed value
            fixed = item.get("value")
            if fixed is not None:
                sem["response_options"] = [{"value": str(fixed), "label": str(fixed)}]
                sem["value_domain"] = "categorical"
            # Quantity
            req, multi = _quantity_to_flags(item.get("quantity"))
            if not req:
                sem["required"] = False
            if multi:
                sem["multivalued"] = True
            # Dims/shape → array
            if item.get("dims") or item.get("shape"):
                sem["data_type"] = "array"

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=sem,
                    provenance={
                        "source": "nwb",
                        "class": type_name,
                        "name": type_name,
                        "description": item.get("doc", ""),
                    },
                    confidence=0.85,
                    source_ref=file_ref,
                )
            )

        # Extract child attributes
        for attr in item.get("attributes", []):
            aname = attr.get("name", "")
            if not aname:
                continue
            adt, aref = _nwb_dtype(attr.get("dtype"))
            asem: dict[str, Any] = {"data_type": adt}
            if aref:
                asem["type_ref"] = aref
            # Fixed value
            fixed = attr.get("value")
            if fixed is not None:
                asem["response_options"] = [{"value": str(fixed), "label": str(fixed)}]
            # Default value
            default = attr.get("default_value")
            if default is not None:
                asem["default_value"] = str(default)
            # Required
            if attr.get("required") is False:
                asem["required"] = False
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=asem,
                    provenance={
                        "source": "nwb",
                        "class": type_name,
                        "name": aname,
                        "description": attr.get("doc", ""),
                    },
                    confidence=0.9,
                    source_ref=file_ref,
                )
            )

        # Extract nested datasets
        for ds in item.get("datasets", []):
            dname = ds.get("name") or ds.get("neurodata_type_def", "")
            if not dname:
                continue
            ddt, dref = _nwb_dtype(ds.get("dtype"))
            dsem: dict[str, Any] = {"data_type": ddt}
            if dref:
                dsem["type_ref"] = dref
            if ds.get("dims") or ds.get("shape"):
                dsem["data_type"] = "array"
            fixed = ds.get("value")
            if fixed is not None:
                dsem["response_options"] = [{"value": str(fixed), "label": str(fixed)}]
            req, multi = _quantity_to_flags(ds.get("quantity"))
            if not req:
                dsem["required"] = False
            if multi:
                dsem["multivalued"] = True
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=dsem,
                    provenance={
                        "source": "nwb",
                        "class": type_name,
                        "name": dname,
                        "description": ds.get("doc", ""),
                    },
                    confidence=0.85,
                    source_ref=file_ref,
                )
            )

        # Extract links (inter-type references)
        for lnk in item.get("links", []):
            lname = lnk.get("name", "")
            target = lnk.get("target_type", "")
            if not lname and not target:
                continue
            display_name = lname or target
            lsem: dict[str, Any] = {"data_type": "object"}
            if target:
                lsem["type_ref"] = target
            req, multi = _quantity_to_flags(lnk.get("quantity"))
            if not req:
                lsem["required"] = False
            if multi:
                lsem["multivalued"] = True
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=lsem,
                    provenance={
                        "source": "nwb",
                        "class": type_name,
                        "name": display_name,
                        "description": lnk.get("doc", ""),
                    },
                    confidence=0.85,
                    source_ref=file_ref,
                )
            )

        # Extract nested groups (composition)
        for grp in item.get("groups", []):
            gname = grp.get("name") or grp.get("neurodata_type_def") or ""
            ginc = grp.get("neurodata_type_inc", "")
            if not gname and not ginc:
                continue
            display_name = gname or ginc
            gsem: dict[str, Any] = {"data_type": "object"}
            if ginc:
                gsem["type_ref"] = ginc
            req, multi = _quantity_to_flags(grp.get("quantity"))
            if not req:
                gsem["required"] = False
            if multi:
                gsem["multivalued"] = True
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=gsem,
                    provenance={
                        "source": "nwb",
                        "class": type_name,
                        "name": display_name,
                        "description": grp.get("doc", ""),
                    },
                    confidence=0.85,
                    source_ref=file_ref,
                )
            )
            # Recurse into nested group if it's a type def
            if grp.get("neurodata_type_def"):
                self._extract_type(grp, "groups", file_ref, results)

    def _file_ref(self, f: Path) -> SourceRef:
        checksum = hashlib.sha256(f.read_bytes()).hexdigest()
        rel = str(f.relative_to(self._base_path)) if f.is_relative_to(self._base_path) else str(f)
        return SourceRef(
            repo=self._repo,
            committish=self._committish,
            file=rel,
            checksum=checksum,
        )
