"""NWB schema extractor — direct YAML parse of neurodata_type_def format."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..models import ProvenanceEntry, SemanticIdentity

# NWB dtype string → DataType mapping
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


def extract_nwb(schema_path: Path) -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Extract elements from NWB YAML namespace files."""
    results: list[tuple[SemanticIdentity, ProvenanceEntry]] = []

    for f in sorted(schema_path.glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        if not isinstance(data, dict):
            continue

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

                sem = SemanticIdentity(data_type=dt)
                prov = ProvenanceEntry(
                    source="nwb",
                    **{"class": name},
                    name=name,
                    description=item.get("doc", ""),
                )
                results.append((sem, prov))

                # Extract attributes
                for attr in item.get("attributes", []):
                    aname = attr.get("name", "")
                    if not aname:
                        continue
                    adt = _NWB_TYPE_MAP.get(str(attr.get("dtype", "")), "string")
                    sem_a = SemanticIdentity(data_type=adt)
                    prov_a = ProvenanceEntry(
                        source="nwb",
                        **{"class": name},
                        name=aname,
                        description=attr.get("doc", ""),
                    )
                    results.append((sem_a, prov_a))

                # Extract nested datasets
                for ds in item.get("datasets", []):
                    dname = ds.get("name") or ds.get("neurodata_type_def", "")
                    if not dname:
                        continue
                    ddt = (
                        "object"
                        if isinstance(ds.get("dtype"), list)
                        else _NWB_TYPE_MAP.get(str(ds.get("dtype", "")), "string")
                    )
                    sem_d = SemanticIdentity(data_type=ddt)
                    prov_d = ProvenanceEntry(
                        source="nwb",
                        **{"class": name},
                        name=dname,
                        description=ds.get("doc", ""),
                    )
                    results.append((sem_d, prov_d))

    return results
