"""NWB schema adapter — dual-path: pynwb code introspection + YAML file."""

from __future__ import annotations

import hashlib
import json

from undata.logging import get_logger
from undata.models import ExtractionMode, NormalizedElement, SchemaClassPayload

logger = get_logger(__name__)

_DTYPE_MAP = {
    "text": "string",
    "ascii": "string",
    "utf": "string",
    "utf8": "string",
    "isodatetime": "string",
    "datetime": "string",
    "int": "number",
    "int8": "number",
    "int16": "number",
    "int32": "number",
    "int64": "number",
    "uint8": "number",
    "uint16": "number",
    "uint32": "number",
    "uint64": "number",
    "float": "number",
    "float32": "number",
    "float64": "number",
    "double": "number",
    "bool": "boolean",
}


def _map_dtype(dtype: str | None) -> str:
    if not dtype:
        return "string"
    return _DTYPE_MAP.get(str(dtype).lower(), "string")


def _quantity_to_required(quantity: str | None) -> bool:
    if quantity is None:
        return True
    return quantity not in ("?", "*", "+")


def _elements_from_groups(
    groups: list[dict], source_name: str, extraction_path: str = "file"
) -> list[NormalizedElement]:
    elements: list[NormalizedElement] = []
    for group in groups:
        group_name = group.get("neurodata_type_def", "NWBGroup")

        for attr in group.get("attributes", []):
            name = attr.get("name", "")
            elements.append(
                NormalizedElement(
                    name=name,
                    data_type=_map_dtype(attr.get("dtype")),
                    description=str(attr.get("doc", "")),
                    required=_quantity_to_required(attr.get("quantity")),
                    multivalued=False,
                    allowed_values=None,
                    constraints={},
                    source_local_id=f"{group_name}.{name}",
                    source_name=source_name,
                    extraction_path=extraction_path,
                    raw_metadata=attr,
                )
            )

        for ds in group.get("datasets", []):
            name = ds.get("name", ds.get("neurodata_type_inc", ""))
            if not name:
                continue
            elements.append(
                NormalizedElement(
                    name=name,
                    data_type=_map_dtype(ds.get("dtype")),
                    description=str(ds.get("doc", "")),
                    required=_quantity_to_required(ds.get("quantity")),
                    multivalued=True,
                    allowed_values=None,
                    constraints={},
                    source_local_id=f"{group_name}.dataset.{name}",
                    source_name=source_name,
                    extraction_path=extraction_path,
                    raw_metadata=ds,
                )
            )
    return elements


def _classes_from_groups(groups: list[dict], extraction_path: str) -> list[SchemaClassPayload]:
    classes = []
    for group in groups:
        neurodata_type = group.get("neurodata_type_def", "")
        if not neurodata_type:
            continue
        parent_inc = group.get("neurodata_type_inc")

        slids: list[str] = []
        for attr in group.get("attributes", []):
            name = attr.get("name", "")
            if name:
                slids.append(f"{neurodata_type}.{name}")
        for ds in group.get("datasets", []):
            name = ds.get("name", ds.get("neurodata_type_inc", ""))
            if name:
                slids.append(f"{neurodata_type}.dataset.{name}")

        classes.append(
            SchemaClassPayload(
                class_name=neurodata_type,
                description=str(group.get("doc", "")),
                element_source_local_ids=slids,
                parent_class_name=parent_inc if parent_inc else None,
                extraction_path=extraction_path,
                schema_format="yaml" if extraction_path in ("file", "both") else "code",
            )
        )
    return classes


class NWBAdapter:
    source_name: str = "NWB"
    source_format: str = "yaml"

    def __init__(self) -> None:
        self._raw_groups: list[dict] = []  # compat / code-path data
        self._file_groups: list[dict] = []  # file-path data
        self._path: str = ""

    # ── Compatibility shim ───────────────────────────────────────────────────

    def load(self, path_or_url: str) -> None:
        """Compat shim: delegates to load_file()."""
        self._path = path_or_url
        self.load_file(path_or_url)
        # Mirror into _raw_groups for backward compat
        self._raw_groups = self._file_groups

    # ── Dual-path loaders ────────────────────────────────────────────────────

    def load_code(self) -> None:
        """Load NWB type map via pynwb introspection."""
        try:
            import pynwb
            from hdmf.spec import GroupSpec

            type_map = pynwb.get_type_map()
            catalog = type_map.namespace_catalog
            groups: list[dict] = []
            for ns_name in catalog.get_namespace_names():
                ns = catalog.get_namespace(ns_name)
                for dt in ns.get_registered_types():
                    spec = ns.get_spec(dt)
                    if isinstance(spec, GroupSpec):
                        groups.append(spec.to_dict())
            self._raw_groups = groups
            logger.info("Loaded NWB types via code", extra={"count": len(groups)})
        except ImportError as exc:
            raise ImportError(
                f"pynwb is required for load_code(): {exc}. Install it with: pip install pynwb"
            ) from exc

    def load_file(self, path_or_url: str) -> None:
        """Load NWB spec YAML from a local file or remote URL."""
        if not path_or_url:
            raise ValueError(
                "path_or_url is required for NWB file-path loading. "
                "Use load_code() for pynwb introspection."
            )
        import yaml

        if path_or_url.startswith(("http://", "https://")):
            import httpx

            resp = httpx.get(path_or_url)
            resp.raise_for_status()
            data = yaml.safe_load(resp.text)
        else:
            with open(path_or_url) as fh:
                data = yaml.safe_load(fh)

        self._file_groups = data.get("groups", []) if isinstance(data, dict) else []
        logger.info("Loaded NWB schema via file", extra={"path": path_or_url})

    # ── Extraction ───────────────────────────────────────────────────────────

    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]:
        if mode == "code":
            elements = _elements_from_groups(self._raw_groups, self.source_name, "code")
        elif mode == "file":
            groups = self._file_groups if self._file_groups else self._raw_groups
            elements = _elements_from_groups(groups, self.source_name, "file")
        else:  # "both"
            from undata.adapters.merge import merge_elements

            code_els = _elements_from_groups(self._raw_groups, self.source_name, "code")
            file_els = _elements_from_groups(self._file_groups, self.source_name, "file")
            elements = merge_elements(code_els, file_els)
            logger.info("Extracted NWB elements (both)", extra={"count": len(elements)})
            return elements

        logger.info("Extracted NWB elements", extra={"count": len(elements), "mode": mode})
        return elements

    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]:
        if mode == "code":
            return _classes_from_groups(self._raw_groups, "code")
        elif mode == "file":
            groups = self._file_groups if self._file_groups else self._raw_groups
            return _classes_from_groups(groups, "file")
        else:  # "both"
            from undata.adapters.merge import merge_classes

            code_cls = _classes_from_groups(self._raw_groups, "code")
            file_cls = _classes_from_groups(self._file_groups, "file")
            return merge_classes(code_cls, file_cls)

    def get_version_info(self) -> dict:
        groups = self._raw_groups or self._file_groups
        raw = json.dumps(groups, default=str, sort_keys=True)
        content_hash = hashlib.sha256(raw.encode()).hexdigest()
        return {"version_tag": "local", "content_hash": content_hash}
