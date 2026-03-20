"""DANDI schema extractor — uses dandischema.

Handles PropertyValue fields by splitting into separate elements per variant
(e.g., age → postnatal age + gestational age as separate elements).
"""

from __future__ import annotations

import enum
import typing

from ..models import Constraints, ProvenanceEntry, ResponseOption, SemanticIdentity

# Fields wrapped in PropertyValue that should be split into variants.
# Maps field_name → list of (variant_suffix, description_note, extra_semantic)
_PROPERTY_VALUE_VARIANTS: dict[str, list[tuple[str, str, dict]]] = {
    "age": [
        (
            "age",
            "postnatal age (ISO 8601 duration, valueReference=BirthReference)",
            {},
        ),
        (
            "gestational_age",
            "gestational age (ISO 8601 duration, valueReference=GestationalReference)",
            {},
        ),
    ],
}


def extract_dandi() -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Extract elements from DANDI via dandischema."""
    try:
        import dandischema.models as dm
    except ImportError as exc:
        raise ImportError(f"dandischema required for DANDI extraction: {exc}") from exc

    import inspect

    results: list[tuple[SemanticIdentity, ProvenanceEntry]] = []

    for cls_name, cls in inspect.getmembers(dm, inspect.isclass):
        if not hasattr(cls, "model_fields"):
            continue
        for field_name, field_info in cls.model_fields.items():
            ann = field_info.annotation
            desc = field_info.description or ""

            # Check if this is a PropertyValue field with known variants
            if field_name in _PROPERTY_VALUE_VARIANTS and _is_property_value(ann):
                for variant_name, variant_desc, extra in _PROPERTY_VALUE_VARIANTS[field_name]:
                    sem = SemanticIdentity(data_type="string", **extra)
                    prov = ProvenanceEntry(
                        source="dandi",
                        **{"class": cls_name},
                        name=variant_name,
                        description=f"{desc} ({variant_desc})",
                    )
                    results.append((sem, prov))
                continue

            dt = _pydantic_type(field_info)

            # Extract enum values as response_options + constraints
            constraints = None
            response_options = None
            if ann is not None:
                enum_cls = _extract_enum_class(ann)
                if enum_cls:
                    allowed = [str(v.value) for v in enum_cls]
                    if allowed:
                        constraints = Constraints(allowed_values=allowed)
                        response_options = [ResponseOption(value=v, label=v) for v in allowed]

            # Extract min/max from Pydantic field metadata
            min_value = None
            max_value = None
            if hasattr(field_info, "metadata"):
                for m in field_info.metadata:
                    if hasattr(m, "ge") and m.ge is not None:
                        min_value = float(m.ge)
                    if hasattr(m, "gt") and m.gt is not None:
                        min_value = float(m.gt)
                    if hasattr(m, "le") and m.le is not None:
                        max_value = float(m.le)
                    if hasattr(m, "lt") and m.lt is not None:
                        max_value = float(m.lt)

            sem = SemanticIdentity(
                data_type=dt,
                constraints=constraints,
                response_options=response_options,
                min_value=min_value,
                max_value=max_value,
            )
            prov = ProvenanceEntry(
                source="dandi",
                **{"class": cls_name},
                name=field_name,
                description=desc,
            )
            results.append((sem, prov))

    return results


def _is_property_value(annotation) -> bool:
    """Check if annotation involves PropertyValue."""
    ann_str = str(annotation) if annotation else ""
    return "PropertyValue" in ann_str


def _extract_enum_class(annotation) -> type | None:
    """Extract an Enum class from a type annotation (including Optional, Union)."""
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
