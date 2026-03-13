"""BIDS schema adapter — dual-path: bidsschematools code + raw YAML file."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from undata.logging import get_logger
from undata.models import ExtractionMode, NormalizedElement, SchemaClassPayload

logger = get_logger(__name__)

_TYPE_MAP = {
    "string": "string",
    "text": "string",
    "number": "number",
    "integer": "number",
    "float": "number",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
}


def _map_type(raw: str | list | None) -> str:
    if isinstance(raw, list):
        raw = raw[0] if raw else "string"
    if not raw:
        return "string"
    return _TYPE_MAP.get(str(raw).lower(), "string")


def _elements_from_fields(
    fields: dict, source_name: str, extraction_path: str = "file"
) -> list[NormalizedElement]:
    elements = []
    for field_name, field_def in fields.items():
        if hasattr(field_def, "__dict__"):
            field_dict = vars(field_def)
        elif isinstance(field_def, dict):
            field_dict = field_def
        else:
            continue

        raw_type = field_dict.get("type", "string")
        enum_vals = field_dict.get("enum") or field_dict.get("levels")
        allowed = [str(v) for v in enum_vals] if enum_vals else None
        data_type = "string" if allowed else _map_type(raw_type)

        elements.append(
            NormalizedElement(
                name=field_name,
                data_type=data_type,
                description=str(field_dict.get("description", "")),
                required=bool(field_dict.get("required", False)),
                multivalued=_map_type(raw_type) == "array",
                allowed_values=allowed,
                constraints={
                    k: field_dict[k] for k in ("minimum", "maximum", "pattern") if k in field_dict
                },
                source_local_id=field_name,
                source_name=source_name,
                extraction_path=extraction_path,
                raw_metadata=field_dict,
            )
        )
    return elements


def _classes_from_sidecars(
    schema, all_fields: dict, extraction_path: str
) -> list[SchemaClassPayload]:
    """Build SchemaClassPayload list from schema.rules.sidecars modality groups.

    Structure: schema.rules.sidecars.<modality>._properties = {
        "<GroupName>": {"selectors": [...], "fields": {"FieldName": ..., ...}}
    }
    """
    seen_groups: dict[str, set[str]] = {}  # group_name → set of field names

    try:
        sidecars = schema.rules.sidecars
        # Iterate modalities (anat, asl, beh, eeg, etc.)
        modality_items = sidecars.items() if hasattr(sidecars, "items") else vars(sidecars).items()
        for modality_name, modality_ns in modality_items:
            if modality_name.startswith("_"):
                continue
            # Each modality namespace has _properties dict
            props = (
                vars(modality_ns).get("_properties", {}) if hasattr(modality_ns, "__dict__") else {}
            )
            if not isinstance(props, dict):
                continue
            for group_name, group_def in props.items():
                if group_name.startswith("_"):
                    continue
                # group_def may be dict with "fields" key or Namespace
                if isinstance(group_def, dict):
                    group_fields = group_def.get("fields", {})
                elif hasattr(group_def, "fields"):
                    group_fields = group_def.fields
                    if hasattr(group_fields, "__dict__"):
                        group_fields = vars(group_fields)
                else:
                    group_fields = {}

                if hasattr(group_fields, "keys"):
                    field_names = set(group_fields.keys())
                else:
                    field_names = set()

                if group_name not in seen_groups:
                    seen_groups[group_name] = set()
                seen_groups[group_name].update(field_names)
    except Exception as exc:
        logger.warning("Failed to load BIDS sidecar groups", extra={"error": str(exc)})

    classes = []
    for group_name, field_names in sorted(seen_groups.items()):
        slids = [fn for fn in sorted(field_names) if fn in all_fields]
        if not slids:
            slids = sorted(field_names)
        classes.append(
            SchemaClassPayload(
                class_name=group_name,
                description=f"BIDS sidecar group '{group_name}'",
                element_source_local_ids=slids,
                extraction_path=extraction_path,
                schema_format="code",
            )
        )
    return classes


def _classes_from_fields(
    fields: dict, source_name: str, extraction_path: str
) -> list[SchemaClassPayload]:
    from collections import defaultdict

    category_map: dict[str, list[str]] = defaultdict(list)
    for field_name in fields:
        category = field_name.split("_")[0] if "_" in field_name else field_name
        category_map[category].append(field_name)

    classes = []
    for category, field_names in sorted(category_map.items()):
        classes.append(
            SchemaClassPayload(
                class_name=category,
                description=f"BIDS fields in category '{category}'",
                element_source_local_ids=field_names,
                extraction_path=extraction_path,
                schema_format="yaml" if extraction_path == "file" else "code",
            )
        )
    return classes


class BIDSAdapter:
    source_name: str = "BIDS"
    source_format: str = "yaml"

    def __init__(self) -> None:
        self._raw_fields: dict = {}  # code-path data (bidsschematools)
        self._file_fields: dict = {}  # file-path data (raw YAML)
        self._path: str = ""
        self._bst_schema = None  # bidsschematools schema object (for sidecar groups)

    # ── Compatibility shim ───────────────────────────────────────────────────

    def load(self, path_or_url: str) -> None:
        """Compat shim: empty path → load_code(); non-empty → load_file()."""
        self._path = path_or_url
        if not path_or_url:
            self.load_code()
        else:
            self.load_file(path_or_url)

    # ── Dual-path loaders ────────────────────────────────────────────────────

    # All 9 vocabulary object types in bidsschematools
    _VOCAB_TYPES = [
        "metadata",
        "columns",
        "entities",
        "suffixes",
        "enums",
        "formats",
        "datatypes",
        "extensions",
        "files",
    ]

    def load_code(self) -> None:
        """Load BIDS schema via bundled bidsschematools library (all 9 vocabulary types)."""
        try:
            import bidsschematools.schema as bst

            schema = bst.load_schema()
            self._raw_fields = {}
            for vocab_type in self._VOCAB_TYPES:
                obj = getattr(schema.objects, vocab_type, None)
                if obj is None:
                    continue
                entries = dict(obj) if hasattr(obj, "keys") else {}
                for field_name, field_def in entries.items():
                    # Tag each entry with its vocabulary_type
                    if hasattr(field_def, "__dict__"):
                        field_dict = vars(field_def).copy()
                    elif isinstance(field_def, dict):
                        field_dict = field_def.copy()
                    else:
                        field_dict = {}
                    field_dict["vocabulary_type"] = vocab_type
                    self._raw_fields[field_name] = field_dict

            # Store schema for sidecar-based class grouping
            self._bst_schema = schema
            logger.info(
                "Loaded bundled BIDS schema via bidsschematools",
                extra={"count": len(self._raw_fields)},
            )
        except ImportError as exc:
            raise ImportError(
                f"bidsschematools is required for load_code(): {exc}. "
                "Install it with: pip install bidsschematools"
            ) from exc
        except Exception as exc:
            logger.warning("bidsschematools unavailable", extra={"error": str(exc)})
            self._raw_fields = {}

    def load_file(self, path_or_url: str) -> None:
        """Load BIDS schema from a local YAML file or BIDS schema directory."""
        if not path_or_url:
            raise ValueError(
                "path_or_url is required for BIDS file-path loading. "
                "Use load_code() for bundled bidsschematools schema."
            )
        import yaml

        p = Path(path_or_url)
        if p.is_dir():
            # BIDS schema directory: look for objects/metadata.yaml
            metadata_yaml = p / "objects" / "metadata.yaml"
            if metadata_yaml.exists():
                with open(metadata_yaml) as fh:
                    self._file_fields = yaml.safe_load(fh) or {}
            else:
                # Try top-level YAML files
                self._file_fields = {}
                for yf in sorted(p.glob("*.yaml")):
                    with open(yf) as fh:
                        data = yaml.safe_load(fh) or {}
                    self._file_fields.update(data.get("objects", {}).get("metadata", {}))
        else:
            with open(p) as fh:
                data = yaml.safe_load(fh)
            if isinstance(data, dict):
                self._file_fields = data.get("objects", {}).get("metadata", {})
                if not self._file_fields:
                    self._file_fields = data
            else:
                self._file_fields = {}
        logger.info("Loaded BIDS schema via file", extra={"path": path_or_url})

    # ── Extraction ───────────────────────────────────────────────────────────

    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]:
        if mode == "code":
            elements = _elements_from_fields(self._raw_fields, self.source_name, "code")
        elif mode == "file":
            fields = self._file_fields if self._file_fields else self._raw_fields
            elements = _elements_from_fields(fields, self.source_name, "file")
        else:  # "both"
            from undata.adapters.merge import merge_elements

            code_els = _elements_from_fields(self._raw_fields, self.source_name, "code")
            file_fields = self._file_fields if self._file_fields else {}
            file_els = _elements_from_fields(file_fields, self.source_name, "file")
            elements = merge_elements(code_els, file_els)

        logger.info("Extracted BIDS elements", extra={"count": len(elements), "mode": mode})
        return elements

    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]:
        if mode == "code":
            if self._bst_schema is not None:
                return _classes_from_sidecars(self._bst_schema, self._raw_fields, "code")
            return _classes_from_fields(self._raw_fields, self.source_name, "code")
        elif mode == "file":
            fields = self._file_fields if self._file_fields else self._raw_fields
            return _classes_from_fields(fields, self.source_name, "file")
        else:  # "both"
            from undata.adapters.merge import merge_classes

            if self._bst_schema is not None:
                code_cls = _classes_from_sidecars(self._bst_schema, self._raw_fields, "code")
            else:
                code_cls = _classes_from_fields(self._raw_fields, self.source_name, "code")
            file_fields = self._file_fields if self._file_fields else {}
            file_cls = _classes_from_fields(file_fields, self.source_name, "file")
            return merge_classes(code_cls, file_cls)

    def get_version_info(self) -> dict:
        fields = self._raw_fields or self._file_fields
        raw = json.dumps(fields, default=str, sort_keys=True)
        content_hash = hashlib.sha256(raw.encode()).hexdigest()
        version_tag = "local"
        try:
            import bidsschematools

            version_tag = getattr(bidsschematools, "__version__", "local")
        except ImportError:
            pass
        return {"version_tag": version_tag, "content_hash": content_hash}
