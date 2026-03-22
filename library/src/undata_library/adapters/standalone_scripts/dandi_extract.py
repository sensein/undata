#!/usr/bin/env python3
"""Standalone DANDI extraction script — runs in isolated venv with dandischema.

Converts dandischema Pydantic models to classified entities:
- Classes with inheritance (subclass_of) and populated property lists
- Attributes with proper type detection (type_ref for model references)
- Enum members as ENUM_VALUE entities
- Enum types as VALUESET entities
"""

import enum
import inspect
import json
import types
import typing


_PROPERTY_VALUE_VARIANTS = {
    "age": [
        ("age", "postnatal age (ISO 8601 duration)"),
        ("gestational_age", "gestational age (ISO 8601 duration)"),
    ],
}


def _get_type_args(annotation):
    """Get type arguments handling both typing.Union and X | Y syntax."""
    origin = getattr(annotation, "__origin__", None)
    if origin is typing.Union:
        return annotation.__args__
    if isinstance(annotation, types.UnionType):
        return annotation.__args__
    return None


def _extract_enum_class(annotation):
    """Extract enum class from an annotation (handles Optional, Union, X|Y)."""
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation
    args = _get_type_args(annotation)
    if args:
        for arg in args:
            if isinstance(arg, type) and issubclass(arg, enum.Enum):
                return arg
    return None


def _extract_ref_classes(annotation):
    """Extract Pydantic model classes referenced by an annotation."""
    refs = []
    if isinstance(annotation, type) and hasattr(annotation, "model_fields"):
        refs.append(annotation)
        return refs
    args = _get_type_args(annotation)
    if args:
        for arg in args:
            if isinstance(arg, type) and hasattr(arg, "model_fields"):
                refs.append(arg)
            elif isinstance(arg, type) and arg is not type(None):
                # Check for list/sequence inner types
                inner_args = getattr(arg, "__args__", None)
                if inner_args:
                    for ia in inner_args:
                        if isinstance(ia, type) and hasattr(ia, "model_fields"):
                            refs.append(ia)
    # Also check list[Model] patterns
    origin = getattr(annotation, "__origin__", None)
    if origin in (list, tuple, set, frozenset):
        inner_args = getattr(annotation, "__args__", ())
        for ia in inner_args:
            if isinstance(ia, type) and hasattr(ia, "model_fields"):
                refs.append(ia)
            else:
                # Recurse for Union inside list
                sub = _extract_ref_classes(ia)
                refs.extend(sub)
    return refs


def _pydantic_type(field_info):
    """Determine data_type from Pydantic field info with proper introspection."""
    ann = field_info.annotation
    if ann is None:
        return "string"

    # Unwrap Optional/Union to get the core type
    args = _get_type_args(ann)
    core = ann
    if args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            core = non_none[0]

    # Check origin for list/dict
    origin = getattr(core, "__origin__", None)
    if origin in (list, tuple, set, frozenset):
        return "array"
    if origin is dict:
        return "object"

    # Direct type checks
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
            return "string"  # Enum values are strings
        if hasattr(core, "model_fields"):
            return "object"  # Pydantic model reference

    return "string"


def _get_type_ref(field_info):
    """Get type_ref if field references another Pydantic model."""
    refs = _extract_ref_classes(field_info.annotation) if field_info.annotation else []
    if refs:
        return refs[0].__name__
    return None


def _is_multivalued(field_info):
    """Check if field is a list/sequence type."""
    ann = field_info.annotation
    if ann is None:
        return False
    origin = getattr(ann, "__origin__", None)
    if origin in (list, tuple, set, frozenset):
        return True
    # Check inside Optional
    args = _get_type_args(ann)
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


def main():
    import dandischema.models as dm

    results = []
    seen_enums = set()  # Track emitted enums to avoid duplicates

    for cls_name, cls in inspect.getmembers(dm, inspect.isclass):
        if not hasattr(cls, "model_fields"):
            continue

        # Get inheritance
        bases = []
        for base in cls.__bases__:
            if base.__name__ != "BaseModel" and hasattr(base, "model_fields"):
                bases.append(base.__name__)

        semantic = {"properties": list(cls.model_fields.keys())}
        if bases:
            semantic["subclass_of"] = bases[0]
            if len(bases) > 1:
                semantic["mixins"] = bases[1:]

        # Get class description from docstring
        desc = cls.__doc__.strip().split("\n")[0] if cls.__doc__ else None

        results.append(
            {
                "entity_type": "class",
                "semantic": semantic,
                "provenance": {
                    "source": "dandi",
                    "class": cls_name,
                    "name": cls_name,
                    "description": desc,
                },
                "confidence": 0.9,
            }
        )

        # Extract fields as attributes
        for field_name, field_info in cls.model_fields.items():
            ann = field_info.annotation
            field_desc = field_info.description or ""

            # PropertyValue variant handling
            if field_name in _PROPERTY_VALUE_VARIANTS and "PropertyValue" in str(ann or ""):
                for variant_name, variant_desc in _PROPERTY_VALUE_VARIANTS[field_name]:
                    results.append(
                        {
                            "entity_type": "attribute",
                            "semantic": {"data_type": "string"},
                            "provenance": {
                                "source": "dandi",
                                "class": cls_name,
                                "name": variant_name,
                                "description": f"{field_desc} ({variant_desc})",
                            },
                            "confidence": 0.9,
                        }
                    )
                continue

            dt = _pydantic_type(field_info)
            semantic_attr = {"data_type": dt}

            # Type reference for model fields
            type_ref = _get_type_ref(field_info)
            if type_ref and dt == "object":
                semantic_attr["type_ref"] = type_ref

            # Multivalued
            if _is_multivalued(field_info):
                semantic_attr["multivalued"] = True

            # Required
            if field_info.is_required():
                semantic_attr["required"] = True

            # Enum handling — emit enum members as ENUM_VALUE
            if ann is not None:
                enum_cls = _extract_enum_class(ann)
                if enum_cls:
                    allowed = [str(v.value) for v in enum_cls]
                    if allowed:
                        semantic_attr["response_options"] = [
                            {"value": v, "label": v} for v in allowed
                        ]
                        semantic_attr["value_domain"] = "categorical"

                        # Emit VALUESET (once per enum class)
                        if enum_cls.__name__ not in seen_enums:
                            seen_enums.add(enum_cls.__name__)
                            results.append(
                                {
                                    "entity_type": "valueset",
                                    "semantic": {
                                        "name": enum_cls.__name__,
                                        "members": sorted(allowed),
                                    },
                                    "provenance": {
                                        "source": "dandi",
                                        "class": cls_name,
                                        "name": enum_cls.__name__,
                                    },
                                    "confidence": 0.9,
                                }
                            )
                            # Emit individual ENUM_VALUE entries
                            for val in allowed:
                                results.append(
                                    {
                                        "entity_type": "enum_value",
                                        "semantic": {
                                            "label": val,
                                            "value_type": "categorical",
                                        },
                                        "provenance": {
                                            "source": "dandi",
                                            "class": enum_cls.__name__,
                                            "name": val,
                                        },
                                        "confidence": 0.95,
                                    }
                                )

            # Min/max from metadata
            if hasattr(field_info, "metadata"):
                for m in field_info.metadata:
                    for attr, key in [
                        ("ge", "min_value"),
                        ("gt", "min_value"),
                        ("le", "max_value"),
                        ("lt", "max_value"),
                    ]:
                        if hasattr(m, attr) and getattr(m, attr) is not None:
                            semantic_attr[key] = float(getattr(m, attr))

            results.append(
                {
                    "entity_type": "attribute",
                    "semantic": semantic_attr,
                    "provenance": {
                        "source": "dandi",
                        "class": cls_name,
                        "name": field_name,
                        "description": field_desc,
                    },
                    "confidence": 0.85,
                }
            )

    print(json.dumps(results))


if __name__ == "__main__":
    main()
