"""DANDI schema adapter — dual-path: code introspection + JSON Schema files."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from undata.logging import get_logger
from undata.models import ExtractionMode, NormalizedElement, SchemaClassPayload

logger = get_logger(__name__)

_TYPE_MAP = {
    "str": "string",
    "string": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "dict": "object",
    "list": "array",
}


def _json_type_to_normalized(json_type: str | list | None) -> tuple[str, bool]:
    """Return (normalized_type, multivalued)."""
    if isinstance(json_type, list):
        non_null = [t for t in json_type if t != "null"]
        json_type = non_null[0] if non_null else "string"
    if not json_type:
        return "string", False
    if json_type == "array":
        return "array", True
    return _TYPE_MAP.get(json_type, "string"), False


def _elements_from_json_schema(
    schema: dict, source_name: str, extraction_path: str = "file"
) -> list[NormalizedElement]:
    """Extract NormalizedElements from a single JSON Schema dict."""
    elements: list[NormalizedElement] = []
    title = schema.get("title", "Unknown")
    props: dict = schema.get("properties", {})
    required_fields: set = set(schema.get("required", []))

    for field_name, field_info in props.items():
        raw_type = field_info.get("type")
        description = field_info.get("description", field_info.get("title", ""))
        enum_vals = field_info.get("enum")
        allowed = [str(v) for v in enum_vals] if enum_vals else None

        data_type, multivalued = _json_type_to_normalized(raw_type)

        constraints = {}
        for key in ("minimum", "maximum", "minLength", "maxLength", "pattern"):
            if key in field_info:
                constraints[key] = field_info[key]

        elements.append(
            NormalizedElement(
                name=field_name,
                data_type=data_type,
                description=str(description),
                required=field_name in required_fields,
                multivalued=multivalued,
                allowed_values=allowed,
                constraints=constraints,
                source_local_id=f"{title}.{field_name}",
                source_name=source_name,
                extraction_path=extraction_path,
                raw_metadata=field_info,
            )
        )
    return elements


class DANDIAdapter:
    source_name: str = "DANDI"
    source_format: str = "json"

    def __init__(self) -> None:
        self._models: list = []  # code-path: dandischema Pydantic classes
        self._file_schemas: list[dict] = []  # file-path: parsed JSON Schema dicts

    # ── Compatibility shim ───────────────────────────────────────────────────

    def load(self, path_or_url: str) -> None:
        """Compat shim: empty path → load_code(); non-empty → load_file()."""
        if path_or_url:
            self.load_file(path_or_url)
        else:
            self.load_code()

    # ── Dual-path loaders ────────────────────────────────────────────────────

    def load_code(self) -> None:
        """Load DANDI schema by introspecting dandischema.models."""
        import pydantic

        try:
            import dandischema.models as dm

            members = inspect.getmembers(dm, inspect.isclass)
            self._models = [
                cls
                for _, cls in members
                if issubclass(cls, pydantic.BaseModel) and cls is not pydantic.BaseModel
            ]
            logger.info("Loaded DANDI models via code", extra={"count": len(self._models)})
        except ImportError as exc:
            raise ImportError(
                f"dandischema is required for load_code(): {exc}. "
                "Install it with: pip install dandischema"
            ) from exc

    def load_file(self, path_or_url: str) -> None:
        """Load DANDI JSON Schema files from a local directory or single file."""
        if not path_or_url:
            raise ValueError(
                "path_or_url is required for DANDI file-path loading. "
                "Use load_code() for dandischema introspection."
            )
        p = Path(path_or_url)
        self._file_schemas = []
        if p.is_dir():
            for jf in sorted(p.rglob("*.json")):
                with open(jf) as fh:
                    self._file_schemas.append(json.load(fh))
        else:
            with open(p) as fh:
                self._file_schemas = [json.load(fh)]
        logger.info("Loaded DANDI file schemas", extra={"count": len(self._file_schemas)})

    # ── Extraction ───────────────────────────────────────────────────────────

    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]:
        if mode == "code":
            return self._extract_elements_code()
        elif mode == "file":
            return self._extract_elements_file()
        else:  # "both"
            from undata.adapters.merge import merge_elements

            return merge_elements(self._extract_elements_code(), self._extract_elements_file())

    def _extract_elements_code(self) -> list[NormalizedElement]:
        seen: set[str] = set()
        elements: list[NormalizedElement] = []

        for model_cls in self._models:
            model_name = model_cls.__name__
            try:
                schema = model_cls.model_json_schema()
            except Exception:
                continue

            props: dict = schema.get("properties", {})
            required_fields: set = set(schema.get("required", []))

            for field_name, field_info in props.items():
                unique_id = f"{model_name}.{field_name}"
                if unique_id in seen:
                    continue
                seen.add(unique_id)

                raw_type = field_info.get("type")
                items = field_info.get("items", {})
                description = field_info.get("description", field_info.get("title", ""))
                enum_vals = field_info.get("enum")
                allowed = [str(v) for v in enum_vals] if enum_vals else None

                data_type, multivalued = _json_type_to_normalized(raw_type)
                if data_type == "array" and items.get("type"):
                    data_type = "array"

                constraints = {}
                for key in ("minimum", "maximum", "minLength", "maxLength", "pattern"):
                    if key in field_info:
                        constraints[key] = field_info[key]

                elements.append(
                    NormalizedElement(
                        name=field_name,
                        data_type=data_type,
                        description=str(description),
                        required=field_name in required_fields,
                        multivalued=multivalued,
                        allowed_values=allowed,
                        constraints=constraints,
                        source_local_id=unique_id,
                        source_name=self.source_name,
                        extraction_path="code",
                        raw_metadata=field_info,
                    )
                )

        logger.info("Extracted DANDI elements (code)", extra={"count": len(elements)})
        return elements

    def _extract_elements_file(self) -> list[NormalizedElement]:
        # Fallback to code path for backward compat when no file loaded
        if not self._file_schemas:
            if self._models:
                return self._extract_elements_code()
            return []

        elements: list[NormalizedElement] = []
        for schema in self._file_schemas:
            elements.extend(_elements_from_json_schema(schema, self.source_name, "file"))
        logger.info("Extracted DANDI elements (file)", extra={"count": len(elements)})
        return elements

    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]:
        if mode == "code":
            return self._extract_classes_code()
        elif mode == "file":
            return self._extract_classes_file()
        else:  # "both"
            from undata.adapters.merge import merge_classes

            return merge_classes(self._extract_classes_code(), self._extract_classes_file())

    def _extract_classes_code(self) -> list[SchemaClassPayload]:
        from collections import defaultdict

        model_fields: dict[str, list[str]] = defaultdict(list)
        for model_cls in self._models:
            model_name = model_cls.__name__
            try:
                schema = model_cls.model_json_schema()
            except Exception:
                continue
            for field_name in schema.get("properties", {}):
                model_fields[model_name].append(f"{model_name}.{field_name}")

        classes = []
        for model_name, slids in sorted(model_fields.items()):
            classes.append(
                SchemaClassPayload(
                    class_name=model_name,
                    description=f"DANDI Pydantic model '{model_name}'",
                    element_source_local_ids=slids,
                    extraction_path="code",
                    schema_format="code",
                )
            )
        return classes

    def _extract_classes_file(self) -> list[SchemaClassPayload]:
        # Fallback for backward compat
        if not self._file_schemas:
            if self._models:
                return self._extract_classes_code()
            return []

        classes = []
        for schema in self._file_schemas:
            title = schema.get("title", "Unknown")
            props = schema.get("properties", {})
            slids = [f"{title}.{p}" for p in props]
            classes.append(
                SchemaClassPayload(
                    class_name=title,
                    description=schema.get("description", ""),
                    element_source_local_ids=slids,
                    extraction_path="file",
                    schema_format="json",
                )
            )
        return classes

    def get_version_info(self) -> dict:
        names = sorted(m.__name__ for m in self._models)
        content_hash = hashlib.sha256(json.dumps(names).encode()).hexdigest()
        version_tag = "local"
        try:
            import dandischema

            version_tag = getattr(dandischema, "__version__", "local")
        except ImportError:
            pass
        return {"version_tag": version_tag, "content_hash": content_hash}
