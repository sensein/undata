"""DANDI schema extractor — uses dandischema."""

from __future__ import annotations

import enum

from ..models import Constraints, ProvenanceEntry, SemanticIdentity


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
            dt = _pydantic_type(field_info)
            desc = field_info.description or ""

            # Extract enum values from Pydantic field annotations
            constraints = None
            ann = field_info.annotation
            if ann is not None:
                # Check if it's an Enum type or Optional[Enum]
                enum_cls = _extract_enum_class(ann)
                if enum_cls:
                    allowed = [str(v.value) for v in enum_cls]
                    if allowed:
                        constraints = Constraints(allowed_values=allowed)

            sem = SemanticIdentity(data_type=dt, constraints=constraints)
            prov = ProvenanceEntry(
                source="dandi",
                **{"class": cls_name},
                name=field_name,
                description=desc,
            )
            results.append((sem, prov))

    return results


def _extract_enum_class(annotation) -> type | None:
    """Extract an Enum class from a type annotation (including Optional, Union)."""
    import typing

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
