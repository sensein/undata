"""openMINDS schema adapter — dual-path: registry code + JSON-LD/Turtle file."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from undata.logging import get_logger
from undata.models import ExtractionMode, NormalizedElement, SchemaClassPayload

logger = get_logger(__name__)


def _infer_type(prop: dict) -> str:
    type_uri = prop.get("@type", "")
    if isinstance(type_uri, list):
        type_uri = " ".join(type_uri)
    type_lower = str(type_uri).lower()
    if any(t in type_lower for t in ("integer", "number", "float", "quantity")):
        return "number"
    if "boolean" in type_lower:
        return "boolean"
    if "array" in type_lower or prop.get("minItems") is not None:
        return "array"
    return "string"


def _elements_from_schema(
    schema: dict, source_name: str, extraction_path: str = "file"
) -> list[NormalizedElement]:
    elements: list[NormalizedElement] = []
    type_name = schema.get("_type", schema.get("@type", "Unknown")).split("/")[-1]
    properties: dict = schema.get("properties", {})

    for prop_name, prop_def in properties.items():
        if not isinstance(prop_def, dict):
            continue
        description = prop_def.get("description", prop_def.get("_instruction", ""))
        data_type = _infer_type(prop_def)
        multivalued = data_type == "array" or prop_def.get("minItems") is not None

        elements.append(
            NormalizedElement(
                name=prop_name,
                data_type=data_type,
                description=str(description),
                required=prop_def.get("_required", False),
                multivalued=multivalued,
                allowed_values=None,
                constraints={},
                source_local_id=f"{type_name}.{prop_name}",
                source_name=source_name,
                extraction_path=extraction_path,
                raw_metadata=prop_def,
            )
        )
    return elements


def _classes_from_schema(
    schema: dict, extraction_path: str, schema_format: str
) -> SchemaClassPayload:
    type_uri = schema.get("_type", schema.get("@type", "Unknown"))
    class_name = type_uri.split("/")[-1] if "/" in type_uri else type_uri
    properties: dict = schema.get("properties", {})
    slids = [f"{class_name}.{prop}" for prop in properties]
    return SchemaClassPayload(
        class_name=class_name,
        description=schema.get("description", ""),
        element_source_local_ids=slids,
        extraction_path=extraction_path,
        schema_format=schema_format,
    )


class OpenMINDSAdapter:
    source_name: str = "openMINDS"
    source_format: str = "json-ld"

    def __init__(self) -> None:
        self._data: dict = {}  # compat / single-file load
        self._file_schemas: list[dict] = []  # file-path: list of parsed schemas
        self._path: str = ""

    # ── Compatibility shim ───────────────────────────────────────────────────

    def load(self, path_or_url: str) -> None:
        """Compat shim: delegates to load_file()."""
        self._path = path_or_url
        self.load_file(path_or_url)
        # Mirror single schema into _data for backward compat
        if self._file_schemas:
            self._data = self._file_schemas[0]

    # ── Dual-path loaders ────────────────────────────────────────────────────

    def load_code(self) -> None:
        """Load openMINDS types via openminds registry."""
        try:
            import openminds

            registry = openminds.registry
            types = registry.get("types", {})
            schemas_latest = types.get("latest", types.get("v4", {}))
            self._code_schemas: list[dict] = []
            for type_uri, cls in schemas_latest.items():
                schema: dict = {"_type": type_uri, "properties": {}}
                try:
                    if isinstance(cls, dict):
                        # Registry value is already a schema dict
                        schema["properties"] = cls.get("properties", {})
                    elif hasattr(cls, "model_fields"):
                        schema["properties"] = {k: {} for k in cls.model_fields}
                    elif hasattr(cls, "__fields__"):
                        schema["properties"] = {k: {} for k in cls.__fields__}
                except Exception:
                    pass
                self._code_schemas.append(schema)
            logger.info(
                "Loaded openMINDS types via code",
                extra={"count": len(self._code_schemas)},
            )
        except ImportError as exc:
            raise ImportError(
                f"openminds is required for load_code(): {exc}. "
                "Install it with: pip install openminds"
            ) from exc

    def load_file(self, path_or_url: str) -> None:
        """Load openMINDS schema from a JSON-LD file, directory, or remote URL."""
        if not path_or_url:
            raise ValueError(
                "path_or_url is required for openMINDS file-path loading. "
                "Use load_code() for openminds registry introspection."
            )
        p = Path(path_or_url)
        self._file_schemas = []

        if p.is_dir():
            # Glob .schema.omi.json files first, fall back to all .json
            schema_files = sorted(p.glob("*.schema.omi.json"))
            if not schema_files:
                schema_files = sorted(p.glob("*.json"))
            for jf in schema_files:
                with open(jf) as fh:
                    self._file_schemas.append(json.load(fh))
        else:
            with open(p) as fh:
                self._file_schemas = [json.load(fh)]

        # Keep backward-compat single _data
        if self._file_schemas:
            self._data = self._file_schemas[0]
        logger.info(
            "Loaded openMINDS schemas via file",
            extra={"count": len(self._file_schemas)},
        )

    def load_turtle(self, path_or_url: str) -> None:
        """Load openMINDS schema from a Turtle (.ttl) RDF file."""
        if not path_or_url:
            raise ValueError("path_or_url is required for Turtle loading.")
        import rdflib
        from rdflib.namespace import RDF, RDFS

        g = rdflib.Graph()
        g.parse(path_or_url, format="turtle")

        schemas: list[dict] = []
        # Collect all classes
        for cls in g.subjects(RDF.type, RDFS.Class):
            props: dict = {}
            for prop in g.subjects(RDFS.domain, cls):
                prop_name = str(prop).split("/")[-1]
                props[str(prop)] = {"label": prop_name}
            schemas.append({"_type": str(cls), "properties": props})

        if not schemas:
            # Fallback: record that we parsed the Turtle but found no RDFS.Class
            schemas = [{"_type": "TurtleSchema", "properties": {}}]

        self._file_schemas = schemas
        if schemas:
            self._data = schemas[0]
        logger.info(
            "Loaded openMINDS schemas via Turtle",
            extra={"count": len(schemas)},
        )

    # ── Extraction ───────────────────────────────────────────────────────────

    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]:
        if mode == "code":
            schemas = getattr(self, "_code_schemas", [])
            elements = sum(
                (_elements_from_schema(s, self.source_name, "code") for s in schemas), []
            )
        elif mode == "file":
            file_s = self._file_schemas or ([self._data] if self._data else [])
            elements = sum((_elements_from_schema(s, self.source_name, "file") for s in file_s), [])
        else:  # "both"
            from undata.adapters.merge import merge_elements

            code = getattr(self, "_code_schemas", [])
            file_s = self._file_schemas or ([self._data] if self._data else [])
            code_els = sum((_elements_from_schema(s, self.source_name, "code") for s in code), [])
            file_els = sum((_elements_from_schema(s, self.source_name, "file") for s in file_s), [])
            elements = merge_elements(code_els, file_els)
            logger.info("Extracted openMINDS elements (both)", extra={"count": len(elements)})
            return elements

        logger.info("Extracted openMINDS elements", extra={"count": len(elements), "mode": mode})
        return elements

    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]:
        if mode == "code":
            schemas = getattr(self, "_code_schemas", [])
            return [_classes_from_schema(s, "code", "code") for s in schemas]
        elif mode == "file":
            schemas = self._file_schemas or ([self._data] if self._data else [])
            return [_classes_from_schema(s, "file", "jsonld") for s in schemas]
        else:  # "both"
            from undata.adapters.merge import merge_classes

            code_schemas = getattr(self, "_code_schemas", [])
            file_schemas = self._file_schemas or ([self._data] if self._data else [])
            code_cls = [_classes_from_schema(s, "code", "code") for s in code_schemas]
            file_cls = [_classes_from_schema(s, "file", "jsonld") for s in file_schemas]
            return merge_classes(code_cls, file_cls)

    def get_version_info(self) -> dict:
        raw = json.dumps(self._data, sort_keys=True)
        content_hash = hashlib.sha256(raw.encode()).hexdigest()
        return {"version_tag": "local", "content_hash": content_hash}
