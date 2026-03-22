"""DANDI schema adapter — delegates to standalone extraction script.

The actual extraction happens in standalone_scripts/dandi_extract.py running in an
isolated venv with dandischema. This adapter class exists for the registry and
as a fallback when dandischema is available in the current environment.
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
        """Extract entities from dandischema.

        Primary path: standalone script in isolated venv (via pipeline).
        Fallback: direct extraction if dandischema is in current env.
        """
        try:
            import dandischema.models as dm
        except ImportError:
            return []

        return self._extract_from_models(dm, source_path)

    def _extract_from_models(self, dm: Any, source_path: Path) -> list[ClassifiedEntity]:
        """Extract entities from dandischema models module."""
        import inspect

        from ..models import EntityType

        results: list[ClassifiedEntity] = []
        base_ref = SourceRef(
            repo="https://github.com/dandi/dandischema",
            committish=getattr(dm, "__version__", None),
            file="models.py",
            checksum="",
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
            semantic: dict[str, Any] = {"properties": list(cls.model_fields.keys())}
            if bases:
                semantic["subclass_of"] = bases[0]
                if len(bases) > 1:
                    semantic["mixins"] = bases[1:]

            desc = cls.__doc__.strip().split("\n")[0] if cls.__doc__ else None
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic=semantic,
                    provenance={
                        "source": "dandi",
                        "class": cls_name,
                        "name": cls_name,
                        "description": desc,
                    },
                    confidence=0.9,
                    source_ref=base_ref,
                )
            )

            for field_name, field_info in cls.model_fields.items():
                ann = field_info.annotation
                field_desc = field_info.description or ""

                dt = self._pydantic_type(field_info)
                sem: dict[str, Any] = {"data_type": dt}

                # Enum → VALUESET + ENUM_VALUE
                enum_cls = self._extract_enum(ann)
                if enum_cls:
                    allowed = [str(v.value) for v in enum_cls]
                    if allowed:
                        sem["response_options"] = [{"value": v, "label": v} for v in allowed]
                        sem["value_domain"] = "categorical"
                        if enum_cls.__name__ not in seen_enums:
                            seen_enums.add(enum_cls.__name__)
                            results.append(
                                ClassifiedEntity(
                                    entity_type=EntityType.VALUESET,
                                    semantic={
                                        "name": enum_cls.__name__,
                                        "members": sorted(allowed),
                                    },
                                    provenance={
                                        "source": "dandi",
                                        "class": cls_name,
                                        "name": enum_cls.__name__,
                                    },
                                    confidence=0.9,
                                    source_ref=base_ref,
                                )
                            )
                            for val in allowed:
                                results.append(
                                    ClassifiedEntity(
                                        entity_type=EntityType.ENUM_VALUE,
                                        semantic={"label": val, "value_type": "categorical"},
                                        provenance={
                                            "source": "dandi",
                                            "class": enum_cls.__name__,
                                            "name": val,
                                        },
                                        confidence=0.95,
                                        source_ref=base_ref,
                                    )
                                )

                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ATTRIBUTE,
                        semantic=sem,
                        provenance={
                            "source": "dandi",
                            "class": cls_name,
                            "name": field_name,
                            "description": field_desc,
                        },
                        confidence=0.85,
                        source_ref=base_ref,
                    )
                )

        return results

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
    def _pydantic_type(field_info: Any) -> str:
        import enum
        import types
        import typing

        ann = field_info.annotation
        if ann is None:
            return "string"
        args = None
        origin = getattr(ann, "__origin__", None)
        if origin is typing.Union:
            args = ann.__args__
        elif isinstance(ann, types.UnionType):
            args = ann.__args__
        core = ann
        if args:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                core = non_none[0]
        co = getattr(core, "__origin__", None)
        if co in (list, tuple, set, frozenset):
            return "array"
        if co is dict:
            return "object"
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
                return "string"
            if hasattr(core, "model_fields"):
                return "object"
        return "string"
