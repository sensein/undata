"""DANDI schema adapter — delegates to standalone extraction script.

The actual extraction happens in standalone_scripts/dandi_extract.py running in
an isolated venv with dandischema. This adapter class provides a fallback when
dandischema is available in the current environment, converting Pydantic models
to LinkML and then extracting via the standard LinkML adapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import SourceRef
from .base import BaseAdapter, ClassifiedEntity


class DANDIAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "dandi"

    @property
    def supported_formats(self) -> list[str]:
        return []

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        try:
            import dandischema.models as dm
        except ImportError:
            return []

        base_ref = SourceRef(
            repo="https://github.com/dandi/dandischema",
            committish=getattr(dm, "__version__", None),
            file="models.py",
            checksum="",
        )

        schema = self._build_linkml_schema(dm)

        from .linkml import LinkMLAdapter

        return LinkMLAdapter().extract_from_schema_definition(
            schema, source_name="dandi", source_ref=base_ref
        )

    def _build_linkml_schema(self, dm: Any) -> Any:
        """Convert dandischema Pydantic models to LinkML SchemaDefinition."""
        import inspect

        from . import linkml_builder as lb

        ld = lb.build_schema(
            name="dandi",
            schema_id="https://dandiarchive.org/schema",
            title="DANDI Schema",
            prefix="dandi",
            prefix_uri="https://dandiarchive.org/schema/",
        )

        seen_enums: set[str] = set()

        for cls_name, cls in inspect.getmembers(dm, inspect.isclass):
            if not hasattr(cls, "model_fields"):
                continue

            # Inheritance
            bases = [
                b.__name__
                for b in cls.__bases__
                if b.__name__ != "BaseModel" and hasattr(b, "model_fields")
            ]
            is_a = bases[0] if bases else None
            mixins = bases[1:] if len(bases) > 1 else None

            # Collect slots + slot_usage
            slot_names = []
            slot_usage = {}
            for field_name, field_info in cls.model_fields.items():
                ann = field_info.annotation
                desc = field_info.description or ""

                # Determine range
                rng = self._linkml_range(ann)

                # Check for enum
                enum_cls = self._extract_enum(ann)
                if enum_cls and enum_cls.__name__ not in seen_enums:
                    seen_enums.add(enum_cls.__name__)
                    vals = [str(v.value) for v in enum_cls]
                    lb.add_enum(ld, enum_cls.__name__, vals)
                if enum_cls:
                    rng = enum_cls.__name__

                multivalued = self._is_multivalued(ann)
                lb.add_slot(
                    ld,
                    field_name,
                    range=rng,
                    description=desc[:500] or None,
                    multivalued=multivalued,
                )
                slot_names.append(field_name)

                if field_info.is_required():
                    slot_usage[field_name] = {"required": True}

            desc = cls.__doc__.strip().split("\n")[0] if cls.__doc__ else None
            lb.add_class(
                ld,
                cls_name,
                slots=slot_names,
                is_a=is_a,
                mixins=mixins,
                description=desc,
                slot_usage=slot_usage,
            )

        return ld

    @staticmethod
    def _linkml_range(annotation: Any) -> str:
        """Map a Pydantic annotation to a LinkML range."""
        import enum
        import types
        import typing

        if annotation is None:
            return "string"

        # Unwrap Optional/Union
        args = None
        origin = getattr(annotation, "__origin__", None)
        if origin is typing.Union:
            args = annotation.__args__
        elif isinstance(annotation, types.UnionType):
            args = annotation.__args__
        core = annotation
        if args:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                core = non_none[0]

        co = getattr(core, "__origin__", None)
        if co in (list, tuple, set, frozenset):
            return "string"  # multivalued handled separately
        if co is dict:
            return "string"
        if isinstance(core, type):
            if issubclass(core, bool):
                return "boolean"
            if issubclass(core, int):
                return "integer"
            if issubclass(core, float):
                return "float"
            if issubclass(core, str):
                return "string"
            if issubclass(core, enum.Enum):
                return core.__name__
            if hasattr(core, "model_fields"):
                return core.__name__  # Reference to another model
        return "string"

    @staticmethod
    def _extract_enum(annotation: Any) -> Any:
        import enum
        import types
        import typing

        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return annotation
        args = None
        origin = getattr(annotation, "__origin__", None)
        if origin is typing.Union:
            args = annotation.__args__
        elif isinstance(annotation, types.UnionType):
            args = annotation.__args__
        if args:
            for a in args:
                if isinstance(a, type) and issubclass(a, enum.Enum):
                    return a
        return None

    @staticmethod
    def _is_multivalued(annotation: Any) -> bool:
        import types
        import typing

        if annotation is None:
            return False
        origin = getattr(annotation, "__origin__", None)
        if origin in (list, tuple, set, frozenset):
            return True
        args = None
        if getattr(annotation, "__origin__", None) is typing.Union:
            args = annotation.__args__
        elif isinstance(annotation, types.UnionType):
            args = annotation.__args__
        if args:
            for a in args:
                if a is not type(None) and getattr(a, "__origin__", None) in (
                    list,
                    tuple,
                    set,
                    frozenset,
                ):
                    return True
        return False
