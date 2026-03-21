"""DANDI schema adapter — uses dandischema for Pydantic model introspection."""

from __future__ import annotations

import enum
import typing
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity

_PROPERTY_VALUE_VARIANTS: dict[str, list[tuple[str, str, dict]]] = {
    "age": [
        ("age", "postnatal age (ISO 8601 duration, valueReference=BirthReference)", {}),
        (
            "gestational_age",
            "gestational age (ISO 8601 duration, valueReference=GestationalReference)",
            {},
        ),
    ],
}


class DANDIAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "dandi"

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        try:
            import dandischema.models as dm
        except ImportError as exc:
            raise ImportError(f"dandischema required for DANDI extraction: {exc}") from exc

        import inspect

        repo = options.get("repo", "https://github.com/dandi/dandischema")
        committish = options.get("committish")
        try:
            version = getattr(dm, "__version__", None) or getattr(
                __import__("dandischema"), "__version__", None
            )
            if version and not committish:
                committish = f"v{version}"
        except Exception:
            pass

        base_ref = SourceRef(
            repo=repo, committish=committish, file="dandischema/models.py", checksum=""
        )

        results: list[ClassifiedEntity] = []

        for cls_name, cls in inspect.getmembers(dm, inspect.isclass):
            if not hasattr(cls, "model_fields"):
                continue

            # Emit class entity
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic={"properties": []},
                    provenance={"source": "dandi", "class": cls_name, "name": cls_name},
                    confidence=0.9,
                    source_ref=base_ref,
                )
            )

            for field_name, field_info in cls.model_fields.items():
                ann = field_info.annotation
                desc = field_info.description or ""

                if field_name in _PROPERTY_VALUE_VARIANTS and _is_property_value(ann):
                    for variant_name, variant_desc, extra in _PROPERTY_VALUE_VARIANTS[field_name]:
                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.ATTRIBUTE,
                                semantic={"data_type": "string", **extra},
                                provenance={
                                    "source": "dandi",
                                    "class": cls_name,
                                    "name": variant_name,
                                    "description": f"{desc} ({variant_desc})",
                                },
                                confidence=0.9,
                                source_ref=base_ref,
                            )
                        )
                    continue

                dt = _pydantic_type(field_info)
                semantic: dict[str, Any] = {"data_type": dt}

                # Enum → valueset + individual values
                if ann is not None:
                    enum_cls = _extract_enum_class(ann)
                    if enum_cls:
                        allowed = [str(v.value) for v in enum_cls]
                        if allowed:
                            semantic["constraints"] = {"allowed_values": allowed}
                            semantic["response_options"] = [
                                {"value": v, "label": v} for v in allowed
                            ]
                            # Emit valueset
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

                # Min/max from Pydantic metadata
                if hasattr(field_info, "metadata"):
                    for m in field_info.metadata:
                        for attr, key in [
                            ("ge", "min_value"),
                            ("gt", "min_value"),
                            ("le", "max_value"),
                            ("lt", "max_value"),
                        ]:
                            if hasattr(m, attr) and getattr(m, attr) is not None:
                                semantic[key] = float(getattr(m, attr))

                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ATTRIBUTE,
                        semantic=semantic,
                        provenance={
                            "source": "dandi",
                            "class": cls_name,
                            "name": field_name,
                            "description": desc,
                        },
                        confidence=0.85,
                        source_ref=base_ref,
                    )
                )

        return results


def _is_property_value(annotation) -> bool:
    return "PropertyValue" in (str(annotation) if annotation else "")


def _extract_enum_class(annotation) -> type | None:
    origin = getattr(annotation, "__origin__", None)
    if origin is typing.Union:
        for arg in annotation.__args__:
            if isinstance(arg, type) and issubclass(arg, enum.Enum):
                return arg
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation
    return None


def _pydantic_type(field_info) -> str:
    ann = str(field_info.annotation) if field_info.annotation else "string"
    if "int" in ann.lower():
        return "integer"
    if "float" in ann.lower():
        return "float"
    if "bool" in ann.lower():
        return "boolean"
    if "list" in ann.lower():
        return "array"
    return "string"
