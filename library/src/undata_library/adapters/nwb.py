"""NWB schema adapter — YAML parse of neurodata_type_def format."""

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

            file_ref = self._file_ref(f)

            for section in ("datasets", "groups"):
                for item in data.get(section, []):
                    name = (
                        item.get("neurodata_type_def")
                        or item.get("default_name")
                        or item.get("name", "")
                    )
                    if not name:
                        continue

                    dt = "object" if section == "groups" else "string"
                    if item.get("dtype") and isinstance(item["dtype"], list):
                        dt = "object"
                    elif isinstance(item.get("dtype"), str):
                        dt = _NWB_TYPE_MAP.get(item["dtype"], "string")

                    # Named type defs are classes
                    if item.get("neurodata_type_def"):
                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.CLASS,
                                semantic={"properties": []},
                                provenance={
                                    "source": "nwb",
                                    "class": name,
                                    "name": name,
                                    "description": item.get("doc", ""),
                                },
                                confidence=0.9,
                                source_ref=file_ref,
                            )
                        )

                    # Main element
                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.ATTRIBUTE,
                            semantic={"data_type": dt},
                            provenance={
                                "source": "nwb",
                                "class": name,
                                "name": name,
                                "description": item.get("doc", ""),
                            },
                            confidence=0.85,
                            source_ref=file_ref,
                        )
                    )

                    # Attributes
                    for attr in item.get("attributes", []):
                        aname = attr.get("name", "")
                        if not aname:
                            continue
                        adt = _NWB_TYPE_MAP.get(str(attr.get("dtype", "")), "string")
                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.ATTRIBUTE,
                                semantic={"data_type": adt},
                                provenance={
                                    "source": "nwb",
                                    "class": name,
                                    "name": aname,
                                    "description": attr.get("doc", ""),
                                },
                                confidence=0.9,
                                source_ref=file_ref,
                            )
                        )

                    # Nested datasets
                    for ds in item.get("datasets", []):
                        dname = ds.get("name") or ds.get("neurodata_type_def", "")
                        if not dname:
                            continue
                        ddt = (
                            "object"
                            if isinstance(ds.get("dtype"), list)
                            else _NWB_TYPE_MAP.get(str(ds.get("dtype", "")), "string")
                        )
                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.ATTRIBUTE,
                                semantic={"data_type": ddt},
                                provenance={
                                    "source": "nwb",
                                    "class": name,
                                    "name": dname,
                                    "description": ds.get("doc", ""),
                                },
                                confidence=0.85,
                                source_ref=file_ref,
                            )
                        )

        return results

    def _file_ref(self, f: Path) -> SourceRef:
        checksum = hashlib.sha256(f.read_bytes()).hexdigest()
        rel = str(f.relative_to(self._base_path)) if f.is_relative_to(self._base_path) else str(f)
        return SourceRef(
            repo=self._repo,
            committish=self._committish,
            file=rel,
            checksum=checksum,
        )
