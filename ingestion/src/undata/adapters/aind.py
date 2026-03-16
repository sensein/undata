"""AINDAdapter — dual-path: code introspection + pre-exported JSON Schema files.

`aind-data-schema` 2.x uses a Rust extension (pyo3-ffi) that does not compile
on Python 3.14. This adapter therefore reads JSON Schema files generated once
from a Python 3.12 venv and bundled in tests/fixtures/aind/.

When aind-data-schema gains Python 3.14 support it can be imported directly
instead and the JSON Schema files regenerated as needed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from undata.logging import get_logger
from undata.models import ExtractionMode, NormalizedElement, SchemaClassPayload

logger = get_logger(__name__)

# Default fixtures directory relative to this file (works when installed in editable mode)
_DEFAULT_FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "aind"

# Core schema files to load (in order)
_SCHEMA_FILES = [
    "subject_schema.json",
    "acquisition_schema.json",
    "data_description_schema.json",
    "procedures_schema.json",
    "instrument_schema.json",
]

# JSON Schema type → NormalizedElement data_type mapping
_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "array": "string",
    "object": "object",
    "null": "string",
}


def _resolve_ref(ref: str, defs: dict[str, Any]) -> dict[str, Any]:
    """Resolve a $ref pointer within the same schema's $defs."""
    if not ref.startswith("#/$defs/"):
        return {}
    key = ref[len("#/$defs/") :]
    return defs.get(key, {})


def _get_data_type(prop: dict[str, Any], defs: dict[str, Any]) -> str:
    """Extract a simple data_type string from a JSON Schema property object."""
    if "$ref" in prop:
        resolved = _resolve_ref(prop["$ref"], defs)
        return _get_data_type(resolved, defs)

    raw_type = prop.get("type")
    if isinstance(raw_type, list):
        # nullable: ["string", "null"] → "string"
        non_null = [t for t in raw_type if t != "null"]
        raw_type = non_null[0] if non_null else "string"

    if raw_type:
        return _TYPE_MAP.get(raw_type, "string")

    # anyOf / oneOf — pick first concrete type
    for combiner in ("anyOf", "oneOf", "allOf"):
        options = prop.get(combiner, [])
        for opt in options:
            if "$ref" in opt:
                resolved = _resolve_ref(opt["$ref"], defs)
                t = _get_data_type(resolved, defs)
                if t != "string":
                    return t
            if "type" in opt:
                return _TYPE_MAP.get(opt["type"], "string")

    return "string"


def _load_schemas_from_dir(schema_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    schemas = []
    # First try the known fixture files
    for fname in _SCHEMA_FILES:
        fpath = schema_dir / fname
        if fpath.exists():
            with open(fpath) as fh:
                schemas.append((fname.replace("_schema.json", ""), json.load(fh)))
    # Also discover any other .json files not in the hardcoded list
    for fpath in sorted(schema_dir.glob("*.json")):
        if fpath.name in _SCHEMA_FILES:
            continue
        with open(fpath) as fh:
            model_name = fpath.stem.replace("_schema", "")
            schemas.append((model_name, json.load(fh)))
    return schemas


def _extract_props_from_object(
    properties: dict[str, Any],
    required_fields: set[str],
    defs: dict[str, Any],
    source_name: str,
    model_name: str,
    prefix: str,
    extraction_path: str,
    schema_file: str,
) -> list[NormalizedElement]:
    """Extract NormalizedElement list from a JSON Schema properties dict."""
    elements: list[NormalizedElement] = []
    for prop_name, prop_def in properties.items():
        if prop_name in ("object_type", "describedBy", "schema_version"):
            continue

        resolved = prop_def
        if "$ref" in prop_def and not prop_def.get("type"):
            resolved = _resolve_ref(prop_def["$ref"], defs)

        title = prop_def.get("title") or resolved.get("title") or prop_name
        description = prop_def.get("description") or resolved.get("description") or ""
        data_type = _get_data_type(prop_def, defs)

        raw_type = prop_def.get("type")
        multivalued = raw_type == "array" or "items" in prop_def

        allowed_values: list[str] = []
        enum_src = resolved.get("enum") or prop_def.get("enum") or []
        if enum_src:
            allowed_values = [str(v) for v in enum_src if v is not None]

        source_local_id = f"{prefix}.{prop_name}"
        elements.append(
            NormalizedElement(
                name=prop_name,
                data_type=data_type,
                description=description,
                required=prop_name in required_fields,
                multivalued=multivalued,
                allowed_values=allowed_values,
                constraints={},
                source_local_id=source_local_id,
                source_name=source_name,
                extraction_path=extraction_path,
                raw_metadata={
                    "schema_file": schema_file,
                    "title": title,
                    "model": model_name,
                },
            )
        )
    return elements


def _elements_from_schemas(
    schemas: list[tuple[str, dict]], source_name: str, extraction_path: str = "file"
) -> list[NormalizedElement]:
    elements: list[NormalizedElement] = []
    seen_ids: set[str] = set()

    for model_name, schema in schemas:
        defs = schema.get("$defs", {})
        schema_file = f"{model_name}_schema.json"

        # 1. Top-level properties
        top_props = schema.get("properties", {})
        top_required = set(schema.get("required", []))
        for el in _extract_props_from_object(
            top_props,
            top_required,
            defs,
            source_name,
            model_name,
            f"aind.{model_name}",
            extraction_path,
            schema_file,
        ):
            if el.source_local_id not in seen_ids:
                seen_ids.add(el.source_local_id)
                elements.append(el)

        # 2. Recurse into $defs — each def is a model with its own properties
        for def_name, def_schema in defs.items():
            def_props = def_schema.get("properties", {})
            if not def_props:
                continue
            def_required = set(def_schema.get("required", []))
            prefix = f"aind.{model_name}.{def_name}"
            for el in _extract_props_from_object(
                def_props,
                def_required,
                defs,
                source_name,
                def_name,
                prefix,
                extraction_path,
                schema_file,
            ):
                if el.source_local_id not in seen_ids:
                    seen_ids.add(el.source_local_id)
                    elements.append(el)

    return elements


def _classes_from_schemas(
    schemas: list[tuple[str, dict]], source_name: str, extraction_path: str
) -> list[SchemaClassPayload]:
    classes = []
    for model_name, schema in schemas:
        title = schema.get("title", model_name)
        properties = schema.get("properties", {})
        slids = [
            f"aind.{model_name}.{prop}"
            for prop in properties
            if prop not in ("object_type", "describedBy", "schema_version")
        ]
        classes.append(
            SchemaClassPayload(
                class_name=title,
                description=schema.get("description", ""),
                element_source_local_ids=slids,
                extraction_path=extraction_path,
                schema_format="json" if extraction_path == "file" else "code",
            )
        )
        # Also create classes for $defs models
        for def_name, def_schema in schema.get("$defs", {}).items():
            def_props = def_schema.get("properties", {})
            if not def_props:
                continue
            def_slids = [f"aind.{model_name}.{def_name}.{p}" for p in def_props]
            classes.append(
                SchemaClassPayload(
                    class_name=def_schema.get("title", def_name),
                    description=def_schema.get("description", ""),
                    element_source_local_ids=def_slids,
                    extraction_path=extraction_path,
                    schema_format="json" if extraction_path == "file" else "code",
                )
            )
    return classes


class AINDAdapter:
    """Adapter for AIND (Allen Institute for Neural Dynamics) schemas.

    Reads pre-exported JSON Schema files. Pass the directory containing the
    ``*_schema.json`` files to ``load()`` or ``load_file()``.
    If path is empty, the bundled fixtures are used.
    """

    source_name: str = "aind"
    source_format: str = "json-schema"

    def __init__(self) -> None:
        self._schemas: list[tuple[str, dict[str, Any]]] = []  # compat / file-path
        self._file_schemas: list[tuple[str, dict[str, Any]]] = []  # explicit file-path
        self._code_schemas: list[tuple[str, dict[str, Any]]] = []  # code-path
        self._schema_dir: Path | None = None

    # ── Compatibility shim ───────────────────────────────────────────────────

    def load(self, path_or_url: str) -> None:
        """Load JSON Schema files from *path_or_url* (must be a directory path)."""
        self.load_file(path_or_url)
        self._schemas = self._file_schemas  # backward compat alias

    # ── Dual-path loaders ────────────────────────────────────────────────────

    def load_code(self) -> None:
        """Load AIND schemas via aind-data-schema Python library.

        Raises ImportError on Python 3.14 due to pyo3-ffi incompatibility.
        """
        try:
            import inspect

            import aind_data_schema.core as aind_core

            schemas: list[tuple[str, dict]] = []
            for name, cls in inspect.getmembers(aind_core, inspect.isclass):
                if hasattr(cls, "model_json_schema"):
                    try:
                        schema = cls.model_json_schema()
                        schemas.append((name.lower(), schema))
                    except Exception:
                        continue
            self._code_schemas = schemas
        except ImportError as exc:
            raise ImportError(
                f"aind-data-schema is required for load_code(): {exc}. "
                "Note: aind-data-schema requires Python <3.14 due to pyo3-ffi. "
                "Use load_file() with pre-exported JSON Schema fixtures instead."
            ) from exc

    def load_file(self, path_or_url: str) -> None:
        """Load JSON Schema files from a directory. Empty path → bundled fixtures."""
        if path_or_url:
            schema_dir = Path(path_or_url)
        else:
            schema_dir = _DEFAULT_FIXTURES_DIR

        self._schema_dir = schema_dir
        self._file_schemas = _load_schemas_from_dir(schema_dir)

    # ── Extraction ───────────────────────────────────────────────────────────

    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]:
        if mode == "code":
            return _elements_from_schemas(self._code_schemas, self.source_name, "code")
        elif mode == "file":
            schemas = self._file_schemas or self._schemas
            if not schemas:
                self.load_file("")
                schemas = self._file_schemas
            return _elements_from_schemas(schemas, self.source_name, "file")
        else:  # "both"
            from undata.adapters.merge import merge_elements

            if not self._file_schemas and not self._schemas:
                self.load_file("")
            file_s = self._file_schemas or self._schemas
            if not self._code_schemas:
                try:
                    self.load_code()
                except ImportError as exc:
                    logger.warning(
                        "AINDAdapter.load_code() unavailable in both-mode; "
                        "falling back to file-only. Reason: %s",
                        exc,
                        extra={"event": "aind_code_path_unavailable", "mode": "both"},
                    )
            code_els = _elements_from_schemas(self._code_schemas, self.source_name, "code")
            file_els = _elements_from_schemas(file_s, self.source_name, "file")
            return merge_elements(code_els, file_els)

    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]:
        if mode == "code":
            return _classes_from_schemas(self._code_schemas, self.source_name, "code")
        elif mode == "file":
            schemas = self._file_schemas or self._schemas
            if not schemas:
                self.load_file("")
                schemas = self._file_schemas
            return _classes_from_schemas(schemas, self.source_name, "file")
        else:  # "both"
            from undata.adapters.merge import merge_classes

            file_s = self._file_schemas or self._schemas
            code_cls = _classes_from_schemas(self._code_schemas, self.source_name, "code")
            file_cls = _classes_from_schemas(file_s, self.source_name, "file")
            return merge_classes(code_cls, file_cls)

    def get_version_info(self) -> dict:
        """Return version info including a content_hash over all loaded schema files."""
        schemas = self._file_schemas or self._schemas
        if not schemas and self._schema_dir is None:
            self.load_file("")
            schemas = self._file_schemas

        combined = ""
        for _, schema in schemas:
            combined += json.dumps(schema, sort_keys=True)

        content_hash = hashlib.sha256(combined.encode()).hexdigest()

        return {
            "source_name": self.source_name,
            "source_format": self.source_format,
            "schema_files": [fname for fname, _ in schemas],
            "content_hash": content_hash,
        }
